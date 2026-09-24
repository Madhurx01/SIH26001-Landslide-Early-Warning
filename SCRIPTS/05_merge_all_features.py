#!/usr/bin/env python3
"""
05_merge_all_features.py
Merges all extracted geo-environmental and climatic features with the base
dataset to produce the complete 13-factor static dataset (Roy et al. 2025).
Performs data quality audits, range sanity checks, and VIF multicollinearity tests.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = PROJECT_ROOT / "dataset"
NDVI_PATH = DATASET_DIR / "features_ndvi_1km.csv"
NDVI_METADATA_PATH = DATASET_DIR / "features_ndvi_1km.metadata.json"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_satellite_ndvi(base_df, ndvi_df):
    """Reject synthetic/stale NDVI before it can enter the model dataset."""
    if not NDVI_METADATA_PATH.is_file():
        raise RuntimeError(
            "NDVI provenance is missing. Run SCRIPTS/04_fetch_ndvi_features.py; "
            "legacy synthetic NDVI files are not accepted."
        )
    metadata = json.loads(NDVI_METADATA_PATH.read_text(encoding="utf-8"))
    if (
        metadata.get("data_origin") != "satellite_observation"
        or metadata.get("synthetic_fallback_used") is not False
        or metadata.get("source", {}).get("collection") != "sentinel-2-l2a"
    ):
        raise RuntimeError("NDVI provenance does not identify genuine Sentinel-2 observations")
    if metadata.get("output_sha256") != sha256_file(NDVI_PATH):
        raise RuntimeError("NDVI CSV checksum does not match its satellite provenance sidecar")
    if list(ndvi_df.columns) != ["cell_id", "ndvi_mean"]:
        raise RuntimeError("NDVI CSV must contain exactly: cell_id, ndvi_mean")
    if ndvi_df["cell_id"].isna().any() or ndvi_df["cell_id"].duplicated().any():
        raise RuntimeError("NDVI cell_id values must be non-null and unique")
    if ndvi_df["cell_id"].astype(str).tolist() != base_df["cell_id"].astype(str).tolist():
        raise RuntimeError("NDVI cell_id rows are not exactly aligned with the base dataset")
    valid_values = ndvi_df["ndvi_mean"].dropna()
    if not valid_values.between(-1.0, 1.0).all():
        raise RuntimeError("NDVI contains values outside the physical [-1, 1] range")

def main():
    print("=== Step 5: Merging All Static Features into Master Dataset ===")
    
    base_df = pd.read_csv("dataset/sikkim_static_features_1km.csv")
    clim_df = pd.read_csv("dataset/features_climatic_1km.csv")
    hydro_df = pd.read_csv("dataset/features_hydrology_faults_1km.csv")
    morph_df = pd.read_csv("dataset/features_morphometry_1km.csv")
    ndvi_df = pd.read_csv(NDVI_PATH)
    validate_satellite_ndvi(base_df, ndvi_df)
    
    # Sequential joins on cell_id
    merged = base_df.merge(clim_df, on='cell_id', how='left')
    merged = merged.merge(hydro_df, on='cell_id', how='left')
    merged = merged.merge(morph_df, on='cell_id', how='left')
    merged = merged.merge(ndvi_df, on='cell_id', how='left', validate='one_to_one')
    
    print(f"Merged master dataset shape: {merged.shape} (Expected rows: 7390)")
    
    # Missing Value Audit
    print("\n--- Missing Value Audit ---")
    missing_counts = merged.isnull().sum()
    cols_with_missing = missing_counts[missing_counts > 0]
    print("Columns with missing values:")
    print(cols_with_missing)
    
    # Save the 13-factor static dataset
    out_path = "dataset/sikkim_static_features_13factors_1km.csv"
    merged.to_csv(out_path, index=False)
    print(f"\nSaved complete 13-factor dataset to {out_path}")
    
    # Run VIF Multicollinearity Analysis on the 13 Factors (Roy et al. 2025)
    print("\n=== Multicollinearity & VIF Analysis (Replicating Roy et al. 2025) ===")
    try:
        from statsmodels.stats.outliers_influence import variance_inflation_factor
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "The existing VIF step requires statsmodels; install it in the active environment."
        ) from error
    # Filter to model eligible cells
    sub = merged[merged['model_eligible'] == True].copy()
    
    factor_cols = [
        'elevation_mean_m',
        'slope_mean_deg',
        'aspect_sin',
        'aspect_cos',
        'conv_index',
        'sti',
        'twi',
        'distance_to_drainage_km',
        'geom_class',
        'distance_to_fault_km',
        'annual_rainfall_mm',
        'dtr_deg_c',
        'ndvi_mean'
    ]
    
    # Check nulls and drop or impute with median for VIF check
    X_vif = sub[factor_cols].dropna()
    print(f"Sample size for VIF test: {len(X_vif)} cells")
    
    # Standardize for stable numerical VIF computation
    X_std = (X_vif - X_vif.mean()) / X_vif.std()
    
    vif_records = []
    for i, col in enumerate(factor_cols):
        vif_val = variance_inflation_factor(X_std.values, i)
        tolerance = 1.0 / vif_val if vif_val > 0 else 0.0
        vif_records.append({
            'Factor Code': col,
            'Tolerance': round(tolerance, 4),
            'VIF': round(vif_val, 3),
            'Status': 'PASS (VIF < 10)' if vif_val < 10 else 'FLAG (VIF >= 10)'
        })
        
    vif_df = pd.DataFrame(vif_records)
    print("\nVIF Multicollinearity Results:")
    print(vif_df.to_string(index=False))
    
    print("\nMaster dataset column list:")
    print(merged.columns.tolist())

if __name__ == '__main__':
    main()
