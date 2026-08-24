"""Build real OSM road and settlement exposure for a historical risk replay.

The outputs describe potential exposure to elevated landslide risk. They do
not assert that a road is blocked, that damage occurred, or that a landslide
will occur.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.geometry import GeometryCollection
from shapely.ops import unary_union


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RISK_PATH = (
    PROJECT_ROOT / "DATA" / "PROCESSED" / "RISK" / "sikkim_landslide_risk_2021.csv"
)
GRID_PATH = (
    PROJECT_ROOT / "DATA" / "PROCESSED" / "GRID" / "sikkim_grid_1km.gpkg"
)
OSM_PATH = (
    PROJECT_ROOT
    / "DATA"
    / "RAW"
    / "STATIC"
    / "OSM"
    / "north-eastern-zone.gpkg"
)
OUTPUT_DIR = PROJECT_ROOT / "DATA" / "PROCESSED" / "EXPOSURE"

GRID_LAYER = "sikkim_grid_1km"
ROAD_LAYER = "gis_osm_roads_free"
SETTLEMENT_LAYER = "gis_osm_places_free"
ANALYSIS_CRS = "EPSG:32645"
OUTPUT_CRS = "EPSG:4326"
DEFAULT_DEMO_DATE = "2021-10-19"
ELEVATED_LEVELS = {"HIGH", "SEVERE"}
SETTLEMENT_TYPES = {"city", "town", "village", "hamlet", "locality", "suburb"}
EXPOSURE_INTERPRETATION = "POTENTIALLY EXPOSED TO ELEVATED LANDSLIDE RISK"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo-date",
        default=DEFAULT_DEMO_DATE,
        help=f"Historical replay date in YYYY-MM-DD format (default: {DEFAULT_DEMO_DATE})",
    )
    return parser.parse_args()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required input: {path}")


def clean_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def unique_text(values: pd.Series) -> list[str]:
    cleaned = {text for value in values for text in [clean_text(value)] if text}
    return sorted(cleaned, key=str.casefold)


def joined_text(values: pd.Series) -> str | None:
    items = unique_text(values)
    return "; ".join(items) if items else None


def semicolon_ids(values: pd.Series) -> str:
    items = sorted({str(value).strip() for value in values if clean_text(value)})
    return ";".join(items)


def discover_required_layers() -> None:
    """Confirm layer names from the actual GeoPackage rather than assuming them."""
    layers = {str(name): str(geometry_type) for name, geometry_type in pyogrio.list_layers(OSM_PATH)}
    required = {
        ROAD_LAYER: "LineString",
        SETTLEMENT_LAYER: "Point",
    }
    missing = sorted(set(required) - set(layers))
    if missing:
        raise RuntimeError(
            f"Required OSM layer(s) not found: {missing}. Available layers: {sorted(layers)}"
        )
    for layer, expected_geometry in required.items():
        if expected_geometry.casefold() not in layers[layer].casefold():
            raise RuntimeError(
                f"OSM layer {layer!r} has geometry {layers[layer]!r}, "
                f"expected {expected_geometry}"
            )


def load_risk_cells(demo_date: str) -> tuple[gpd.GeoDataFrame, dict[str, int]]:
    try:
        normalized_date = pd.Timestamp(demo_date).strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid --demo-date value: {demo_date!r}") from exc
    if normalized_date != demo_date:
        raise ValueError("--demo-date must use exact YYYY-MM-DD format")

    risk = pd.read_csv(RISK_PATH, dtype={"cell_id": "string", "date": "string"})
    if "static_susceptibility_score" not in risk.columns:
        if "static_susceptibility" not in risk.columns:
            raise RuntimeError("Risk table lacks a static susceptibility score column")
        risk = risk.rename(
            columns={"static_susceptibility": "static_susceptibility_score"}
        )

    required_columns = {
        "cell_id",
        "date",
        "static_susceptibility_score",
        "dynamic_trigger_score",
        "final_risk_score",
        "risk_level",
    }
    missing = sorted(required_columns - set(risk.columns))
    if missing:
        raise RuntimeError(f"Risk table is missing columns: {missing}")

    demo = risk.loc[risk["date"] == demo_date, list(required_columns)].copy()
    if demo.empty:
        raise RuntimeError(f"No risk records found for {demo_date}")
    if demo["cell_id"].isna().any() or demo["cell_id"].duplicated().any():
        raise RuntimeError("Demo-date risk table contains blank or duplicate cell_id values")
    if not demo["date"].eq(demo_date).all():
        raise RuntimeError("Risk filtering admitted a date other than the requested demo date")
    demo["risk_level"] = demo["risk_level"].astype("string").str.strip().str.upper()

    grid = gpd.read_file(GRID_PATH, layer=GRID_LAYER)
    if grid.crs is None:
        raise RuntimeError("Grid has no CRS")
    grid = grid.to_crs(ANALYSIS_CRS)
    if grid["cell_id"].isna().any() or grid["cell_id"].duplicated().any():
        raise RuntimeError("Grid contains blank or duplicate cell_id values")

    grid_ids = set(grid["cell_id"].astype(str))
    missing_grid_ids = sorted(set(demo["cell_id"].astype(str)) - grid_ids)
    if missing_grid_ids:
        raise RuntimeError(
            f"{len(missing_grid_ids)} demo-date risk cells do not exist in the grid"
        )

    joined = grid[["cell_id", "geometry"]].merge(
        demo.drop(columns="date"), on="cell_id", how="inner", validate="one_to_one"
    )
    if len(joined) != len(demo):
        raise RuntimeError("Risk-to-grid join lost demo-date records")
    if joined.geometry.isna().any() or joined.geometry.is_empty.any():
        raise RuntimeError("Joined risk cells contain empty geometry")
    if not joined.geometry.is_valid.all():
        raise RuntimeError("Joined risk cells contain invalid geometry")

    counts = joined["risk_level"].value_counts().to_dict()
    elevated = joined.loc[joined["risk_level"].isin(ELEVATED_LEVELS)].copy()
    if elevated.empty:
        raise RuntimeError("No HIGH or SEVERE risk cells found for exposure analysis")
    elevated = elevated[
        [
            "cell_id",
            "static_susceptibility_score",
            "dynamic_trigger_score",
            "final_risk_score",
            "risk_level",
            "geometry",
        ]
    ].sort_values("cell_id", kind="stable")
    return elevated, {str(level): int(count) for level, count in counts.items()}


def read_osm_extent(layer: str, risk_cells: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    bbox = tuple(float(value) for value in risk_cells.to_crs(OUTPUT_CRS).total_bounds)
    features = gpd.read_file(OSM_PATH, layer=layer, bbox=bbox)
    if features.crs is None:
        raise RuntimeError(f"OSM layer {layer!r} has no CRS")
    features = features.loc[features.geometry.notna() & ~features.geometry.is_empty].copy()
    if not features.geometry.is_valid.all():
        features.geometry = features.geometry.make_valid()
    return features.to_crs(ANALYSIS_CRS)


def line_only(geometry):
    if geometry is None or geometry.is_empty:
        return GeometryCollection()
    if geometry.geom_type in {"LineString", "MultiLineString"}:
        return geometry
    if geometry.geom_type == "GeometryCollection":
        lines = [
            part
            for part in geometry.geoms
            if part.geom_type in {"LineString", "MultiLineString"}
            and not part.is_empty
        ]
        return unary_union(lines) if lines else GeometryCollection()
    return GeometryCollection()


def road_identity(row: pd.Series) -> str:
    name = clean_text(row.get("name"))
    ref = clean_text(row.get("ref"))
    osm_id = clean_text(row.get("osm_id"))
    if name:
        return f"name:{name.casefold()}"
    if ref:
        return f"ref:{ref.casefold()}"
    return f"osm:{osm_id}"


def build_road_exposure(
    risk_cells: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    roads = read_osm_extent(ROAD_LAYER, risk_cells)
    required = {"osm_id", "fclass", "name", "ref", "geometry"}
    missing = sorted(required - set(roads.columns))
    if missing:
        raise RuntimeError(f"OSM road layer is missing fields: {missing}")
    roads = roads[list(required)].copy()
    roads["road_key"] = roads.apply(road_identity, axis=1)

    risk_for_join = risk_cells[
        ["cell_id", "final_risk_score", "risk_level", "geometry"]
    ].reset_index(drop=True)
    pairs = gpd.sjoin(roads, risk_for_join, how="inner", predicate="intersects")
    if pairs.empty:
        raise RuntimeError("No OSM road geometries intersect HIGH/SEVERE risk cells")

    cell_geometries = risk_for_join.geometry
    pairs["geometry"] = [
        line_only(road_geometry.intersection(cell_geometries.iloc[int(cell_index)]))
        for road_geometry, cell_index in zip(pairs.geometry, pairs["index_right"])
    ]
    # Point-only contact at a grid boundary is not exposed road length.
    pairs = pairs.loc[pairs.geometry.length > 0.01].copy()
    if pairs.empty:
        raise RuntimeError("Road intersections contain no positive-length segments")

    records: list[dict] = []
    for road_key, group in pairs.groupby("road_key", sort=True):
        geometry = unary_union(group.geometry.tolist())
        if geometry.is_empty or geometry.length <= 0.01:
            continue
        worst = group.sort_values(
            ["final_risk_score", "risk_level", "cell_id"],
            ascending=[False, False, True],
            kind="stable",
        ).iloc[0]
        records.append(
            {
                "road_key": road_key,
                "osm_ids": semicolon_ids(group["osm_id"]),
                "road_name": joined_text(group["name"]),
                "ref": joined_text(group["ref"]),
                "highway_type": joined_text(group["fclass"]),
                "cell_id": str(worst["cell_id"]),
                "affected_cell_ids": ";".join(sorted(set(group["cell_id"].astype(str)))),
                "final_risk_score": float(worst["final_risk_score"]),
                "risk_level": str(worst["risk_level"]),
                "affected_length_km": float(geometry.length / 1_000.0),
                "exposure_interpretation": EXPOSURE_INTERPRETATION,
                "geometry": geometry,
            }
        )

    exposed = gpd.GeoDataFrame(records, geometry="geometry", crs=ANALYSIS_CRS)
    exposed = exposed.sort_values(
        ["final_risk_score", "road_key"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)
    if exposed["road_key"].duplicated().any():
        raise RuntimeError("Road aggregation produced duplicate road keys")
    if not exposed["risk_level"].isin(ELEVATED_LEVELS).all():
        raise RuntimeError("Road output contains a risk level below HIGH")
    return exposed, pairs


def build_settlement_exposure(risk_cells: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    settlements = read_osm_extent(SETTLEMENT_LAYER, risk_cells)
    required = {"osm_id", "fclass", "name", "geometry"}
    missing = sorted(required - set(settlements.columns))
    if missing:
        raise RuntimeError(f"OSM settlement layer is missing fields: {missing}")
    settlements = settlements[list(required)].copy()
    settlements["name"] = settlements["name"].map(clean_text)
    settlements["fclass"] = settlements["fclass"].map(clean_text)
    settlements = settlements.loc[
        settlements["name"].notna()
        & settlements["fclass"].fillna("").str.casefold().isin(SETTLEMENT_TYPES)
        & settlements.geometry.geom_type.eq("Point")
    ].copy()

    risk_for_join = risk_cells[
        ["cell_id", "final_risk_score", "risk_level", "geometry"]
    ]
    matches = gpd.sjoin(
        settlements, risk_for_join, how="inner", predicate="intersects"
    )
    if matches.empty:
        raise RuntimeError(
            "No named settlement points directly intersect HIGH/SEVERE cells; "
            "review whether a documented proximity rule is needed"
        )

    # A point on a cell boundary can match multiple cells. Retain one real
    # settlement record and associate it with the maximum risk score.
    matches = matches.sort_values(
        ["osm_id", "final_risk_score", "risk_level", "cell_id"],
        ascending=[True, False, False, True],
        kind="stable",
    )
    matches = matches.drop_duplicates(subset="osm_id", keep="first").copy()
    matches = matches.rename(
        columns={"name": "settlement_name", "fclass": "place_type"}
    )
    matches["longitude"] = matches.to_crs(OUTPUT_CRS).geometry.x.to_numpy()
    matches["latitude"] = matches.to_crs(OUTPUT_CRS).geometry.y.to_numpy()
    matches["association_method"] = "direct_intersection"
    matches["distance_to_risk_m"] = 0.0
    matches["exposure_interpretation"] = EXPOSURE_INTERPRETATION
    exposed = matches[
        [
            "osm_id",
            "settlement_name",
            "place_type",
            "longitude",
            "latitude",
            "cell_id",
            "final_risk_score",
            "risk_level",
            "association_method",
            "distance_to_risk_m",
            "exposure_interpretation",
            "geometry",
        ]
    ].sort_values(
        ["final_risk_score", "settlement_name"],
        ascending=[False, True],
        kind="stable",
    )
    exposed = exposed.reset_index(drop=True)
    if exposed["osm_id"].duplicated().any():
        raise RuntimeError("Settlement output contains duplicate OSM IDs")
    if exposed["settlement_name"].isna().any():
        raise RuntimeError("Settlement output contains a fabricated/blank name")
    if not exposed["risk_level"].isin(ELEVATED_LEVELS).all():
        raise RuntimeError("Settlement output contains a risk level below HIGH")
    return exposed


def cell_name_map(frame: pd.DataFrame, name_column: str) -> dict[str, list[str]]:
    result: dict[str, set[str]] = {}
    for row in frame.itertuples(index=False):
        name = clean_text(getattr(row, name_column))
        if not name:
            continue
        for cell_id in str(getattr(row, "cell_id")).split(";"):
            result.setdefault(cell_id, set()).add(name)
    return {
        cell_id: sorted(names, key=str.casefold)
        for cell_id, names in result.items()
    }


def build_action_priority(
    demo_date: str,
    risk_cells: gpd.GeoDataFrame,
    road_pairs: pd.DataFrame,
    settlements: gpd.GeoDataFrame,
) -> tuple[dict, list[dict]]:
    road_cells = set(road_pairs["cell_id"].astype(str))
    settlement_cells = set(settlements["cell_id"].astype(str))

    road_names: dict[str, set[str]] = {}
    for row in road_pairs.itertuples(index=False):
        name = clean_text(row.name)
        if name:
            road_names.setdefault(str(row.cell_id), set()).add(name)
    settlement_names: dict[str, set[str]] = {}
    for row in settlements.itertuples(index=False):
        settlement_names.setdefault(str(row.cell_id), set()).add(
            str(row.settlement_name)
        )

    entries: list[dict] = []
    for row in risk_cells.itertuples(index=False):
        cell_id = str(row.cell_id)
        has_road = cell_id in road_cells
        has_settlement = cell_id in settlement_cells
        has_exposure = has_road or has_settlement
        if row.risk_level == "SEVERE" and has_exposure:
            priority = 1
            action = (
                "Field verification recommended; verify road condition where applicable; "
                "notify local authorities for readiness; monitor rainfall and slope conditions."
            )
        elif row.risk_level == "HIGH" and has_exposure:
            priority = 2
            action = (
                "Verify road condition where applicable; notify local authorities for "
                "readiness; monitor rainfall and slope conditions."
            )
        elif row.risk_level == "SEVERE":
            priority = 3
            action = (
                "Field verification recommended; notify local authorities for readiness; "
                "monitor rainfall and slope conditions."
            )
        else:
            continue
        entries.append(
            {
                "priority": priority,
                "cell_id": cell_id,
                "risk_level": str(row.risk_level),
                "final_risk_score": round(float(row.final_risk_score), 6),
                "has_road_exposure": has_road,
                "has_settlement_exposure": has_settlement,
                "road_names": sorted(road_names.get(cell_id, set()), key=str.casefold),
                "settlement_names": sorted(
                    settlement_names.get(cell_id, set()), key=str.casefold
                ),
                "recommended_action": action,
            }
        )

    entries.sort(key=lambda item: (item["priority"], -item["final_risk_score"], item["cell_id"]))
    counts = {
        str(priority): sum(entry["priority"] == priority for entry in entries)
        for priority in (1, 2, 3)
    }
    document = {
        "demo_date": demo_date,
        "interpretation": EXPOSURE_INTERPRETATION,
        "priority_rules": {
            "1": "SEVERE risk with real exposed road and/or settlement",
            "2": "HIGH risk with real exposed road and/or settlement",
            "3": "SEVERE risk without identified road/settlement exposure",
        },
        "priority_counts": counts,
        "entries": entries,
    }
    return document, entries


def write_geospatial_outputs(
    demo_date: str,
    roads: gpd.GeoDataFrame,
    settlements: gpd.GeoDataFrame,
) -> list[Path]:
    road_csv = OUTPUT_DIR / f"road_exposure_{demo_date}.csv"
    road_geojson = OUTPUT_DIR / f"road_exposure_{demo_date}.geojson"
    settlement_csv = OUTPUT_DIR / f"settlement_exposure_{demo_date}.csv"
    settlement_geojson = OUTPUT_DIR / f"settlement_exposure_{demo_date}.geojson"

    roads_wgs84 = roads.to_crs(OUTPUT_CRS)
    road_table = pd.DataFrame(roads_wgs84.drop(columns="geometry"))
    road_table["geometry"] = roads_wgs84.geometry.to_wkt(rounding_precision=7)
    road_table.to_csv(road_csv, index=False, encoding="utf-8")
    roads_wgs84.to_file(road_geojson, driver="GeoJSON", index=False)

    settlements_wgs84 = settlements.to_crs(OUTPUT_CRS)
    settlement_table = pd.DataFrame(settlements_wgs84.drop(columns="geometry"))
    settlement_table["geometry"] = settlements_wgs84.geometry.to_wkt(
        rounding_precision=7
    )
    settlement_table.to_csv(settlement_csv, index=False, encoding="utf-8")
    settlements_wgs84.to_file(settlement_geojson, driver="GeoJSON", index=False)
    return [road_csv, road_geojson, settlement_csv, settlement_geojson]


def validate_written_outputs(
    paths: list[Path], roads: gpd.GeoDataFrame, settlements: gpd.GeoDataFrame
) -> None:
    for path in paths:
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Output was not created correctly: {path}")
    road_csv, road_geojson, settlement_csv, settlement_geojson = paths
    if len(pd.read_csv(road_csv)) != len(roads):
        raise RuntimeError("Road CSV row count does not match in-memory exposure")
    if len(pd.read_csv(settlement_csv)) != len(settlements):
        raise RuntimeError("Settlement CSV row count does not match in-memory exposure")
    road_check = gpd.read_file(road_geojson)
    settlement_check = gpd.read_file(settlement_geojson)
    if len(road_check) != len(roads) or len(settlement_check) != len(settlements):
        raise RuntimeError("GeoJSON feature count does not match in-memory exposure")
    if road_check.crs is None or settlement_check.crs is None:
        raise RuntimeError("GeoJSON output has no CRS")
    if not road_check.geometry.is_valid.all() or not settlement_check.geometry.is_valid.all():
        raise RuntimeError("GeoJSON output contains invalid geometry")


def main() -> None:
    args = parse_args()
    for path in (RISK_PATH, GRID_PATH, OSM_PATH):
        require_file(path)
    discover_required_layers()

    risk_cells, risk_counts = load_risk_cells(args.demo_date)
    roads, road_pairs = build_road_exposure(risk_cells)
    settlements = build_settlement_exposure(risk_cells)
    action_document, priority_entries = build_action_priority(
        args.demo_date, risk_cells, road_pairs, settlements
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    geospatial_paths = write_geospatial_outputs(args.demo_date, roads, settlements)
    action_path = OUTPUT_DIR / f"action_priority_{args.demo_date}.json"
    action_path.write_text(
        json.dumps(action_document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    priority_counts = {
        priority: sum(entry["priority"] == priority for entry in priority_entries)
        for priority in (1, 2, 3)
    }
    # Prefer operationally identifiable entries in the compact frontend
    # summary. The full action JSON still retains every priority cell,
    # including cells whose exposure is supported only by unnamed OSM ways.
    named_entries = [
        entry
        for entry in priority_entries
        if entry["road_names"] or entry["settlement_names"]
    ]
    unnamed_entries = [
        entry
        for entry in priority_entries
        if not entry["road_names"] and not entry["settlement_names"]
    ]
    top_10 = (named_entries + unnamed_entries)[:10]
    total_length_km = float(roads["affected_length_km"].sum())
    summary = {
        "demo_date": args.demo_date,
        "high_risk_cells": int(risk_counts.get("HIGH", 0)),
        "severe_risk_cells": int(risk_counts.get("SEVERE", 0)),
        "unique_exposed_roads": int(len(roads)),
        "total_exposed_road_length_km": round(total_length_km, 3),
        "unique_exposed_settlements": int(len(settlements)),
        "priority_1_count": int(priority_counts[1]),
        "priority_2_count": int(priority_counts[2]),
        "priority_3_count": int(priority_counts[3]),
        "top_10_priority_locations": top_10,
    }
    summary_path = OUTPUT_DIR / f"exposure_summary_{args.demo_date}.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    validate_written_outputs(geospatial_paths, roads, settlements)
    if not action_path.is_file() or not summary_path.is_file():
        raise RuntimeError("JSON outputs were not created")
    if not math.isclose(
        total_length_km,
        float(roads.to_crs(ANALYSIS_CRS).geometry.length.sum() / 1_000.0),
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise RuntimeError("Stored road lengths do not match EPSG:32645 geometries")

    print(f"Demo date: {args.demo_date}")
    print(f"OSM layers used: {ROAD_LAYER}, {SETTLEMENT_LAYER}")
    print(
        f"Risk cells analyzed: HIGH={risk_counts.get('HIGH', 0):,}, "
        f"SEVERE={risk_counts.get('SEVERE', 0):,}"
    )
    print(f"Unique exposed road records: {len(roads):,}")
    print(f"Total exposed road length: {total_length_km:.3f} km")
    print(f"Unique named exposed settlements: {len(settlements):,}")
    print(
        "Priorities: "
        f"P1={priority_counts[1]:,}, P2={priority_counts[2]:,}, "
        f"P3={priority_counts[3]:,}"
    )
    print("Settlement rule: named OSM place point directly intersects a HIGH/SEVERE cell")
    print("Created:")
    for path in [*geospatial_paths, action_path, summary_path]:
        print(f"  {path}")


if __name__ == "__main__":
    main()
