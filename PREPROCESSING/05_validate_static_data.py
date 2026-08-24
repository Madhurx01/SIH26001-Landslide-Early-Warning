"""Validate all Static Preprocessing Phase 1 outputs and write a JSON report."""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import box


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "DATA" / "PROCESSED" / "STATIC"
BOUNDARY_WGS84 = STATIC_DIR / "BOUNDARY" / "sikkim_boundary_wgs84.gpkg"
BOUNDARY_UTM = STATIC_DIR / "BOUNDARY" / "sikkim_boundary_utm45n.gpkg"
ELEVATION = STATIC_DIR / "DEM" / "sikkim_elevation_30m.tif"
SLOPE = STATIC_DIR / "DEM" / "sikkim_slope_30m.tif"
ASPECT = STATIC_DIR / "DEM" / "sikkim_aspect_30m.tif"
WORLDCOVER = STATIC_DIR / "LANDCOVER" / "sikkim_worldcover_10m.tif"
ROADS = STATIC_DIR / "OSM" / "sikkim_roads.gpkg"
SETTLEMENTS = STATIC_DIR / "OSM" / "sikkim_settlements.gpkg"
REPORT_PATH = STATIC_DIR / "validation_report.json"

TARGET_EPSG = 32645
EXPECTED_WORLDCOVER_CLASSES = {10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100}


def raster_statistics(path: Path) -> dict:
    """Compute exact valid-pixel statistics block by block."""
    count = 0
    total = 0.0
    minimum = np.inf
    maximum = -np.inf
    unique: set[int] = set()
    with rasterio.open(path) as source:
        for _, window in source.block_windows(1):
            block = source.read(1, window=window, masked=True)
            values = block.compressed()
            if values.size == 0:
                continue
            count += int(values.size)
            total += float(values.astype("float64").sum())
            minimum = min(minimum, float(values.min()))
            maximum = max(maximum, float(values.max()))
            if np.issubdtype(values.dtype, np.integer):
                unique.update(int(value) for value in np.unique(values))
        return {
            "crs": source.crs.to_string() if source.crs else None,
            "epsg": source.crs.to_epsg() if source.crs else None,
            "resolution_m": [abs(float(source.res[0])), abs(float(source.res[1]))],
            "width": source.width,
            "height": source.height,
            "valid_pixel_count": count,
            "min": minimum if count else None,
            "max": maximum if count else None,
            "mean": total / count if count else None,
            "unique_values": sorted(unique),
            "bounds": [
                float(source.bounds.left),
                float(source.bounds.bottom),
                float(source.bounds.right),
                float(source.bounds.top),
            ],
            "dtype": source.dtypes[0],
            "nodata": source.nodata,
        }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    required = [
        BOUNDARY_WGS84,
        BOUNDARY_UTM,
        ELEVATION,
        SLOPE,
        ASPECT,
        WORLDCOVER,
        ROADS,
        SETTLEMENTS,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing processed outputs: {missing}")

    boundary_wgs84 = gpd.read_file(BOUNDARY_WGS84).to_crs("EPSG:4326")
    boundary_utm = gpd.read_file(BOUNDARY_UTM)
    require(boundary_utm.crs.to_epsg() == TARGET_EPSG, "Projected boundary is not EPSG:32645")
    require(boundary_wgs84.geometry.is_valid.all(), "WGS84 boundary geometry is invalid")
    require(boundary_utm.geometry.is_valid.all(), "UTM boundary geometry is invalid")

    boundary_report = {
        "name": str(boundary_wgs84.iloc[0]["name"]),
        "admin_level": int(boundary_wgs84.iloc[0]["admin_level"]),
        "epsg4326_bounds": [float(value) for value in boundary_wgs84.total_bounds],
        "area_km2": float(boundary_utm.geometry.area.sum() / 1_000_000),
        "geometry_valid": bool(
            boundary_wgs84.geometry.is_valid.all() and boundary_utm.geometry.is_valid.all()
        ),
    }

    elevation = raster_statistics(ELEVATION)
    slope = raster_statistics(SLOPE)
    aspect = raster_statistics(ASPECT)
    worldcover = raster_statistics(WORLDCOVER)
    for label, stats in {
        "elevation": elevation,
        "slope": slope,
        "aspect": aspect,
        "worldcover": worldcover,
    }.items():
        require(stats["epsg"] == TARGET_EPSG, f"{label} is not EPSG:32645")

    require(elevation["resolution_m"] == [30.0, 30.0], "Elevation is not 30 m")
    require(slope["resolution_m"] == [30.0, 30.0], "Slope is not 30 m")
    require(aspect["resolution_m"] == [30.0, 30.0], "Aspect is not 30 m")
    require(worldcover["resolution_m"] == [10.0, 10.0], "WorldCover is not 10 m")
    require(0.0 <= slope["min"] <= slope["max"] <= 90.0, "Slope range is invalid")
    require(0.0 <= aspect["min"] <= aspect["max"] < 360.0, "Aspect range is invalid")

    worldcover_classes = set(worldcover["unique_values"])
    require(
        worldcover_classes <= EXPECTED_WORLDCOVER_CLASSES,
        f"WorldCover contains interpolated or invalid classes: {worldcover_classes}",
    )
    worldcover["categorical_values_preserved"] = True

    roads = gpd.read_file(ROADS)
    settlements = gpd.read_file(SETTLEMENTS)
    require(roads.crs.to_epsg() == TARGET_EPSG, "Roads are not EPSG:32645")
    require(settlements.crs.to_epsg() == TARGET_EPSG, "Settlements are not EPSG:32645")
    require(roads.geometry.is_valid.all(), "Road output contains invalid geometry")
    require(settlements.geometry.is_valid.all(), "Settlement output contains invalid geometry")

    boundary_shape = boundary_utm.geometry.union_all()
    raster_paths = [ELEVATION, SLOPE, ASPECT, WORLDCOVER]
    raster_footprints = []
    for path in raster_paths:
        with rasterio.open(path) as source:
            raster_footprints.append(box(*source.bounds))
    vector_bounds = [box(*roads.total_bounds), box(*settlements.total_bounds)]
    all_bounds_overlap_boundary = all(
        footprint.intersects(boundary_shape)
        for footprint in [*raster_footprints, *vector_bounds]
    )
    all_pairwise_rasters_overlap = all(
        first.intersects(second)
        for index, first in enumerate(raster_footprints)
        for second in raster_footprints[index + 1 :]
    )
    # A 1 mm buffer absorbs harmless floating-point differences introduced when
    # clipped WGS84 line endpoints and the boundary are independently reprojected.
    roads_covered_by_boundary = bool(
        roads.geometry.covered_by(boundary_shape.buffer(0.001)).all()
    )
    settlements_within_boundary = bool(settlements.geometry.covered_by(boundary_shape).all())
    overlap_report = {
        "common_crs_epsg": TARGET_EPSG,
        "all_layer_bounds_overlap_sikkim": all_bounds_overlap_boundary,
        "all_raster_bounds_overlap_each_other": all_pairwise_rasters_overlap,
        "all_roads_covered_by_sikkim_with_1mm_tolerance": roads_covered_by_boundary,
        "all_settlements_covered_by_sikkim": settlements_within_boundary,
        "verified": bool(
            all_bounds_overlap_boundary
            and all_pairwise_rasters_overlap
            and roads_covered_by_boundary
            and settlements_within_boundary
        ),
    }
    require(overlap_report["verified"], f"Spatial overlap validation failed: {overlap_report}")

    report = {
        "boundary": boundary_report,
        "dem": {
            "elevation": elevation,
            "slope": slope,
            "aspect": aspect,
        },
        "worldcover": worldcover,
        "osm": {
            "road_feature_count": int(len(roads)),
            "settlement_feature_count": int(len(settlements)),
            "settlement_counts_by_type": {
                str(key): int(value)
                for key, value in settlements["fclass"]
                .value_counts()
                .sort_index()
                .items()
            },
        },
        "spatial_overlap": overlap_report,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Validation passed. Report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
