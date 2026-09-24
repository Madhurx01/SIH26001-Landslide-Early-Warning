#!/usr/bin/env python3
"""Build the 1 km NDVI feature from real Sentinel-2 L2A observations.

There is deliberately no land-cover-derived or constant-value fallback. If the
public satellite catalog or imagery is unavailable, the script fails without
overwriting its output. Missing satellite coverage remains NaN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from contextlib import ExitStack
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.errors import WindowError
from rasterio.features import geometry_window, rasterize
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, bounds as window_bounds
from shapely.geometry import box, mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
COLLECTION = "sentinel-2-l2a"
GRID_CANDIDATES = (
    PROJECT_ROOT / "DATA/PROCESSED/GRID/sikkim_grid_1km.gpkg",
    PROJECT_ROOT / "dataset/sikkim_grid_1km.gpkg",
)
BOUNDARY_CANDIDATES = (
    PROJECT_ROOT / "DATA/PROCESSED/STATIC/BOUNDARY/sikkim_boundary_utm45n.gpkg",
    PROJECT_ROOT / "DATA/PROCESSED/STATIC/BOUNDARY/sikkim_boundary_wgs84.gpkg",
    PROJECT_ROOT / "dataset/sikkim_boundary_utm45n.gpkg",
    PROJECT_ROOT / "dataset/sikkim_boundary_wgs84.gpkg",
)
STATIC_CANDIDATES = (
    PROJECT_ROOT / "dataset/sikkim_static_features_1km.csv",
    PROJECT_ROOT / "DATA/PROCESSED/FEATURES/sikkim_static_features_1km.csv",
)
DEFAULT_OUTPUT = PROJECT_ROOT / "dataset/features_ndvi_1km.csv"

# SCL surface classes retained: vegetation, non-vegetated, water, unclassified.
# Values 0,1,2,3,8,9,10,11 (nodata, defects, shadows, clouds, snow/ice) are masked.
CLEAR_SCL_CLASSES = np.array([4, 5, 6, 7], dtype="uint8")
CHUNK_SIZE = 2_048
USER_AGENT = "SIH26001-real-ndvi/1.0"
SAS_QUERY_CACHE: dict[tuple[str, str], str] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate cloud-masked Sentinel-2 L2A NDVI to the existing Sikkim grid."
    )
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2021, 10, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2021, 11, 30))
    parser.add_argument("--max-cloud-cover", type=float, default=30.0)
    parser.add_argument("--min-valid-fraction", type=float, default=0.20)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--catalog-only", action="store_true",
        help="Validate inputs/query STAC without reading imagery or writing output.",
    )
    return parser.parse_args()


def first_existing(candidates: tuple[Path, ...], label: str) -> Path:
    for path in candidates:
        if path.is_file():
            return path
    checked = "\n  - ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Missing {label}. Checked:\n  - {checked}")


def http_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Accept": "application/geo+json", "User-Agent": USER_AGENT}
    if data is not None:
        headers["Content-Type"] = "application/json"
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            with urlopen(Request(url, data=data, headers=headers), timeout=120) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < 4:
                delay = 2 ** (attempt - 1)
                print(f"HTTP attempt {attempt}/4 failed: {error}; retrying in {delay}s")
                time.sleep(delay)
    raise RuntimeError(f"Satellite request failed after four attempts: {url}") from last_error


def load_analysis_units() -> tuple[gpd.GeoDataFrame, Any, Path, Path, Path]:
    grid_path = first_existing(GRID_CANDIDATES, "canonical 1 km grid")
    boundary_path = first_existing(BOUNDARY_CANDIDATES, "Sikkim boundary")
    static_path = first_existing(STATIC_CANDIDATES, "static 1 km feature CSV")
    grid = gpd.read_file(grid_path).reset_index(drop=True)
    required = {"cell_id", "sikkim_fraction", "geometry"}
    if required - set(grid.columns):
        raise RuntimeError(f"Grid is missing columns: {sorted(required - set(grid.columns))}")
    if grid.crs is None or not grid.crs.is_projected:
        raise RuntimeError("Canonical grid must have a projected CRS")
    if grid.empty or grid.geometry.is_empty.any() or not grid.geometry.is_valid.all():
        raise RuntimeError("Canonical grid contains empty or invalid geometry")
    if grid["cell_id"].isna().any() or grid["cell_id"].duplicated().any():
        raise RuntimeError("Canonical grid cell_id values must be non-null and unique")
    expected_ids = [f"SKM_{index:05d}" for index in range(1, len(grid) + 1)]
    if grid["cell_id"].astype(str).tolist() != expected_ids:
        raise RuntimeError("Canonical cell_id ordering/format has changed")
    if not np.allclose(grid.geometry.area, 1_000_000.0, rtol=0.0, atol=1.0):
        raise RuntimeError("Canonical grid is no longer composed of 1 km squares")
    static_ids = pd.read_csv(static_path, usecols=["cell_id"])["cell_id"].astype(str).tolist()
    if static_ids != expected_ids:
        raise RuntimeError("Static features are not exactly aligned with canonical cell_id order")

    boundary_frame = gpd.read_file(boundary_path)
    if boundary_frame.empty or boundary_frame.crs is None:
        raise RuntimeError("Sikkim boundary is empty or has no CRS")
    boundary = boundary_frame.to_crs(grid.crs).geometry.union_all()
    if boundary.is_empty or not boundary.is_valid:
        raise RuntimeError("Sikkim boundary is empty or invalid")
    clipped = grid[["cell_id", "geometry"]].copy()
    clipped["geometry"] = clipped.geometry.intersection(boundary)
    if clipped.geometry.is_empty.any():
        raise RuntimeError("At least one canonical grid cell does not intersect Sikkim")
    return clipped, boundary, grid_path, boundary_path, static_path


def search_items(boundary_wgs84: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "collections": [COLLECTION],
        "intersects": mapping(boundary_wgs84),
        "datetime": (
            f"{args.start_date.isoformat()}T00:00:00Z/"
            f"{args.end_date.isoformat()}T23:59:59Z"
        ),
        "query": {"eo:cloud_cover": {"lte": args.max_cloud_cover}},
        "limit": 1_000,
    }
    response = http_json(f"{STAC_URL}/search", payload)
    items = list(response.get("features", []))
    while True:
        next_link = next(
            (link for link in response.get("links", []) if link.get("rel") == "next"), None
        )
        if next_link is None:
            break
        if str(next_link.get("method", "GET")).upper() == "POST":
            response = http_json(next_link["href"], next_link.get("body", payload))
        else:
            response = http_json(next_link["href"])
        items.extend(response.get("features", []))
    items = list({item["id"]: item for item in items}.values())
    # Enforce the numeric threshold locally as well. Catalog implementations can
    # occasionally return a boundary/legacy item outside the requested query.
    items = [
        item for item in items
        if float(item["properties"].get("eo:cloud_cover", 101.0))
        <= args.max_cloud_cover
    ]
    # Historical acquisitions can have both original and Collection-1
    # reprocessed items for the same timestamp/MGRS tile. Prefer the newest
    # processing baseline/generation so the same observation is not repeated.
    newest_by_observation: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        key = (
            item["properties"]["datetime"],
            str(item["properties"].get("s2:mgrs_tile", "")),
        )
        rank = (
            str(item["properties"].get("s2:processing_baseline", "")),
            str(item["properties"].get("s2:generation_time", "")),
            item["id"],
        )
        current = newest_by_observation.get(key)
        if current is None:
            newest_by_observation[key] = item
        else:
            current_rank = (
                str(current["properties"].get("s2:processing_baseline", "")),
                str(current["properties"].get("s2:generation_time", "")),
                current["id"],
            )
            if rank > current_rank:
                newest_by_observation[key] = item
    items = sorted(
        newest_by_observation.values(),
        key=lambda item: (item["properties"]["datetime"], item["id"]),
    )
    if not items:
        raise RuntimeError("No Sentinel-2 items matched the boundary, dates, and cloud filter")
    for item in items:
        missing = {"B04", "B08", "SCL"} - set(item.get("assets", {}))
        if missing:
            raise RuntimeError(f"STAC item {item['id']} lacks assets: {sorted(missing)}")
    return items


def signed_href(item: dict[str, Any], key: str) -> str:
    href = item["assets"][key]["href"]
    parts = urlsplit(href)
    container = parts.path.strip("/").split("/", 1)[0]
    cache_key = (parts.netloc, container)
    sas_query = SAS_QUERY_CACHE.get(cache_key)
    if sas_query is None:
        signed = http_json(f"{SIGN_URL}?href={quote(href, safe='')}").get("href")
        if not signed:
            raise RuntimeError(f"Signing service returned no URL for {item['id']} {key}")
        sas_query = urlsplit(str(signed)).query
        if not sas_query:
            raise RuntimeError("Signing service response did not contain a SAS query token")
        SAS_QUERY_CACHE[cache_key] = sas_query
    if not sas_query:
        raise RuntimeError(f"Signing service returned no URL for {item['id']} {key}")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, sas_query, parts.fragment))


def scale_offset(item: dict[str, Any], key: str) -> tuple[float, float]:
    bands = item["assets"][key].get("raster:bands", [])
    if bands and ("scale" in bands[0] or "offset" in bands[0]):
        return float(bands[0].get("scale", 1.0)), float(bands[0].get("offset", 0.0))
    try:
        baseline = float(item["properties"].get("s2:processing_baseline", "0"))
    except ValueError as error:
        raise RuntimeError(f"Invalid processing baseline in {item['id']}") from error
    # Copernicus PB >=04.00: BOA_ADD_OFFSET=-1000, quantification=10000.
    return 0.0001, (-0.1 if baseline >= 4.0 else 0.0)


def grids_match(left: rasterio.DatasetReader, right: rasterio.DatasetReader) -> bool:
    return (
        left.crs == right.crs
        and left.width == right.width
        and left.height == right.height
        and left.transform.almost_equals(right.transform)
    )


def iter_windows(outer: Window):
    row_start, col_start = math.floor(outer.row_off), math.floor(outer.col_off)
    row_stop = math.ceil(outer.row_off + outer.height)
    col_stop = math.ceil(outer.col_off + outer.width)
    for row_off in range(row_start, row_stop, CHUNK_SIZE):
        height = min(CHUNK_SIZE, row_stop - row_off)
        for col_off in range(col_start, col_stop, CHUNK_SIZE):
            width = min(CHUNK_SIZE, col_stop - col_off)
            yield Window(col_off, row_off, width, height)


def aggregate_item(
    item: dict[str, Any], clipped_grid: gpd.GeoDataFrame
) -> tuple[np.ndarray, np.ndarray]:
    """Return cloud-masked NDVI sums and valid native-pixel counts per cell."""
    red_url, nir_url, scl_url = (signed_href(item, key) for key in ("B04", "B08", "SCL"))
    red_scale, red_offset = scale_offset(item, "B04")
    nir_scale, nir_offset = scale_offset(item, "B08")
    sums = np.zeros(len(clipped_grid), dtype="float64")
    counts = np.zeros(len(clipped_grid), dtype="int64")

    with ExitStack() as stack:
        red_src = stack.enter_context(rasterio.open(red_url))
        nir_src = stack.enter_context(rasterio.open(nir_url))
        scl_src = stack.enter_context(rasterio.open(scl_url))
        if red_src.crs is None:
            raise RuntimeError(f"B04 has no CRS for {item['id']}")
        source_grid = clipped_grid.to_crs(red_src.crs)
        item_aoi = source_grid.geometry.union_all().intersection(box(*red_src.bounds))
        if item_aoi.is_empty:
            return sums, counts
        try:
            outer_window = geometry_window(red_src, [mapping(item_aoi)])
        except WindowError:
            return sums, counts

        nir_reader = nir_src
        if not grids_match(red_src, nir_src):
            nir_reader = stack.enter_context(
                WarpedVRT(
                    nir_src, crs=red_src.crs, transform=red_src.transform,
                    width=red_src.width, height=red_src.height,
                    resampling=Resampling.bilinear, nodata=nir_src.nodata,
                )
            )
        scl_reader = stack.enter_context(
            WarpedVRT(
                scl_src, crs=red_src.crs, transform=red_src.transform,
                width=red_src.width, height=red_src.height,
                resampling=Resampling.nearest, src_nodata=scl_src.nodata, nodata=0,
            )
        )
        spatial_index = source_grid.sindex

        for window in iter_windows(outer_window):
            shape = (int(window.height), int(window.width))
            candidates = spatial_index.query(
                box(*window_bounds(window, red_src.transform)), predicate="intersects"
            )
            if not len(candidates):
                continue
            labels = rasterize(
                [
                    (mapping(source_grid.geometry.iloc[int(i)]), int(i) + 1)
                    for i in candidates
                    if not source_grid.geometry.iloc[int(i)].is_empty
                ],
                out_shape=shape,
                transform=red_src.window_transform(window),
                fill=0,
                all_touched=False,
                dtype="int32",
            )
            valid = (labels > 0) & np.isin(scl_reader.read(1, window=window), CLEAR_SCL_CLASSES)
            if not valid.any():
                continue
            red_dn = red_src.read(1, window=window)
            nir_dn = nir_reader.read(1, window=window)
            if red_src.nodata is not None:
                valid &= red_dn != red_src.nodata
            if nir_reader.nodata is not None:
                valid &= nir_dn != nir_reader.nodata
            valid &= (red_dn != 0) & (nir_dn != 0)
            red = red_dn.astype("float32") * red_scale + red_offset
            nir = nir_dn.astype("float32") * nir_scale + nir_offset
            denominator = nir + red
            valid &= (
                np.isfinite(red) & np.isfinite(nir) & (red >= 0.0) & (nir >= 0.0)
                & (denominator > 1e-6)
            )
            if not valid.any():
                continue
            ndvi = np.zeros(red.shape, dtype="float32")
            np.divide(nir - red, denominator, out=ndvi, where=valid)
            valid &= np.isfinite(ndvi) & (ndvi >= -1.0) & (ndvi <= 1.0)
            valid_labels = labels[valid]
            sums += np.bincount(
                valid_labels, weights=ndvi[valid], minlength=len(clipped_grid) + 1
            )[1:]
            counts += np.bincount(valid_labels, minlength=len(clipped_grid) + 1)[1:]
    return sums, counts


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_atomic(path: Path, content_writer) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    content_writer(temporary)
    temporary.replace(path)


def metadata_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}.metadata.json")


def main() -> None:
    args = parse_args()
    if args.start_date > args.end_date:
        raise ValueError("--start-date must be on or before --end-date")
    if not 0.0 <= args.max_cloud_cover <= 100.0:
        raise ValueError("--max-cloud-cover must be between 0 and 100")
    if not 0.0 < args.min_valid_fraction <= 1.0:
        raise ValueError("--min-valid-fraction must be in (0, 1]")

    grid, boundary, grid_path, boundary_path, static_path = load_analysis_units()
    boundary_wgs84 = gpd.GeoSeries([boundary], crs=grid.crs).to_crs(4326).iloc[0]
    print("=== Step 4: Real Sentinel-2 L2A NDVI ===")
    print(f"Canonical grid: {grid_path} ({len(grid):,} cells)")
    print(f"Static alignment reference: {static_path}")
    print(f"Period: {args.start_date} through {args.end_date} (inclusive)")
    items = search_items(boundary_wgs84, args)
    acquisitions = sorted({item["properties"]["datetime"] for item in items})
    print(f"Catalog: {len(items):,} tiles across {len(acquisitions):,} acquisitions")
    if args.catalog_only:
        for acquisition in acquisitions:
            count = sum(item["properties"]["datetime"] == acquisition for item in items)
            print(f"  {acquisition}: {count} tile(s)")
        print("Catalog-only validation complete; no output was written.")
        return

    expected_pixels = np.maximum(grid.geometry.area.to_numpy(dtype="float64") / 100.0, 1.0)
    observations: list[np.ndarray] = []
    coverages: list[np.ndarray] = []
    item_qa: list[dict[str, Any]] = []
    gdal_options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF",
        "GDAL_HTTP_CONNECTTIMEOUT": "30",
        "GDAL_HTTP_TIMEOUT": "120",
        "GDAL_HTTP_MAX_RETRY": "4",
        "GDAL_HTTP_RETRY_DELAY": "2",
        "VSI_CACHE": "TRUE",
        "VSI_CACHE_SIZE": str(64 * 1024 * 1024),
    }

    with rasterio.Env(**gdal_options):
        for number, acquisition in enumerate(acquisitions, start=1):
            acquisition_items = [
                item for item in items if item["properties"]["datetime"] == acquisition
            ]
            best_means = np.full(len(grid), np.nan, dtype="float64")
            best_counts = np.zeros(len(grid), dtype="int64")
            print(f"Acquisition {number}/{len(acquisitions)}: {acquisition}")
            for item in acquisition_items:
                print(f"  {item['id']} (catalog cloud {item['properties'].get('eo:cloud_cover')}%)")
                sums, counts = aggregate_item(item, grid)
                means = np.full(len(grid), np.nan, dtype="float64")
                np.divide(sums, counts, out=means, where=counts > 0)
                item_coverage = counts / expected_pixels
                accepted = (counts > 0) & (item_coverage >= args.min_valid_fraction)
                # Avoid double-counting adjacent MGRS tile overlap: retain the
                # same-acquisition tile observation with most valid pixels.
                use_item = accepted & (counts > best_counts)
                best_means[use_item] = means[use_item]
                best_counts[use_item] = counts[use_item]
                item_qa.append(
                    {
                        "item_id": item["id"],
                        "datetime": acquisition,
                        "mgrs_tile": item["properties"].get("s2:mgrs_tile"),
                        "processing_baseline": item["properties"].get("s2:processing_baseline"),
                        "catalog_cloud_cover_percent": item["properties"].get("eo:cloud_cover"),
                        "cells_meeting_valid_fraction": int(accepted.sum()),
                        "valid_native_pixels": int(counts.sum()),
                    }
                )
            best_coverage = best_counts / expected_pixels
            best_means[best_coverage < args.min_valid_fraction] = np.nan
            observations.append(best_means)
            coverages.append(best_coverage)
            print(f"  Accepted cells: {np.isfinite(best_means).sum():,}/{len(grid):,}")

    matrix = np.vstack(observations)
    observation_counts = np.isfinite(matrix).sum(axis=0)
    has_data = observation_counts > 0
    ndvi = np.full(len(grid), np.nan, dtype="float64")
    ndvi[has_data] = np.nanmedian(matrix[:, has_data], axis=0)
    if np.isfinite(ndvi).any() and (np.nanmin(ndvi) < -1.0 or np.nanmax(ndvi) > 1.0):
        raise RuntimeError("Computed NDVI lies outside [-1, 1]")
    output_frame = pd.DataFrame(
        {"cell_id": grid["cell_id"].astype(str), "ndvi_mean": np.round(ndvi, 6)}
    )
    if len(output_frame) != len(grid) or output_frame["cell_id"].duplicated().any():
        raise RuntimeError("NDVI output violated the one-row-per-cell contract")

    output = args.output.resolve()
    write_atomic(output, lambda path: output_frame.to_csv(path, index=False))
    output_hash = sha256_file(output)
    valid_values = output_frame["ndvi_mean"].dropna()
    metadata = {
        "schema_version": 1,
        "data_origin": "satellite_observation",
        "synthetic_fallback_used": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_csv": str(output),
        "output_sha256": output_hash,
        "output_columns": ["cell_id", "ndvi_mean"],
        "canonical_grid": str(grid_path.resolve()),
        "boundary": str(boundary_path.resolve()),
        "static_alignment_reference": str(static_path.resolve()),
        "row_count": len(output_frame),
        "source": {
            "provider": "Microsoft Planetary Computer public STAC API",
            "stac_url": STAC_URL,
            "collection": COLLECTION,
            "satellite_product": "Copernicus Sentinel-2 MSI Level-2A surface reflectance",
            "red_asset": "B04 (10 m native pixel spacing)",
            "nir_asset": "B08 (10 m native pixel spacing)",
            "quality_asset": "SCL (20 m native pixel spacing)",
            "credentials_required": False,
        },
        "temporal_period": {
            "start_date_inclusive": args.start_date.isoformat(),
            "end_date_inclusive": args.end_date.isoformat(),
            "acquisition_timestamp_count": len(acquisitions),
            "acquisition_timestamps": acquisitions,
        },
        "quality_filtering": {
            "maximum_catalog_cloud_cover_percent": args.max_cloud_cover,
            "retained_scl_classes": {
                "4": "vegetation", "5": "not_vegetated",
                "6": "water", "7": "unclassified",
            },
            "excluded_scl_classes": [0, 1, 2, 3, 8, 9, 10, 11],
            "scl_resampling": "nearest neighbour from native 20 m to B04/B08 10 m grid",
            "minimum_valid_fraction_per_cell_acquisition": args.min_valid_fraction,
            "nodata_handling": "DN=0/nodata, invalid denominator, and non-finite values excluded",
            "radiometry": (
                "STAC scale/offset when supplied; otherwise PB >=04.00 uses "
                "scale 0.0001 and BOA offset -0.1, older PB uses zero offset"
            ),
        },
        "aggregation": {
            "analysis_unit": "unchanged existing 1 km square Sikkim grid",
            "boundary_handling": "partial cells clipped to Sikkim for pixel aggregation",
            "spatial_reducer": "mean of valid native 10 m NDVI pixels per acquisition",
            "overlap_handling": "same-acquisition tile with most valid pixels retained",
            "temporal_reducer": "median of accepted per-acquisition cell means",
            "output_name_note": "ndvi_mean retained for downstream compatibility",
            "native_resolution_claim": "1 km aggregate; not native 1 km satellite data",
        },
        "qa": {
            "catalog_item_count": len(items),
            "items": item_qa,
            "cells_with_ndvi": int(has_data.sum()),
            "cells_missing_ndvi": int((~has_data).sum()),
            "missing_values_preserved": True,
            "ndvi_min": float(valid_values.min()) if not valid_values.empty else None,
            "ndvi_max": float(valid_values.max()) if not valid_values.empty else None,
            "ndvi_mean_across_cells": float(valid_values.mean()) if not valid_values.empty else None,
            "accepted_acquisitions_per_cell_min": (
                int(observation_counts[has_data].min()) if has_data.any() else 0
            ),
            "accepted_acquisitions_per_cell_median": (
                float(np.median(observation_counts[has_data])) if has_data.any() else 0.0
            ),
            "accepted_acquisitions_per_cell_max": (
                int(observation_counts.max()) if has_data.any() else 0
            ),
            "maximum_observed_clear_fraction": float(np.nanmax(np.vstack(coverages))),
        },
    }
    metadata_output = metadata_path(output)
    write_atomic(
        metadata_output,
        lambda path: path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8"),
    )
    print(f"Saved real satellite NDVI features: {output}")
    print(f"Saved provenance and QA: {metadata_output}")
    print(f"Rows: {len(output_frame):,}; missing NDVI: {(~has_data).sum():,}")
    if not valid_values.empty:
        print(
            f"NDVI range: {valid_values.min():.4f} to {valid_values.max():.4f}; "
            f"cell mean: {valid_values.mean():.4f}"
        )


if __name__ == "__main__":
    main()
