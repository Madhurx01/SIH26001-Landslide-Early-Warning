"""Create the reproducible 1 km square analysis grid for Sikkim.

The grid is an analysis unit, not a claim that its source datasets have 1 km
native resolution. SRTM (~30 m), WorldCover (10 m), and OSM vectors retain
their native information and are aggregated into these cells in Phase 2.
"""

import math
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import box


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_PATH = (
    PROJECT_ROOT
    / "DATA"
    / "PROCESSED"
    / "STATIC"
    / "BOUNDARY"
    / "sikkim_boundary_utm45n.gpkg"
)
OUTPUT_DIR = PROJECT_ROOT / "DATA" / "PROCESSED" / "GRID"
OUTPUT_PATH = OUTPUT_DIR / "sikkim_grid_1km.gpkg"

TARGET_CRS = "EPSG:32645"
CELL_SIZE_M = 1_000.0


def main() -> None:
    if not BOUNDARY_PATH.is_file():
        raise FileNotFoundError(f"Missing Phase 1 boundary: {BOUNDARY_PATH}")

    boundary = gpd.read_file(BOUNDARY_PATH).to_crs(TARGET_CRS)
    if boundary.empty or boundary.geometry.is_empty.any():
        raise RuntimeError("Sikkim boundary is empty")
    if not boundary.geometry.is_valid.all():
        raise RuntimeError("Sikkim boundary geometry is invalid")
    boundary_shape = boundary.geometry.union_all()

    min_x, min_y, max_x, max_y = boundary.total_bounds
    grid_min_x = math.floor(min_x / CELL_SIZE_M) * CELL_SIZE_M
    grid_min_y = math.floor(min_y / CELL_SIZE_M) * CELL_SIZE_M
    grid_max_x = math.ceil(max_x / CELL_SIZE_M) * CELL_SIZE_M
    grid_max_y = math.ceil(max_y / CELL_SIZE_M) * CELL_SIZE_M

    records: list[dict] = []
    # Stable ordering: top row to bottom row, and west to east within each row.
    for top in np.arange(grid_max_y, grid_min_y, -CELL_SIZE_M):
        bottom = top - CELL_SIZE_M
        for left in np.arange(grid_min_x, grid_max_x, CELL_SIZE_M):
            cell = box(left, bottom, left + CELL_SIZE_M, top)
            intersection = cell.intersection(boundary_shape)
            intersection_area = float(intersection.area)
            if intersection_area <= 0.0:
                continue
            fraction = float(
                np.clip(intersection_area / (CELL_SIZE_M**2), 0.0, 1.0)
            )
            square_centroid = cell.centroid
            if fraction >= 1.0 - 1e-9:
                analysis_point = square_centroid
            else:
                intersection_centroid = intersection.centroid
                analysis_point = (
                    intersection_centroid
                    if intersection.contains(intersection_centroid)
                    else intersection.representative_point()
                )
            records.append(
                {
                    "centroid_x": float(square_centroid.x),
                    "centroid_y": float(square_centroid.y),
                    "analysis_x": float(analysis_point.x),
                    "analysis_y": float(analysis_point.y),
                    "sikkim_fraction": fraction,
                    "geometry": cell,
                }
            )

    if not records:
        raise RuntimeError("Grid creation produced no cells")
    grid = gpd.GeoDataFrame(records, crs=TARGET_CRS)
    grid.insert(0, "cell_id", [f"SKM_{index:05d}" for index in range(1, len(grid) + 1)])

    centroids_wgs84 = gpd.GeoSeries(grid.geometry.centroid, crs=TARGET_CRS).to_crs(
        "EPSG:4326"
    )
    grid["centroid_lon"] = centroids_wgs84.x.to_numpy()
    grid["centroid_lat"] = centroids_wgs84.y.to_numpy()
    analysis_points_wgs84 = gpd.GeoSeries(
        gpd.points_from_xy(grid["analysis_x"], grid["analysis_y"]), crs=TARGET_CRS
    ).to_crs("EPSG:4326")
    grid["analysis_lon"] = analysis_points_wgs84.x.to_numpy()
    grid["analysis_lat"] = analysis_points_wgs84.y.to_numpy()
    grid = grid[
        [
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
            "geometry",
        ]
    ]

    if grid["cell_id"].duplicated().any():
        raise RuntimeError("Grid contains duplicate cell IDs")
    if not np.allclose(grid.geometry.area.to_numpy(), CELL_SIZE_M**2):
        raise RuntimeError("Grid contains non-square or clipped geometries")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()
    grid.to_file(OUTPUT_PATH, layer="sikkim_grid_1km", driver="GPKG")

    covered_area_km2 = float((grid["sikkim_fraction"] * CELL_SIZE_M**2).sum() / 1e6)
    full_cells = int((grid["sikkim_fraction"] >= 1.0 - 1e-9).sum())
    print(f"Created: {OUTPUT_PATH}")
    print(f"Grid cells: {len(grid):,}")
    print(f"Full cells: {full_cells:,}")
    print(f"Partial cells: {len(grid) - full_cells:,}")
    print(f"Grid-covered Sikkim area: {covered_area_km2:.6f} km²")


if __name__ == "__main__":
    main()
