"""Aggregate real Phase 1 static data into the 1 km Sikkim analysis grid.

The output resolution is the analysis unit only. It does not change or inflate
the native resolution of SRTM (~30 m), WorldCover (10 m), or OSM vectors. The
same distinction must later be preserved for coarser IMERG and SMAP products.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.errors import WindowError
from rasterio.features import geometry_mask, geometry_window
from shapely import STRtree
from shapely.geometry import mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED = PROJECT_ROOT / "DATA" / "PROCESSED"
GRID_PATH = PROCESSED / "GRID" / "sikkim_grid_1km.gpkg"
ELEVATION_PATH = PROCESSED / "STATIC" / "DEM" / "sikkim_elevation_30m.tif"
SLOPE_PATH = PROCESSED / "STATIC" / "DEM" / "sikkim_slope_30m.tif"
ASPECT_PATH = PROCESSED / "STATIC" / "DEM" / "sikkim_aspect_30m.tif"
WORLDCOVER_PATH = PROCESSED / "STATIC" / "LANDCOVER" / "sikkim_worldcover_10m.tif"
ROADS_PATH = PROCESSED / "STATIC" / "OSM" / "sikkim_roads.gpkg"
SETTLEMENTS_PATH = PROCESSED / "STATIC" / "OSM" / "sikkim_settlements.gpkg"
OUTPUT_DIR = PROCESSED / "FEATURES"
CSV_OUTPUT = OUTPUT_DIR / "sikkim_static_features_1km.csv"
GPKG_OUTPUT = OUTPUT_DIR / "sikkim_static_features_1km.gpkg"

TARGET_EPSG = 32645
LANDCOVER_FEATURES = {
    10: "lc_tree_fraction",
    20: "lc_shrub_fraction",
    30: "lc_grass_fraction",
    40: "lc_cropland_fraction",
    50: "lc_builtup_fraction",
    60: "lc_bare_fraction",
    70: "lc_snow_ice_fraction",
    80: "lc_water_fraction",
    90: "lc_wetland_fraction",
    100: "lc_moss_lichen_fraction",
}
COUNT_FEATURES = {
    "village": "village_count",
    "hamlet": "hamlet_count",
    "town": "town_count",
    "city": "city_count",
}
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
    *LANDCOVER_FEATURES.values(),
    "road_length_m",
    "road_density_km_per_km2",
    "distance_to_nearest_road_m",
    "settlement_count",
    "village_count",
    "hamlet_count",
    "town_count",
    "city_count",
    "distance_to_nearest_settlement_m",
]


def values_inside_cell(source: rasterio.DatasetReader, cell) -> np.ndarray:
    """Read only the raster window touching a cell and return valid in-cell pixels."""
    try:
        window = geometry_window(source, [mapping(cell)])
    except WindowError:
        return np.array([], dtype=source.dtypes[0])
    block = source.read(1, window=window, masked=True)
    in_cell = geometry_mask(
        [mapping(cell)],
        out_shape=block.shape,
        transform=source.window_transform(window),
        invert=True,
        all_touched=False,
    )
    valid = in_cell & ~np.ma.getmaskarray(block) & np.isfinite(block.data)
    return np.asarray(block.data[valid])


def nearest_distances_and_indices(geometries, targets) -> tuple[np.ndarray, np.ndarray]:
    """Return metric nearest-neighbour distances and target indices using STRtree."""
    tree = STRtree(targets)
    pairs, distances = tree.query_nearest(
        geometries, all_matches=False, return_distance=True
    )
    nearest_indices = np.full(len(geometries), -1, dtype="int64")
    nearest_distances = np.full(len(geometries), np.nan, dtype="float64")
    nearest_indices[pairs[0]] = pairs[1]
    nearest_distances[pairs[0]] = distances
    return nearest_distances, nearest_indices


def extract_raster_features(grid: gpd.GeoDataFrame) -> pd.DataFrame:
    records: list[dict] = []
    with (
        rasterio.open(ELEVATION_PATH) as elevation_source,
        rasterio.open(SLOPE_PATH) as slope_source,
        rasterio.open(ASPECT_PATH) as aspect_source,
        rasterio.open(WORLDCOVER_PATH) as landcover_source,
    ):
        for label, source in {
            "elevation": elevation_source,
            "slope": slope_source,
            "aspect": aspect_source,
            "WorldCover": landcover_source,
        }.items():
            if source.crs is None or source.crs.to_epsg() != TARGET_EPSG:
                raise RuntimeError(f"{label} raster is not EPSG:{TARGET_EPSG}")

        for position, cell in enumerate(grid.geometry, start=1):
            elevation = values_inside_cell(elevation_source, cell).astype("float64")
            slope = values_inside_cell(slope_source, cell).astype("float64")
            aspect = values_inside_cell(aspect_source, cell).astype("float64")
            landcover = values_inside_cell(landcover_source, cell).astype("uint8")

            record = {
                "elevation_mean_m": float(np.mean(elevation)) if elevation.size else np.nan,
                "elevation_min_m": float(np.min(elevation)) if elevation.size else np.nan,
                "elevation_max_m": float(np.max(elevation)) if elevation.size else np.nan,
                "elevation_std_m": float(np.std(elevation)) if elevation.size else np.nan,
                "slope_mean_deg": float(np.mean(slope)) if slope.size else np.nan,
                "slope_max_deg": float(np.max(slope)) if slope.size else np.nan,
                "slope_std_deg": float(np.std(slope)) if slope.size else np.nan,
                "aspect_sin": np.nan,
                "aspect_cos": np.nan,
                "dominant_landcover_class": pd.NA,
                **{name: np.nan for name in LANDCOVER_FEATURES.values()},
            }
            record["terrain_relief_m"] = (
                record["elevation_max_m"] - record["elevation_min_m"]
                if elevation.size
                else np.nan
            )

            if aspect.size:
                radians = np.deg2rad(aspect)
                record["aspect_sin"] = float(np.mean(np.sin(radians)))
                record["aspect_cos"] = float(np.mean(np.cos(radians)))

            if landcover.size:
                classes, counts = np.unique(landcover, return_counts=True)
                unexpected = set(int(value) for value in classes) - set(LANDCOVER_FEATURES)
                if unexpected:
                    raise RuntimeError(f"Unexpected WorldCover classes: {unexpected}")
                total = int(counts.sum())
                for class_code, count in zip(classes, counts, strict=True):
                    record[LANDCOVER_FEATURES[int(class_code)]] = float(count / total)
                for feature_name in LANDCOVER_FEATURES.values():
                    if pd.isna(record[feature_name]):
                        record[feature_name] = 0.0
                record["dominant_landcover_class"] = int(classes[np.argmax(counts)])

            records.append(record)
            if position % 1_000 == 0 or position == len(grid):
                print(f"Raster aggregation: {position:,}/{len(grid):,} cells")

    result = pd.DataFrame.from_records(records)
    result["dominant_landcover_class"] = pd.array(
        result["dominant_landcover_class"], dtype="Int64"
    )
    return result


def extract_road_features(grid: gpd.GeoDataFrame) -> pd.DataFrame:
    roads = gpd.read_file(ROADS_PATH).to_crs(epsg=TARGET_EPSG)
    if roads.empty:
        raise RuntimeError("Road layer is empty")
    road_index = roads.sindex
    lengths = np.zeros(len(grid), dtype="float64")
    for position, cell in enumerate(grid.geometry):
        candidates = road_index.query(cell, predicate="intersects")
        if len(candidates):
            lengths[position] = float(
                roads.geometry.iloc[candidates].intersection(cell).length.sum()
            )

    analysis_points = gpd.points_from_xy(
        grid["analysis_x"], grid["analysis_y"]
    ).to_numpy()
    distances, _ = nearest_distances_and_indices(
        analysis_points, roads.geometry.to_numpy()
    )
    effective_area_km2 = grid["sikkim_fraction"].to_numpy(dtype="float64")
    density = (lengths / 1_000.0) / effective_area_km2
    return pd.DataFrame(
        {
            "road_length_m": lengths,
            "road_density_km_per_km2": density,
            "distance_to_nearest_road_m": distances,
        }
    )


def extract_settlement_features(grid: gpd.GeoDataFrame) -> pd.DataFrame:
    settlements = gpd.read_file(SETTLEMENTS_PATH).to_crs(epsg=TARGET_EPSG).reset_index(
        names="settlement_index"
    )
    if settlements.empty:
        raise RuntimeError("Settlement layer is empty")

    # An intersect join includes rare grid-edge points. Sorting and de-duplicating
    # assigns any such point deterministically to the lowest stable cell_id.
    joined = gpd.sjoin(
        settlements,
        grid[["cell_id", "geometry"]],
        how="left",
        predicate="intersects",
    )
    if joined["cell_id"].isna().any():
        raise RuntimeError("At least one Sikkim settlement was not assigned to a grid cell")
    joined = joined.sort_values(["settlement_index", "cell_id"]).drop_duplicates(
        "settlement_index", keep="first"
    )

    counts = pd.DataFrame(index=grid["cell_id"])
    counts["settlement_count"] = joined.groupby("cell_id").size().reindex(counts.index, fill_value=0)
    for place_type, feature_name in COUNT_FEATURES.items():
        counts[feature_name] = (
            joined.loc[joined["fclass"] == place_type].groupby("cell_id").size()
            .reindex(counts.index, fill_value=0)
        )
    counts = counts.reset_index(drop=True).astype("int64")

    analysis_points = gpd.points_from_xy(
        grid["analysis_x"], grid["analysis_y"]
    ).to_numpy()
    distances, nearest_indices = nearest_distances_and_indices(
        analysis_points, settlements.geometry.to_numpy()
    )
    nearest = settlements.iloc[nearest_indices]
    counts["distance_to_nearest_settlement_m"] = distances
    counts["nearest_settlement_name"] = nearest["name"].to_numpy()
    counts["nearest_settlement_type"] = nearest["fclass"].to_numpy()
    return counts


def main() -> None:
    required = [
        GRID_PATH,
        ELEVATION_PATH,
        SLOPE_PATH,
        ASPECT_PATH,
        WORLDCOVER_PATH,
        ROADS_PATH,
        SETTLEMENTS_PATH,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing Phase 1/grid inputs: {missing}")

    grid = gpd.read_file(GRID_PATH).to_crs(epsg=TARGET_EPSG)
    raster_features = extract_raster_features(grid)
    road_features = extract_road_features(grid)
    settlement_features = extract_settlement_features(grid)

    identity = grid.drop(columns="geometry").reset_index(drop=True)
    features = pd.concat(
        [identity, raster_features, road_features, settlement_features], axis=1
    )
    ml_values = features[STATIC_ML_FEATURES].astype("float64")
    features["model_eligible"] = ml_values.notna().all(axis=1) & np.isfinite(
        ml_values.to_numpy()
    ).all(axis=1)
    required_order = [
        "cell_id",
        "centroid_x",
        "centroid_y",
        "centroid_lon",
        "centroid_lat",
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
        *LANDCOVER_FEATURES.values(),
        "road_length_m",
        "road_density_km_per_km2",
        "distance_to_nearest_road_m",
        "settlement_count",
        "village_count",
        "hamlet_count",
        "town_count",
        "city_count",
        "distance_to_nearest_settlement_m",
        "nearest_settlement_name",
        "nearest_settlement_type",
    ]
    features = features[required_order]
    if len(features) != len(grid) or features["cell_id"].duplicated().any():
        raise RuntimeError("Feature extraction violated the one-row-per-cell contract")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features.to_csv(CSV_OUTPUT, index=False)
    geospatial = grid[["cell_id", "geometry"]].merge(
        features, on="cell_id", how="left", validate="one_to_one"
    )
    if GPKG_OUTPUT.exists():
        GPKG_OUTPUT.unlink()
    geospatial.to_file(GPKG_OUTPUT, layer="sikkim_static_features_1km", driver="GPKG")
    print(f"Created: {CSV_OUTPUT}")
    print(f"Created: {GPKG_OUTPUT}")
    print(f"Feature rows: {len(features):,}")


if __name__ == "__main__":
    main()
