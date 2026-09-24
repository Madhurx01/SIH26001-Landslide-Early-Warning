#!/usr/bin/env python3
"""Update a transparent prototype Operational Risk Index.

Live mode uses model/API precipitation and 0--7 cm volumetric soil moisture
from an Open-Meteo sampling lattice spanning Sikkim. It is not NASA IMERG,
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
WEATHER_GRID_SPACING_DEGREES = 0.25
OPEN_METEO_BATCH_SIZE = 12
IDW_NEIGHBOURS = 4
IDW_POWER = 2.0
DTI_VERSION = "dti-v2-spatial-forecast"
ORI_VERSION = "ori-v2-65-static-35-trigger"
INDEX_THRESHOLDS = {
    "LOW": {"minimum": 0, "maximum_exclusive": 20},
    "MODERATE": {"minimum": 20, "maximum_exclusive": 50},
    "HIGH": {"minimum": 50, "maximum_exclusive": 75},
    "SEVERE": {"minimum": 75, "maximum_inclusive": 100},
}
SIMULATIONS = {
    "dry": (0.0, 1.0, 2.0, 3.0, 8.0, 0.0, 0.16, 0.0, 0.0, 0.0, "Dry-condition demonstration"),
    "storm": (170.0, 210.0, 250.0, 280.0, 360.0, 12.0, 0.42, 90.0, 150.0, 210.0, "Extreme-storm demonstration"),
}
TIMELINE_SCENARIOS = {
    "2021-05-15": (3.0, 5.0, 7.0, 9.0, 15.0, 0.18, 1.0, 2.0, 3.0),
    "2021-06-18": (22.0, 38.0, 52.0, 68.0, 115.0, 0.27, 18.0, 30.0, 45.0),
    "2021-07-29": (8.0, 28.0, 46.0, 70.0, 145.0, 0.34, 20.0, 38.0, 58.0),
    "2021-08-26": (20.0, 40.0, 58.0, 78.0, 135.0, 0.31, 25.0, 44.0, 66.0),
    "2021-10-19": (121.0, 150.0, 168.0, 205.0, 280.0, 0.42, 70.0, 120.0, 170.0),
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
    rainfall_2d_mm: float
    rainfall_3d_mm: float
    rainfall_4d_mm: float
    rainfall_7d_mm: float
    soil_moisture_m3_m3: float
    forecast_rainfall_24h_mm: float
    forecast_rainfall_48h_mm: float
    forecast_rainfall_72h_mm: float
    forecast_soil_moisture_24h_m3_m3: float
    forecast_soil_moisture_48h_m3_m3: float
    forecast_soil_moisture_72h_m3_m3: float
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


def build_sampling_grid(inputs: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build a deterministic rectangular lattice over the canonical centroid extent."""
    lon_min, lon_max = float(inputs["analysis_lon"].min()), float(inputs["analysis_lon"].max())
    lat_min, lat_max = float(inputs["analysis_lat"].min()), float(inputs["analysis_lat"].max())
    lon_count = int(math.ceil((lon_max - lon_min) / WEATHER_GRID_SPACING_DEGREES)) + 1
    lat_count = int(math.ceil((lat_max - lat_min) / WEATHER_GRID_SPACING_DEGREES)) + 1
    longitudes = np.linspace(lon_min, lon_max, lon_count)
    latitudes = np.linspace(lat_min, lat_max, lat_count)
    locations = []
    for latitude in latitudes:
        for longitude in longitudes:
            locations.append({
                "name": f"WX-{len(locations) + 1:03d}",
                "latitude": round(float(latitude), 6),
                "longitude": round(float(longitude), 6),
            })
    mean_latitude = float(np.mean(latitudes))
    return locations, {
        "requested_spacing_degrees": WEATHER_GRID_SPACING_DEGREES,
        "longitude_spacing_degrees": round(float(longitudes[1] - longitudes[0]), 6),
        "latitude_spacing_degrees": round(float(latitudes[1] - latitudes[0]), 6),
        "approx_longitude_spacing_km": round(float((longitudes[1] - longitudes[0]) * 111.32 * math.cos(math.radians(mean_latitude))), 2),
        "approx_latitude_spacing_km": round(float((latitudes[1] - latitudes[0]) * 110.57), 2),
        "grid_shape": [lat_count, lon_count],
        "bounds": {"west": lon_min, "south": lat_min, "east": lon_max, "north": lat_max},
    }


def parse_open_meteo_payload(location: dict[str, Any], payload: dict[str, Any]) -> TelemetryPoint:
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
    if len(precipitation) < current_index + 73 or len(moisture) < current_index + 73:
        raise ValueError("response does not contain a complete 72-hour forecast")
    relevant_rain = [finite_number(value, f"hourly precipitation[{index}]") for index, value in enumerate(precipitation[:current_index + 73])]
    relevant_soil = [finite_number(value, f"hourly soil moisture[{index}]") for index, value in enumerate(moisture[:current_index + 73])]
    if any(value > 1.0 for value in relevant_soil):
        raise ValueError("soil moisture exceeds 1 m3/m3")

    def total(hours: int) -> float:
        window = relevant_rain[:current_index + 1][-hours:]
        if len(window) != hours:
            raise ValueError(f"incomplete {hours}-hour precipitation window")
        return round(float(sum(window)), 3)

    def forecast_total(hours: int) -> float:
        window = relevant_rain[current_index + 1:current_index + 1 + hours]
        if len(window) != hours:
            raise ValueError(f"incomplete {hours}-hour forecast window")
        return round(float(sum(window)), 3)

    start = max(0, current_index - 5)
    trend = [{"time": parsed_times[i].strftime("%H:%M"), "value": round(relevant_rain[i], 2)} for i in range(start, current_index + 1)]
    return TelemetryPoint(
        str(location["name"]), float(location["latitude"]), float(location["longitude"]),
        current_time.isoformat(), round(current_rain, 3), total(24), total(48), total(72), total(96), total(168),
        round(relevant_soil[current_index], 5), forecast_total(24), forecast_total(48), forecast_total(72),
        round(relevant_soil[current_index + 24], 5), round(relevant_soil[current_index + 48], 5),
        round(relevant_soil[current_index + 72], 5), trend,
    )


def fetch_realtime_sikkim_telemetry(locations: list[dict[str, Any]], api_url: str = OPEN_METEO_URL, timeout: float = 30.0) -> tuple[list[TelemetryPoint], dict[str, Any]]:
    """Fetch the complete lattice in batches; any failed point fails the live run."""
    print(f"Fetching Open-Meteo model/API data at {len(locations)} spatial sampling points...")
    points: list[TelemetryPoint] = []
    failures: list[dict[str, str]] = []
    for batch_start in range(0, len(locations), OPEN_METEO_BATCH_SIZE):
        batch = locations[batch_start:batch_start + OPEN_METEO_BATCH_SIZE]
        try:
            query = urllib.parse.urlencode({
                "latitude": ",".join(str(item["latitude"]) for item in batch),
                "longitude": ",".join(str(item["longitude"]) for item in batch),
                "current": "precipitation", "hourly": "precipitation,soil_moisture_0_to_7cm",
                "past_days": 7, "forecast_days": 4, "timezone": "UTC",
            })
            request = urllib.request.Request(f"{api_url}?{query}", headers={"User-Agent": "SIH26001-spatial-operational-risk-index/2.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            payloads = response_payload if isinstance(response_payload, list) else [response_payload]
            if len(payloads) != len(batch):
                raise ValueError(f"response count {len(payloads)} does not match request count {len(batch)}")
            for location, payload in zip(batch, payloads):
                try:
                    points.append(parse_open_meteo_payload(location, payload))
                except Exception as error:
                    failures.append({"location": str(location["name"]), "coordinates": [location["latitude"], location["longitude"]], "error": str(error)})
        except Exception as error:
            failures.extend({"location": str(location["name"]), "coordinates": [location["latitude"], location["longitude"]], "error": str(error)} for location in batch)
        print(f"  batch {batch_start // OPEN_METEO_BATCH_SIZE + 1}: {len(points)} cumulative successes, {len(failures)} failures")
    names = [point.name for point in points]
    if failures or len(points) != len(locations):
        raise TelemetryUnavailable("Complete Open-Meteo telemetry unavailable; preserving last trusted values", names, failures)
    timestamps = [parse_utc(point.timestamp_utc) for point in points]
    freshness = (utc_now() - min(timestamps)).total_seconds() / 60
    if freshness < -60 or freshness > FRESHNESS_LIMIT_MINUTES:
        raise TelemetryUnavailable(f"Open-Meteo telemetry is stale/future-dated ({freshness:.1f} minutes)", names, [])
    return points, {
        "source": "Open-Meteo Forecast API", "source_type": "model/API data",
        "not_satellite_products": ["NASA IMERG", "NASA SMAP"], "api_url": api_url,
        "fetch_timestamp_utc": max(timestamps).isoformat(), "freshness_minutes": round(max(0, freshness), 1),
        "state": "fresh", "successful_location_count": len(points), "failed_location_count": 0,
        "successful_locations": names, "failed_locations": [], "missing_data": False,
        "weather_source_coordinates": [[point.latitude, point.longitude] for point in points],
    }


def simulated_telemetry(mode: str, locations: list[dict[str, Any]]) -> tuple[list[TelemetryPoint], dict[str, Any]]:
    rain1, rain2, rain3, rain4, rain7, current, soil, forecast24, forecast48, forecast72, label = SIMULATIONS[mode]
    timestamp = utc_now().isoformat()
    points = [TelemetryPoint(str(item["name"]), float(item["latitude"]), float(item["longitude"]), timestamp, current, rain1, rain2, rain3, rain4, rain7, soil, forecast24, forecast48, forecast72, soil, soil, soil, []) for item in locations]
    return points, {
        "source": label, "source_type": "simulation/demo; not observed telemetry",
        "not_satellite_products": ["NASA IMERG", "NASA SMAP"], "api_url": None,
        "fetch_timestamp_utc": timestamp, "freshness_minutes": 0, "state": "simulation",
        "successful_location_count": 0, "failed_location_count": 0,
        "successful_locations": [], "failed_locations": [], "missing_data": False,
        "weather_source_coordinates": [[point.latitude, point.longitude] for point in points],
    }


WEATHER_VARIABLES = [
    "current_rainfall_mm_hr", "rainfall_1d_mm", "rainfall_2d_mm", "rainfall_3d_mm", "rainfall_4d_mm", "rainfall_7d_mm",
    "soil_moisture_m3_m3", "forecast_rainfall_24h_mm", "forecast_rainfall_48h_mm", "forecast_rainfall_72h_mm",
    "forecast_soil_moisture_24h_m3_m3", "forecast_soil_moisture_48h_m3_m3", "forecast_soil_moisture_72h_m3_m3",
]


def interpolate_weather(inputs: pd.DataFrame, points: list[TelemetryPoint]) -> pd.DataFrame:
    """Interpolate source values with 4-neighbour IDW in approximate local kilometres."""
    if len(points) < IDW_NEIGHBOURS:
        raise RuntimeError("Insufficient real weather points for spatial interpolation")
    mean_latitude = math.radians(float(inputs["analysis_lat"].mean()))
    source_x = np.array([point.longitude * 111.32 * math.cos(mean_latitude) for point in points])
    source_y = np.array([point.latitude * 110.57 for point in points])
    target_x = inputs["analysis_lon"].to_numpy(float) * 111.32 * math.cos(mean_latitude)
    target_y = inputs["analysis_lat"].to_numpy(float) * 110.57
    distance_squared = (target_x[:, None] - source_x[None, :]) ** 2 + (target_y[:, None] - source_y[None, :]) ** 2
    nearest = np.argpartition(distance_squared, IDW_NEIGHBOURS - 1, axis=1)[:, :IDW_NEIGHBOURS]
    nearest_distance = np.take_along_axis(distance_squared, nearest, axis=1)
    weights = 1.0 / np.maximum(nearest_distance, 1e-12) ** (IDW_POWER / 2.0)
    weights /= weights.sum(axis=1, keepdims=True)
    frame = pd.DataFrame({"cell_id": inputs["cell_id"].astype(str)})
    for variable in WEATHER_VARIABLES:
        source_values = np.array([float(getattr(point, variable)) for point in points])
        frame[variable] = np.sum(source_values[nearest] * weights, axis=1)
    if frame[WEATHER_VARIABLES].isna().any().any() or not np.isfinite(frame[WEATHER_VARIABLES].to_numpy()).all():
        raise RuntimeError("Spatial weather interpolation produced missing/non-finite values")
    validate_id_frame(frame, "interpolated weather layer")
    return frame


def dynamic_trigger_index(row: pd.Series, horizon: int = 0) -> float:
    if horizon == 0:
        rain1, rain3, rain7, soil, forecast, forecast_threshold = row.rainfall_1d_mm, row.rainfall_3d_mm, row.rainfall_7d_mm, row.soil_moisture_m3_m3, row.forecast_rainfall_24h_mm, 100.0
    elif horizon == 24:
        rain1, rain3, rain7 = row.forecast_rainfall_24h_mm, row.rainfall_3d_mm - row.rainfall_1d_mm + row.forecast_rainfall_24h_mm, row.rainfall_7d_mm - row.rainfall_1d_mm + row.forecast_rainfall_24h_mm
        soil, forecast, forecast_threshold = row.forecast_soil_moisture_24h_m3_m3, row.forecast_rainfall_24h_mm, 100.0
    elif horizon == 48:
        rain1, rain3, rain7 = row.forecast_rainfall_48h_mm - row.forecast_rainfall_24h_mm, row.rainfall_1d_mm + row.forecast_rainfall_48h_mm, row.rainfall_7d_mm - row.rainfall_2d_mm + row.forecast_rainfall_48h_mm
        soil, forecast, forecast_threshold = row.forecast_soil_moisture_48h_m3_m3, row.forecast_rainfall_48h_mm, 160.0
    elif horizon == 72:
        rain1, rain3, rain7 = row.forecast_rainfall_72h_mm - row.forecast_rainfall_48h_mm, row.forecast_rainfall_72h_mm, row.rainfall_7d_mm - row.rainfall_3d_mm + row.forecast_rainfall_72h_mm
        soil, forecast, forecast_threshold = row.forecast_soil_moisture_72h_m3_m3, row.forecast_rainfall_72h_mm, 220.0
    else:
        raise ValueError(f"Unsupported forecast horizon: {horizon}")
    r1 = float(np.clip(max(0, rain1) / 100, 0, 1)); r3 = float(np.clip(max(0, rain3) / 200, 0, 1)); r7 = float(np.clip(max(0, rain7) / 350, 0, 1))
    moisture = float(np.clip((soil - 0.15) / 0.30, 0, 1)); future = float(np.clip(forecast / forecast_threshold, 0, 1))
    return round(100 * (0.35 * r1 + 0.25 * r3 + 0.10 * r7 + 0.20 * moisture + 0.10 * future), 1)


def build_operational_layer(inputs: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    layer = inputs.merge(weather, on="cell_id", how="left", validate="one_to_one")
    validate_id_frame(layer, "operational weather/static layer")
    for horizon, suffix in ((0, ""), (24, "_24h"), (48, "_48h"), (72, "_72h")):
        trigger_column = f"dynamic_trigger_index{suffix}"
        risk_column = f"operational_risk_index{suffix}"
        level_column = f"risk_level{suffix}"
        layer[trigger_column] = layer.apply(lambda row: dynamic_trigger_index(row, horizon), axis=1)
        layer[risk_column] = (0.65 * layer["static_susceptibility"] + 0.35 * layer[trigger_column]).clip(0, 100).round(1)
        layer[level_column] = layer[risk_column].map(risk_level)
    return layer


def risk_level(index: float) -> str:
    return "SEVERE" if index >= 75 else "HIGH" if index >= 50 else "MODERATE" if index >= 20 else "LOW"


def factor_type(value: float, warning: float, danger: float) -> str:
    return "danger" if value >= danger else "warning" if value >= warning else "context"


def optional_float(value: Any, digits: int = 2) -> float | None:
    return None if pd.isna(value) else round(float(value), digits)


def build_risk_factors(row: pd.Series, state: str, source_point_count: int) -> list[dict[str, str]]:
    weather_prefix = "Open-Meteo" if state == "fresh" else "Simulated"
    weather_context = (
        f"Four-neighbour inverse-distance interpolation from {source_point_count} model/API source points"
        if state == "fresh" else "Explicit demo assumption; not observed telemetry"
    )
    factors = [
        {"factor": "Static susceptibility", "value": f"{row['static_susceptibility']:.1f}/100", "type": factor_type(float(row["static_susceptibility"]), 20, 50), "context": "Existing uncalibrated susceptibility score; not probability"},
        {"factor": f"{weather_prefix} prior 24-hour precipitation", "value": f"{row['rainfall_1d_mm']:.1f} mm", "type": factor_type(float(row["rainfall_1d_mm"]), 40, 100), "context": weather_context},
        {"factor": f"{weather_prefix} 0–7 cm soil moisture", "value": f"{row['soil_moisture_m3_m3']:.3f} m³/m³", "type": factor_type(float(row["soil_moisture_m3_m3"]), .25, .38), "context": "Model-derived volumetric water content; not satellite saturation" if state == "fresh" else weather_context},
        {"factor": f"{weather_prefix} next-24-hour precipitation", "value": f"{row['forecast_rainfall_24h_mm']:.1f} mm", "type": factor_type(float(row["forecast_rainfall_24h_mm"]), 40, 100), "context": "Forecast model/API input; not an observed event" if state == "fresh" else weather_context},
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


def update_cells(existing_cells: list[dict[str, Any]], layer: pd.DataFrame, state: str, source_point_count: int) -> list[dict[str, Any]]:
    if not existing_cells:
        raise RuntimeError("Dashboard has no riskCells to update")
    display_ids = [str(cell.get("cell_id", "")) for cell in existing_cells]
    if not all(display_ids) or len(display_ids) != len(set(display_ids)):
        raise RuntimeError("Dashboard riskCells have missing or duplicate cell_id values")
    indexed = layer.set_index("cell_id")
    if not indexed.index.is_unique:
        raise RuntimeError("Joined operational inputs contain duplicate cell_id values")
    missing = sorted(set(display_ids) - set(indexed.index))
    if missing:
        raise RuntimeError(f"Dashboard cell_ids are absent from canonical inputs: {missing[:5]}")
    canonical_position = {cell_id: index for index, cell_id in enumerate(expected_cell_ids())}
    if display_ids != sorted(display_ids, key=canonical_position.__getitem__):
        raise RuntimeError("Dashboard riskCells are not in canonical cell_id order")

    updated = []
    for existing, cell_id in zip(existing_cells, display_ids):
        row = indexed.loc[cell_id]
        ndvi = optional_float(row["ndvi_mean"], 6)
        cell = dict(existing)
        for legacy in ("risk_probability", "shap_factors", "soil_moisture"):
            cell.pop(legacy, None)
        cell.update({
            "operational_risk_index": float(row["operational_risk_index"]), "risk_level": str(row["risk_level"]),
            "operational_risk_index_24h": float(row["operational_risk_index_24h"]), "risk_level_24h": str(row["risk_level_24h"]),
            "operational_risk_index_48h": float(row["operational_risk_index_48h"]), "risk_level_48h": str(row["risk_level_48h"]),
            "operational_risk_index_72h": float(row["operational_risk_index_72h"]), "risk_level_72h": str(row["risk_level_72h"]),
            "forecast_semantics": "forecast-based risk index; not an observed event or guaranteed prediction",
            "index_semantics": "prototype decision-support score; not probability",
            "static_susceptibility": round(float(row["static_susceptibility"]), 3),
            "dynamic_trigger_index": float(row["dynamic_trigger_index"]),
            "dynamic_trigger_index_24h": float(row["dynamic_trigger_index_24h"]),
            "dynamic_trigger_index_48h": float(row["dynamic_trigger_index_48h"]),
            "dynamic_trigger_index_72h": float(row["dynamic_trigger_index_72h"]),
            "elevation_m": optional_float(row["elevation_mean_m"], 1),
            "slope_deg": optional_float(row["slope_mean_deg"], 2),
            "distance_to_fault_km": round(float(row["distance_to_fault_km"]), 6),
            "distance_to_drainage_km": round(float(row["distance_to_drainage_km"]), 6),
            "ndvi_mean": ndvi, "ndvi_status": "available" if ndvi is not None else "unavailable",
            "rainfall_1d_mm": round(float(row["rainfall_1d_mm"]), 2),
            "rainfall_3d_mm": round(float(row["rainfall_3d_mm"]), 2),
            "rainfall_7d_mm": round(float(row["rainfall_7d_mm"]), 2),
            "forecast_rainfall_24h_mm": round(float(row["forecast_rainfall_24h_mm"]), 2),
            "forecast_rainfall_48h_mm": round(float(row["forecast_rainfall_48h_mm"]), 2),
            "forecast_rainfall_72h_mm": round(float(row["forecast_rainfall_72h_mm"]), 2),
            "soil_moisture_m3_m3": round(float(row["soil_moisture_m3_m3"]), 5),
            "soil_moisture_vwc_percent": round(float(row["soil_moisture_m3_m3"]) * 100, 1),
            "telemetry_source": "Open-Meteo model/API data" if state == "fresh" else "Scenario simulation; not live telemetry",
            "telemetry_location": f"Four-neighbour IDW from {source_point_count} source points", "telemetry_state": state,
            "road_distance_m": optional_float(row["distance_to_nearest_road_m"], 1),
            "nearest_road": "Nearest mapped OSM road",
            "settlement_distance_m": optional_float(row["distance_to_nearest_settlement_m"], 1),
            "nearest_settlement": None if pd.isna(row["nearest_settlement_name"]) else str(row["nearest_settlement_name"]),
            "risk_factors": build_risk_factors(row, state, source_point_count),
            "explanation": (
                f"Operational Risk Index {row['operational_risk_index']:.1f}/100 combines the existing static "
                f"susceptibility score ({row['static_susceptibility']:.1f}) with a "
                f"spatial weather-trigger index ({row['dynamic_trigger_index']:.1f}). It is a "
                "prototype decision-support score, not a calibrated landslide probability."
            ),
        })
        updated.append(cell)
    return updated


def summary_stats(series: pd.Series) -> dict[str, float]:
    return {"min": round(float(series.min()), 3), "median": round(float(series.median()), 3), "max": round(float(series.max()), 3)}


def category_counts(series: pd.Series) -> dict[str, int]:
    counts = series.value_counts().to_dict()
    return {level: int(counts.get(level, 0)) for level in INDEX_THRESHOLDS}


def build_run_qa(layer: pd.DataFrame, display_ids: list[str]) -> dict[str, Any]:
    displayed = layer.set_index("cell_id").loc[display_ids]
    required_weather = WEATHER_VARIABLES + [
        "dynamic_trigger_index", "dynamic_trigger_index_24h", "dynamic_trigger_index_48h", "dynamic_trigger_index_72h",
        "operational_risk_index", "operational_risk_index_24h", "operational_risk_index_48h", "operational_risk_index_72h",
    ]
    return {
        "canonical_cells_interpolated": len(layer), "dashboard_cells_updated": len(displayed),
        "cells_with_missing_ndvi": int(layer["ndvi_mean"].isna().sum()),
        "displayed_cells_with_missing_ndvi": int(displayed["ndvi_mean"].isna().sum()),
        "cells_with_real_fault_distance": int(layer["distance_to_fault_km"].notna().sum()),
        "rainfall_1d_mm": summary_stats(layer["rainfall_1d_mm"]),
        "rainfall_3d_mm": summary_stats(layer["rainfall_3d_mm"]),
        "rainfall_7d_mm": summary_stats(layer["rainfall_7d_mm"]),
        "soil_moisture_m3_m3": summary_stats(layer["soil_moisture_m3_m3"]),
        "dynamic_trigger_index": summary_stats(layer["dynamic_trigger_index"]),
        "operational_risk_index": summary_stats(layer["operational_risk_index"]),
        "category_counts": category_counts(layer["risk_level"]),
        "forecast_category_counts": {
            "24h": category_counts(layer["risk_level_24h"]),
            "48h": category_counts(layer["risk_level_48h"]),
            "72h": category_counts(layer["risk_level_72h"]),
        },
        "missing_data_counts": {column: int(layer[column].isna().sum()) for column in required_weather},
    }


def weather_summary(layer: pd.DataFrame, points: list[TelemetryPoint], telemetry: dict[str, Any]) -> dict[str, Any]:
    trend = []
    if points and all(point.trend for point in points):
        count = min(len(point.trend) for point in points)
        trend = [{"time": points[0].trend[i]["time"], "value": round(float(np.mean([point.trend[i]["value"] for point in points])), 2)} for i in range(-count, 0)]
    soil = float(layer["soil_moisture_m3_m3"].median())
    return {
        "source": "Open-Meteo Forecast API model/API data" if telemetry["state"] == "fresh" else "Scenario simulation; not live telemetry",
        "telemetry_state": telemetry["state"], "fetch_timestamp_utc": telemetry["fetch_timestamp_utc"],
        "freshness_minutes": telemetry["freshness_minutes"], "source_point_count": len(points),
        "interpolation": (
            f"{IDW_NEIGHBOURS}-neighbour inverse-distance weighting (power {IDW_POWER:g})"
            if telemetry["state"] == "fresh" else "Uniform scenario assumption; no live spatial interpolation"
        ),
        "summary_statistic": "median across 7,390 interpolated canonical cells",
        "current_rainfall_mm_hr": round(float(layer["current_rainfall_mm_hr"].median()), 3),
        "rainfall_1d_mm": round(float(layer["rainfall_1d_mm"].median()), 3),
        "rainfall_3d_mm": round(float(layer["rainfall_3d_mm"].median()), 3),
        "rainfall_7d_mm": round(float(layer["rainfall_7d_mm"].median()), 3),
        "forecast_rainfall_24h_mm": round(float(layer["forecast_rainfall_24h_mm"].median()), 3),
        "forecast_rainfall_48h_mm": round(float(layer["forecast_rainfall_48h_mm"].median()), 3),
        "forecast_rainfall_72h_mm": round(float(layer["forecast_rainfall_72h_mm"].median()), 3),
        "soil_moisture_m3_m3": round(soil, 5), "soil_moisture_vwc_percent": round(soil * 100, 1),
        "operational_category": risk_level(float(layer["operational_risk_index"].median())),
        "forecast_operational_category_24h": risk_level(float(layer["operational_risk_index_24h"].median())),
        "forecast_operational_category_48h": risk_level(float(layer["operational_risk_index_48h"].median())),
        "forecast_operational_category_72h": risk_level(float(layer["operational_risk_index_72h"].median())),
        "trend": trend,
    }


def timeline_point(date: str) -> TelemetryPoint:
    rain1, rain2, rain3, rain4, rain7, soil, forecast24, forecast48, forecast72 = TIMELINE_SCENARIOS[date]
    return TelemetryPoint(
        "Uniform scenario assumption", 27.45, 88.50, f"{date}T12:00:00+00:00", round(rain1 / 24, 2),
        rain1, rain2, rain3, rain4, rain7, soil, forecast24, forecast48, forecast72, soil, soil, soil, [],
    )


def uniform_weather(inputs: pd.DataFrame, point: TelemetryPoint) -> pd.DataFrame:
    frame = pd.DataFrame({"cell_id": inputs["cell_id"].astype(str)})
    for variable in WEATHER_VARIABLES:
        frame[variable] = float(getattr(point, variable))
    validate_id_frame(frame, "uniform simulation weather layer")
    return frame


def migrate_timeline_snapshots(master: dict[str, Any], inputs: pd.DataFrame) -> None:
    snapshots = master.get("timelineSnapshots")
    if not isinstance(snapshots, dict):
        return
    for date, snapshot in snapshots.items():
        if date not in TIMELINE_SCENARIOS or not isinstance(snapshot, dict):
            continue
        old_meta = snapshot.get("meta", {})
        point = timeline_point(date)
        layer = build_operational_layer(inputs, uniform_weather(inputs, point))
        cells = update_cells(snapshot.get("riskCells", []), layer, "simulation", 1)
        display_ids = [str(cell["cell_id"]) for cell in cells]
        qa = build_run_qa(layer, display_ids)
        snapshot["riskCells"] = cells
        snapshot["weather"] = weather_summary(layer, [point], {
            "state": "simulation", "fetch_timestamp_utc": point.timestamp_utc, "freshness_minutes": None,
        })
        snapshot["meta"] = {
            "date": date, "label": old_meta.get("label", date), "tag": old_meta.get("tag", "SIMULATION"),
            "mode": "simulation", "telemetry_source": "Scenario simulation; not live observations",
            "index_semantics": "prototype decision-support score; not probability",
            "severe_count": qa["category_counts"]["SEVERE"], "high_count": qa["category_counts"]["HIGH"],
            "weather_summary": {
                "rainfall_1d_mm": point.rainfall_1d_mm, "rainfall_3d_mm": point.rainfall_3d_mm,
                "rainfall_7d_mm": point.rainfall_7d_mm,
                "forecast_rainfall_24h_mm": point.forecast_rainfall_24h_mm,
                "forecast_rainfall_48h_mm": point.forecast_rainfall_48h_mm,
                "forecast_rainfall_72h_mm": point.forecast_rainfall_72h_mm,
                "soil_moisture_vwc_percent": round(point.soil_moisture_m3_m3 * 100, 1),
            },
        }


def data_sources(telemetry: dict[str, Any], exposure: dict[str, Any]) -> list[dict[str, str]]:
    weather_status = (f"Fresh at {telemetry['fetch_timestamp_utc']} · {telemetry['successful_location_count']} spatial source points" if telemetry["state"] == "fresh" else "Explicit simulation/demo values; not observations")
    return [
        {"source": "Static susceptibility score", "status": "Existing 7,390-cell uncalibrated model output; not probability", "type": "available"},
        {"source": "Open-Meteo Forecast API precipitation and soil moisture", "status": weather_status, "type": "available" if telemetry["state"] == "fresh" else "demo"},
        {"source": "Sentinel-2 L2A NDVI", "status": "Real satellite NDVI; missing observations remain unavailable", "type": "available"},
        {"source": "GEM active-fault proxy and OpenStreetMap drainage", "status": "Pinned/provenance-validated static distance features", "type": "available"},
        {
            "source": "OpenStreetMap roads and settlements",
            "status": (
                f"Exact GIS overlay · {exposure['road_feature_count']:,} road features and "
                f"{exposure['settlement_feature_count']:,} settlements processed"
            ),
            "type": "available",
        },
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
    inputs = load_static_inputs(repo_root)
    sampling_locations, sampling_grid = build_sampling_grid(inputs)
    try:
        points, telemetry = (
            fetch_realtime_sikkim_telemetry(sampling_locations, api_base_url, timeout_seconds)
            if mode == "live" else simulated_telemetry(mode, sampling_locations)
        )
    except TelemetryUnavailable as error:
        mark_live_failure(output, master, attempt.isoformat(), error)
        print(f"FAIL-CLOSED: {error}", file=sys.stderr)
        return False

    telemetry.update({
        "fetch_attempt_utc": attempt.isoformat(),
        "last_trusted_fetch_utc": telemetry["fetch_timestamp_utc"],
        "values_preserved_from_last_trusted_update": False,
        "sampling_grid": sampling_grid,
        "interpolation_method": f"{IDW_NEIGHBOURS}-nearest inverse-distance weighting in local approximate kilometres",
        "interpolation_neighbours": IDW_NEIGHBOURS,
        "interpolation_power": IDW_POWER,
        "weather_resolution_statement": "Spatially interpolated model/API samples; not native 1 km weather observations",
        "dynamic_trigger_index_version": DTI_VERSION,
        "dynamic_trigger_index_formula": "100 * (0.35*R1/100 + 0.25*R3/200 + 0.10*R7/350 + 0.20*scaled_soil_moisture + 0.10*forecast/horizon_threshold), with each component clipped to [0,1]",
        "operational_risk_index_version": ORI_VERSION,
        "operational_risk_index_formula": "0.65 * static_susceptibility + 0.35 * Dynamic Trigger Index",
    })
    weather = interpolate_weather(inputs, points)
    layer = build_operational_layer(inputs, weather)
    from exposure_engine import build_gis_exposure, write_exposure_artifacts

    exposure_payload, exposure_artifacts = build_gis_exposure(
        repo_root, layer, telemetry["fetch_timestamp_utc"]
    )
    cells = update_cells(master.get("riskCells", []), layer, telemetry["state"], len(points))
    display_ids = [str(cell["cell_id"]) for cell in cells]
    qa = build_run_qa(layer, display_ids)
    migrate_timeline_snapshots(master, inputs)
    counts = qa["category_counts"]
    master["riskCells"] = cells
    master["weather"] = weather_summary(layer, points, telemetry)
    master["roads"] = exposure_payload["roads"]
    master["settlements"] = exposure_payload["settlements"]
    master["emergencyPriorities"] = exposure_payload["emergencyPriorities"]
    master["alerts"] = exposure_payload["alerts"]
    master["dataSources"] = data_sources(telemetry, exposure_payload["metadata"])
    meta = master.setdefault("meta", {})
    meta.update({
        "system_status": "Operational Risk Index prototype · monitoring",
        "last_updated": telemetry["fetch_timestamp_utc"],
        "data_mode": "PROTOTYPE DECISION-SUPPORT INDEX",
        "index_name": "Operational Risk Index",
        "index_semantics": "0–100 prototype decision-support score combining static susceptibility and dynamic weather triggers; not a calibrated landslide probability",
        "index_thresholds": INDEX_THRESHOLDS,
        "forecast_semantics": "24h/48h/72h values are forecast-based risk indices, not observed events or guaranteed predictions",
        "telemetry": telemetry,
        "exposure": exposure_payload["metadata"],
        "input_validation": {
            "canonical_cell_count": EXPECTED_CELL_COUNT, "ordered_one_to_one_static_join": True,
            "interpolated_cell_count": qa["canonical_cells_interpolated"],
            "displayed_cell_count": qa["dashboard_cells_updated"],
            "missing_ndvi_canonical_cells": qa["cells_with_missing_ndvi"],
            "missing_ndvi_displayed_cells": qa["displayed_cells_with_missing_ndvi"],
            "real_fault_distance_canonical_cells": qa["cells_with_real_fault_distance"],
        },
        "summary": {
            "severe_risk_cells": counts["SEVERE"], "high_risk_cells": counts["HIGH"],
            "roads_at_risk": exposure_payload["summary"]["roads_at_risk"],
            "settlements_at_risk": exposure_payload["summary"]["settlements_at_risk"],
            "exposure_status": exposure_payload["summary"]["exposure_status"],
            "weather_trigger": f"{telemetry['source']} · median interpolated 1-day rain {master['weather']['rainfall_1d_mm']:.1f} mm · soil moisture {master['weather']['soil_moisture_vwc_percent']:.1f}% VWC",
        },
        "run_qa": qa,
    })
    write_exposure_artifacts(repo_root, exposure_artifacts, exposure_payload["metadata"])
    atomic_write_json(output, master)
    print(
        "Interpolated {canonical:,} canonical cells and updated {cells:,} dashboard cells atomically in {seconds:.2f}s · index {minimum:.1f}/{median:.1f}/{maximum:.1f} · "
        "LOW {low:,}, MODERATE {moderate:,}, HIGH {high:,}, SEVERE {severe:,}".format(
            canonical=qa["canonical_cells_interpolated"], cells=qa["dashboard_cells_updated"], seconds=time.time() - start,
            minimum=qa["operational_risk_index"]["min"], median=qa["operational_risk_index"]["median"], maximum=qa["operational_risk_index"]["max"],
            low=counts["LOW"], moderate=counts["MODERATE"], high=counts["HIGH"], severe=counts["SEVERE"],
        )
    )
    print(
        "GIS exposure · {road_features:,} OSM road features · {settlements:,} settlements · "
        "{road_entities:,} exposed road entities · {settlement_exposure:,} exposed settlements · "
        "P1 {p1:,}, P2 {p2:,}, P3 {p3:,}".format(
            road_features=exposure_payload["metadata"]["road_feature_count"],
            settlements=exposure_payload["metadata"]["settlement_feature_count"],
            road_entities=exposure_payload["metadata"]["road_entities_exposed_current"],
            settlement_exposure=exposure_payload["metadata"]["settlements_exposed_current"],
            p1=exposure_payload["metadata"]["priority_counts"]["P1"],
            p2=exposure_payload["metadata"]["priority_counts"]["P2"],
            p3=exposure_payload["metadata"]["priority_counts"]["P3"],
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
