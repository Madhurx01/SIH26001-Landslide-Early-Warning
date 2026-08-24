"""Mosaic, clip, reproject, and derive terrain products from SRTM DEM tiles."""

from contextlib import ExitStack
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from scipy.ndimage import correlate


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DEM_DIR = PROJECT_ROOT / "DATA" / "RAW" / "STATIC" / "DEM"
DEM_INPUTS = [RAW_DEM_DIR / "N27E088.hgt", RAW_DEM_DIR / "N28E088.hgt"]
BOUNDARY_WGS84 = (
    PROJECT_ROOT
    / "DATA"
    / "PROCESSED"
    / "STATIC"
    / "BOUNDARY"
    / "sikkim_boundary_wgs84.gpkg"
)
BOUNDARY_UTM = (
    PROJECT_ROOT
    / "DATA"
    / "PROCESSED"
    / "STATIC"
    / "BOUNDARY"
    / "sikkim_boundary_utm45n.gpkg"
)
OUTPUT_DIR = PROJECT_ROOT / "DATA" / "PROCESSED" / "STATIC" / "DEM"
ELEVATION_OUTPUT = OUTPUT_DIR / "sikkim_elevation_30m.tif"
SLOPE_OUTPUT = OUTPUT_DIR / "sikkim_slope_30m.tif"
ASPECT_OUTPUT = OUTPUT_DIR / "sikkim_aspect_30m.tif"

TARGET_CRS = "EPSG:32645"
TARGET_RESOLUTION = 30.0
OUTPUT_NODATA = -9999.0


def aligned_grid(bounds: np.ndarray, resolution: float) -> tuple[rasterio.Affine, int, int]:
    """Create a north-up target grid aligned to whole resolution units."""
    left = np.floor(bounds[0] / resolution) * resolution
    bottom = np.floor(bounds[1] / resolution) * resolution
    right = np.ceil(bounds[2] / resolution) * resolution
    top = np.ceil(bounds[3] / resolution) * resolution
    width = int(round((right - left) / resolution))
    height = int(round((top - bottom) / resolution))
    return from_origin(left, top, resolution, resolution), width, height


def terrain_derivatives(
    elevation: np.ndarray, valid: np.ndarray, xres: float, yres: float
) -> tuple[np.ndarray, np.ndarray]:
    """Calculate Horn 3x3 slope and downslope aspect on a metric grid."""
    z = np.where(valid, elevation, 0.0).astype("float32", copy=False)

    # Horn kernels. Raster rows increase southward, hence the north-positive dz/dy kernel.
    kernel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype="float32") / (8 * xres)
    kernel_y = np.array([[1, 2, 1], [0, 0, 0], [-1, -2, -1]], dtype="float32") / (8 * yres)
    dzdx = correlate(z, kernel_x, mode="constant", cval=0.0)
    dzdy = correlate(z, kernel_y, mode="constant", cval=0.0)
    valid_neighbourhood = correlate(
        valid.astype("uint8"), np.ones((3, 3), dtype="uint8"), mode="constant"
    ) == 9

    slope = np.full(elevation.shape, OUTPUT_NODATA, dtype="float32")
    slope[valid_neighbourhood] = np.degrees(
        np.arctan(np.hypot(dzdx[valid_neighbourhood], dzdy[valid_neighbourhood]))
    )

    # Bearing of the negative gradient: 0=north, 90=east, 180=south, 270=west.
    aspect = np.full(elevation.shape, OUTPUT_NODATA, dtype="float32")
    gradient = np.hypot(dzdx, dzdy)
    directional = valid_neighbourhood & (gradient > 1e-7)
    aspect[directional] = (
        np.degrees(np.arctan2(-dzdx[directional], -dzdy[directional])) + 360.0
    ) % 360.0
    # Aspect is undefined on perfectly flat pixels; they intentionally remain nodata.
    return slope, aspect


def write_raster(path: Path, data: np.ndarray, profile: dict) -> None:
    with rasterio.open(path, "w", **profile) as destination:
        destination.write(data, 1)


def main() -> None:
    missing = [str(path) for path in DEM_INPUTS if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing SRTM inputs: {missing}")
    if not BOUNDARY_WGS84.is_file() or not BOUNDARY_UTM.is_file():
        raise FileNotFoundError("Run 01_extract_sikkim_boundary.py first")

    boundary_wgs84 = gpd.read_file(BOUNDARY_WGS84).to_crs("EPSG:4326")
    boundary_utm = gpd.read_file(BOUNDARY_UTM).to_crs(TARGET_CRS)
    target_transform, width, height = aligned_grid(boundary_utm.total_bounds, TARGET_RESOLUTION)

    with ExitStack() as stack:
        sources = [stack.enter_context(rasterio.open(path)) for path in DEM_INPUTS]
        for source in sources:
            if source.crs is None or source.crs.to_epsg() != 4326:
                raise RuntimeError(f"Unexpected SRTM CRS in {source.name}: {source.crs}")
        source_nodata = sources[0].nodata if sources[0].nodata is not None else -32768
        mosaic, mosaic_transform = merge(sources, nodata=source_nodata)

    elevation = np.full((height, width), OUTPUT_NODATA, dtype="float32")
    reproject(
        source=mosaic[0],
        destination=elevation,
        src_transform=mosaic_transform,
        src_crs="EPSG:4326",
        src_nodata=source_nodata,
        dst_transform=target_transform,
        dst_crs=TARGET_CRS,
        dst_nodata=OUTPUT_NODATA,
        resampling=Resampling.bilinear,
    )

    inside_boundary = geometry_mask(
        boundary_utm.geometry,
        out_shape=(height, width),
        transform=target_transform,
        invert=True,
        all_touched=False,
    )
    elevation[~inside_boundary] = OUTPUT_NODATA
    valid_elevation = inside_boundary & np.isfinite(elevation) & (elevation != OUTPUT_NODATA)
    if not valid_elevation.any():
        raise RuntimeError("DEM reprojection produced no valid pixels inside Sikkim")

    # Terrain gradients must use metric horizontal distances, not longitude/latitude degrees.
    slope, aspect = terrain_derivatives(
        elevation, valid_elevation, TARGET_RESOLUTION, TARGET_RESOLUTION
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "crs": TARGET_CRS,
        "transform": target_transform,
        "nodata": OUTPUT_NODATA,
        "compress": "deflate",
        "predictor": 3,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "BIGTIFF": "IF_SAFER",
    }
    write_raster(ELEVATION_OUTPUT, elevation, profile)
    write_raster(SLOPE_OUTPUT, slope, profile)
    write_raster(ASPECT_OUTPUT, aspect, profile)

    print(f"Created: {ELEVATION_OUTPUT}")
    print(f"Created: {SLOPE_OUTPUT}")
    print(f"Created: {ASPECT_OUTPUT}")
    print(f"Grid: {width} x {height} at {TARGET_RESOLUTION:.1f} m in {TARGET_CRS}")


if __name__ == "__main__":
    main()
