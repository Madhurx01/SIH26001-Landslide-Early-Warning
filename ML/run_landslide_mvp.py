"""Build the SIH two-layer Sikkim landslide-risk MVP from local real data.

This script is intentionally self-contained and reads DATA/RAW without writing
to it. Static model outputs are susceptibility scores, and dynamic/final
outputs are engineering early-warning scores; none are calibrated landslide
probabilities.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import joblib
import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW = PROJECT_ROOT / "DATA" / "RAW"
PROCESSED = PROJECT_ROOT / "DATA" / "PROCESSED"

STATIC_PATH = PROCESSED / "FEATURES" / "sikkim_static_features_with_history.csv"
GRID_PATH = PROCESSED / "GRID" / "sikkim_grid_1km.gpkg"
DATED_EVENTS_PATH = PROCESSED / "LANDSLIDES" / "gsi_sikkim_dated_events.csv"
IMERG_DIR = RAW / "DYNAMIC" / "Rainfall" / "IMERG_2021"
SMAP_DIR = RAW / "DYNAMIC" / "Soil_Moisture" / "SMAP_2021"

DYNAMIC_DIR = PROCESSED / "DYNAMIC"
RISK_DIR = PROCESSED / "RISK"
MODEL_DIR = PROJECT_ROOT / "ML" / "models"
REPORT_DIR = PROJECT_ROOT / "ML" / "reports"

STATIC_OUTPUT = RISK_DIR / "static_susceptibility.csv"
DYNAMIC_OUTPUT = DYNAMIC_DIR / "sikkim_dynamic_features_2021.csv"
RISK_OUTPUT = RISK_DIR / "sikkim_landslide_risk_2021.csv"
DEMO_OUTPUT = RISK_DIR / "demo_risk.geojson"
EVENT_OUTPUT = REPORT_DIR / "event_validation_2021.csv"
EVENT_REPORT = REPORT_DIR / "event_validation_2021.json"
MODEL_OUTPUT = MODEL_DIR / "static_susceptibility_model.joblib"
METRICS_OUTPUT = REPORT_DIR / "static_model_metrics.json"
QA_OUTPUT = REPORT_DIR / "pipeline_qa.json"
RUN_SUMMARY_OUTPUT = REPORT_DIR / "run_summary.json"

START_DATE = pd.Timestamp("2021-05-11")
END_DATE = pd.Timestamp("2021-10-19")
EXPECTED_DATES = pd.date_range(START_DATE, END_DATE, freq="D")
RANDOM_STATE = 42
SPATIAL_BLOCK_M = 10_000.0

STATIC_FEATURES = [
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
    "lc_tree_fraction",
    "lc_shrub_fraction",
    "lc_grass_fraction",
    "lc_cropland_fraction",
    "lc_builtup_fraction",
    "lc_bare_fraction",
    "lc_snow_ice_fraction",
    "lc_water_fraction",
    "lc_wetland_fraction",
    "lc_moss_lichen_fraction",
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

DYNAMIC_WEIGHTS = {
    "rainfall_1d": 0.35,
    "rainfall_3d": 0.25,
    "rainfall_7d": 0.20,
    "soil_moisture": 0.20,
}
RISK_FORMULA = (
    "final_risk_score = 100 * (0.35*S + 0.25*D + 0.40*S*D), "
    "where S=static_susceptibility/100 and D=dynamic_trigger_score/100"
)
RISK_THRESHOLDS = {
    "LOW": "[0, 30)",
    "MODERATE": "[30, 50)",
    "HIGH": "[50, 70)",
    "SEVERE": "[70, 100]",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def json_value(value: Any) -> Any:
    """Convert common numpy/pandas values into strict JSON-compatible values."""
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def write_json(path: Path, payload: dict[str, Any], *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            json_value(payload),
            ensure_ascii=False,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def raw_manifest() -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in RAW.rglob("*") if item.is_file()):
        stat = path.stat()
        manifest[path.relative_to(PROJECT_ROOT).as_posix()] = {
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "sha256": sha256(path),
        }
    return manifest


def input_checks() -> None:
    required = [STATIC_PATH, GRID_PATH, DATED_EVENTS_PATH, IMERG_DIR, SMAP_DIR]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required inputs: {missing}")


def make_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            (
                "numeric",
                SimpleImputer(strategy="median", add_indicator=True),
                STATIC_FEATURES,
            )
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def build_static_models(y_train: pd.Series) -> dict[str, Pipeline]:
    positive = int(y_train.sum())
    negative = int(len(y_train) - positive)
    require(positive > 0 and negative > 0, "Static training split lacks a class")
    scale_pos_weight = negative / positive
    return {
        "random_forest": Pipeline(
            [
                ("preprocess", make_preprocessor()),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=600,
                        class_weight="balanced_subsample",
                        min_samples_leaf=2,
                        max_features="sqrt",
                        n_jobs=-1,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
        "xgboost": Pipeline(
            [
                ("preprocess", make_preprocessor()),
                (
                    "model",
                    XGBClassifier(
                        n_estimators=500,
                        learning_rate=0.04,
                        max_depth=4,
                        min_child_weight=2,
                        subsample=0.9,
                        colsample_bytree=0.9,
                        reg_lambda=2.0,
                        scale_pos_weight=scale_pos_weight,
                        eval_metric="logloss",
                        tree_method="hist",
                        n_jobs=-1,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
    }


def classification_metrics(y_true: pd.Series, score: np.ndarray) -> dict[str, Any]:
    prediction = (score >= 0.5).astype("int8")
    matrix = confusion_matrix(y_true, prediction, labels=[0, 1])
    return {
        "decision_threshold": 0.5,
        "precision": precision_score(y_true, prediction, zero_division=0),
        "recall": recall_score(y_true, prediction, zero_division=0),
        "f1": f1_score(y_true, prediction, zero_division=0),
        "pr_auc_average_precision": average_precision_score(y_true, score),
        "roc_auc": roc_auc_score(y_true, score),
        "accuracy_secondary": accuracy_score(y_true, prediction),
        "confusion_matrix": {
            "labels": [0, 1],
            "matrix": matrix.tolist(),
            "tn": int(matrix[0, 0]),
            "fp": int(matrix[0, 1]),
            "fn": int(matrix[1, 0]),
            "tp": int(matrix[1, 1]),
        },
    }


def train_static_layer(static: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    require(static["cell_id"].is_unique, "Static cell IDs are not unique")
    require(set(static["historically_affected"].unique()) <= {0, 1}, "Bad labels")
    require(set(STATIC_FEATURES) <= set(static.columns), "Static features are missing")

    static = static.copy()
    static[STATIC_FEATURES] = static[STATIC_FEATURES].replace([np.inf, -np.inf], np.nan)
    y = static["historically_affected"].astype("int8")
    block_x = np.floor(static["centroid_x"] / SPATIAL_BLOCK_M).astype("int64")
    block_y = np.floor(static["centroid_y"] / SPATIAL_BLOCK_M).astype("int64")
    groups = block_x.astype(str) + "_" + block_y.astype(str)

    outer_splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    development_index, test_index = next(outer_splitter.split(static, y, groups=groups))
    development_groups = groups.iloc[development_index]
    development_y = y.iloc[development_index]

    inner_splitter = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=RANDOM_STATE + 1)
    train_relative, validation_relative = next(
        inner_splitter.split(
            static.iloc[development_index],
            development_y,
            groups=development_groups,
        )
    )
    train_index = development_index[train_relative]
    validation_index = development_index[validation_relative]

    train_groups = set(groups.iloc[train_index])
    validation_groups = set(groups.iloc[validation_index])
    test_groups = set(groups.iloc[test_index])
    require(train_groups.isdisjoint(validation_groups), "Train/validation block leakage")
    require(train_groups.isdisjoint(test_groups), "Train/test block leakage")
    require(validation_groups.isdisjoint(test_groups), "Validation/test block leakage")

    y_train = y.iloc[train_index]
    y_validation = y.iloc[validation_index]
    y_test = y.iloc[test_index]
    require(
        y_train.nunique() == y_validation.nunique() == y_test.nunique() == 2,
        "A train/validation/test split lacks a class",
    )

    candidates = build_static_models(y_train)
    validation_metrics: dict[str, Any] = {}
    for name, model in candidates.items():
        print(f"Training static model for validation: {name}")
        model.fit(static.iloc[train_index], y_train)
        validation_score = model.predict_proba(static.iloc[validation_index])[:, 1]
        validation_metrics[name] = classification_metrics(y_validation, validation_score)

    selected_name = max(
        validation_metrics,
        key=lambda name: (
            validation_metrics[name]["pr_auc_average_precision"],
            validation_metrics[name]["recall"],
            validation_metrics[name]["f1"],
        ),
    )
    print(f"Selected static model from validation only: {selected_name}")

    test_model = build_static_models(y_train)[selected_name]
    test_model.fit(static.iloc[train_index], y_train)
    untouched_test_score = test_model.predict_proba(static.iloc[test_index])[:, 1]
    test_metrics = classification_metrics(y_test, untouched_test_score)

    final_model = build_static_models(development_y)[selected_name]
    final_model.fit(static.iloc[development_index], development_y)
    all_scores = np.clip(final_model.predict_proba(static)[:, 1] * 100.0, 0.0, 100.0)
    output = static[
        [
            "cell_id",
            "centroid_lon",
            "centroid_lat",
            "analysis_lon",
            "analysis_lat",
            "historically_affected",
        ]
    ].copy()
    output["static_susceptibility"] = all_scores
    output["score_semantics"] = "uncalibrated susceptibility score; not probability"

    model_payload = {
        "pipeline": final_model,
        "selected_model": selected_name,
        "feature_columns": STATIC_FEATURES,
        "score_semantics": "uncalibrated susceptibility score; not probability",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_scope": "train + validation; untouched test excluded",
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_payload, MODEL_OUTPUT)

    report = {
        "score_semantics": "uncalibrated susceptibility score; not probability",
        "target_semantics": {
            "positive": "cell present in the available GSI inventory",
            "zero": "background/pseudo-negative; not confirmed landslide-free",
        },
        "features": STATIC_FEATURES,
        "target_distribution": {
            "rows": len(static),
            "positive_affected_cells": int(y.sum()),
            "background_pseudo_negative_cells": int((y == 0).sum()),
            "positive_fraction": float(y.mean()),
        },
        "evaluation_design": {
            "method": "nested deterministic spatial-group train/validation/untouched-test split",
            "spatial_block_size_m": SPATIAL_BLOCK_M,
            "outer_test_split": "first fold of shuffled 5-fold stratified group split",
            "inner_validation_split": "first fold of shuffled 4-fold stratified group split within outer development rows",
            "selection_data": "validation only",
            "test_usage": "selected model evaluated exactly once; never used for model selection",
            "refit_scope": "train + validation after untouched test evaluation",
            "limitation": (
                "Inventory-derived pseudo-negatives and spatial sampling bias remain; "
                "this is not independent prospective validation."
            ),
        },
        "splits": {
            "train": {
                "rows": len(train_index),
                "positive": int(y_train.sum()),
                "groups": len(train_groups),
            },
            "validation": {
                "rows": len(validation_index),
                "positive": int(y_validation.sum()),
                "groups": len(validation_groups),
            },
            "test": {
                "rows": len(test_index),
                "positive": int(y_test.sum()),
                "groups": len(test_groups),
                "untouched_until_after_selection": True,
            },
            "group_overlap": {
                "train_validation": len(train_groups & validation_groups),
                "train_test": len(train_groups & test_groups),
                "validation_test": len(validation_groups & test_groups),
            },
        },
        "validation_metrics": validation_metrics,
        "selected_model": selected_name,
        "selection_rule": "highest validation PR-AUC, then recall, then F1",
        "test_metrics": test_metrics,
        "test_metrics_semantics": "untouched spatial-group test metrics for the selected model",
        "model_path": str(MODEL_OUTPUT.relative_to(PROJECT_ROOT)),
    }
    return output, report


def dated_files(directory: Path, glob_pattern: str, regex: str) -> dict[pd.Timestamp, Path]:
    result: dict[pd.Timestamp, Path] = {}
    for path in sorted(directory.glob(glob_pattern)):
        match = re.search(regex, path.name)
        if not match:
            continue
        date = pd.to_datetime(match.group(1), format="%Y%m%d")
        if START_DATE <= date <= END_DATE:
            require(date not in result, f"Duplicate source date {date.date()} in {directory}")
            result[date] = path
    require(set(result) == set(EXPECTED_DATES), f"Incomplete dates in {directory}")
    return result


def subdataset(path: Path, ending: str) -> str:
    with rasterio.open(path) as root:
        matches = [item for item in root.subdatasets if item.endswith(ending)]
    require(len(matches) == 1, f"Expected one {ending} subdataset in {path}, got {matches}")
    return matches[0]


def read_array(path: Path, ending: str) -> tuple[np.ndarray, dict[str, str], Any]:
    uri = subdataset(path, ending)
    with rasterio.open(uri) as source:
        masked = source.read(1, masked=True).astype("float64")
        data = masked.filled(np.nan)
        return data, source.tags(), source.transform


def nearest_mapping(
    source_lon: np.ndarray,
    source_lat: np.ndarray,
    target_lon: np.ndarray,
    target_lat: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    flat_lon = source_lon.ravel()
    flat_lat = source_lat.ravel()
    finite = np.isfinite(flat_lon) & np.isfinite(flat_lat)
    source_indices = np.flatnonzero(finite)
    require(len(source_indices) > 0, "No finite satellite geolocation pixels")
    tree = cKDTree(np.column_stack([flat_lon[finite], flat_lat[finite]]))
    distance, local_index = tree.query(np.column_stack([target_lon, target_lat]), k=1)
    return source_indices[local_index], distance, source_indices


def imerg_layout(path: Path, target_lon: np.ndarray, target_lat: np.ndarray) -> dict[str, Any]:
    rainfall, tags, transform = read_array(path, ":precipitation")
    rows, cols = np.indices(rainfall.shape)
    axis_x, axis_y = rasterio.transform.xy(transform, rows, cols, offset="center")
    axis_x = np.asarray(axis_x, dtype="float64")
    axis_y = np.asarray(axis_y, dtype="float64")
    # IMERG's NetCDF dimension order can be lat/lon rather than the x/y order
    # assumed by GDAL's generic transform. Select the interpretation that is
    # geographically nearest to the known Sikkim analysis points.
    candidates = []
    for axis_order, lon, lat in [
        ("x=longitude,y=latitude", axis_x, axis_y),
        ("x=latitude,y=longitude", axis_y, axis_x),
    ]:
        mapping, distance, finite_indices = nearest_mapping(lon, lat, target_lon, target_lat)
        candidates.append((float(np.max(distance)), axis_order, lon, lat, mapping, distance, finite_indices))
    _, axis_order, lon, lat, mapping, distance, finite_indices = min(candidates, key=lambda item: item[0])
    require(float(np.max(distance)) < 0.20, "IMERG nearest pixel is unexpectedly distant")
    return {
        "shape": rainfall.shape,
        "lon": lon,
        "lat": lat,
        "mapping": mapping,
        "distance": distance,
        "finite_indices": finite_indices,
        "units": tags.get("precipitation#units", "mm/day"),
        "axis_order": axis_order,
    }


def smap_layout(path: Path, target_lon: np.ndarray, target_lat: np.ndarray) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for orbit, lat_name, lon_name in [
        ("am", "/Soil_Moisture_Retrieval_Data_AM/latitude", "/Soil_Moisture_Retrieval_Data_AM/longitude"),
        ("pm", "/Soil_Moisture_Retrieval_Data_PM/latitude_pm", "/Soil_Moisture_Retrieval_Data_PM/longitude_pm"),
    ]:
        lat, _, _ = read_array(path, lat_name)
        lon, _, _ = read_array(path, lon_name)
        require(lat.shape == lon.shape, f"SMAP {orbit.upper()} geolocation shape mismatch")
        if not (np.isfinite(lat).any() and np.isfinite(lon).any()):
            am_layout = result.get("am")
            if (
                orbit == "pm"
                and am_layout is not None
                and am_layout.get("geolocation_available", False)
                and lat.shape == am_layout["shape"]
            ):
                result[orbit] = {
                    **am_layout,
                    "shape": lat.shape,
                    "geolocation_fallback": (
                        "PM latitude/longitude arrays are fill-only; corresponding AM "
                        "EASE2 grid coordinates used for the same array indices"
                    ),
                }
            else:
                result[orbit] = {
                    "shape": lat.shape,
                    "geolocation_available": False,
                    "geolocation_fallback": None,
                }
            continue
        mapping, distance, finite_indices = nearest_mapping(lon, lat, target_lon, target_lat)
        if not bool(np.any(distance < 0.20)):
            result[orbit] = {
                "shape": lat.shape,
                "geolocation_available": False,
                "geolocation_fallback": None,
            }
            continue
        result[orbit] = {
            "shape": lat.shape,
            "lat": lat,
            "lon": lon,
            "mapping": mapping,
            "distance": distance,
            "finite_indices": finite_indices,
            "geolocation_available": True,
            "geolocation_fallback": None,
        }
    return result

def same_geolocation(reference: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return (
        reference["shape"] == candidate["shape"]
        and np.allclose(reference["lon"], candidate["lon"], equal_nan=True)
        and np.allclose(reference["lat"], candidate["lat"], equal_nan=True)
    )


def scaled_component(values: np.ndarray, lower_q: float = 0.05, upper_q: float = 0.95) -> tuple[np.ndarray, dict[str, float]]:
    finite = values[np.isfinite(values)]
    require(len(finite) > 0, "Cannot scale an all-missing dynamic component")
    lower, upper = np.quantile(finite, [lower_q, upper_q])
    require(upper > lower, "Dynamic component percentile range collapsed")
    scaled = np.clip((values - lower) / (upper - lower), 0.0, 1.0)
    return scaled, {
        "lower_percentile": lower_q * 100.0,
        "lower_value": float(lower),
        "upper_percentile": upper_q * 100.0,
        "upper_value": float(upper),
    }


def rolling_sum(values: np.ndarray, window: int) -> np.ndarray:
    frame = pd.DataFrame(values)
    return frame.rolling(window=window, min_periods=1).sum().to_numpy(dtype="float64")


def build_dynamic_layer(static_scores: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    imerg_files = dated_files(IMERG_DIR, "3B-DAY*.nc4", r"\.(\d{8})-S")
    smap_files = dated_files(SMAP_DIR, "SMAP_L3_SM_P_E_*_subsetted.nc4", r"_(\d{8})_")
    dates = EXPECTED_DATES
    target_lon = static_scores["analysis_lon"].to_numpy(dtype="float64")
    target_lat = static_scores["analysis_lat"].to_numpy(dtype="float64")
    n_dates = len(dates)
    n_cells = len(static_scores)

    first_imerg = imerg_layout(imerg_files[dates[0]], target_lon, target_lat)
    first_smap = smap_layout(smap_files[dates[0]], target_lon, target_lat)
    require(
        all(layout.get("geolocation_available", False) for layout in first_smap.values()),
        "Reference SMAP file must provide usable AM/PM geolocation",
    )
    rainfall = np.full((n_dates, n_cells), np.nan, dtype="float64")
    soil_am = np.full_like(rainfall, np.nan)
    soil_pm = np.full_like(rainfall, np.nan)
    quality_am = np.full_like(rainfall, np.nan)
    quality_pm = np.full_like(rainfall, np.nan)
    smap_files_checked = 0
    smap_geolocation_consistent_count = 0
    smap_geolocation_remapped_count = 0
    smap_geolocation_unavailable_count = 0

    for date_index, date in enumerate(dates):
        rain_array, _, transform = read_array(imerg_files[date], ":precipitation")
        require(rain_array.shape == first_imerg["shape"], f"IMERG shape changed on {date.date()}")
        rows, cols = np.indices(rain_array.shape)
        axis_x, axis_y = rasterio.transform.xy(transform, rows, cols, offset="center")
        if first_imerg["axis_order"] == "x=longitude,y=latitude":
            lon, lat = axis_x, axis_y
        else:
            lon, lat = axis_y, axis_x
        current_layout = {
            "shape": rain_array.shape,
            "lon": np.asarray(lon),
            "lat": np.asarray(lat),
        }
        require(same_geolocation(first_imerg, current_layout), f"IMERG grid changed on {date.date()}")
        mapped_rain = rain_array.ravel()[first_imerg["mapping"]]
        mapped_rain[mapped_rain < 0] = np.nan
        rainfall[date_index] = mapped_rain

        smap_path = smap_files[date]
        current_smap = first_smap if date_index == 0 else smap_layout(
            smap_path, target_lon, target_lat
        )
        file_was_remapped = False
        file_had_unavailable_geolocation = False
        for orbit, sm_name, q_name in [
            ("am", "/Soil_Moisture_Retrieval_Data_AM/soil_moisture", "/Soil_Moisture_Retrieval_Data_AM/retrieval_qual_flag"),
            ("pm", "/Soil_Moisture_Retrieval_Data_PM/soil_moisture_pm", "/Soil_Moisture_Retrieval_Data_PM/retrieval_qual_flag_pm"),
        ]:
            sm, _, _ = read_array(smap_path, sm_name)
            quality, _, _ = read_array(smap_path, q_name)
            reference_layout = first_smap[orbit]
            daily_layout = current_smap[orbit]
            require(
                sm.shape == daily_layout["shape"] == quality.shape,
                f"SMAP {orbit} shape changed on {date.date()}",
            )

            if not daily_layout.get("geolocation_available", False):
                mapped_sm = np.full(n_cells, np.nan, dtype="float64")
                mapped_q = np.full(n_cells, np.nan, dtype="float64")
                file_had_unavailable_geolocation = True
            else:
                coordinates_match = same_geolocation(reference_layout, daily_layout)
                layout = reference_layout if coordinates_match else daily_layout
                file_was_remapped = file_was_remapped or not coordinates_match
                mapped_sm = sm.ravel()[layout["mapping"]]
                mapped_q = quality.ravel()[layout["mapping"]]
                within_mapping_distance = layout["distance"] < 0.20
                mapped_sm[~within_mapping_distance] = np.nan
                mapped_q[~within_mapping_distance] = np.nan

            # The SMAP product specification identifies decimal flag values 0
            # and 8 as recommended-quality soil-moisture retrievals.
            recommended = np.isfinite(mapped_q) & np.isin(mapped_q, [0.0, 8.0])
            physically_valid = np.isfinite(mapped_sm) & (mapped_sm >= 0.0) & (mapped_sm <= 1.0)
            mapped_sm[~(recommended & physically_valid)] = np.nan
            if orbit == "am":
                soil_am[date_index] = mapped_sm
                quality_am[date_index] = mapped_q
            else:
                soil_pm[date_index] = mapped_sm
                quality_pm[date_index] = mapped_q

        smap_files_checked += 1
        if file_had_unavailable_geolocation:
            smap_geolocation_unavailable_count += 1
        elif file_was_remapped:
            smap_geolocation_remapped_count += 1
        else:
            smap_geolocation_consistent_count += 1

        if (date_index + 1) % 25 == 0 or date_index + 1 == n_dates:
            print(f"Dynamic extraction: {date_index + 1}/{n_dates} dates")

    require(np.isfinite(rainfall).all(), "IMERG has missing mapped cell-days")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        soil = np.nanmean(np.stack([soil_am, soil_pm]), axis=0)
    rain_3d = rolling_sum(rainfall, 3)
    rain_7d = rolling_sum(rainfall, 7)

    components: dict[str, np.ndarray] = {}
    scaling: dict[str, dict[str, float]] = {}
    for name, values in {
        "rainfall_1d": rainfall,
        "rainfall_3d": rain_3d,
        "rainfall_7d": rain_7d,
        "soil_moisture": soil,
    }.items():
        components[name], scaling[name] = scaled_component(values)

    weighted_sum = np.zeros_like(rainfall)
    available_weight = np.zeros_like(rainfall)
    for name, weight in DYNAMIC_WEIGHTS.items():
        valid = np.isfinite(components[name])
        weighted_sum[valid] += weight * components[name][valid]
        available_weight[valid] += weight
    require((available_weight >= 0.80).all(), "Too few dynamic components for a trigger score")
    dynamic_trigger = np.clip(100.0 * weighted_sum / available_weight, 0.0, 100.0)

    date_values = np.repeat(dates.to_numpy(dtype="datetime64[D]"), n_cells)
    cell_values = np.tile(static_scores["cell_id"].to_numpy(), n_dates)
    imerg_pixel = np.tile(first_imerg["mapping"].astype("int32"), n_dates)
    smap_am_pixel = np.tile(first_smap["am"]["mapping"].astype("int32"), n_dates)
    smap_pm_pixel = np.tile(first_smap["pm"]["mapping"].astype("int32"), n_dates)
    rain_3d_days = np.repeat(np.minimum(np.arange(1, n_dates + 1), 3), n_cells)
    rain_7d_days = np.repeat(np.minimum(np.arange(1, n_dates + 1), 7), n_cells)

    dynamic = pd.DataFrame(
        {
            "cell_id": cell_values,
            "date": date_values,
            "imerg_pixel_id": imerg_pixel,
            "smap_am_pixel_id": smap_am_pixel,
            "smap_pm_pixel_id": smap_pm_pixel,
            "rainfall_1d": rainfall.ravel(),
            "rainfall_3d": rain_3d.ravel(),
            "rainfall_7d": rain_7d.ravel(),
            "rainfall_3d_days_available": rain_3d_days,
            "rainfall_7d_days_available": rain_7d_days,
            "soil_moisture_am": soil_am.ravel(),
            "soil_moisture_pm": soil_pm.ravel(),
            "soil_moisture": soil.ravel(),
            "soil_moisture_am_quality_flag": quality_am.ravel(),
            "soil_moisture_pm_quality_flag": quality_pm.ravel(),
            "dynamic_trigger_score": dynamic_trigger.ravel(),
        }
    )
    dynamic["date"] = pd.to_datetime(dynamic["date"])

    metadata = {
        "rows": len(dynamic),
        "cells": n_cells,
        "dates": n_dates,
        "date_min": dates.min(),
        "date_max": dates.max(),
        "imerg": {
            "product": "NASA GPM IMERG daily precipitation",
            "units": first_imerg["units"],
            "native_grid_shape_in_subset": list(first_imerg["shape"]),
            "native_resolution": "0.1 degree (approximately 10 km; not 1 km)",
            "unique_native_pixels_mapped_to_1km_cells": int(np.unique(first_imerg["mapping"]).size),
            "maximum_nearest_mapping_distance_degrees": float(first_imerg["distance"].max()),
        },
        "smap": {
            "product": "NASA SMAP L3 enhanced soil moisture",
            "native_resolution": "approximately 9 km; not 1 km",
            "am_native_grid_shape_in_subset": list(first_smap["am"]["shape"]),
            "pm_native_grid_shape_in_subset": list(first_smap["pm"]["shape"]),
            "am_unique_native_pixels_mapped_to_1km_cells": int(np.unique(first_smap["am"]["mapping"]).size),
            "pm_unique_native_pixels_mapped_to_1km_cells": int(np.unique(first_smap["pm"]["mapping"]).size),
            "pm_geolocation_fallback": first_smap["pm"]["geolocation_fallback"],
            "quality_filter": "retrieval_qual_flag must be 0 or 8; soil moisture constrained to [0,1]",
            "daily_representative": "mean of valid AM and PM; valid single orbit used when only one is available",
            "smap_files_checked": smap_files_checked,
            "smap_geolocation_consistent_count": smap_geolocation_consistent_count,
            "smap_geolocation_remapped_count": smap_geolocation_remapped_count,
            "smap_geolocation_unavailable_count": smap_geolocation_unavailable_count,
            "geolocation_verification": "shape and latitude/longitude coordinate order checked for every daily file; orbits with unavailable geolocation are left missing",
        },
        "rolling_rainfall": (
            "calendar-day sums; the first 2/6 dates use available-period partial 3d/7d windows "
            "and days_available columns make this left-censoring explicit"
        ),
        "trigger_formula": (
            "0-100 weighted mean of P5-P95 clipped components: "
            "35% rainfall_1d + 25% rainfall_3d + 20% rainfall_7d + 20% soil_moisture; "
            "weights are renormalized if a quality-filtered soil value is unavailable"
        ),
        "scaling_cutpoints": scaling,
        "score_semantics": "engineering early-warning trigger score; not calibrated probability",
    }
    return dynamic, metadata


def risk_level(score: pd.Series) -> pd.Categorical:
    return pd.cut(
        score,
        bins=[-np.inf, 30.0, 50.0, 70.0, np.inf],
        labels=["LOW", "MODERATE", "HIGH", "SEVERE"],
        right=False,
        ordered=True,
    )


def build_risk_table(dynamic: pd.DataFrame, static_scores: pd.DataFrame) -> pd.DataFrame:
    risk = dynamic[["cell_id", "date", "dynamic_trigger_score"]].merge(
        static_scores[["cell_id", "static_susceptibility"]],
        on="cell_id",
        how="left",
        validate="many_to_one",
    )
    require(risk["static_susceptibility"].notna().all(), "Risk table lost static scores")
    susceptibility = risk["static_susceptibility"] / 100.0
    trigger = risk["dynamic_trigger_score"] / 100.0
    risk["final_risk_score"] = np.clip(
        100.0 * (0.35 * susceptibility + 0.25 * trigger + 0.40 * susceptibility * trigger),
        0.0,
        100.0,
    )
    risk["risk_level"] = risk_level(risk["final_risk_score"])
    return risk[
        [
            "cell_id",
            "date",
            "static_susceptibility",
            "dynamic_trigger_score",
            "final_risk_score",
            "risk_level",
        ]
    ]


def validate_events(
    dynamic: pd.DataFrame,
    risk: pd.DataFrame,
    static_scores: pd.DataFrame,
    static_source: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any], pd.Timestamp]:
    events = pd.read_csv(DATED_EVENTS_PATH)
    events["event_date"] = pd.to_datetime(events["event_date"], errors="raise")
    in_window = events["event_date"].between(START_DATE, END_DATE, inclusive="both")
    events = events.loc[in_window].copy()
    require((events["temporal_type"] == "exact_date").all(), "Non-exact dated event leaked")
    require(events["cell_id"].notna().all(), "An in-window event is missing a cell")

    dynamic_subset = dynamic[
        dynamic.set_index(["cell_id", "date"]).index.isin(
            pd.MultiIndex.from_frame(events[["cell_id", "event_date"]])
        )
    ].rename(columns={"date": "event_date"})
    event_rows = events.merge(
        dynamic_subset,
        on=["cell_id", "event_date"],
        how="left",
        validate="many_to_one",
    ).merge(
        risk.rename(columns={"date": "event_date"}),
        on=["cell_id", "event_date", "dynamic_trigger_score"],
        how="left",
        validate="many_to_one",
    )
    require(event_rows["final_risk_score"].notna().all(), "Event join lost risk values")

    background_ids = set(
        static_source.loc[static_source["historically_affected"].eq(0), "cell_id"]
    )
    comparison_columns = [
        "rainfall_1d",
        "rainfall_3d",
        "rainfall_7d",
        "soil_moisture",
        "dynamic_trigger_score",
        "static_susceptibility",
        "final_risk_score",
    ]
    comparison_source = dynamic.merge(
        risk[
            ["cell_id", "date", "static_susceptibility", "final_risk_score"]
        ],
        on=["cell_id", "date"],
        validate="one_to_one",
    )
    comparison_source = comparison_source[
        comparison_source["cell_id"].isin(background_ids)
        & comparison_source["date"].isin(events["event_date"].unique())
    ]
    background_medians = (
        comparison_source.groupby("date")[comparison_columns]
        .median()
        .add_prefix("same_date_background_median_")
        .reset_index()
        .rename(columns={"date": "event_date"})
    )
    event_rows = event_rows.merge(background_medians, on="event_date", validate="many_to_one")

    demo_by_date = event_rows.groupby("event_date")["final_risk_score"].max()
    demo_date = demo_by_date.idxmax()
    report = {
        "validation_type": "preliminary event-based validation; small exact-date sample",
        "source_exact_dated_rows_all_years": len(pd.read_csv(DATED_EVENTS_PATH)),
        "window": {"start": START_DATE, "end": END_DATE},
        "valid_2021_event_records": len(event_rows),
        "unique_event_dates": int(event_rows["event_date"].nunique()),
        "unique_event_cells": int(event_rows["cell_id"].nunique()),
        "event_dates": sorted(event_rows["event_date"].dt.strftime("%Y-%m-%d").unique().tolist()),
        "event_cells": sorted(event_rows["cell_id"].unique().tolist()),
        "event_summary": {
            column: {
                "mean": float(event_rows[column].mean()),
                "median": float(event_rows[column].median()),
                "min": float(event_rows[column].min()),
                "max": float(event_rows[column].max()),
            }
            for column in comparison_columns
        },
        "background_comparison": (
            "Each event row includes the median across all inventory-background/pseudo-negative "
            "cells on that exact date; these are not confirmed landslide-free controls."
        ),
        "demo_date_selection": "in-window GSI event date with highest event-cell final risk",
        "demo_date": demo_date,
        "limitations": [
            "Only exact GSI dates inside the real satellite window are used.",
            "The sample is too small for claims of calibration or operational sensitivity.",
            "Inventory background cells are pseudo-negatives and observation effort is spatially biased.",
            "Satellite values are coarse observations assigned to 1-km analysis cells, not downscaled measurements.",
        ],
    }
    return event_rows, report, demo_date


def create_demo_geojson(
    risk: pd.DataFrame,
    static_scores: pd.DataFrame,
    demo_date: pd.Timestamp,
) -> None:
    demo = risk.loc[risk["date"].eq(demo_date)].merge(
        static_scores[["cell_id", "analysis_lon", "analysis_lat"]],
        on="cell_id",
        validate="one_to_one",
    )
    features = []
    for row in demo.itertuples(index=False):
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(float(row.analysis_lon), 5), round(float(row.analysis_lat), 5)],
                },
                "properties": {
                    "cell_id": row.cell_id,
                    "date": demo_date.strftime("%Y-%m-%d"),
                    "static_susceptibility": round(float(row.static_susceptibility), 2),
                    "dynamic_trigger_score": round(float(row.dynamic_trigger_score), 2),
                    "final_risk_score": round(float(row.final_risk_score), 2),
                    "risk_level": str(row.risk_level),
                },
            }
        )
    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "demo_date": demo_date.strftime("%Y-%m-%d"),
            "feature_geometry": "1-km analysis-cell representative points",
            "dynamic_source_resolution": "IMERG 0.1 degree and SMAP approximately 9 km; not 1 km",
            "score_semantics": "engineering risk score; not calibrated probability",
        },
        "features": features,
    }
    write_json(DEMO_OUTPUT, payload, compact=True)


def dataframe_missing(frame: pd.DataFrame) -> dict[str, int]:
    return {column: int(count) for column, count in frame.isna().sum().items() if count}


def final_qa(
    raw_before: dict[str, dict[str, Any]],
    raw_after: dict[str, dict[str, Any]],
    static_source: pd.DataFrame,
    static_scores: pd.DataFrame,
    dynamic: pd.DataFrame,
    risk: pd.DataFrame,
    events: pd.DataFrame,
    dynamic_report: dict[str, Any],
) -> dict[str, Any]:
    raw_unchanged = raw_before == raw_after
    expected_rows = len(static_source) * len(EXPECTED_DATES)
    duplicate_dynamic = int(dynamic.duplicated(["cell_id", "date"]).sum())
    duplicate_risk = int(risk.duplicated(["cell_id", "date"]).sum())
    require(raw_unchanged, "A DATA/RAW file changed during the pipeline")
    require(len(static_source) == len(static_scores) == 7390, "Unexpected grid-cell count")
    require(len(dynamic) == len(risk) == expected_rows, "Unexpected cell-day row count")
    require(duplicate_dynamic == duplicate_risk == 0, "Duplicate cell-date rows found")
    require(dynamic["date"].min() == START_DATE and dynamic["date"].max() == END_DATE, "Bad date range")
    require(dynamic["date"].dt.year.eq(2021).all(), "Out-of-year dynamic data leaked")
    require(risk["final_risk_score"].between(0, 100, inclusive="both").all(), "Risk out of range")
    require(risk["risk_level"].notna().all(), "Missing risk levels")
    require(dynamic["dynamic_trigger_score"].notna().all(), "Missing trigger scores")
    require(events["event_date"].between(START_DATE, END_DATE, inclusive="both").all(), "Bad event date")
    smap_report = dynamic_report["smap"]
    require(smap_report["smap_files_checked"] == len(EXPECTED_DATES), "Not every SMAP file was checked")
    require(
        smap_report["smap_geolocation_consistent_count"]
        + smap_report["smap_geolocation_remapped_count"]
        + smap_report["smap_geolocation_unavailable_count"]
        == len(EXPECTED_DATES),
        "SMAP geolocation QA counts do not reconcile",
    )

    changed_paths = sorted(
        set(raw_before).symmetric_difference(raw_after)
        | {path for path in set(raw_before) & set(raw_after) if raw_before[path] != raw_after[path]}
    )
    return {
        "passed": True,
        "raw_immutability": {
            "unchanged": raw_unchanged,
            "files_before": len(raw_before),
            "files_after": len(raw_after),
            "changed_paths": changed_paths,
            "verification": "path, size, mtime_ns, and SHA-256 compared before vs after",
        },
        "static": {
            "rows": len(static_source),
            "unique_cells": int(static_source["cell_id"].nunique()),
            "target_distribution": static_source["historically_affected"].value_counts().sort_index().to_dict(),
            "input_missing": dataframe_missing(static_source[STATIC_FEATURES]),
            "output_missing": dataframe_missing(static_scores),
            "susceptibility_range": [
                float(static_scores["static_susceptibility"].min()),
                float(static_scores["static_susceptibility"].max()),
            ],
        },
        "dynamic": {
            "rows": len(dynamic),
            "expected_rows": expected_rows,
            "unique_cells": int(dynamic["cell_id"].nunique()),
            "unique_dates": int(dynamic["date"].nunique()),
            "date_min": dynamic["date"].min(),
            "date_max": dynamic["date"].max(),
            "duplicate_cell_dates": duplicate_dynamic,
            "missing": dataframe_missing(dynamic),
            "smap_files_checked": smap_report["smap_files_checked"],
            "smap_geolocation_consistent_count": smap_report["smap_geolocation_consistent_count"],
            "smap_geolocation_remapped_count": smap_report["smap_geolocation_remapped_count"],
            "smap_geolocation_unavailable_count": smap_report["smap_geolocation_unavailable_count"],
            "trigger_range": [
                float(dynamic["dynamic_trigger_score"].min()),
                float(dynamic["dynamic_trigger_score"].max()),
            ],
        },
        "risk": {
            "rows": len(risk),
            "duplicate_cell_dates": duplicate_risk,
            "missing": dataframe_missing(risk),
            "score_range": [float(risk["final_risk_score"].min()), float(risk["final_risk_score"].max())],
            "level_counts": risk["risk_level"].value_counts().to_dict(),
        },
        "events": {
            "valid_records": len(events),
            "unique_dates": int(events["event_date"].nunique()),
            "unique_cells": int(events["cell_id"].nunique()),
            "missing": dataframe_missing(events),
            "all_inside_window": True,
        },
    }


def main() -> None:
    input_checks()
    for directory in [DYNAMIC_DIR, RISK_DIR, MODEL_DIR, REPORT_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    print("Hashing DATA/RAW before run...")
    raw_before = raw_manifest()
    static_source = pd.read_csv(STATIC_PATH)

    static_scores, model_report = train_static_layer(static_source)
    static_scores.to_csv(STATIC_OUTPUT, index=False, float_format="%.6f")
    write_json(METRICS_OUTPUT, model_report)

    dynamic, dynamic_report = build_dynamic_layer(static_scores)
    dynamic.to_csv(DYNAMIC_OUTPUT, index=False, date_format="%Y-%m-%d", float_format="%.6f")

    risk = build_risk_table(dynamic, static_scores)
    risk.to_csv(RISK_OUTPUT, index=False, date_format="%Y-%m-%d", float_format="%.6f")

    event_rows, event_report, demo_date = validate_events(dynamic, risk, static_scores, static_source)
    event_rows.to_csv(EVENT_OUTPUT, index=False, date_format="%Y-%m-%d", float_format="%.6f")
    write_json(EVENT_REPORT, event_report)
    create_demo_geojson(risk, static_scores, demo_date)

    print("Hashing DATA/RAW after run...")
    raw_after = raw_manifest()
    qa = final_qa(
        raw_before,
        raw_after,
        static_source,
        static_scores,
        dynamic,
        risk,
        event_rows,
        dynamic_report,
    )
    write_json(QA_OUTPUT, qa)

    outputs = [
        STATIC_OUTPUT,
        DYNAMIC_OUTPUT,
        RISK_OUTPUT,
        DEMO_OUTPUT,
        EVENT_OUTPUT,
        EVENT_REPORT,
        MODEL_OUTPUT,
        METRICS_OUTPUT,
        QA_OUTPUT,
        RUN_SUMMARY_OUTPUT,
    ]
    summary = {
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "outputs": [str(path.relative_to(PROJECT_ROOT)) for path in outputs],
        "dimensions": {
            "static_rows": len(static_scores),
            "dynamic_rows": len(dynamic),
            "risk_rows": len(risk),
            "grid_cells": int(static_scores["cell_id"].nunique()),
            "dynamic_dates": int(dynamic["date"].nunique()),
        },
        "selected_static_model": model_report["selected_model"],
        "static_model_validation_metrics": model_report["validation_metrics"],
        "static_model_test_metrics": model_report["test_metrics"],
        "valid_2021_gsi_events": event_report["valid_2021_event_records"],
        "unique_2021_gsi_event_dates": event_report["unique_event_dates"],
        "dynamic_date_range": [START_DATE, END_DATE],
        "dynamic": dynamic_report,
        "risk_formula": RISK_FORMULA,
        "risk_thresholds": RISK_THRESHOLDS,
        "threshold_semantics": "MVP operational categories, not scientifically calibrated thresholds",
        "demo_date": demo_date,
        "qa_passed": qa["passed"],
        "raw_unchanged": qa["raw_immutability"]["unchanged"],
        "rerun_command": r".\venv\Scripts\python.exe ML\run_landslide_mvp.py",
    }
    write_json(RUN_SUMMARY_OUTPUT, summary)
    print(json.dumps(json_value(summary), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
