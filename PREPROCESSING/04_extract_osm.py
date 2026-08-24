"""Clip OSM roads and meaningful settlement points to the Sikkim boundary."""

from pathlib import Path

import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_GPKG = PROJECT_ROOT / "DATA" / "RAW" / "STATIC" / "OSM" / "north-eastern-zone.gpkg"
BOUNDARY_WGS84 = (
    PROJECT_ROOT
    / "DATA"
    / "PROCESSED"
    / "STATIC"
    / "BOUNDARY"
    / "sikkim_boundary_wgs84.gpkg"
)
OUTPUT_DIR = PROJECT_ROOT / "DATA" / "PROCESSED" / "STATIC" / "OSM"
ROADS_OUTPUT = OUTPUT_DIR / "sikkim_roads.gpkg"
SETTLEMENTS_OUTPUT = OUTPUT_DIR / "sikkim_settlements.gpkg"

ROADS_LAYER = "gis_osm_roads_free"
PLACES_LAYER = "gis_osm_places_free"
TARGET_CRS = "EPSG:32645"
SETTLEMENT_TYPES = {"city", "town", "village", "hamlet", "locality", "suburb"}


def remove_existing_output(path: Path) -> None:
    if path.exists():
        path.unlink()


def main() -> None:
    if not RAW_GPKG.is_file():
        raise FileNotFoundError(f"Missing OSM GeoPackage: {RAW_GPKG}")
    if not BOUNDARY_WGS84.is_file():
        raise FileNotFoundError("Run 01_extract_sikkim_boundary.py first")

    boundary = gpd.read_file(BOUNDARY_WGS84).to_crs("EPSG:4326")
    bbox = tuple(float(value) for value in boundary.total_bounds)

    # Bounding-box filtering avoids loading the entire North-East road network;
    # the subsequent geometric clip enforces the actual state boundary.
    roads = gpd.read_file(RAW_GPKG, layer=ROADS_LAYER, bbox=bbox).to_crs("EPSG:4326")
    roads = gpd.clip(roads, boundary, keep_geom_type=True)
    roads = roads.loc[~roads.geometry.is_empty & roads.geometry.notna()].copy()
    roads = roads.to_crs(TARGET_CRS)

    settlements = gpd.read_file(RAW_GPKG, layer=PLACES_LAYER, bbox=bbox).to_crs("EPSG:4326")
    settlements["fclass"] = settlements["fclass"].fillna("").str.casefold()
    settlements = settlements.loc[settlements["fclass"].isin(SETTLEMENT_TYPES)].copy()
    settlements = gpd.clip(settlements, boundary, keep_geom_type=True)
    settlements = settlements.loc[
        ~settlements.geometry.is_empty & settlements.geometry.notna()
    ].copy()
    settlements = settlements.to_crs(TARGET_CRS)

    if roads.empty:
        raise RuntimeError("No roads were extracted inside Sikkim")
    if settlements.empty:
        raise RuntimeError("No meaningful settlements were extracted inside Sikkim")
    if not roads.geometry.is_valid.all() or not settlements.geometry.is_valid.all():
        raise RuntimeError("Invalid geometry encountered in clipped OSM outputs")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    remove_existing_output(ROADS_OUTPUT)
    remove_existing_output(SETTLEMENTS_OUTPUT)
    roads.to_file(ROADS_OUTPUT, layer="sikkim_roads", driver="GPKG")
    settlements.to_file(
        SETTLEMENTS_OUTPUT, layer="sikkim_settlements", driver="GPKG"
    )

    print(f"Created: {ROADS_OUTPUT} ({len(roads):,} features)")
    print(f"Created: {SETTLEMENTS_OUTPUT} ({len(settlements):,} features)")
    print("Settlement counts by type:")
    print(settlements["fclass"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
