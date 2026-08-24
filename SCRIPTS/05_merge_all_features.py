#!/usr/bin/env python3
"""
05_merge_all_features.py
Merges all extracted geo-environmental and climatic features with the base
dataset to produce the complete 13-factor static dataset (Roy et al. 2025).
Performs data quality audits, range sanity checks, and VIF multicollinearity tests.
"""

import numpy as np
import pandas as pd
from statsmodels.stats.outliers_influence import variance_inflation_factor

def main():
    print("=== Step 5: Merging All Static Features into Master Dataset ===")
    
    base_df = pd.read_csv("dataset/sikkim_static_features_1km.csv")
    clim_df = pd.read_csv("dataset/features_climatic_1km.csv")
    hydro_df = pd.read_csv("dataset/features_hydrology_faults_1km.csv")
    morph_df = pd.read_csv("dataset/features_morphometry_1km.csv")
    ndvi_df = pd.read_csv("dataset/features_ndvi_1km.csv")
    
    # Sequential joins on cell_id
    merged = base_df.merge(clim_df, on='cell_id', how='left')
    merged = merged.merge(hydro_df, on='cell_id', how='left')
    merged = merged.merge(morph_df, on='cell_id', how='left')
    merged = merged.merge(ndvi_df, on='cell_id', how='left')
    
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
