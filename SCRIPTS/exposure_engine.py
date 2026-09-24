"""GIS exposure and emergency-priority derivation for operational risk output.

This module consumes the authoritative processed OSM road and settlement
GeoPackages, the canonical 1 km grid, and a complete 7,390-cell operational
risk layer. It never creates substitute geometries, road names, settlement
names, population estimates, blockage states, or evacuation orders.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely import union_all
from shapely.geometry import GeometryCollection, LineString, MultiLineString, Point


EXPECTED_CELL_COUNT = 7_390
TARGET_CRS = "EPSG:32645"
EXPOSURE_VERSION = "gis-exposure-v1"
DASHBOARD_UNNAMED_ROAD_LIMIT = 200
HORIZONS = {
    "current": ("risk_level", "operational_risk_index"),
    "24h": ("risk_level_24h", "operational_risk_index_24h"),
    "48h": ("risk_level_48h", "operational_risk_index_48h"),
    "72h": ("risk_level_72h", "operational_risk_index_72h"),
}
EXPOSED_LEVELS = {"HIGH", "SEVERE"}
COORDINATE_PATTERN = re.compile(
    r"(?P<lat>\d+(?:\.\d+)?)\s*°?\s*(?P<lat_dir>[NS])\s*[,; ]+\s*"
    r"(?P<lon>\d+(?:\.\d+)?)\s*°?\s*(?P<lon_dir>[EW])",
    re.IGNORECASE,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_ids() -> list[str]:
    return [f"SKM_{index:05d}" for index in range(1, EXPECTED_CELL_COUNT + 1)]


def _require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise RuntimeError(f"{label} is missing required columns: {missing}")


def _clean_tag(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def _road_identity(row: pd.Series) -> tuple[str, str]:
    name = _clean_tag(row.get("name"))
    reference = _clean_tag(row.get("ref"))
    osm_id = _clean_tag(row.get("osm_id"))
    if reference and name:
        return f"ref-name:{reference.casefold()}|{name.casefold()}", f"{reference} · {name}"
    if reference:
        return f"ref:{reference.casefold()}", reference
    if name:
        return f"name:{name.casefold()}", name
    return f"osm:{osm_id}:{row.name}", "Unnamed OSM road"


def _line_parts(geometry: Any) -> list[LineString]:
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, MultiLineString):
        return list(geometry.geoms)
    if isinstance(geometry, GeometryCollection):
        parts: list[LineString] = []
        for item in geometry.geoms:
            parts.extend(_line_parts(item))
        return parts
    return []


def _map_coordinates(geometry: Any) -> list[Any]:
    parts = _line_parts(geometry)
    if not parts:
        return []
    converted = gpd.GeoSeries(parts, crs=TARGET_CRS).to_crs("EPSG:4326")
    lines = [
        [[round(float(latitude), 6), round(float(longitude), 6)] for longitude, latitude in line.coords]
        for line in converted
        if len(line.coords) >= 2
    ]
    return lines[0] if len(lines) == 1 else lines


def _risk_cell_layer(grid: gpd.GeoDataFrame, risk: pd.DataFrame) -> gpd.GeoDataFrame:
    required = {"cell_id"}
    for level_column, index_column in HORIZONS.values():
        required.update({level_column, index_column})
    _require_columns(risk, required, "operational risk layer")
    if len(risk) != EXPECTED_CELL_COUNT:
        raise RuntimeError(f"Operational risk layer must contain {EXPECTED_CELL_COUNT:,} cells")
    identifiers = risk["cell_id"].astype(str)
    if identifiers.duplicated().any() or identifiers.tolist() != _expected_ids():
        raise RuntimeError("Operational risk layer is not in unique canonical cell_id order")
    for level_column, index_column in HORIZONS.values():
        if risk[level_column].isna().any() or not set(risk[level_column].astype(str)).issubset({"LOW", "MODERATE", "HIGH", "SEVERE"}):
            raise RuntimeError(f"Invalid or missing values in {level_column}")
        if risk[index_column].isna().any() or not risk[index_column].between(0, 100).all():
            raise RuntimeError(f"Invalid or missing values in {index_column}")
    if len(grid) != EXPECTED_CELL_COUNT or grid["cell_id"].astype(str).tolist() != _expected_ids():
        raise RuntimeError("Canonical grid is missing, duplicated, reordered, or incomplete")
    attributes = ["cell_id"] + [column for pair in HORIZONS.values() for column in pair]
    joined = grid[["cell_id", "geometry"]].merge(risk[attributes], on="cell_id", how="left", validate="one_to_one")
    return gpd.GeoDataFrame(joined, geometry="geometry", crs=grid.crs)


def _road_cell_intersections(
    roads: gpd.GeoDataFrame,
    cells: gpd.GeoDataFrame,
    level_column: str,
    index_column: str,
) -> pd.DataFrame:
    exposed_cells = cells.loc[cells[level_column].isin(EXPOSED_LEVELS), ["cell_id", level_column, index_column, "geometry"]]
    if exposed_cells.empty:
        return pd.DataFrame(columns=["road_row", "feature_id", "entity_key", "cell_id", "risk_level", "risk_index", "intersection_length_m"])
    pairs = gpd.sjoin(
        roads[["feature_id", "entity_key", "geometry"]],
        exposed_cells,
        how="inner",
        predicate="intersects",
    ).reset_index(names="road_row")
    if pairs.empty:
        return pd.DataFrame(columns=["road_row", "feature_id", "entity_key", "cell_id", "risk_level", "risk_index", "intersection_length_m"])
    cell_geometry = exposed_cells.geometry.loc[pairs["index_right"]].to_list()
    road_geometry = roads.geometry.loc[pairs["road_row"]].to_list()
    pairs["intersection_length_m"] = [float(road.intersection(cell).length) for road, cell in zip(road_geometry, cell_geometry)]
    pairs = pairs.loc[pairs["intersection_length_m"] > 0.01].copy()
    return pairs.rename(columns={level_column: "risk_level", index_column: "risk_index"})[
        ["road_row", "feature_id", "entity_key", "cell_id", "risk_level", "risk_index", "intersection_length_m"]
    ]


def _aggregate_pair_values(pairs: pd.DataFrame) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for entity_key, group in pairs.groupby("entity_key", sort=False):
        high_cells = sorted(group.loc[group["risk_level"] == "HIGH", "cell_id"].unique().tolist())
        severe_cells = sorted(group.loc[group["risk_level"] == "SEVERE", "cell_id"].unique().tolist())
        result[str(entity_key)] = {
            "high_cell_count": len(high_cells),
            "severe_cell_count": len(severe_cells),
            "exposed_cell_count": len(set(high_cells + severe_cells)),
            "exposed_length_km": round(float(group["intersection_length_m"].sum()) / 1000.0, 3),
            "max_operational_risk_index": round(float(group["risk_index"].max()), 1),
            "exposed_cell_ids": sorted(set(high_cells + severe_cells)),
        }
    return result


def _empty_exposure() -> dict[str, Any]:
    return {
        "high_cell_count": 0,
        "severe_cell_count": 0,
        "exposed_cell_count": 0,
        "exposed_length_km": 0.0,
        "max_operational_risk_index": None,
        "exposed_cell_ids": [],
    }


def _status(current: dict[str, Any], forecasts: list[dict[str, Any]]) -> tuple[str, str]:
    if current["severe_cell_count"] > 0:
        return "CRITICAL", "SEVERE"
    if current["high_cell_count"] > 0:
        return "HIGH RISK", "HIGH"
    if any(item["exposed_cell_count"] > 0 for item in forecasts):
        return "WATCH", "MODERATE"
    return "NORMAL", "LOW"


def _assign_points_to_cells(points: gpd.GeoDataFrame, cells: gpd.GeoDataFrame) -> list[str]:
    spatial_index = cells.sindex
    assigned: list[str] = []
    for point in points.geometry:
        candidates = list(spatial_index.query(point, predicate="intersects"))
        if candidates:
            selected = min(candidates, key=lambda index: str(cells.iloc[index]["cell_id"]))
        else:
            selected = int(spatial_index.nearest(point, return_all=False)[1][0])
        assigned.append(str(cells.iloc[selected]["cell_id"]))
    return assigned


def _parse_verified_reports(report_path: Path, cells: gpd.GeoDataFrame) -> tuple[list[dict[str, Any]], int]:
    if not report_path.is_file():
        return [], 0
    try:
        raw_reports = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read citizen-report data: {report_path}") from error
    if not isinstance(raw_reports, list):
        raise RuntimeError("Citizen-report data must be a JSON array")
    verified = [item for item in raw_reports if isinstance(item, dict) and str(item.get("status", "")).upper() == "VERIFIED"]
    mapped: list[dict[str, Any]] = []
    for report in verified:
        match = COORDINATE_PATTERN.search(str(report.get("coords", "")))
        if not match:
            continue
        latitude = float(match.group("lat")) * (-1 if match.group("lat_dir").upper() == "S" else 1)
        longitude = float(match.group("lon")) * (-1 if match.group("lon_dir").upper() == "W" else 1)
        point = gpd.GeoDataFrame([{"geometry": Point(longitude, latitude)}], crs="EPSG:4326").to_crs(TARGET_CRS)
        mapped.append({
            "report_id": str(report.get("id", "verified-report")),
            "cell_id": _assign_points_to_cells(point, cells)[0],
            "latitude": latitude,
            "longitude": longitude,
        })
    return mapped, len(verified)


def _priority_records(
    cells: gpd.GeoDataFrame,
    current_pairs: pd.DataFrame,
    settlements: pd.DataFrame,
    verified_reports: list[dict[str, Any]],
    road_names: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    road_cells: dict[str, set[str]] = defaultdict(set)
    for pair in current_pairs.itertuples(index=False):
        road_cells[str(pair.cell_id)].add(str(pair.entity_key))
    settlement_cells: dict[str, list[str]] = defaultdict(list)
    for row in settlements.itertuples(index=False):
        settlement_cells[str(row.cell_id)].append(str(row.name))
    report_cells: dict[str, list[str]] = defaultdict(list)
    for report in verified_reports:
        report_cells[str(report["cell_id"])].append(str(report["report_id"]))

    cell_centroids_wgs84 = gpd.GeoSeries(cells.geometry.centroid, crs=cells.crs).to_crs("EPSG:4326")
    centroid_by_cell = {
        str(cell_id): point
        for cell_id, point in zip(cells["cell_id"].astype(str), cell_centroids_wgs84)
    }
    records: list[dict[str, Any]] = []
    boosted_reports = 0
    for cell in cells.itertuples(index=False):
        cell_id = str(cell.cell_id)
        level = str(cell.risk_level)
        road_keys = sorted(road_cells.get(cell_id, set()))
        settlement_names = sorted(set(settlement_cells.get(cell_id, [])))
        report_ids = sorted(set(report_cells.get(cell_id, [])))
        has_exposure = bool(road_keys or settlement_names)
        report_boost = bool(report_ids and level in EXPOSED_LEVELS)
        if report_boost:
            priority_class = "P1"
            boosted_reports += len(report_ids)
        elif level == "SEVERE" and has_exposure:
            priority_class = "P1"
        elif level == "HIGH" and has_exposure:
            priority_class = "P2"
        elif level == "SEVERE":
            priority_class = "P3"
        else:
            continue
        mapped_road_names = sorted({road_names[key] for key in road_keys if key in road_names})
        location_parts = settlement_names[:3] or mapped_road_names[:3] or [cell_id]
        exposure_parts = []
        if road_keys:
            exposure_parts.append(f"{len(road_keys)} OSM road entit{'y' if len(road_keys) == 1 else 'ies'}")
        if settlement_names:
            exposure_parts.append(f"{len(settlement_names)} mapped settlement{'s' if len(settlement_names) != 1 else ''}")
        if not exposure_parts:
            exposure_parts.append("no mapped road or settlement exposure")
        reasons = [f"Current Operational Risk Index {float(cell.operational_risk_index):.1f}/100 ({level})."]
        if has_exposure:
            reasons.append("Exact GIS overlay identifies mapped road and/or settlement exposure.")
        if report_boost:
            reasons.append(f"Verified geo-tagged incident report(s) {', '.join(report_ids)} provide a priority boost; no blockage or evacuation is inferred.")
        if priority_class == "P3":
            reasons.append("No mapped road or settlement exposure intersects this severe cell.")
        recommended = {
            "P1": "Urgent human review and field verification; coordinate precautionary road and settlement checks.",
            "P2": "Prioritize monitoring and local verification of the mapped exposed assets.",
            "P3": "Monitor the severe cell and verify unmapped or remote exposure before deployment.",
        }[priority_class]
        records.append({
            "priority_id": "",
            "rank": 0,
            "priority_class": priority_class,
            "risk_level": level,
            "cell_id": cell_id,
            "operational_risk_index": round(float(cell.operational_risk_index), 1),
            "forecast_operational_risk_index_24h": round(float(cell.operational_risk_index_24h), 1),
            "forecast_operational_risk_index_48h": round(float(cell.operational_risk_index_48h), 1),
            "forecast_operational_risk_index_72h": round(float(cell.operational_risk_index_72h), 1),
            "location": " / ".join(location_parts),
            "exposure": "; ".join(exposure_parts),
            "road_entity_count": len(road_keys),
            "settlement_count": len(settlement_names),
            "verified_report_ids": report_ids,
            "report_priority_boost": report_boost,
            "reason": " ".join(reasons),
            "recommended_action": recommended,
            "latitude": round(float(centroid_by_cell[cell_id].y), 6),
            "longitude": round(float(centroid_by_cell[cell_id].x), 6),
        })
    priority_order = {"P1": 1, "P2": 2, "P3": 3}
    records.sort(key=lambda item: (priority_order[item["priority_class"]], -item["operational_risk_index"], item["cell_id"]))
    class_counts = {"P1": 0, "P2": 0, "P3": 0}
    for rank, record in enumerate(records, start=1):
        record["rank"] = rank
        class_counts[record["priority_class"]] += 1
        record["priority_id"] = f"{record['priority_class']}-{class_counts[record['priority_class']]:03d}"
    return records, class_counts, boosted_reports


def build_gis_exposure(
    repo_root: Path,
    operational_layer: pd.DataFrame,
    generated_at_utc: str,
) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    grid_path = repo_root / "DATA/PROCESSED/GRID/sikkim_grid_1km.gpkg"
    roads_path = repo_root / "DATA/PROCESSED/STATIC/OSM/sikkim_roads.gpkg"
    settlements_path = repo_root / "DATA/PROCESSED/STATIC/OSM/sikkim_settlements.gpkg"
    report_path = repo_root / "FRONTEND/src/data/pooledReportsDb.json"
    for path in (grid_path, roads_path, settlements_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required authoritative GIS input is unavailable: {path}")

    grid = gpd.read_file(grid_path, layer="sikkim_grid_1km").to_crs(TARGET_CRS)
    roads = gpd.read_file(roads_path, layer="sikkim_roads").to_crs(TARGET_CRS).reset_index(drop=True)
    settlements = gpd.read_file(settlements_path, layer="sikkim_settlements").to_crs(TARGET_CRS).reset_index(drop=True)
    if roads.empty or settlements.empty or roads.geometry.isna().any() or settlements.geometry.isna().any():
        raise RuntimeError("Authoritative OSM road/settlement geometry is empty or missing")
    if not roads.geometry.is_valid.all() or not settlements.geometry.is_valid.all():
        raise RuntimeError("Authoritative OSM road/settlement geometry is invalid")
    _require_columns(roads, {"osm_id", "fclass", "name", "ref", "geometry"}, "OSM roads")
    _require_columns(settlements, {"osm_id", "fclass", "name", "population", "geometry"}, "OSM settlements")
    cells = _risk_cell_layer(grid, operational_layer)

    roads["feature_id"] = [f"OSM-ROAD-{_clean_tag(value) or index}" for index, value in enumerate(roads["osm_id"])]
    identities = roads.apply(_road_identity, axis=1)
    roads["entity_key"] = [item[0] for item in identities]
    roads["display_name"] = [item[1] for item in identities]
    roads["total_length_m"] = roads.geometry.length.astype(float)

    pairs_by_horizon: dict[str, pd.DataFrame] = {}
    aggregate_by_horizon: dict[str, dict[str, dict[str, Any]]] = {}
    for horizon, (level_column, index_column) in HORIZONS.items():
        pairs = _road_cell_intersections(roads, cells, level_column, index_column)
        pairs_by_horizon[horizon] = pairs
        aggregate_by_horizon[horizon] = _aggregate_pair_values(pairs)

    entity_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    road_names: dict[str, str] = {}
    for entity_key, group in roads.groupby("entity_key", sort=True):
        display_name = str(group.iloc[0]["display_name"])
        road_names[str(entity_key)] = display_name
        exposure = {horizon: aggregate_by_horizon[horizon].get(str(entity_key), _empty_exposure()) for horizon in HORIZONS}
        status, risk_level = _status(exposure["current"], [exposure["24h"], exposure["48h"], exposure["72h"]])
        merged_geometry = union_all(group.geometry.to_numpy())
        row = {
            "road_id": f"OSM-ENTITY-{hashlib.sha1(str(entity_key).encode('utf-8')).hexdigest()[:12].upper()}",
            "road_name": display_name,
            "source_name": _clean_tag(group.iloc[0].get("name")) or None,
            "source_ref": _clean_tag(group.iloc[0].get("ref")) or None,
            "osm_feature_count": int(len(group)),
            "osm_ids": sorted({_clean_tag(value) for value in group["osm_id"] if _clean_tag(value)}),
            "road_classes": sorted({_clean_tag(value) for value in group["fclass"] if _clean_tag(value)}),
            "risk_level": risk_level,
            "status": status,
            "exposure_semantics": "potential GIS exposure; not a confirmed blockage",
            "total_length_km": round(float(group["total_length_m"].sum()) / 1000.0, 3),
            "affected_segment_km": exposure["current"]["exposed_length_km"],
            "current_exposure": {key: value for key, value in exposure["current"].items() if key != "exposed_cell_ids"},
            "forecast_exposure_24h": {key: value for key, value in exposure["24h"].items() if key != "exposed_cell_ids"},
            "forecast_exposure_48h": {key: value for key, value in exposure["48h"].items() if key != "exposed_cell_ids"},
            "forecast_exposure_72h": {key: value for key, value in exposure["72h"].items() if key != "exposed_cell_ids"},
            "coordinates": _map_coordinates(merged_geometry),
        }
        entity_rows.append(row)

    entity_rows.sort(key=lambda item: ({"CRITICAL": 0, "HIGH RISK": 1, "WATCH": 2, "NORMAL": 3}[item["status"]], -item["affected_segment_km"], item["road_name"], item["road_id"]))
    tagged_entities = [item for item in entity_rows if item["source_name"] or item["source_ref"]]
    unnamed_exposed = [item for item in entity_rows if not item["source_name"] and not item["source_ref"] and item["status"] != "NORMAL"]
    dashboard_entities = tagged_entities + unnamed_exposed[:DASHBOARD_UNNAMED_ROAD_LIMIT]
    dashboard_entities.sort(key=lambda item: ({"CRITICAL": 0, "HIGH RISK": 1, "WATCH": 2, "NORMAL": 3}[item["status"]], -item["affected_segment_km"], item["road_name"], item["road_id"]))

    for road in roads.itertuples():
        horizon_values: dict[str, dict[str, Any]] = {}
        for horizon, pairs in pairs_by_horizon.items():
            selected = pairs.loc[pairs["road_row"] == road.Index]
            high = int(selected.loc[selected["risk_level"] == "HIGH", "cell_id"].nunique())
            severe = int(selected.loc[selected["risk_level"] == "SEVERE", "cell_id"].nunique())
            horizon_values[horizon] = {
                "high_cell_count": high,
                "severe_cell_count": severe,
                "exposed_cell_count": int(selected["cell_id"].nunique()),
                "exposed_length_km": round(float(selected["intersection_length_m"].sum()) / 1000.0, 3),
            }
        status, risk_level = _status(horizon_values["current"], [horizon_values["24h"], horizon_values["48h"], horizon_values["72h"]])
        feature_rows.append({
            "feature_id": road.feature_id,
            "osm_id": _clean_tag(road.osm_id),
            "osm_name": _clean_tag(road.name) or None,
            "osm_ref": _clean_tag(road.ref) or None,
            "osm_fclass": _clean_tag(road.fclass),
            "entity_key": road.entity_key,
            "total_length_km": round(float(road.total_length_m) / 1000.0, 3),
            "status": status,
            "risk_level": risk_level,
            **{f"{horizon}_{key}": value for horizon, values in horizon_values.items() for key, value in values.items()},
        })

    settlements = settlements.copy()
    settlements["cell_id"] = _assign_points_to_cells(settlements, cells)
    settlement_join = settlements.merge(
        cells.drop(columns="geometry")[["cell_id"] + [column for pair in HORIZONS.values() for column in pair]],
        on="cell_id",
        how="left",
        validate="many_to_one",
    )
    wgs84 = settlements.to_crs("EPSG:4326")
    settlement_records: list[dict[str, Any]] = []
    settlement_rows: list[dict[str, Any]] = []
    for index, row in settlement_join.iterrows():
        name = _clean_tag(row.get("name")) or "Unnamed OSM settlement"
        population_value = row.get("population")
        population = int(population_value) if pd.notna(population_value) and float(population_value) > 0 else None
        record = {
            "settlement_id": f"OSM-SETTLEMENT-{_clean_tag(row.get('osm_id')) or index}",
            "osm_id": _clean_tag(row.get("osm_id")),
            "name": name,
            "settlement_type": _clean_tag(row.get("fclass")),
            "latitude": round(float(wgs84.geometry.iloc[index].y), 6),
            "longitude": round(float(wgs84.geometry.iloc[index].x), 6),
            "cell_id": str(row["cell_id"]),
            "operational_risk_index": round(float(row["operational_risk_index"]), 1),
            "risk_level": str(row["risk_level"]),
            "operational_risk_index_24h": round(float(row["operational_risk_index_24h"]), 1),
            "risk_level_24h": str(row["risk_level_24h"]),
            "operational_risk_index_48h": round(float(row["operational_risk_index_48h"]), 1),
            "risk_level_48h": str(row["risk_level_48h"]),
            "operational_risk_index_72h": round(float(row["operational_risk_index_72h"]), 1),
            "risk_level_72h": str(row["risk_level_72h"]),
            "potentially_exposed": str(row["risk_level"]) in EXPOSED_LEVELS,
            "potentially_exposed_24h": str(row["risk_level_24h"]) in EXPOSED_LEVELS,
            "potentially_exposed_48h": str(row["risk_level_48h"]) in EXPOSED_LEVELS,
            "potentially_exposed_72h": str(row["risk_level_72h"]) in EXPOSED_LEVELS,
            "population": population,
            "population_source": "OSM tag" if population is not None else "unavailable",
            "exposure_semantics": "potential GIS exposure; not confirmed affected",
        }
        settlement_records.append(record)
        settlement_rows.append(record.copy())

    verified_reports, verified_total = _parse_verified_reports(report_path, cells)
    priorities, priority_counts, report_boost_count = _priority_records(
        cells, pairs_by_horizon["current"], pd.DataFrame(settlement_records), verified_reports, road_names
    )
    alerts = [
        {
            "alert_id": f"GIS-{item['priority_id']}",
            "risk_level": item["risk_level"],
            "title": f"{item['priority_class']} review: potentially exposed assets in {item['cell_id']}",
            "location_cell_id": item["cell_id"],
            "detail": item["reason"],
            "channels": ["Dashboard review queue"],
            "status": "decision-support; field confirmation required",
        }
        for item in priorities[:10]
        if item["priority_class"] in {"P1", "P2"}
    ]

    current_pairs = pairs_by_horizon["current"]
    exposed_entities = {str(value) for value in current_pairs["entity_key"].unique().tolist()}
    exposed_features = int(current_pairs["feature_id"].nunique())
    settlement_current_count = sum(bool(item["potentially_exposed"]) for item in settlement_records)
    metadata = {
        "version": EXPOSURE_VERSION,
        "generated_at_utc": generated_at_utc,
        "source": "Processed OpenStreetMap roads and settlements clipped to Sikkim",
        "source_files": {
            "roads": {"path": roads_path.relative_to(repo_root).as_posix(), "sha256": _sha256(roads_path)},
            "settlements": {"path": settlements_path.relative_to(repo_root).as_posix(), "sha256": _sha256(settlements_path)},
            "canonical_grid": {"path": grid_path.relative_to(repo_root).as_posix(), "sha256": _sha256(grid_path)},
            "verified_report_input": {"path": report_path.relative_to(repo_root).as_posix(), "sha256": _sha256(report_path) if report_path.is_file() else None},
        },
        "crs": TARGET_CRS,
        "road_feature_count": int(len(roads)),
        "road_entity_count": int(roads["entity_key"].nunique()),
        "dashboard_road_entity_count": len(dashboard_entities),
        "dashboard_road_selection": (
            "All entities carrying an actual OSM name/ref plus the 200 highest-ranked exposed unnamed OSM entities; "
            "the segment-level CSV retains all road features"
        ),
        "settlement_feature_count": int(len(settlements)),
        "road_features_exposed_current": exposed_features,
        "road_entities_exposed_current": len(exposed_entities),
        "settlements_exposed_current": settlement_current_count,
        "road_intersection_method": "Exact LineString/MultiLineString intersection with canonical 1 km cell polygons in EPSG:32645; exposed length is intersection length",
        "settlement_assignment_method": "Containing canonical cell; deterministic cell_id tie-break on boundaries; nearest cell only if no containing cell",
        "road_grouping_method": "Group segments only by actual OSM ref/name tags; unnamed features retain individual OSM identity",
        "road_status_rules": {
            "CRITICAL": "At least one current SEVERE cell intersects the road entity",
            "HIGH RISK": "At least one current HIGH cell and no current SEVERE cell intersects the road entity",
            "WATCH": "No current HIGH/SEVERE intersection, but at least one 24h/48h/72h forecast HIGH/SEVERE intersection",
            "NORMAL": "No current or 24h/48h/72h HIGH/SEVERE intersection",
        },
        "priority_rules": {
            "P1": "Current SEVERE cell with road or settlement exposure, or a verified geo-tagged report in a current HIGH/SEVERE cell",
            "P2": "Current HIGH cell with road or settlement exposure",
            "P3": "Current SEVERE cell without mapped road or settlement exposure",
        },
        "priority_counts": priority_counts,
        "verified_report_count": verified_total,
        "verified_report_mapped_count": len(verified_reports),
        "verified_report_priority_boost_count": report_boost_count,
        "semantics": "Potential exposure and review priority only; not confirmed blockage, affected population, evacuation order, or guaranteed impact",
    }
    payload = {
        "roads": dashboard_entities,
        "settlements": settlement_records,
        "emergencyPriorities": priorities,
        "alerts": alerts,
        "metadata": metadata,
        "summary": {
            "roads_at_risk": len(exposed_entities),
            "settlements_at_risk": settlement_current_count,
            "exposure_status": "GIS-derived potential exposure; not confirmed blocked or affected",
        },
    }
    artifacts = {
        "road_exposure_current.csv": pd.DataFrame(feature_rows),
        "settlement_exposure_current.csv": pd.DataFrame(settlement_rows),
        "emergency_priorities_current.csv": pd.DataFrame(priorities),
    }
    return payload, artifacts


def write_exposure_artifacts(repo_root: Path, artifacts: dict[str, pd.DataFrame], metadata: dict[str, Any]) -> None:
    dataset_dir = repo_root / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    checksums: dict[str, str] = {}
    for filename, frame in artifacts.items():
        data = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
        checksums[filename] = hashlib.sha256(data).hexdigest()
        temporary = None
        target = dataset_dir / filename
        try:
            with tempfile.NamedTemporaryFile(mode="wb", prefix=f".{filename}.", suffix=".tmp", dir=dataset_dir, delete=False) as stream:
                temporary = stream.name
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
    metadata_value = {**metadata, "artifact_sha256": checksums}
    metadata_data = (json.dumps(metadata_value, indent=2, allow_nan=False) + "\n").encode("utf-8")
    target = dataset_dir / "exposure_current.metadata.json"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".exposure_current.metadata.json.", suffix=".tmp", dir=dataset_dir, delete=False) as stream:
            temporary = stream.name
            stream.write(metadata_data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
