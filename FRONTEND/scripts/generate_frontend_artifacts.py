"""Build compact, frontend-only artifacts from existing processed pipeline outputs."""

from __future__ import annotations

import csv
import json
import math
import shutil
from collections import Counter
from pathlib import Path
from statistics import median

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = FRONTEND_ROOT / "public" / "data"
DEMO_DATE = "2021-10-19"

SOURCE_GEOJSON = PROJECT_ROOT / "DATA" / "PROCESSED" / "RISK" / "demo_risk.geojson"
SOURCE_DYNAMIC = PROJECT_ROOT / "DATA" / "PROCESSED" / "DYNAMIC" / "sikkim_dynamic_features_2021.csv"
MODEL_REPORT = PROJECT_ROOT / "ML" / "reports" / "static_model_metrics.json"
RUN_SUMMARY = PROJECT_ROOT / "ML" / "reports" / "run_summary.json"
EXPOSURE_DIR = PROJECT_ROOT / "DATA" / "PROCESSED" / "EXPOSURE"
SOURCE_EXPOSURE_SUMMARY = EXPOSURE_DIR / f"exposure_summary_{DEMO_DATE}.json"
SOURCE_ACTION_PRIORITY = EXPOSURE_DIR / f"action_priority_{DEMO_DATE}.json"
SOURCE_VEHICULAR_ROADS = EXPOSURE_DIR / f"vehicular_road_exposure_{DEMO_DATE}.geojson"
SOURCE_SETTLEMENT_EXPOSURE = EXPOSURE_DIR / f"settlement_exposure_{DEMO_DATE}.geojson"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def number_or_none(value: str) -> float | None:
    if value is None or value.strip() == "":
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def rounded(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with SOURCE_GEOJSON.open("r", encoding="utf-8") as handle:
    geojson = json.load(handle)

risk_features = geojson.get("features", [])
require(risk_features, "Risk/demo GeoJSON contains no features")
risk_ids = [str(feature.get("properties", {}).get("cell_id", "")).strip() for feature in risk_features]
require(all(risk_ids), "Risk/demo GeoJSON contains an empty cell_id")
risk_id_counts = Counter(risk_ids)
risk_duplicates = sorted(cell_id for cell_id, count in risk_id_counts.items() if count > 1)
require(not risk_duplicates, f"Risk/demo GeoJSON contains duplicate cell_id values: {risk_duplicates[:10]}")

risk_dates = {
    str(feature.get("properties", {}).get("date", ""))[:10]
    for feature in risk_features
}
require(risk_dates == {DEMO_DATE}, f"Risk/demo feature dates do not match {DEMO_DATE}: {sorted(risk_dates)}")
geojson_demo_date = str(geojson.get("metadata", {}).get("demo_date", ""))[:10]
require(geojson_demo_date == DEMO_DATE, f"Risk/demo GeoJSON metadata date is {geojson_demo_date}, expected {DEMO_DATE}")

risk_counts = Counter(feature["properties"]["risk_level"] for feature in risk_features)
score_values = [float(feature["properties"]["final_risk_score"]) for feature in risk_features]

records: list[dict[str, object]] = []
metric_values: dict[str, list[float]] = {
    "rainfall_1d": [],
    "rainfall_3d": [],
    "rainfall_7d": [],
    "soil_moisture": [],
    "dynamic_trigger_score": [],
}

with SOURCE_DYNAMIC.open("r", encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    for row in reader:
        if row["date"] != DEMO_DATE:
            continue
        record = {
            "cell_id": row["cell_id"],
            "rainfall_1d": number_or_none(row["rainfall_1d"]),
            "rainfall_3d": number_or_none(row["rainfall_3d"]),
            "rainfall_7d": number_or_none(row["rainfall_7d"]),
            "soil_moisture": number_or_none(row["soil_moisture"]),
            "dynamic_trigger_score": number_or_none(row["dynamic_trigger_score"]),
        }
        records.append(record)
        for metric in metric_values:
            value = record[metric]
            if value is not None:
                metric_values[metric].append(float(value))

dynamic_ids = [str(record["cell_id"]).strip() for record in records]
require(all(dynamic_ids), "Demo dynamic artifact contains an empty cell_id")
dynamic_id_counts = Counter(dynamic_ids)
dynamic_duplicates = sorted(cell_id for cell_id, count in dynamic_id_counts.items() if count > 1)
require(not dynamic_duplicates, f"Demo dynamic artifact contains duplicate cell_id values: {dynamic_duplicates[:10]}")

risk_id_set = set(risk_ids)
dynamic_id_set = set(dynamic_ids)
missing_dynamic = sorted(risk_id_set - dynamic_id_set)
extra_dynamic = sorted(dynamic_id_set - risk_id_set)
require(
    risk_id_set == dynamic_id_set,
    "Exact cell_id alignment failed: "
    f"missing dynamic cells={missing_dynamic[:10]} (total {len(missing_dynamic)}), "
    f"extra dynamic cells={extra_dynamic[:10]} (total {len(extra_dynamic)})",
)
verified_cell_count = len(risk_id_set)
require(verified_cell_count == len(risk_features) == len(records), "Cell alignment counts do not reconcile")

with MODEL_REPORT.open("r", encoding="utf-8") as handle:
    model_report = json.load(handle)
with RUN_SUMMARY.open("r", encoding="utf-8") as handle:
    run_summary = json.load(handle)
run_demo_date = str(run_summary.get("demo_date", ""))[:10]
require(run_demo_date == DEMO_DATE, f"ML run summary demo date is {run_demo_date}, expected {DEMO_DATE}")

with SOURCE_EXPOSURE_SUMMARY.open("r", encoding="utf-8") as handle:
    exposure_summary = json.load(handle)
with SOURCE_ACTION_PRIORITY.open("r", encoding="utf-8") as handle:
    action_priority = json.load(handle)
with SOURCE_VEHICULAR_ROADS.open("r", encoding="utf-8") as handle:
    vehicular_roads = json.load(handle)
with SOURCE_SETTLEMENT_EXPOSURE.open("r", encoding="utf-8") as handle:
    settlement_exposure = json.load(handle)

require(exposure_summary.get("demo_date") == DEMO_DATE, "Exposure summary date mismatch")
require(action_priority.get("demo_date") == DEMO_DATE, "Action-priority date mismatch")
road_features = vehicular_roads.get("features", [])
settlement_features = settlement_exposure.get("features", [])
require(
    len(road_features) == exposure_summary.get("exposed_vehicular_road_segments"),
    "Vehicular-road GeoJSON count does not match exposure summary",
)
require(
    len(settlement_features) == exposure_summary.get("unique_exposed_settlements"),
    "Settlement GeoJSON count does not match exposure summary",
)
road_osm_ids = [str(feature.get("properties", {}).get("osm_id", "")).strip() for feature in road_features]
require(all(road_osm_ids), "Vehicular-road GeoJSON contains an empty OSM ID")
require(len(set(road_osm_ids)) == len(road_osm_ids), "Vehicular-road GeoJSON contains duplicate OSM IDs")
require(
    {feature.get("properties", {}).get("risk_level") for feature in road_features} <= {"HIGH", "SEVERE"},
    "Vehicular-road exposure contains a risk level below HIGH",
)
settlement_osm_ids = [str(feature.get("properties", {}).get("osm_id", "")).strip() for feature in settlement_features]
require(all(settlement_osm_ids), "Settlement GeoJSON contains an empty OSM ID")
require(len(set(settlement_osm_ids)) == len(settlement_osm_ids), "Settlement GeoJSON contains duplicate OSM IDs")
priority_counts = action_priority.get("priority_counts", {})
require(
    priority_counts == {
        "1": exposure_summary.get("priority_1_count"),
        "2": exposure_summary.get("priority_2_count"),
        "3": exposure_summary.get("priority_3_count"),
    },
    "Action-priority counts do not match exposure summary",
)

rainfall_1d_p95 = percentile(metric_values["rainfall_1d"], 0.95)
rainfall_3d_p95 = percentile(metric_values["rainfall_3d"], 0.95)
rainfall_7d_p95 = percentile(metric_values["rainfall_7d"], 0.95)
if (rainfall_1d_p95 or 0) >= 37.86 or (rainfall_3d_p95 or 0) >= 84.5:
    trigger_description = "Localized heavy rainfall"
elif (rainfall_7d_p95 or 0) >= 120:
    trigger_description = "Elevated rainfall accumulation"
else:
    trigger_description = "Rainfall trigger monitored"

selected_model = model_report["selected_model"]
validation_metrics = model_report["validation_metrics"]
test_metrics = model_report["test_metrics"]
summary = {
    "artifact_version": 2,
    "context": "historical_replay",
    "demo_date": DEMO_DATE,
    "demo_date_display": "19 Oct 2021",
    "feature_count": verified_cell_count,
    "artifact_alignment": {
        "verified": True,
        "verified_cell_count": verified_cell_count,
        "risk_cell_ids_unique": True,
        "dynamic_cell_ids_unique": True,
        "exact_cell_id_set_match": True,
        "replay_date_match": True,
    },
    "risk_counts": {level: int(risk_counts.get(level, 0)) for level in ["LOW", "MODERATE", "HIGH", "SEVERE"]},
    "final_risk_score": {
        "min": rounded(min(score_values)),
        "max": rounded(max(score_values)),
        "median": rounded(median(score_values)),
    },
    "weather": {
        "trigger_description": trigger_description,
        "rainfall_1d_median_mm": rounded(median(metric_values["rainfall_1d"])),
        "rainfall_1d_p95_mm": rounded(rainfall_1d_p95),
        "rainfall_3d_median_mm": rounded(median(metric_values["rainfall_3d"])),
        "rainfall_3d_p95_mm": rounded(rainfall_3d_p95),
        "rainfall_7d_median_mm": rounded(median(metric_values["rainfall_7d"])),
        "rainfall_7d_p95_mm": rounded(rainfall_7d_p95),
        "soil_moisture_median": rounded(median(metric_values["soil_moisture"])) if metric_values["soil_moisture"] else None,
        "soil_moisture_valid_cells": len(metric_values["soil_moisture"]),
        "dynamic_trigger_median": rounded(median(metric_values["dynamic_trigger_score"])),
        "dynamic_trigger_p95": rounded(percentile(metric_values["dynamic_trigger_score"], 0.95)),
    },
    "model": {
        "static_model": "XGBoost" if selected_model == "xgboost" else "Random Forest" if selected_model == "random_forest" else selected_model,
        "validation": "Untouched 10-km spatial-block test",
        "pr_auc": rounded(test_metrics["pr_auc_average_precision"], 3),
        "recall": rounded(test_metrics["recall"], 3),
        "precision": rounded(test_metrics["precision"], 3),
        "f1": rounded(test_metrics["f1"], 3),
        "roc_auc": rounded(test_metrics["roc_auc"], 3),
        "accuracy_secondary": rounded(test_metrics["accuracy_secondary"], 3),
        "candidate_validation_metrics": validation_metrics,
        "risk_engine": "Static susceptibility + rainfall/soil-moisture trigger",
        "score_semantics": run_summary["threshold_semantics"],
    },
}

shutil.copyfile(SOURCE_GEOJSON, OUTPUT_DIR / "demo_risk.geojson")
with (OUTPUT_DIR / "demo_dynamic_2021-10-19.json").open("w", encoding="utf-8") as handle:
    json.dump({"demo_date": DEMO_DATE, "records": records}, handle, separators=(",", ":"), allow_nan=False)
with (OUTPUT_DIR / "dashboard_summary_2021-10-19.json").open("w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, allow_nan=False)
shutil.copyfile(SOURCE_EXPOSURE_SUMMARY, OUTPUT_DIR / SOURCE_EXPOSURE_SUMMARY.name)
shutil.copyfile(SOURCE_ACTION_PRIORITY, OUTPUT_DIR / SOURCE_ACTION_PRIORITY.name)
shutil.copyfile(SOURCE_VEHICULAR_ROADS, OUTPUT_DIR / SOURCE_VEHICULAR_ROADS.name)
shutil.copyfile(SOURCE_SETTLEMENT_EXPOSURE, OUTPUT_DIR / SOURCE_SETTLEMENT_EXPOSURE.name)

print(f"Verified exact cell alignment: {verified_cell_count} unique cells for {DEMO_DATE}")
print(
    "Verified real exposure artifacts: "
    f"{len(road_features)} vehicular OSM segments, "
    f"{exposure_summary['unique_named_roads']} named roads, "
    f"{len(settlement_features)} named settlements, "
    f"P1/P2/P3={priority_counts['1']}/{priority_counts['2']}/{priority_counts['3']}"
)
print(json.dumps(summary, indent=2))
