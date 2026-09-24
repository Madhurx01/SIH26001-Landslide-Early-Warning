#!/usr/bin/env python3
"""Build drainage- and active-fault-distance features from real vectors.

Drainage comes from OpenStreetMap waterways returned by a live Overpass API.
Fault traces come from an immutable revision of the GEM Global Active Faults
Database. There is deliberately no hand-drawn or synthetic geometry fallback:
an unavailable, empty, or invalid source aborts before outputs change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import STRtree, make_valid, points
from shapely.geometry import GeometryCollection, LineString, MultiLineString, shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_CRS = "EPSG:32645"
EXPECTED_CELL_COUNT = 7_390
GEM_REVISION = "56816508ad92fd6846dad1163b1c8c01376a2cd1"
GEM_SOURCE_SHA256 = "37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1"
GEM_DATASET_PATH = "geojson/gem_active_faults_harmonized.geojson"
GEM_URL = (
    "https://raw.githubusercontent.com/GEMScienceTools/gem-global-active-faults/"
    f"{GEM_REVISION}/{GEM_DATASET_PATH}"
)
GEM_COMMIT_URL = (
    "https://github.com/GEMScienceTools/gem-global-active-faults/commit/"
    f"{GEM_REVISION}"
)
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
WATERWAY_TAGS = ("river", "stream", "canal")
USER_AGENT = "SIH26001-provenance-safe-fault-drainage/1.0"
GRID_CANDIDATES = (
    PROJECT_ROOT / "DATA/PROCESSED/GRID/sikkim_grid_1km.gpkg",
    PROJECT_ROOT / "dataset/sikkim_grid_1km.gpkg",
)
BOUNDARY_CANDIDATES = (
    PROJECT_ROOT / "DATA/PROCESSED/STATIC/BOUNDARY/sikkim_boundary_utm45n.gpkg",
    PROJECT_ROOT / "DATA/PROCESSED/STATIC/BOUNDARY/sikkim_boundary_wgs84.gpkg",
)
STATIC_CANDIDATES = (
    PROJECT_ROOT / "dataset/sikkim_static_features_1km.csv",
    PROJECT_ROOT / "DATA/PROCESSED/FEATURES/sikkim_static_features_1km.csv",
)
DEFAULT_OUTPUT = PROJECT_ROOT / "dataset/features_hydrology_faults_1km.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate exact distances to real OSM waterways and GEM faults."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fault-buffer-km", type=float, default=100.0)
    parser.add_argument("--drainage-buffer-km", type=float, default=10.0)
    parser.add_argument("--minimum-drainage-ways", type=int, default=10)
    return parser.parse_args()


def first_existing(candidates: tuple[Path, ...], label: str) -> Path:
    for path in candidates:
        if path.is_file():
            return path
    checked = "\n  - ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Missing {label}. Checked:\n  - {checked}")


def project_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def http_bytes(
    url: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
    attempts: int = 3,
    timeout: int = 180,
) -> bytes:
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if content_type is not None:
        headers["Content-Type"] = content_type
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(url, data=data, headers=headers)
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            last_error = error
            if attempt < attempts:
                delay = 2 ** (attempt - 1)
                print(f"HTTP attempt {attempt}/{attempts} failed: {error}; retrying in {delay}s")
                time.sleep(delay)
    raise RuntimeError(f"Request failed after {attempts} attempts: {url}") from last_error


def load_analysis_units() -> tuple[gpd.GeoDataFrame, Any, Path, Path, Path]:
    grid_path = first_existing(GRID_CANDIDATES, "canonical 1 km grid")
    boundary_path = first_existing(BOUNDARY_CANDIDATES, "Sikkim boundary")
    static_path = first_existing(STATIC_CANDIDATES, "static 1 km feature CSV")
    grid = gpd.read_file(grid_path).reset_index(drop=True)
    required = {
        "cell_id", "centroid_x", "centroid_y", "sikkim_fraction", "geometry"
    }
    if missing := required - set(grid.columns):
        raise RuntimeError(f"Canonical grid is missing columns: {sorted(missing)}")
    if grid.crs is None or grid.crs.to_epsg() != 32645:
        raise RuntimeError(f"Canonical grid must be {TARGET_CRS}")
    if len(grid) != EXPECTED_CELL_COUNT:
        raise RuntimeError(
            f"Canonical grid has {len(grid):,} rows; expected {EXPECTED_CELL_COUNT:,}"
        )
    if grid.geometry.isna().any() or grid.geometry.is_empty.any():
        raise RuntimeError("Canonical grid contains missing or empty geometry")
    if not grid.geometry.is_valid.all():
        raise RuntimeError("Canonical grid contains invalid geometry")
    if not np.allclose(grid.geometry.area, 1_000_000.0, rtol=0.0, atol=1.0):
        raise RuntimeError("Canonical grid is no longer composed of 1 km squares")
    expected_ids = [f"SKM_{index:05d}" for index in range(1, EXPECTED_CELL_COUNT + 1)]
    if grid["cell_id"].astype(str).tolist() != expected_ids:
        raise RuntimeError("Canonical cell_id ordering/format has changed")
    static_ids = pd.read_csv(static_path, usecols=["cell_id"])["cell_id"].astype(str).tolist()
    if static_ids != expected_ids:
        raise RuntimeError("Static features are not exactly aligned with the canonical grid")

    boundary_frame = gpd.read_file(boundary_path)
    if boundary_frame.empty or boundary_frame.crs is None:
        raise RuntimeError("Sikkim boundary is empty or has no CRS")
    boundary = boundary_frame.to_crs(TARGET_CRS).geometry.union_all()
    if boundary.is_empty or not boundary.is_valid:
        raise RuntimeError("Sikkim boundary is empty or invalid")
    if not grid.geometry.intersects(boundary).all():
        raise RuntimeError("At least one canonical grid cell does not intersect Sikkim")
    return grid, boundary, grid_path, boundary_path, static_path


def line_parts(geometry: Any) -> Iterable[LineString]:
    if geometry is None or geometry.is_empty:
        return
    if isinstance(geometry, LineString):
        if geometry.length > 0:
            yield geometry
        return
    if isinstance(geometry, (MultiLineString, GeometryCollection)):
        for member in geometry.geoms:
            yield from line_parts(member)


def project_clip_lines(
    source_geometries: list[Any], clip_polygon: Any
) -> tuple[list[LineString], int, int]:
    if not source_geometries:
        raise RuntimeError("Source returned no line geometry")
    projected = gpd.GeoSeries(source_geometries, crs="EPSG:4326").to_crs(TARGET_CRS)
    used: list[LineString] = []
    intersecting_features = 0
    repaired_features = 0
    for geometry in projected:
        if geometry is None or geometry.is_empty:
            continue
        if not geometry.is_valid:
            geometry = make_valid(geometry)
            repaired_features += 1
        if geometry.is_empty or not geometry.intersects(clip_polygon):
            continue
        parts = list(line_parts(geometry.intersection(clip_polygon)))
        if parts:
            intersecting_features += 1
            used.extend(parts)
    if not used:
        raise RuntimeError("No valid line geometry intersects the configured source buffer")
    return used, intersecting_features, repaired_features


def fetch_gem_faults(fault_clip: Any) -> tuple[list[LineString], dict[str, Any]]:
    print(f"Fetching pinned GEM active faults at revision {GEM_REVISION}...")
    raw = http_bytes(GEM_URL)
    source_hash = sha256_bytes(raw)
    if source_hash != GEM_SOURCE_SHA256:
        raise RuntimeError(
            "Pinned GEM content checksum mismatch; refusing unexpected source bytes"
        )
    try:
        collection = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("Pinned GEM response is not valid GeoJSON") from error
    if collection.get("type") != "FeatureCollection":
        raise RuntimeError("Pinned GEM response is not a GeoJSON FeatureCollection")
    features = collection.get("features", [])
    geometries: list[Any] = []
    for feature in features:
        geometry_data = feature.get("geometry")
        if not geometry_data:
            continue
        geometry = shape(geometry_data)
        if isinstance(geometry, (LineString, MultiLineString, GeometryCollection)):
            geometries.append(geometry)
    lines, feature_count_used, repaired_count = project_clip_lines(geometries, fault_clip)
    print(
        f"GEM: {feature_count_used:,} source features / {len(lines):,} line geometries "
        "intersect the fault buffer"
    )
    return lines, {
        "provider": "Global Earthquake Model (GEM) Foundation",
        "dataset": "GEM Global Active Faults Database, harmonized GeoJSON",
        "role": "active_fault_proxy",
        "source_url": GEM_URL,
        "repository_commit_url": GEM_COMMIT_URL,
        "revision": GEM_REVISION,
        "revision_is_immutable_commit": True,
        "source_content_sha256": source_hash,
        "source_bytes": len(raw),
        "source_feature_count_total": len(features),
        "source_line_feature_count_total": len(geometries),
        "source_feature_count_used": feature_count_used,
        "line_geometry_count_used": len(lines),
        "invalid_features_repaired": repaired_count,
        "license": "CC BY-SA 4.0",
    }


def overpass_query(bounds: tuple[float, float, float, float]) -> str:
    west, south, east, north = bounds
    tags = "|".join(WATERWAY_TAGS)
    return (
        "[out:json][timeout:120];"
        f'(way["waterway"~"^({tags})$"]'
        f"({south:.7f},{west:.7f},{north:.7f},{east:.7f}););"
        "out geom;"
    )


def fetch_osm_drainage(
    drainage_clip: Any, minimum_ways: int
) -> tuple[list[LineString], dict[str, Any]]:
    drainage_wgs84 = gpd.GeoSeries([drainage_clip], crs=TARGET_CRS).to_crs(4326).iloc[0]
    query = overpass_query(drainage_wgs84.bounds)
    body = urlencode({"data": query}).encode("utf-8")
    errors: list[str] = []
    for endpoint in OVERPASS_ENDPOINTS:
        print(f"Fetching real OSM waterways from {endpoint}...")
        try:
            raw = http_bytes(
                endpoint,
                data=body,
                content_type="application/x-www-form-urlencoded; charset=utf-8",
                attempts=2,
            )
            response = json.loads(raw)
            if response.get("remark"):
                raise RuntimeError(f"Overpass returned a remark: {response['remark']}")
            elements = response.get("elements", [])
            geometries: list[LineString] = []
            way_ids: list[int] = []
            for element in elements:
                if element.get("type") != "way":
                    continue
                coordinates = [
                    (float(vertex["lon"]), float(vertex["lat"]))
                    for vertex in element.get("geometry", [])
                    if "lon" in vertex and "lat" in vertex
                ]
                if len(coordinates) >= 2:
                    geometries.append(LineString(coordinates))
                    way_ids.append(int(element["id"]))
            if len(geometries) < minimum_ways:
                raise RuntimeError(
                    f"Overpass returned only {len(geometries)} valid waterway ways; "
                    f"minimum is {minimum_ways}"
                )
            lines, feature_count_used, repaired_count = project_clip_lines(
                geometries, drainage_clip
            )
            if feature_count_used < minimum_ways:
                raise RuntimeError(
                    f"Only {feature_count_used} valid waterways intersect the drainage buffer; "
                    f"minimum is {minimum_ways}"
                )
            print(
                f"OSM: {feature_count_used:,} source ways / {len(lines):,} line geometries "
                "intersect the drainage buffer"
            )
            attempted_count = OVERPASS_ENDPOINTS.index(endpoint) + 1
            return lines, {
                "provider": "OpenStreetMap contributors",
                "dataset": "OSM waterways via Overpass API",
                "role": "drainage_network",
                "api_endpoint_used": endpoint,
                "api_endpoints_attempted": list(OVERPASS_ENDPOINTS[:attempted_count]),
                "source_url": "https://www.openstreetmap.org/",
                "osm_base_timestamp": response.get("osm3s", {}).get("timestamp_osm_base"),
                "overpass_generator": response.get("generator"),
                "overpass_query": query,
                "waterway_tags": list(WATERWAY_TAGS),
                "response_content_sha256": sha256_bytes(raw),
                "response_bytes": len(raw),
                "source_element_count_total": len(elements),
                "source_way_count_valid": len(geometries),
                "source_feature_count_used": feature_count_used,
                "line_geometry_count_used": len(lines),
                "invalid_features_repaired": repaired_count,
                "minimum_required_waterway_ways": minimum_ways,
                "osm_way_id_min": min(way_ids),
                "osm_way_id_max": max(way_ids),
                "license": "Open Data Commons Open Database License (ODbL)",
            }
        except (RuntimeError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            errors.append(f"{endpoint}: {error}")
            print(f"Overpass endpoint failed validation: {error}")
    details = "\n  - ".join(errors)
    raise RuntimeError(
        "No Overpass endpoint returned a complete, valid drainage network. "
        "Synthetic drainage is prohibited. Errors:\n  - " + details
    )


def exact_nearest_distances(
    centroid_x: np.ndarray, centroid_y: np.ndarray, lines: list[LineString]
) -> np.ndarray:
    if not lines:
        raise RuntimeError("Cannot calculate distance without real line geometry")
    targets = points(centroid_x, centroid_y)
    pairs, distances = STRtree(lines).query_nearest(
        targets, all_matches=False, return_distance=True
    )
    result = np.full(len(targets), np.nan, dtype="float64")
    result[pairs[0]] = distances
    if not np.isfinite(result).all() or (result < 0).any():
        raise RuntimeError("Nearest-line calculation produced missing or invalid distance")
    return result


def metadata_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}.metadata.json")


def write_outputs_atomic(
    output: Path, frame: pd.DataFrame, metadata: dict[str, Any]
) -> tuple[Path, str]:
    output = output.resolve()
    sidecar = metadata_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    csv_temporary = output.with_name(f".{output.name}.{token}.tmp")
    metadata_temporary = sidecar.with_name(f".{sidecar.name}.{token}.tmp")
    try:
        frame.to_csv(csv_temporary, index=False)
        output_hash = sha256_file(csv_temporary)
        metadata["output_sha256"] = output_hash
        metadata_temporary.write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        # Each replacement is atomic; both temporary files are complete before
        # either existing destination is replaced.
        csv_temporary.replace(output)
        metadata_temporary.replace(sidecar)
    finally:
        csv_temporary.unlink(missing_ok=True)
        metadata_temporary.unlink(missing_ok=True)
    return sidecar, output_hash


def main() -> None:
    args = parse_args()
    if args.fault_buffer_km <= 0 or args.drainage_buffer_km <= 0:
        raise ValueError("Source buffer distances must be positive")
    if args.minimum_drainage_ways <= 0:
        raise ValueError("--minimum-drainage-ways must be positive")

    grid, boundary, grid_path, boundary_path, static_path = load_analysis_units()
    fault_clip = boundary.buffer(args.fault_buffer_km * 1_000.0)
    drainage_clip = boundary.buffer(args.drainage_buffer_km * 1_000.0)
    print("=== Provenance-safe real drainage and active-fault distances ===")
    print(f"Canonical grid: {project_relative(grid_path)} ({len(grid):,} cells)")
    print(f"Static alignment reference: {project_relative(static_path)}")
    fault_lines, fault_source = fetch_gem_faults(fault_clip)
    drainage_lines, drainage_source = fetch_osm_drainage(
        drainage_clip, args.minimum_drainage_ways
    )

    centroid_x = grid["centroid_x"].to_numpy(dtype="float64")
    centroid_y = grid["centroid_y"].to_numpy(dtype="float64")
    drainage_km = exact_nearest_distances(centroid_x, centroid_y, drainage_lines) / 1_000.0
    fault_km = exact_nearest_distances(centroid_x, centroid_y, fault_lines) / 1_000.0
    output_frame = pd.DataFrame(
        {
            "cell_id": grid["cell_id"].astype(str),
            "distance_to_drainage_km": np.round(drainage_km, 6),
            "distance_to_fault_km": np.round(fault_km, 6),
        }
    )
    expected_ids = [f"SKM_{index:05d}" for index in range(1, EXPECTED_CELL_COUNT + 1)]
    if output_frame["cell_id"].tolist() != expected_ids:
        raise RuntimeError("Output cell_id order does not match the canonical grid")
    if len(output_frame) != EXPECTED_CELL_COUNT or output_frame["cell_id"].duplicated().any():
        raise RuntimeError("Output violated the one-row-per-cell contract")
    numeric = output_frame[["distance_to_drainage_km", "distance_to_fault_km"]]
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
        raise RuntimeError("Distance output contains missing or non-finite values")
    if (numeric < 0).any().any():
        raise RuntimeError("Distance output contains negative values")

    generated_at = datetime.now(timezone.utc)
    metadata: dict[str, Any] = {
        "schema_version": 1,
        "data_origin": "authoritative_geospatial_vectors",
        "synthetic_fallback_used": False,
        "manual_geometry_used": False,
        "generated_at_utc": generated_at.isoformat(),
        "source_access_date_utc": generated_at.date().isoformat(),
        "output_csv": project_relative(args.output),
        "output_columns": list(output_frame.columns),
        "output_row_count": len(output_frame),
        "ordered_cell_validation": True,
        "canonical_grid": {
            "path": project_relative(grid_path),
            "crs": TARGET_CRS,
            "row_count": len(grid),
            "cell_id_first": expected_ids[0],
            "cell_id_last": expected_ids[-1],
            "cell_size_metres": 1_000,
            "geometry_unchanged": True,
        },
        "boundary": project_relative(boundary_path),
        "static_alignment_reference": project_relative(static_path),
        "sources": {"fault": fault_source, "drainage": drainage_source},
        "parameters": {
            "target_crs": TARGET_CRS,
            "distance_point": "canonical grid centroid_x/centroid_y",
            "distance_method": "exact Shapely point-to-LineString nearest distance",
            "distance_units": "kilometres",
            "fault_source_buffer_km": args.fault_buffer_km,
            "drainage_source_buffer_km": args.drainage_buffer_km,
            "minimum_drainage_ways": args.minimum_drainage_ways,
        },
        "qa": {
            "row_count": len(output_frame),
            "unique_cell_id_count": int(output_frame["cell_id"].nunique()),
            "ordered_cell_ids_match_canonical_grid": True,
            "missing_values": {
                column: int(output_frame[column].isna().sum())
                for column in output_frame.columns
            },
            "distance_to_drainage_km": {
                "min": float(output_frame["distance_to_drainage_km"].min()),
                "median": float(output_frame["distance_to_drainage_km"].median()),
                "max": float(output_frame["distance_to_drainage_km"].max()),
            },
            "distance_to_fault_km": {
                "min": float(output_frame["distance_to_fault_km"].min()),
                "median": float(output_frame["distance_to_fault_km"].median()),
                "max": float(output_frame["distance_to_fault_km"].max()),
            },
        },
        "limitations": [
            "GEM is an active-fault proxy/source, not GSI lithology or a complete geological map.",
            "OSM waterways are community-maintained and completeness varies spatially.",
            "Distances are from canonical 1 km cell centroids; source vectors are not 1 km data.",
            "No lithology feature is produced by this workflow.",
        ],
    }
    sidecar, output_hash = write_outputs_atomic(args.output, output_frame, metadata)
    print(f"Saved features: {args.output.resolve()}")
    print(f"Saved provenance: {sidecar}")
    print(f"SHA-256: {output_hash}")
    print(
        "Fault distance km — "
        f"min {fault_km.min():.6f}, median {np.median(fault_km):.6f}, "
        f"max {fault_km.max():.6f}"
    )


if __name__ == "__main__":
    main()
