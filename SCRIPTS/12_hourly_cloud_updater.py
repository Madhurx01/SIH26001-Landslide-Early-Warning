#!/usr/bin/env python3
"""Update a transparent prototype Operational Risk Index.

Live mode uses model/API precipitation and 0--7 cm volumetric soil moisture
from Open-Meteo at four Sikkim reference locations. It is not NASA IMERG,
NASA SMAP, a calibrated probability, or an ML inference service. A failed or
incomplete live fetch preserves the last trusted values and marks them stale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

EXPECTED_CELL_COUNT = 7_390
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
FRESHNESS_LIMIT_MINUTES = 180
INDEX_THRESHOLDS = {
    "LOW": {"minimum": 0, "maximum_exclusive": 20},
    "MODERATE": {"minimum": 20, "maximum_exclusive": 50},
    "HIGH": {"minimum": 50, "maximum_exclusive": 75},
    "SEVERE": {"minimum": 75, "maximum_inclusive": 100},
}
REFERENCE_LOCATIONS = (
    {"name": "Gangtok", "latitude": 27.3389, "longitude": 88.6065},
    {"name": "Mangan", "latitude": 27.5000, "longitude": 88.5333},
    {"name": "Namchi", "latitude": 27.1667, "longitude": 88.3500},
    {"name": "Gyalshing", "latitude": 27.2833, "longitude": 88.2500},
)
SIMULATIONS = {
    "dry": (0.0, 2.0, 8.0, 0.0, 0.16, "Dry-condition demonstration"),
    "storm": (170.0, 250.0, 360.0, 12.0, 0.42, "Extreme-storm demonstration"),
}
TIMELINE_SCENARIOS = {
    "2021-05-15": (3.0, 7.0, 15.0, 0.18),
    "2021-06-18": (22.0, 52.0, 115.0, 0.27),
    "2021-07-29": (8.0, 46.0, 145.0, 0.34),
    "2021-08-26": (20.0, 58.0, 135.0, 0.31),
    "2021-10-19": (121.0, 168.0, 280.0, 0.42),
}


class TelemetryUnavailable(RuntimeError):
    def __init__(self, message: str, successful: list[str], failed: list[dict[str, str]]):
        super().__init__(message)
        self.successful = successful
        self.failed = failed


@dataclass(frozen=True)
class TelemetryPoint:
    name: str
    latitude: float
    longitude: float
    timestamp_utc: str
    current_rainfall_mm_hr: float
    rainfall_1d_mm: float
    rainfall_3d_mm: float
    rainfall_7d_mm: float
    soil_moisture_m3_m3: float
    trend: list[dict[str, Any]]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def finite_number(value: Any, label: str, minimum: float = 0.0) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} is not numeric")
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise ValueError(f"{label} is invalid: {value!r}")
    return number


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read valid JSON from {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object in {path}")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as stream:
            temporary_name = stream.name
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def expected_cell_ids() -> list[str]:
    return [f"SKM_{index:05d}" for index in range(1, EXPECTED_CELL_COUNT + 1)]


def validate_id_frame(frame: pd.DataFrame, label: str) -> None:
    if "cell_id" not in frame or len(frame) != EXPECTED_CELL_COUNT:
        raise RuntimeError(f"{label} does not contain exactly {EXPECTED_CELL_COUNT:,} cells")
    ids = frame["cell_id"].astype(str)
    if ids.isna().any() or ids.duplicated().any() or ids.tolist() != expected_cell_ids():
        raise RuntimeError(f"{label} is not in unique canonical cell_id order")


def validate_sidecar(csv_path: Path, metadata_path: Path, label: str) -> dict[str, Any]:
    metadata = read_json(metadata_path)
    if metadata.get("output_sha256") != sha256_file(csv_path):
        raise RuntimeError(f"{label} checksum does not match provenance metadata")
    if metadata.get("synthetic_fallback_used") is not False:
        raise RuntimeError(f"{label} provenance permits synthetic fallback data")
    return metadata


def load_static_inputs(repo_root: Path) -> pd.DataFrame:
    susceptibility_path = repo_root / "DATA/PROCESSED/RISK/static_susceptibility.csv"
    static_path = repo_root / "DATA/PROCESSED/FEATURES/sikkim_static_features_1km.csv"
    fault_path = repo_root / "dataset/features_hydrology_faults_1km.csv"
    ndvi_path = repo_root / "dataset/features_ndvi_1km.csv"
    ndvi_meta = validate_sidecar(ndvi_path, repo_root / "dataset/features_ndvi_1km.metadata.json", "NDVI")
    fault_meta = validate_sidecar(fault_path, repo_root / "dataset/features_hydrology_faults_1km.metadata.json", "hydrology/fault")
    if ndvi_meta.get("data_origin") != "satellite_observation":
        raise RuntimeError("NDVI metadata is not satellite-observation provenance")
    if fault_meta.get("manual_geometry_used") is not False:
        raise RuntimeError("Hydrology/fault metadata permits manual geometry")

    susceptibility = pd.read_csv(susceptibility_path)
    static = pd.read_csv(static_path)
    fault = pd.read_csv(fault_path)
    ndvi = pd.read_csv(ndvi_path)
    for frame, label in ((susceptibility, "static susceptibility"), (static, "static features"), (fault, "fault/drainage"), (ndvi, "Sentinel-2 NDVI")):
        validate_id_frame(frame, label)
    if set(susceptibility["score_semantics"].dropna().astype(str)) != {"uncalibrated susceptibility score; not probability"}:
        raise RuntimeError("Static susceptibility semantics are unexpected")
    if susceptibility["static_susceptibility"].isna().any() or not susceptibility["static_susceptibility"].between(0, 100).all():
        raise RuntimeError("Static susceptibility contains missing or out-of-range values")
    if fault[["distance_to_fault_km", "distance_to_drainage_km"]].isna().any().any():
        raise RuntimeError("Fault/drainage distances contain missing values")
    if not ndvi["ndvi_mean"].dropna().between(-1, 1).all():
        raise RuntimeError("NDVI contains values outside [-1, 1]")

    static_columns = ["cell_id", "elevation_mean_m", "slope_mean_deg", "distance_to_nearest_road_m", "distance_to_nearest_settlement_m", "nearest_settlement_name"]
    joined = susceptibility.merge(static[static_columns], on="cell_id", how="left", validate="one_to_one")
    joined = joined.merge(fault, on="cell_id", how="left", validate="one_to_one")
    joined = joined.merge(ndvi, on="cell_id", how="left", validate="one_to_one")
    validate_id_frame(joined, "joined operational inputs")
    return joined


def fetch_open_meteo_location(location: dict[str, Any], api_url: str, timeout: float) -> TelemetryPoint:
    query = urllib.parse.urlencode({
        "latitude": location["latitude"], "longitude": location["longitude"],
        "current": "precipitation", "hourly": "precipitation,soil_moisture_0_to_7cm",
        "past_days": 7, "forecast_days": 1, "timezone": "UTC",
    })
    request = urllib.request.Request(f"{api_url}?{query}", headers={"User-Agent": "SIH26001-operational-risk-index/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    current, hourly = payload.get("current"), payload.get("hourly")
    if not isinstance(current, dict) or not isinstance(hourly, dict):
        raise ValueError("response lacks current or hourly data")
    current_time = parse_utc(str(current.get("time", "")))
    current_rain = finite_number(current.get("precipitation"), "current precipitation")
    times, precipitation, moisture = hourly.get("time"), hourly.get("precipitation"), hourly.get("soil_moisture_0_to_7cm")
    if not all(isinstance(values, list) for values in (times, precipitation, moisture)):
        raise ValueError("hourly arrays are missing")
    if not (len(times) == len(precipitation) == len(moisture)):
        raise ValueError("hourly arrays have inconsistent lengths")
    parsed_times = [parse_utc(str(value)) for value in times]
    eligible = [index for index, value in enumerate(parsed_times) if value <= current_time]
    if not eligible:
        raise ValueError("no hourly record exists at or before current.time")
    current_index = eligible[-1]
    if current_index + 1 < 168:
        raise ValueError("response does not contain a complete 7-day history")
    rain = [finite_number(value, f"hourly precipitation[{index}]") for index, value in enumerate(precipitation[:current_index + 1])]
    soil = finite_number(moisture[current_index], "current 0--7 cm soil moisture")
    if soil > 1.0:
        raise ValueError("soil moisture exceeds 1 m3/m3")

    def total(hours: int) -> float:
        window = rain[-hours:]
        if len(window) != hours:
            raise ValueError(f"incomplete {hours}-hour precipitation window")
        return round(float(sum(window)), 3)

    start = max(0, current_index - 5)
    trend = [{"time": parsed_times[i].strftime("%H:%M"), "value": round(rain[i], 2)} for i in range(start, current_index + 1)]
    return TelemetryPoint(
        str(location["name"]), float(location["latitude"]), float(location["longitude"]),
        current_time.isoformat(), round(current_rain, 3), total(24), total(72), total(168), round(soil, 5), trend,
    )


def fetch_realtime_sikkim_telemetry(api_url: str = OPEN_METEO_URL, timeout: float = 20.0) -> tuple[list[TelemetryPoint], dict[str, Any]]:
    """Require a complete, valid, fresh four-location Open-Meteo dataset."""
    print("Fetching Open-Meteo model/API data at four Sikkim reference locations...")
    points: list[TelemetryPoint] = []
    failures: list[dict[str, str]] = []
    for location in REFERENCE_LOCATIONS:
        try:
            point = fetch_open_meteo_location(location, api_url, timeout)
            points.append(point)
            print(f"  {point.name:10s} | 1d {point.rainfall_1d_mm:7.1f} mm | 3d {point.rainfall_3d_mm:7.1f} mm | soil {point.soil_moisture_m3_m3:.3f} m3/m3")
        except Exception as error:
            failures.append({"location": str(location["name"]), "error": str(error)})
            print(f"  {location['name']:10s} | FAILED: {error}")
    names = [point.name for point in points]
    if failures or len(points) != len(REFERENCE_LOCATIONS):
        raise TelemetryUnavailable("Complete Open-Meteo telemetry unavailable; preserving last trusted values", names, failures)
    timestamps = [parse_utc(point.timestamp_utc) for point in points]
    freshness = (utc_now() - min(timestamps)).total_seconds() / 60
    if freshness < -60 or freshness > FRESHNESS_LIMIT_MINUTES:
        raise TelemetryUnavailable(f"Open-Meteo telemetry is stale/future-dated ({freshness:.1f} minutes)", names, [])
    return points, {
        "source": "Open-Meteo Forecast API", "source_type": "model/API data",
        "not_satellite_products": ["NASA IMERG", "NASA SMAP"], "api_url": api_url,
        "fetch_timestamp_utc": max(timestamps).isoformat(), "freshness_minutes": round(max(0, freshness), 1),
        "state": "fresh", "successful_location_count": 4, "failed_location_count": 0,
        "successful_locations": names, "failed_locations": [], "missing_data": False,
    }


def simulated_telemetry(mode: str) -> tuple[list[TelemetryPoint], dict[str, Any]]:
    rain1, rain3, rain7, current, soil, label = SIMULATIONS[mode]
    timestamp = utc_now().isoformat()
    points = [TelemetryPoint(str(item["name"]), float(item["latitude"]), float(item["longitude"]), timestamp, current, rain1, rain3, rain7, soil, []) for item in REFERENCE_LOCATIONS]
    return points, {
        "source": label, "source_type": "simulation/demo; not observed telemetry",
        "not_satellite_products": ["NASA IMERG", "NASA SMAP"], "api_url": None,
        "fetch_timestamp_utc": timestamp, "freshness_minutes": 0, "state": "simulation",
        "successful_location_count": 0, "failed_location_count": 0,
        "successful_locations": [], "failed_locations": [], "missing_data": False,
    }


def operational_risk_index(static_score: float, point: TelemetryPoint) -> tuple[float, float]:
    """Combine baseline and trigger as a heuristic index, never a probability."""
    r1 = float(np.clip(point.rainfall_1d_mm / 100, 0, 1))
    r3 = float(np.clip(point.rainfall_3d_mm / 200, 0, 1))
    r7 = float(np.clip(point.rainfall_7d_mm / 350, 0, 1))
    soil = float(np.clip((point.soil_moisture_m3_m3 - 0.15) / 0.30, 0, 1))
    trigger = 100 * (0.45 * r1 + 0.30 * r3 + 0.10 * r7 + 0.15 * soil)
    index = static_score + (100 - static_score) * 0.55 * (trigger / 100)
    return round(float(np.clip(index, 0, 100)), 1), round(trigger, 1)


def risk_level(index: float) -> str:
    return "SEVERE" if index >= 75 else "HIGH" if index >= 50 else "MODERATE" if index >= 20 else "LOW"


def factor_type(value: float, warning: float, danger: float) -> str:
    return "danger" if value >= danger else "warning" if value >= warning else "context"


def optional_float(value: Any, digits: int = 2) -> float | None:
    return None if pd.isna(value) else round(float(value), digits)


def build_risk_factors(row: pd.Series, point: TelemetryPoint, state: str) -> list[dict[str, str]]:
    weather_prefix = "Open-Meteo" if state == "fresh" else "Simulated"
    weather_context = f"Model/API point data at {point.name}" if state == "fresh" else "Explicit demo assumption; not observed telemetry"
    factors = [
        {"factor": "Static susceptibility", "value": f"{row['static_susceptibility']:.1f}/100", "type": factor_type(float(row["static_susceptibility"]), 20, 50), "context": "Existing uncalibrated susceptibility score; not probability"},
        {"factor": f"{weather_prefix} 24-hour precipitation", "value": f"{point.rainfall_1d_mm:.1f} mm", "type": factor_type(point.rainfall_1d_mm, 40, 100), "context": weather_context},
        {"factor": f"{weather_prefix} 0–7 cm soil moisture", "value": f"{point.soil_moisture_m3_m3:.3f} m³/m³", "type": factor_type(point.soil_moisture_m3_m3, .25, .38), "context": "Model-derived volumetric water content; not satellite saturation" if state == "fresh" else weather_context},
    ]
    slope = optional_float(row["slope_mean_deg"], 1)
    if slope is not None:
        factors.append({"factor": "SRTM-derived mean slope", "value": f"{slope:.1f}°", "type": factor_type(slope, 25, 40), "context": "Static terrain descriptor"})
    fault = float(row["distance_to_fault_km"])
    factors.append({"factor": "Distance to GEM active-fault source", "value": f"{fault:.2f} km", "type": "warning" if fault <= 5 else "context", "context": "Active-fault proxy distance; not lithology"})
    ndvi = optional_float(row["ndvi_mean"], 3)
    if ndvi is not None:
        factors.append({"factor": "Sentinel-2 NDVI", "value": f"{ndvi:.3f}", "type": "warning" if ndvi < .30 else "context", "context": "Observed NDVI aggregate; not imputed"})
    return factors


def nearest_telemetry(row: pd.Series, points: list[TelemetryPoint]) -> TelemetryPoint:
    lat, lon = float(row["analysis_lat"]), float(row["analysis_lon"])
    return min(points, key=lambda point: (point.latitude - lat) ** 2 + (point.longitude - lon) ** 2)


def update_cells(existing_cells: list[dict[str, Any]], inputs: pd.DataFrame, points: list[TelemetryPoint], state: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not existing_cells:
        raise RuntimeError("Dashboard has no riskCells to update")
    display_ids = [str(cell.get("cell_id", "")) for cell in existing_cells]
    if not all(display_ids) or len(display_ids) != len(set(display_ids)):
        raise RuntimeError("Dashboard riskCells have missing or duplicate cell_id values")
    indexed = inputs.set_index("cell_id")
    if not indexed.index.is_unique:
        raise RuntimeError("Joined operational inputs contain duplicate cell_id values")
    missing = sorted(set(display_ids) - set(indexed.index))
    if missing:
        raise RuntimeError(f"Dashboard cell_ids are absent from canonical inputs: {missing[:5]}")
    canonical_position = {cell_id: index for index, cell_id in enumerate(expected_cell_ids())}
    if display_ids != sorted(display_ids, key=canonical_position.__getitem__):
        raise RuntimeError("Dashboard riskCells are not in canonical cell_id order")

    updated, indexes = [], []
    missing_ndvi = 0
    categories = {level: 0 for level in INDEX_THRESHOLDS}
    for existing, cell_id in zip(existing_cells, display_ids):
        row = indexed.loc[cell_id]
        point = nearest_telemetry(row, points)
        index, trigger = operational_risk_index(float(row["static_susceptibility"]), point)
        level = risk_level(index)
        categories[level] += 1
        indexes.append(index)
        ndvi = optional_float(row["ndvi_mean"], 6)
        missing_ndvi += int(ndvi is None)
        cell = dict(existing)
        for legacy in ("risk_probability", "shap_factors", "soil_moisture"):
            cell.pop(legacy, None)
        cell.update({
            "operational_risk_index": index, "risk_level": level,
            "index_semantics": "prototype decision-support score; not probability",
            "static_susceptibility": round(float(row["static_susceptibility"]), 3),
            "dynamic_trigger_index": trigger,
            "elevation_m": optional_float(row["elevation_mean_m"], 1),
            "slope_deg": optional_float(row["slope_mean_deg"], 2),
            "distance_to_fault_km": round(float(row["distance_to_fault_km"]), 6),
            "distance_to_drainage_km": round(float(row["distance_to_drainage_km"]), 6),
            "ndvi_mean": ndvi, "ndvi_status": "available" if ndvi is not None else "unavailable",
            "rainfall_1d_mm": round(point.rainfall_1d_mm, 2),
            "rainfall_3d_mm": round(point.rainfall_3d_mm, 2),
            "rainfall_7d_mm": round(point.rainfall_7d_mm, 2),
            "soil_moisture_m3_m3": round(point.soil_moisture_m3_m3, 5),
            "soil_moisture_vwc_percent": round(point.soil_moisture_m3_m3 * 100, 1),
            "telemetry_source": "Open-Meteo model/API data" if state == "fresh" else "Scenario simulation; not live telemetry",
            "telemetry_location": point.name, "telemetry_state": state,
            "road_distance_m": optional_float(row["distance_to_nearest_road_m"], 1),
            "nearest_road": "Nearest mapped OSM road",
            "settlement_distance_m": optional_float(row["distance_to_nearest_settlement_m"], 1),
            "nearest_settlement": None if pd.isna(row["nearest_settlement_name"]) else str(row["nearest_settlement_name"]),
            "risk_factors": build_risk_factors(row, point, state),
            "explanation": (
                f"Operational Risk Index {index:.1f}/100 combines the existing static "
                f"susceptibility score ({row['static_susceptibility']:.1f}) with a "
                f"weather-trigger index ({trigger:.1f}) from {point.name}. It is a "
                "prototype decision-support score, not a calibrated landslide probability."
            ),
        })
        updated.append(cell)
    return updated, {
        "cells_updated": len(updated), "cells_with_missing_ndvi": missing_ndvi,
        "cells_with_real_fault_distance": len(updated),
        "index_min": round(float(np.min(indexes)), 1),
        "index_median": round(float(np.median(indexes)), 1),
        "index_max": round(float(np.max(indexes)), 1), "category_counts": categories,
    }


def mean_weather(points: list[TelemetryPoint], category: str, state: str) -> dict[str, Any]:
    def mean(attribute: str) -> float:
        return round(float(np.mean([getattr(point, attribute) for point in points])), 3)
    trend = []
    if points and all(point.trend for point in points):
        count = min(len(point.trend) for point in points)
        trend = [{"time": points[0].trend[i]["time"], "value": round(float(np.mean([point.trend[i]["value"] for point in points])), 2)} for i in range(-count, 0)]
    soil = mean("soil_moisture_m3_m3")
    return {
        "source": "Open-Meteo Forecast API model/API data" if state == "fresh" else "Scenario simulation; not live telemetry",
        "telemetry_state": state, "current_rainfall_mm_hr": mean("current_rainfall_mm_hr"),
        "rainfall_1d_mm": mean("rainfall_1d_mm"), "rainfall_3d_mm": mean("rainfall_3d_mm"),
        "rainfall_7d_mm": mean("rainfall_7d_mm"), "soil_moisture_m3_m3": soil,
        "soil_moisture_vwc_percent": round(soil * 100, 1), "operational_category": category,
        "trend": trend,
    }


def timeline_point(date: str) -> TelemetryPoint:
    rain1, rain3, rain7, soil = TIMELINE_SCENARIOS[date]
    return TelemetryPoint("Statewide scenario assumption", 27.45, 88.50, f"{date}T12:00:00+00:00", round(rain1 / 24, 2), rain1, rain3, rain7, soil, [])


def migrate_timeline_snapshots(master: dict[str, Any], inputs: pd.DataFrame) -> None:
    snapshots = master.get("timelineSnapshots")
    if not isinstance(snapshots, dict):
        return
    for date, snapshot in snapshots.items():
        if date not in TIMELINE_SCENARIOS or not isinstance(snapshot, dict):
            continue
        old_meta = snapshot.get("meta", {})
        point = timeline_point(date)
        cells, qa = update_cells(snapshot.get("riskCells", []), inputs, [point], "simulation")
        snapshot["riskCells"] = cells
        snapshot["meta"] = {
            "date": date, "label": old_meta.get("label", date), "tag": old_meta.get("tag", "SIMULATION"),
            "mode": "simulation", "telemetry_source": "Scenario simulation; not live observations",
            "index_semantics": "prototype decision-support score; not probability",
            "severe_count": qa["category_counts"]["SEVERE"], "high_count": qa["category_counts"]["HIGH"],
            "weather_summary": {
                "rainfall_1d_mm": point.rainfall_1d_mm, "rainfall_3d_mm": point.rainfall_3d_mm,
                "rainfall_7d_mm": point.rainfall_7d_mm,
                "soil_moisture_vwc_percent": round(point.soil_moisture_m3_m3 * 100, 1),
            },
        }


def data_sources(telemetry: dict[str, Any]) -> list[dict[str, str]]:
    weather_status = (f"Fresh at {telemetry['fetch_timestamp_utc']} · {telemetry['successful_location_count']}/4 locations" if telemetry["state"] == "fresh" else "Explicit simulation/demo values; not observations")
    return [
        {"source": "Static susceptibility score", "status": "Existing 7,390-cell uncalibrated model output; not probability", "type": "available"},
        {"source": "Open-Meteo Forecast API precipitation and soil moisture", "status": weather_status, "type": "available" if telemetry["state"] == "fresh" else "demo"},
        {"source": "Sentinel-2 L2A NDVI", "status": "Real satellite NDVI; missing observations remain unavailable", "type": "available"},
        {"source": "GEM active-fault proxy and OpenStreetMap drainage", "status": "Pinned/provenance-validated static distance features", "type": "available"},
        {"source": "NASA rainfall / soil-moisture products", "status": "Not connected in this prototype; future adapters planned", "type": "pending"},
    ]


def mark_live_failure(output: Path, master: dict[str, Any], attempt: str, error: TelemetryUnavailable) -> None:
    meta = master.setdefault("meta", {})
    previous = meta.get("telemetry", {})
    last_trusted = previous.get("last_trusted_fetch_utc") or previous.get("fetch_timestamp_utc")
    meta["telemetry"] = {
        **previous, "source": "Open-Meteo Forecast API", "source_type": "model/API data",
        "state": "unavailable", "missing_data": True, "fetch_attempt_utc": attempt,
        "last_trusted_fetch_utc": last_trusted, "successful_location_count": len(error.successful),
        "failed_location_count": len(error.failed), "successful_locations": error.successful,
        "failed_locations": error.failed, "status_message": str(error),
        "values_preserved_from_last_trusted_update": True,
    }
    meta["system_status"] = "Operational Risk Index prototype · telemetry unavailable/stale"
    if isinstance(master.get("weather"), dict):
        master["weather"]["telemetry_state"] = "unavailable"
        master["weather"]["values_preserved_from_last_trusted_update"] = True
    for source in master.get("dataSources", []):
        if str(source.get("source", "")).startswith("Open-Meteo"):
            source["status"] = "Unavailable/stale; last trusted values preserved"
            source["type"] = "pending"
    atomic_write_json(output, master)


def run_hourly_update(mode: str = "live", output_dir: str | Path | None = None, api_base_url: str = OPEN_METEO_URL, timeout_seconds: float = 20.0) -> bool:
    start = time.time()
    attempt = utc_now()
    repo_root = Path(__file__).resolve().parent.parent
    target_dir = Path(output_dir).resolve() if output_dir else repo_root / "FRONTEND/src/data"
    output = target_dir / "realRiskData.json"
    if not output.is_file():
        raise FileNotFoundError(f"Dashboard output does not exist: {output}")
    master = read_json(output)
    print(f"Operational Risk Index updater · mode={mode} · displayed cells={len(master.get('riskCells', [])):,}")
    try:
        points, telemetry = fetch_realtime_sikkim_telemetry(api_base_url, timeout_seconds) if mode == "live" else simulated_telemetry(mode)
    except TelemetryUnavailable as error:
        mark_live_failure(output, master, attempt.isoformat(), error)
        print(f"FAIL-CLOSED: {error}", file=sys.stderr)
        return False

    inputs = load_static_inputs(repo_root)
    cells, qa = update_cells(master.get("riskCells", []), inputs, points, telemetry["state"])
    migrate_timeline_snapshots(master, inputs)
    counts = qa["category_counts"]
    telemetry.update({
        "fetch_attempt_utc": attempt.isoformat(),
        "last_trusted_fetch_utc": telemetry["fetch_timestamp_utc"],
        "values_preserved_from_last_trusted_update": False,
    })
    master["riskCells"] = cells
    master["weather"] = mean_weather(points, risk_level(qa["index_median"]), telemetry["state"])
    master["dataSources"] = data_sources(telemetry)
    meta = master.setdefault("meta", {})
    meta.update({
        "system_status": "Operational Risk Index prototype · monitoring",
        "last_updated": telemetry["fetch_timestamp_utc"],
        "data_mode": "PROTOTYPE DECISION-SUPPORT INDEX",
        "index_name": "Operational Risk Index",
        "index_semantics": "0–100 prototype decision-support score combining static susceptibility and dynamic weather triggers; not a calibrated landslide probability",
        "index_thresholds": INDEX_THRESHOLDS,
        "telemetry": telemetry,
        "input_validation": {
            "canonical_cell_count": EXPECTED_CELL_COUNT, "ordered_one_to_one_static_join": True,
            "displayed_cell_count": qa["cells_updated"], "missing_ndvi_displayed_cells": qa["cells_with_missing_ndvi"],
            "real_fault_distance_displayed_cells": qa["cells_with_real_fault_distance"],
        },
        "summary": {
            "severe_risk_cells": counts["SEVERE"], "high_risk_cells": counts["HIGH"],
            "roads_at_risk": None, "settlements_at_risk": None,
            "exposure_status": "unavailable; no live spatial exposure calculation",
            "weather_trigger": f"{telemetry['source']} · mean 1-day rain {master['weather']['rainfall_1d_mm']:.1f} mm · soil moisture {master['weather']['soil_moisture_vwc_percent']:.1f}% VWC",
        },
        "run_qa": qa,
    })
    atomic_write_json(output, master)
    print(
        "Updated {cells:,} cells atomically in {seconds:.2f}s · index {minimum:.1f}/{median:.1f}/{maximum:.1f} · "
        "LOW {low:,}, MODERATE {moderate:,}, HIGH {high:,}, SEVERE {severe:,}".format(
            cells=qa["cells_updated"], seconds=time.time() - start,
            minimum=qa["index_min"], median=qa["index_median"], maximum=qa["index_max"],
            low=counts["LOW"], moderate=counts["MODERATE"], high=counts["HIGH"], severe=counts["SEVERE"],
        )
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Update the prototype Operational Risk Index")
    parser.add_argument("--mode", default="live", choices=["live", "storm", "dry"], help="live Open-Meteo data or explicitly labelled demo scenario")
    parser.add_argument("--output-dir", default=None, help="Dashboard data directory")
    parser.add_argument("--api-base-url", default=OPEN_METEO_URL, help="Open-Meteo endpoint; override for fail-closed testing")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args()
    return 0 if run_hourly_update(**vars(args)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
