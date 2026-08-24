"""Validate the Phase 2 Sikkim grid and real static feature table."""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import STRtree, points


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED = PROJECT_ROOT / "DATA" / "PROCESSED"
BOUNDARY_PATH = PROCESSED / "STATIC" / "BOUNDARY" / "sikkim_boundary_utm45n.gpkg"
GRID_PATH = PROCESSED / "GRID" / "sikkim_grid_1km.gpkg"
CSV_PATH = PROCESSED / "FEATURES" / "sikkim_static_features_1km.csv"
GPKG_PATH = PROCESSED / "FEATURES" / "sikkim_static_features_1km.gpkg"
REPORT_PATH = PROCESSED / "FEATURES" / "sikkim_static_features_1km_validation.json"
ROADS_PATH = PROCESSED / "STATIC" / "OSM" / "sikkim_roads.gpkg"
SETTLEMENTS_PATH = PROCESSED / "STATIC" / "OSM" / "sikkim_settlements.gpkg"

TARGET_EPSG = 32645
CELL_AREA_M2 = 1_000_000.0
LANDCOVER_COLUMNS = [
    "lc_tree_fraction",
    "lc_shrub_fraction",
    "lc_grass_fraction",
    "lc_cropland_fraction",
    "lc_builtup_fraction",
    "lc_bare_fraction",
    "lc_snow_ice_fraction",
    "lc_water_fraction",
    "lc_wetland_fraction",
    "lc_moss_lichen_fraction",
]
COUNT_COLUMNS = [
    "settlement_count",
    "village_count",
    "hamlet_count",
    "town_count",
    "city_count",
]
STATIC_ML_FEATURES = [
    "sikkim_fraction",
    "elevation_mean_m",
    "elevation_min_m",
    "elevation_max_m",
    "elevation_std_m",
    "terrain_relief_m",
    "slope_mean_deg",
    "slope_max_deg",
    "slope_std_deg",
    "aspect_sin",
    "aspect_cos",
    "dominant_landcover_class",
    *LANDCOVER_COLUMNS,
    "road_length_m",
    "road_density_km_per_km2",
    "distance_to_nearest_road_m",
    *COUNT_COLUMNS,
    "distance_to_nearest_settlement_m",
]
REQUIRED_COLUMNS = [
    "cell_id",
    "centroid_lat",
    "centroid_lon",
    "analysis_x",
    "analysis_y",
    "analysis_lon",
    "analysis_lat",
    "sikkim_fraction",
    "model_eligible",
    "elevation_mean_m",
    "elevation_min_m",
    "elevation_max_m",
    "elevation_std_m",
    "terrain_relief_m",
    "slope_mean_deg",
    "slope_max_deg",
    "slope_std_deg",
    "aspect_sin",
    "aspect_cos",
    "dominant_landcover_class",
    *LANDCOVER_COLUMNS,
    "road_length_m",
    "road_density_km_per_km2",
    "distance_to_nearest_road_m",
    *COUNT_COLUMNS,
    "distance_to_nearest_settlement_m",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def finite_or_none(value) -> float | None:
    value = float(value)
    return value if np.isfinite(value) else None


def numeric_summary(series: pd.Series) -> dict:
    valid = series.dropna()
    return {
        "missing_count": int(series.isna().sum()),
        "min": finite_or_none(valid.min()) if len(valid) else None,
        "max": finite_or_none(valid.max()) if len(valid) else None,
        "mean": finite_or_none(valid.mean()) if len(valid) else None,
    }


def nearest_distances(query_geometries, target_geometries) -> np.ndarray:
    tree = STRtree(target_geometries)
    pairs, distances = tree.query_nearest(
        query_geometries, all_matches=False, return_distance=True
    )
    result = np.full(len(query_geometries), np.nan, dtype="float64")
    result[pairs[0]] = distances
    return result


def main() -> None:
    required_files = [
        BOUNDARY_PATH,
        GRID_PATH,
        CSV_PATH,
        GPKG_PATH,
        ROADS_PATH,
        SETTLEMENTS_PATH,
    ]
    missing_files = [str(path) for path in required_files if not path.is_file()]
    if missing_files:
        raise FileNotFoundError(f"Missing Phase 2 outputs: {missing_files}")

    boundary = gpd.read_file(BOUNDARY_PATH).to_crs(epsg=TARGET_EPSG)
    grid = gpd.read_file(GRID_PATH).to_crs(epsg=TARGET_EPSG)
    features = pd.read_csv(CSV_PATH)
    spatial_features = gpd.read_file(GPKG_PATH).to_crs(epsg=TARGET_EPSG)

    require(not grid.empty, "Grid is empty")
    require(grid.crs.to_epsg() == TARGET_EPSG, "Grid is not EPSG:32645")
    require(spatial_features.crs.to_epsg() == TARGET_EPSG, "Feature GPKG is not EPSG:32645")
    require(grid.geometry.is_valid.all(), "Grid has invalid geometries")
    require(np.allclose(grid.geometry.area, CELL_AREA_M2), "Grid cells are not intact 1 km squares")
    require((grid["sikkim_fraction"] > 0).all(), "Grid contains zero-area Sikkim cells")
    require((grid["sikkim_fraction"] <= 1.0).all(), "Sikkim fraction exceeds 1")

    bounds = grid.geometry.bounds
    require(np.allclose(np.mod(bounds["minx"], 1_000), 0), "Grid x origin is not 1 km aligned")
    require(np.allclose(np.mod(bounds["miny"], 1_000), 0), "Grid y origin is not 1 km aligned")
    expected_ids = [f"SKM_{index:05d}" for index in range(1, len(grid) + 1)]
    require(grid["cell_id"].tolist() == expected_ids, "Grid IDs are not stable and sequential")
    ordered = grid.sort_values(
        ["centroid_y", "centroid_x"], ascending=[False, True]
    )["cell_id"].tolist()
    require(ordered == expected_ids, "Grid is not ordered north-to-south then west-to-east")

    boundary_shape = boundary.geometry.union_all()
    full_mask = grid["sikkim_fraction"] >= 1.0 - 1e-9
    analysis_points = points(grid["analysis_x"], grid["analysis_y"])
    square_centroids = grid.geometry.centroid.to_numpy()
    require(
        np.allclose(grid.loc[full_mask, "analysis_x"], grid.loc[full_mask, "centroid_x"])
        and np.allclose(grid.loc[full_mask, "analysis_y"], grid.loc[full_mask, "centroid_y"]),
        "Full cells do not use their square centroid as the analysis point",
    )
    intersections = grid.geometry.intersection(boundary_shape)
    require(
        all(
            intersection.covers(analysis_point)
            for intersection, analysis_point in zip(
                intersections, analysis_points, strict=True
            )
        ),
        "At least one analysis point lies outside its Sikkim cell intersection",
    )
    analysis_wgs84 = gpd.GeoSeries(
        analysis_points, crs=f"EPSG:{TARGET_EPSG}"
    ).to_crs("EPSG:4326")
    require(
        np.allclose(grid["analysis_lon"], analysis_wgs84.x)
        and np.allclose(grid["analysis_lat"], analysis_wgs84.y),
        "Analysis longitude/latitude fields are inconsistent",
    )

    require(len(features) == len(grid), "CSV does not have one row per grid cell")
    require(len(spatial_features) == len(grid), "GPKG does not have one row per grid cell")
    require(not features["cell_id"].duplicated().any(), "CSV contains duplicate cell_id")
    require(set(features["cell_id"]) == set(grid["cell_id"]), "CSV/grid cell IDs differ")
    require(set(spatial_features["cell_id"]) == set(grid["cell_id"]), "GPKG/grid cell IDs differ")
    absent_columns = sorted(set(REQUIRED_COLUMNS) - set(features.columns))
    require(not absent_columns, f"Required feature columns are missing: {absent_columns}")

    ml_values = features[STATIC_ML_FEATURES].astype("float64")
    expected_eligibility = ml_values.notna().all(axis=1) & np.isfinite(
        ml_values.to_numpy()
    ).all(axis=1)
    require(
        features["model_eligible"].astype(bool).equals(expected_eligibility),
        "model_eligible is inconsistent with required finite static ML features",
    )

    numeric = features.select_dtypes(include=[np.number])
    require(not np.isinf(numeric.to_numpy()).any(), "Numeric features contain infinity")
    require((features["slope_mean_deg"].dropna().between(0, 90)).all(), "Mean slope is invalid")
    require((features["slope_max_deg"].dropna().between(0, 90)).all(), "Maximum slope is invalid")
    for column in ["aspect_sin", "aspect_cos"]:
        require(features[column].dropna().between(-1, 1).all(), f"{column} is outside [-1, 1]")
    aspect_valid = features[["aspect_sin", "aspect_cos"]].dropna()
    require(
        (np.hypot(aspect_valid["aspect_sin"], aspect_valid["aspect_cos"]) <= 1 + 1e-12).all(),
        "Circular aspect vector magnitude exceeds 1",
    )

    for column in LANDCOVER_COLUMNS:
        require(features[column].dropna().between(0, 1).all(), f"{column} is outside [0, 1]")
    landcover_valid = features[LANDCOVER_COLUMNS].notna().any(axis=1)
    require(
        features.loc[landcover_valid, LANDCOVER_COLUMNS].notna().all(axis=1).all(),
        "Valid land-cover rows contain partial missing fractions",
    )
    landcover_sums = features.loc[landcover_valid, LANDCOVER_COLUMNS].sum(axis=1)
    require(np.allclose(landcover_sums, 1.0, atol=1e-9), "Land-cover fractions do not sum to 1")

    require((features["road_length_m"] >= 0).all(), "Road lengths are negative")
    require((features["road_density_km_per_km2"] >= 0).all(), "Road densities are negative")
    require((features["distance_to_nearest_road_m"] >= 0).all(), "Road distances are negative")
    require(
        (features["distance_to_nearest_settlement_m"] >= 0).all(),
        "Settlement distances are negative",
    )
    for column in COUNT_COLUMNS:
        require((features[column] >= 0).all(), f"{column} is negative")
        require(np.equal(features[column], np.floor(features[column])).all(), f"{column} is not integer")

    elevation_valid = features[
        ["elevation_min_m", "elevation_mean_m", "elevation_max_m"]
    ].dropna()
    require(
        (
            (elevation_valid["elevation_min_m"] <= elevation_valid["elevation_mean_m"])
            & (elevation_valid["elevation_mean_m"] <= elevation_valid["elevation_max_m"])
        ).all(),
        "Elevation summary ordering is invalid",
    )
    relief_expected = features["elevation_max_m"] - features["elevation_min_m"]
    require(
        np.allclose(features["terrain_relief_m"], relief_expected, equal_nan=True),
        "Terrain relief is inconsistent",
    )
    density_expected = (features["road_length_m"] / 1_000) / features["sikkim_fraction"]
    require(
        np.allclose(features["road_density_km_per_km2"], density_expected),
        "Road density is inconsistent with effective Sikkim area",
    )

    roads = gpd.read_file(ROADS_PATH).to_crs(epsg=TARGET_EPSG)
    settlements = gpd.read_file(SETTLEMENTS_PATH).to_crs(epsg=TARGET_EPSG)
    centroid_road_distances = nearest_distances(
        square_centroids, roads.geometry.to_numpy()
    )
    analysis_road_distances = nearest_distances(
        analysis_points, roads.geometry.to_numpy()
    )
    centroid_settlement_distances = nearest_distances(
        square_centroids, settlements.geometry.to_numpy()
    )
    analysis_settlement_distances = nearest_distances(
        analysis_points, settlements.geometry.to_numpy()
    )
    require(
        np.allclose(features["distance_to_nearest_road_m"], analysis_road_distances),
        "Stored road distances do not use the analysis point",
    )
    require(
        np.allclose(
            features["distance_to_nearest_settlement_m"],
            analysis_settlement_distances,
        ),
        "Stored settlement distances do not use the analysis point",
    )
    max_road_distance_change_m = float(
        np.max(np.abs(analysis_road_distances - centroid_road_distances))
    )
    max_settlement_distance_change_m = float(
        np.max(
            np.abs(analysis_settlement_distances - centroid_settlement_distances)
        )
    )

    boundary_area_km2 = float(boundary.geometry.area.sum() / 1e6)
    grid_covered_area_km2 = float(grid["sikkim_fraction"].sum())
    coverage_difference_km2 = grid_covered_area_km2 - boundary_area_km2
    coverage_error_percent = abs(coverage_difference_km2) / boundary_area_km2 * 100
    require(coverage_error_percent < 1e-8, "Grid does not reproduce the Sikkim boundary area")
    full_cells = int((grid["sikkim_fraction"] >= 1.0 - 1e-9).sum())
    eligible_cells = int(expected_eligibility.sum())
    excluded_cells = int(len(features) - eligible_cells)
    excluded_area_km2 = float(
        features.loc[~expected_eligibility, "sikkim_fraction"].sum()
    )
    excluded_area_percent = excluded_area_km2 / boundary_area_km2 * 100

    feature_statistics = {
        column: numeric_summary(features[column]) for column in numeric.columns
    }
    missing_numeric = {
        column: stats["missing_count"]
        for column, stats in feature_statistics.items()
        if stats["missing_count"] > 0
    }
    report = {
        "grid": {
            "total_cells": int(len(grid)),
            "full_cells": full_cells,
            "partial_boundary_cells": int(len(grid) - full_cells),
            "sikkim_boundary_area_km2": boundary_area_km2,
            "grid_covered_sikkim_area_km2": grid_covered_area_km2,
            "coverage_difference_km2": coverage_difference_km2,
            "coverage_error_percent": coverage_error_percent,
            "crs": "EPSG:32645",
            "cell_size_m": 1_000,
        },
        "model_eligibility": {
            "eligible_cells": eligible_cells,
            "excluded_cells": excluded_cells,
            "excluded_sikkim_area_km2": excluded_area_km2,
            "excluded_sikkim_area_percent": excluded_area_percent,
        },
        "analysis_point_distance_changes": {
            "maximum_nearest_road_distance_change_m": max_road_distance_change_m,
            "maximum_nearest_settlement_distance_change_m": max_settlement_distance_change_m,
        },
        "checks": {
            "one_row_per_cell": True,
            "duplicate_cell_ids": 0,
            "infinite_numeric_values": 0,
            "landcover_fraction_max_sum_error": finite_or_none(
                np.max(np.abs(landcover_sums - 1.0)) if len(landcover_sums) else 0.0
            ),
            "all_analysis_points_inside_sikkim_cell_intersection": True,
            "model_eligibility_recomputed_and_verified": True,
            "all_scientific_range_checks_passed": True,
        },
        "feature_statistics": feature_statistics,
        "missing_numeric_values": missing_numeric,
        "missing_value_notes": [
            "Elevation and land-cover values remain missing when a very small boundary sliver contains no valid native-resolution pixel centre.",
            "Slope and aspect require a valid 3x3 DEM neighbourhood, so additional edge-sliver cells can lack terrain derivatives; aspect is also undefined on perfectly flat pixels and is never replaced with an arbitrary zero.",
            "Zero road lengths and settlement counts mean observed absence within a cell and are valid data, not imputation.",
        ],
        "analysis_unit_note": (
            "The 1 km grid is an aggregation unit. SRTM remains ~30 m, WorldCover remains "
            "10 m, and OSM remains vector data. Future IMERG/SMAP values must retain their "
            "coarser native-resolution provenance when joined to this grid."
        ),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Validation passed. Report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
