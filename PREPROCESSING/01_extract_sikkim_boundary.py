"""Extract and validate the Sikkim state boundary from the OSM GeoPackage."""

from pathlib import Path

import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_GPKG = PROJECT_ROOT / "DATA" / "RAW" / "STATIC" / "OSM" / "north-eastern-zone.gpkg"
OUTPUT_DIR = PROJECT_ROOT / "DATA" / "PROCESSED" / "STATIC" / "BOUNDARY"
WGS84_OUTPUT = OUTPUT_DIR / "sikkim_boundary_wgs84.gpkg"
UTM_OUTPUT = OUTPUT_DIR / "sikkim_boundary_utm45n.gpkg"
ADMIN_LAYER = "gis_osm_adminareas_a_free"


def remove_existing_output(path: Path) -> None:
    """Remove only a known generated output so reruns are deterministic."""
    if path.exists():
        path.unlink()


def main() -> None:
    if not RAW_GPKG.is_file():
        raise FileNotFoundError(f"Missing OSM GeoPackage: {RAW_GPKG}")

    admin = gpd.read_file(RAW_GPKG, layer=ADMIN_LAYER)
    if admin.crs is None:
        raise RuntimeError(f"{ADMIN_LAYER} has no CRS")

    # A state-level OSM boundary is encoded by Geofabrik as fclass=admin_level4.
    exact_name = admin["name"].fillna("").str.strip().str.casefold() == "sikkim"
    state_level = admin["fclass"].fillna("").str.casefold() == "admin_level4"
    candidates = admin.loc[exact_name & state_level].copy()
    if len(candidates) != 1:
        nearby = admin.loc[admin["name"].fillna("").str.contains("sikkim", case=False)]
        details = nearby.drop(columns="geometry", errors="ignore").to_dict("records")
        raise RuntimeError(
            "Sikkim could not be identified unambiguously as a single admin_level4 "
            f"feature. Matching records: {details}"
        )

    boundary = candidates.to_crs("EPSG:4326")
    if boundary.geometry.is_empty.any() or boundary.geometry.isna().any():
        raise RuntimeError("The Sikkim boundary has an empty or missing geometry")
    if not boundary.geometry.is_valid.all():
        raise RuntimeError("The source Sikkim boundary geometry is invalid")

    bounds = boundary.total_bounds
    plausible_bounds = (
        87.8 <= bounds[0] <= 88.2
        and 26.9 <= bounds[1] <= 27.3
        and 88.7 <= bounds[2] <= 89.1
        and 27.9 <= bounds[3] <= 28.3
    )
    if not plausible_bounds:
        raise RuntimeError(f"Sikkim boundary has implausible bounds: {bounds.tolist()}")

    boundary["admin_level"] = 4
    keep = [
        column
        for column in ["osm_id", "code", "fclass", "name", "admin_level", "geometry"]
        if column in boundary.columns
    ]
    boundary = boundary[keep]

    # EPSG:32645 is the metric CRS covering Sikkim; areas and distances are in metres.
    boundary_utm = boundary.to_crs("EPSG:32645")
    area_km2 = float(boundary_utm.geometry.area.sum() / 1_000_000)
    if not 5_000 <= area_km2 <= 9_000:
        raise RuntimeError(f"Sikkim boundary has implausible projected area: {area_km2:.2f} km²")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    remove_existing_output(WGS84_OUTPUT)
    remove_existing_output(UTM_OUTPUT)
    boundary.to_file(WGS84_OUTPUT, layer="sikkim_boundary", driver="GPKG")
    boundary_utm.to_file(UTM_OUTPUT, layer="sikkim_boundary", driver="GPKG")

    print(f"Name: {boundary.iloc[0]['name']}")
    print(f"Admin level: {int(boundary.iloc[0]['admin_level'])}")
    print(f"Geometry valid: {bool(boundary.geometry.is_valid.all())}")
    print(f"EPSG:4326 bounds: {[round(value, 7) for value in bounds]}")
    print(f"Area in EPSG:32645: {area_km2:.2f} km²")
    print(f"Created: {WGS84_OUTPUT}")
    print(f"Created: {UTM_OUTPUT}")


if __name__ == "__main__":
    main()
