"""Refine broad OSM transport exposure to a government-operational road subset.

This script does not alter risk cells, settlement artifacts, broad transport
exposure outputs, DATA/RAW, or frontend code. It rebuilds road intersections
read-only from the same historical risk/grid/OSM sources, retains clearly
vehicular OSM classes, writes one record per exposed OSM way, and regenerates
the action/summary JSON using only vehicular roads plus existing settlements.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import geopandas as gpd
import pandas as pd
from shapely.geometry import GeometryCollection
from shapely.ops import unary_union


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = PROJECT_ROOT / "PREPROCESSING" / "11_build_exposure_layer.py"
OUTPUT_DIR = PROJECT_ROOT / "DATA" / "PROCESSED" / "EXPOSURE"
DEFAULT_DEMO_DATE = "2021-10-19"
ANALYSIS_CRS = "EPSG:32645"
OUTPUT_CRS = "EPSG:4326"

# These are OSM/GeoFabrik road classes that clearly describe vehicular roads.
# Link variants are retained because they are connectors within the same road
# hierarchy. Track classes are deliberately reported separately, not promoted
# into the primary road-risk dashboard.
VEHICULAR_CLASSES = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
}
CONDITIONAL_SERVICE_CLASS = "service"
TRACK_CLASSES = {
    "track",
    "track_grade1",
    "track_grade2",
    "track_grade3",
    "track_grade4",
    "track_grade5",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo-date",
        default=DEFAULT_DEMO_DATE,
        help=f"Historical replay date (default: {DEFAULT_DEMO_DATE})",
    )
    return parser.parse_args()


def load_base_module() -> ModuleType:
    if not BASE_SCRIPT.is_file():
        raise FileNotFoundError(f"Missing base exposure script: {BASE_SCRIPT}")
    spec = importlib.util.spec_from_file_location("exposure_layer_11", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load base exposure script: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def normalized_class(value: object) -> str:
    return (clean_text(value) or "").casefold()


def is_vehicular_row(row: pd.Series) -> bool:
    highway_class = normalized_class(row.get("fclass"))
    if highway_class in VEHICULAR_CLASSES:
        return True
    if highway_class == CONDITIONAL_SERVICE_CLASS:
        # The source exposes no service subtype. Retain a service way only when
        # a real OSM name or route reference provides evidence that it is a
        # meaningful, identifiable vehicular connection.
        return bool(clean_text(row.get("name")) or clean_text(row.get("ref")))
    return False


def line_union(geometries: pd.Series):
    geometry = unary_union([item for item in geometries if item is not None and not item.is_empty])
    if geometry.is_empty:
        return GeometryCollection()
    return geometry


def semicolon_values(values: pd.Series) -> str:
    items = sorted({str(value).strip() for value in values if clean_text(value)})
    return ";".join(items)


def one_text(values: pd.Series) -> str | None:
    items = sorted(
        {text for value in values for text in [clean_text(value)] if text},
        key=str.casefold,
    )
    return "; ".join(items) if items else None


def build_vehicular_segments(
    broad_pairs: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    pairs = broad_pairs.copy()
    pairs["fclass"] = pairs["fclass"].map(normalized_class)
    mask = pairs.apply(is_vehicular_row, axis=1)
    retained = pairs.loc[mask].copy()
    excluded = pairs.loc[~mask].copy()
    if retained.empty:
        raise RuntimeError("Vehicular-road classification retained no OSM ways")

    records: list[dict] = []
    for osm_id, group in retained.groupby("osm_id", sort=True):
        geometry = line_union(group.geometry)
        if geometry.is_empty or geometry.length <= 0.01:
            continue
        severe_geometry = line_union(
            group.loc[group["risk_level"].eq("SEVERE"), "geometry"]
        )
        high_geometry = line_union(group.loc[group["risk_level"].eq("HIGH"), "geometry"])
        # Assign any positive-length boundary overlap to SEVERE so HIGH and
        # SEVERE subtotals never double-count the same exposed road geometry.
        high_only_geometry = high_geometry.difference(severe_geometry)
        worst = group.sort_values(
            ["final_risk_score", "risk_level", "cell_id"],
            ascending=[False, False, True],
            kind="stable",
        ).iloc[0]
        records.append(
            {
                "osm_id": str(osm_id),
                "road_name": one_text(group["name"]),
                "ref": one_text(group["ref"]),
                "highway_type": one_text(group["fclass"]),
                "cell_id": str(worst["cell_id"]),
                "affected_cell_ids": semicolon_values(group["cell_id"]),
                "final_risk_score": float(worst["final_risk_score"]),
                "risk_level": str(worst["risk_level"]),
                "high_exposed_length_km": float(high_only_geometry.length / 1_000.0),
                "severe_exposed_length_km": float(severe_geometry.length / 1_000.0),
                "affected_length_km": float(geometry.length / 1_000.0),
                "exposure_interpretation": (
                    "POTENTIALLY EXPOSED TO ELEVATED LANDSLIDE RISK"
                ),
                "geometry": geometry,
            }
        )

    segments = gpd.GeoDataFrame(records, geometry="geometry", crs=ANALYSIS_CRS)
    segments = segments.sort_values(
        ["final_risk_score", "osm_id"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)
    if segments["osm_id"].duplicated().any():
        raise RuntimeError("Refined output contains duplicate OSM way IDs")
    if not segments["risk_level"].isin({"HIGH", "SEVERE"}).all():
        raise RuntimeError("Refined output contains a risk level below HIGH")
    if not segments.geometry.is_valid.all():
        raise RuntimeError("Refined output contains invalid geometry")
    component_sum = (
        segments["high_exposed_length_km"] + segments["severe_exposed_length_km"]
    )
    if not (component_sum.sub(segments["affected_length_km"]).abs() < 1e-8).all():
        raise RuntimeError("HIGH/SEVERE length components do not equal total length")
    return segments, excluded


def class_metrics(pairs: gpd.GeoDataFrame) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    for highway_class, class_group in pairs.groupby("fclass", sort=True):
        by_way = class_group.groupby("osm_id", sort=False).geometry.apply(line_union)
        result[str(highway_class)] = {
            "osm_segments": int(len(by_way)),
            "affected_length_km": round(
                float(sum(geometry.length for geometry in by_way) / 1_000.0), 3
            ),
        }
    return result


def named_road_metrics(segments: gpd.GeoDataFrame) -> tuple[int, list[dict]]:
    named = segments.loc[segments["road_name"].notna()].copy()
    named["normalized_name"] = named["road_name"].str.casefold().str.strip()
    records: list[dict] = []
    for _, group in named.groupby("normalized_name", sort=True):
        geometry = line_union(group.geometry)
        worst = group.sort_values(
            ["final_risk_score", "risk_level", "cell_id"],
            ascending=[False, False, True],
            kind="stable",
        ).iloc[0]
        records.append(
            {
                "road_name": one_text(group["road_name"]),
                "osm_segments": int(group["osm_id"].nunique()),
                "affected_length_km": round(float(geometry.length / 1_000.0), 3),
                "maximum_risk_level": str(worst["risk_level"]),
                "maximum_final_risk_score": round(
                    float(worst["final_risk_score"]), 6
                ),
                "affected_cell_ids": sorted(
                    {
                        cell_id
                        for value in group["affected_cell_ids"]
                        for cell_id in str(value).split(";")
                    }
                ),
            }
        )
    records.sort(
        key=lambda item: (
            0 if item["maximum_risk_level"] == "SEVERE" else 1,
            -item["maximum_final_risk_score"],
            -item["affected_length_km"],
            str(item["road_name"]).casefold(),
        )
    )
    return int(named["normalized_name"].nunique()), records[:10]


def load_existing_settlements(demo_date: str) -> gpd.GeoDataFrame:
    path = OUTPUT_DIR / f"settlement_exposure_{demo_date}.geojson"
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing existing settlement exposure; run the base exposure pipeline first: {path}"
        )
    settlements = gpd.read_file(path)
    required = {
        "osm_id",
        "settlement_name",
        "cell_id",
        "risk_level",
        "final_risk_score",
        "geometry",
    }
    missing = sorted(required - set(settlements.columns))
    if missing:
        raise RuntimeError(f"Existing settlement exposure lacks fields: {missing}")
    if settlements["osm_id"].duplicated().any():
        raise RuntimeError("Existing settlement exposure contains duplicate OSM IDs")
    return settlements.to_crs(ANALYSIS_CRS)


def write_refined_outputs(
    demo_date: str, segments: gpd.GeoDataFrame
) -> tuple[Path, Path]:
    csv_path = OUTPUT_DIR / f"vehicular_road_exposure_{demo_date}.csv"
    geojson_path = OUTPUT_DIR / f"vehicular_road_exposure_{demo_date}.geojson"
    wgs84 = segments.to_crs(OUTPUT_CRS)
    table = pd.DataFrame(wgs84.drop(columns="geometry"))
    table["geometry"] = wgs84.geometry.to_wkt(rounding_precision=7)
    table.to_csv(csv_path, index=False, encoding="utf-8")
    wgs84.to_file(geojson_path, driver="GeoJSON", index=False)
    return csv_path, geojson_path


def main() -> None:
    args = parse_args()
    base = load_base_module()
    risk_cells, risk_counts = base.load_risk_cells(args.demo_date)
    _, broad_pairs = base.build_road_exposure(risk_cells)
    broad_pairs["fclass"] = broad_pairs["fclass"].map(normalized_class)
    segments, excluded_pairs = build_vehicular_segments(broad_pairs)
    settlements = load_existing_settlements(args.demo_date)

    retained_osm_ids = set(segments["osm_id"].astype(str))
    vehicular_pairs = broad_pairs.loc[
        broad_pairs["osm_id"].astype(str).isin(retained_osm_ids)
    ].copy()
    action_document, priority_entries = base.build_action_priority(
        args.demo_date, risk_cells, vehicular_pairs, settlements
    )
    action_document["priority_rules"] = {
        "1": "SEVERE risk with exposed settlement and/or vehicular road",
        "2": "HIGH risk with exposed settlement and/or vehicular road",
        "3": "SEVERE risk without identified settlement/vehicular-road exposure",
    }
    for entry in action_document["entries"]:
        entry["has_vehicular_road_exposure"] = entry["has_road_exposure"]

    priority_counts = {
        priority: sum(entry["priority"] == priority for entry in priority_entries)
        for priority in (1, 2, 3)
    }
    named_priority_entries = [
        entry
        for entry in priority_entries
        if entry["road_names"] or entry["settlement_names"]
    ]
    unnamed_priority_entries = [
        entry
        for entry in priority_entries
        if not entry["road_names"] and not entry["settlement_names"]
    ]
    top_priorities = (named_priority_entries + unnamed_priority_entries)[:10]

    unique_named_roads, top_named_roads = named_road_metrics(segments)
    unnamed_ways = int(segments["road_name"].isna().sum())
    total_length = float(segments["affected_length_km"].sum())
    cells_with_roads = set(vehicular_pairs["cell_id"].astype(str))
    cells_by_risk = {
        level: int(
            risk_cells.loc[
                risk_cells["risk_level"].eq(level)
                & risk_cells["cell_id"].astype(str).isin(cells_with_roads),
                "cell_id",
            ].nunique()
        )
        for level in ("HIGH", "SEVERE")
    }
    road_risk_breakdown = {
        level: {
            "segments_by_maximum_risk": int(segments["risk_level"].eq(level).sum()),
            "affected_length_km": round(
                float(
                    segments[
                        "high_exposed_length_km"
                        if level == "HIGH"
                        else "severe_exposed_length_km"
                    ].sum()
                ),
                3,
            ),
        }
        for level in ("HIGH", "SEVERE")
    }

    actual_classes = set(broad_pairs["fclass"].dropna().astype(str))
    retained_classes = sorted(set(vehicular_pairs["fclass"].astype(str)))
    fully_excluded_classes = sorted(
        actual_classes - set(retained_classes) - {CONDITIONAL_SERVICE_CLASS}
    )
    classification = {
        "retained_highway_classes": retained_classes,
        "conditional_service_rule": (
            "service retained only when the OSM way has a real name or ref"
        ),
        "fully_excluded_highway_classes": fully_excluded_classes,
        "excluded_service_rule": "unnamed and unreferenced service ways excluded",
        "track_treatment": "excluded from main metrics; preserved in broad transport outputs",
        "retained_class_metrics": class_metrics(vehicular_pairs),
        "excluded_class_metrics": class_metrics(excluded_pairs),
    }

    summary = {
        "demo_date": args.demo_date,
        "high_risk_cells": int(risk_counts.get("HIGH", 0)),
        "severe_risk_cells": int(risk_counts.get("SEVERE", 0)),
        # Compatibility keys now intentionally represent the refined primary
        # road dashboard rather than the broad highway=* transport layer.
        "unique_exposed_roads": int(len(segments)),
        "total_exposed_road_length_km": round(total_length, 3),
        "exposed_vehicular_road_segments": int(len(segments)),
        "unique_named_roads": unique_named_roads,
        "unnamed_vehicular_osm_ways": unnamed_ways,
        "total_exposed_vehicular_road_length_km": round(total_length, 3),
        "vehicular_road_exposure_by_risk_level": road_risk_breakdown,
        "risk_cells_with_vehicular_road": {
            "total": int(len(cells_with_roads)),
            "HIGH": cells_by_risk["HIGH"],
            "SEVERE": cells_by_risk["SEVERE"],
        },
        "unique_exposed_settlements": int(len(settlements)),
        "priority_1_count": int(priority_counts[1]),
        "priority_2_count": int(priority_counts[2]),
        "priority_3_count": int(priority_counts[3]),
        "top_named_exposed_roads": top_named_roads,
        "top_10_priority_locations": top_priorities,
        "road_classification": classification,
        "interpretation": "POTENTIALLY EXPOSED TO ELEVATED LANDSLIDE RISK",
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path, geojson_path = write_refined_outputs(args.demo_date, segments)
    action_path = OUTPUT_DIR / f"action_priority_{args.demo_date}.json"
    summary_path = OUTPUT_DIR / f"exposure_summary_{args.demo_date}.json"
    action_path.write_text(
        json.dumps(action_document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    csv_check = pd.read_csv(csv_path, dtype={"osm_id": "string"})
    geojson_check = gpd.read_file(geojson_path)
    if len(csv_check) != len(segments) or len(geojson_check) != len(segments):
        raise RuntimeError("Refined CSV/GeoJSON feature counts do not match")
    if not csv_check["osm_id"].is_unique:
        raise RuntimeError("Refined CSV contains duplicate OSM way IDs")
    if geojson_check.crs is None or geojson_check.crs.to_epsg() != 4326:
        raise RuntimeError("Refined GeoJSON is not EPSG:4326")
    measured_km = float(geojson_check.to_crs(ANALYSIS_CRS).geometry.length.sum() / 1_000.0)
    if abs(measured_km - total_length) >= 1e-8:
        raise RuntimeError("Refined stored length does not match projected geometry")

    print(f"Demo date: {args.demo_date}")
    print(f"Retained actual classes: {', '.join(retained_classes)}")
    print(f"Fully excluded actual classes: {', '.join(fully_excluded_classes)}")
    print(classification["conditional_service_rule"])
    print(f"Exposed vehicular OSM segments: {len(segments):,}")
    print(f"Unique named roads: {unique_named_roads:,}")
    print(f"Unnamed vehicular OSM ways: {unnamed_ways:,}")
    print(f"Potentially exposed vehicular-road length: {total_length:.3f} km")
    print(f"Exposed settlements (unchanged): {len(settlements):,}")
    print(
        f"Priorities: P1={priority_counts[1]:,}, P2={priority_counts[2]:,}, "
        f"P3={priority_counts[3]:,}"
    )
    print(f"Created: {csv_path}")
    print(f"Created: {geojson_path}")
    print(f"Regenerated: {action_path}")
    print(f"Regenerated: {summary_path}")


if __name__ == "__main__":
    main()
