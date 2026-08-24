"""Clip and reproject ESA WorldCover for Sikkim while preserving class codes."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_LANDCOVER_DIR = PROJECT_ROOT / "DATA" / "RAW" / "STATIC" / "LAND COVER"
BOUNDARY_UTM = (
    PROJECT_ROOT
    / "DATA"
    / "PROCESSED"
    / "STATIC"
    / "BOUNDARY"
    / "sikkim_boundary_utm45n.gpkg"
)
OUTPUT_DIR = PROJECT_ROOT / "DATA" / "PROCESSED" / "STATIC" / "LANDCOVER"
OUTPUT_PATH = OUTPUT_DIR / "sikkim_worldcover_10m.tif"

TARGET_CRS = "EPSG:32645"
TARGET_RESOLUTION = 10.0
NODATA = 0
VALID_WORLDCOVER_CLASSES = {10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100}


def find_worldcover_map() -> Path:
    candidates = sorted(
        path
        for path in RAW_LANDCOVER_DIR.rglob("*.tif")
        if "worldcover" in path.name.casefold()
        and "2021" in path.name.casefold()
        and "v200" in path.name.casefold()
        and "map" in path.name.casefold()
    )
    if len(candidates) != 1:
        raise RuntimeError(
            "Expected exactly one ESA WorldCover 2021 v200 Map GeoTIFF under "
            f"{RAW_LANDCOVER_DIR}, found {len(candidates)}: {candidates}"
        )
    return candidates[0]


def aligned_grid(bounds: np.ndarray, resolution: float) -> tuple[rasterio.Affine, int, int]:
    left = np.floor(bounds[0] / resolution) * resolution
    bottom = np.floor(bounds[1] / resolution) * resolution
    right = np.ceil(bounds[2] / resolution) * resolution
    top = np.ceil(bounds[3] / resolution) * resolution
    width = int(round((right - left) / resolution))
    height = int(round((top - bottom) / resolution))
    return from_origin(left, top, resolution, resolution), width, height


def main() -> None:
    if not BOUNDARY_UTM.is_file():
        raise FileNotFoundError("Run 01_extract_sikkim_boundary.py first")
    source_path = find_worldcover_map()
    boundary = gpd.read_file(BOUNDARY_UTM).to_crs(TARGET_CRS)
    transform, width, height = aligned_grid(boundary.total_bounds, TARGET_RESOLUTION)
    output = np.full((height, width), NODATA, dtype="uint8")

    with rasterio.open(source_path) as source:
        if source.crs is None or source.crs.to_epsg() != 4326:
            raise RuntimeError(f"Unexpected WorldCover CRS: {source.crs}")
        # WorldCover is categorical, so nearest-neighbour is mandatory: interpolation
        # would create class codes that do not represent real land-cover categories.
        reproject(
            source=rasterio.band(source, 1),
            destination=output,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata if source.nodata is not None else NODATA,
            dst_transform=transform,
            dst_crs=TARGET_CRS,
            dst_nodata=NODATA,
            resampling=Resampling.nearest,
        )

    inside = geometry_mask(
        boundary.geometry,
        out_shape=(height, width),
        transform=transform,
        invert=True,
        all_touched=False,
    )
    output[~inside] = NODATA
    classes = set(int(value) for value in np.unique(output[inside]) if value != NODATA)
    unexpected = classes - VALID_WORLDCOVER_CLASSES
    if unexpected:
        raise RuntimeError(f"Unexpected WorldCover class codes after reprojection: {unexpected}")
    if not classes:
        raise RuntimeError("WorldCover reprojection produced no valid classes inside Sikkim")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "uint8",
        "crs": TARGET_CRS,
        "transform": transform,
        "nodata": NODATA,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "BIGTIFF": "IF_SAFER",
    }
    with rasterio.open(OUTPUT_PATH, "w", **profile) as destination:
        destination.write(output, 1)
        destination.update_tags(
            source="ESA WorldCover 2021 v200",
            resampling="nearest",
            class_codes=",".join(map(str, sorted(classes))),
        )

    print(f"Source: {source_path}")
    print(f"Created: {OUTPUT_PATH}")
    print(f"Grid: {width} x {height} at {TARGET_RESOLUTION:.1f} m in {TARGET_CRS}")
    print(f"Classes inside Sikkim: {sorted(classes)}")


if __name__ == "__main__":
    main()
