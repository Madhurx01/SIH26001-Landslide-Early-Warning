#!/usr/bin/env python3
"""
07_run_shap_analysis.py
Performs full SHAP (SHapley Additive exPlanations) Analysis using TreeSHAP on the 
Layer 1 Susceptibility Model (Roy et al. 2025):
1. Computes Global SHAP values (Beeswarm Summary Plot & Bar Importance)
2. Computes Feature Interaction & Dependence plots (Slope vs DTR, Fault Proximity vs Rainfall)
3. Computes Local Cell-Level Waterfall Explanations for real Sikkim settlements:
   - High-Risk Critical Cell (e.g. Chungthang / Singtam Gorge)
   - Moderate-Risk Transition Cell (e.g. Namchi slope)
   - Low-Risk Stable Valley Cell (e.g. Melli river terrace)
4. Saves SHAP values and high-res plots in outputs/
"""

import os
import shap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import xgboost as xgb
from sklearn.model_selection import train_test_split

def main():
    print("=== Step 1: Loading Dataset & Training Primary Model for SHAP ===")
    os.makedirs("outputs", exist_ok=True)
    
    # Load master predictions and feature table
    df = pd.read_csv("dataset/sikkim_landslide_susceptibility_predictions_1km.csv")
    
    feature_cols = [
        'elevation_mean_m', 'slope_mean_deg', 'aspect_sin', 'aspect_cos',
        'conv_index', 'sti', 'twi', 'distance_to_drainage_km', 'geom_class',
        'distance_to_fault_km', 'annual_rainfall_mm', 'dtr_deg_c', 'ndvi_mean'
    ]
    
    feature_names = [
        'Elevation', 'Slope', 'Aspect (Sin)', 'Aspect (Cos)',
        'Convergence Index', 'Sediment Transport (STI)', 'Topographic Wetness (TWI)',
        'Distance to Drainage', 'Geomorphology Class', 'Distance to Fault',
        'Annual Rainfall', 'Diurnal Temp Range (DTR)', 'NDVI'
    ]
    
    # Extract labeled sample
    sample_df = df[df['historically_affected'].notna()].copy()
    X = sample_df[feature_cols].copy()
    y = sample_df['historically_affected'].values.astype(int)
    
    for col in feature_cols:
        X[col] = X[col].fillna(X[col].median())
        
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.30, stratify=y, random_state=42
    )
    
    print(f"Fitting XGBoost model on {len(X_train)} training rows...")
    model = xgb.XGBClassifier(
        n_estimators=150, learning_rate=0.08, max_depth=3, subsample=0.85,
        colsample_bytree=0.85, eval_metric='logloss', random_state=42
    )
    model.fit(X_train, y_train)
    
    print("\n=== Step 2: Initializing TreeSHAP Explainer ===")
    explainer = shap.TreeExplainer(model, feature_perturbation="tree_path_dependent")
    
    # Compute SHAP values on test set
    shap_values = explainer(X_test)
    shap_values.feature_names = feature_names
    
    print("Computed SHAP values on test set. Shape:", shap_values.values.shape)
    
    # 1. Global SHAP Summary / Beeswarm Plot
    print("\n=== Step 3: Generating Global SHAP Plots ===")
    plt.figure(figsize=(11, 7))
    shap.summary_plot(shap_values, X_test, feature_names=feature_names, show=False)
    plt.title("Global SHAP Beeswarm Plot (Feature Impact on Landslide Risk)", fontsize=13, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig("outputs/shap_summary_beeswarm.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved outputs/shap_summary_beeswarm.png")
    
    # 2. Global SHAP Bar Importance Plot
    plt.figure(figsize=(10, 6))
    shap.plots.bar(shap_values, max_display=13, show=False)
    plt.title("Mean Absolute SHAP Feature Importance (|SHAP Value|)", fontsize=13, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig("outputs/shap_bar_importance.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved outputs/shap_bar_importance.png")
    
    # 3. SHAP Dependence Plots for Top Drivers
    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    
    # Slope (index 1) vs DTR (index 11)
    shap.dependence_plot(
        1, shap_values.values, X_test.values, feature_names=feature_names,
        interaction_index=11, ax=axes[0, 0], show=False
    )
    axes[0, 0].set_title("SHAP Dependence: Slope Angle (colored by DTR)", fontsize=11, fontweight='bold')
    
    # DTR (index 11) vs Elevation (index 0)
    shap.dependence_plot(
        11, shap_values.values, X_test.values, feature_names=feature_names,
        interaction_index=0, ax=axes[0, 1], show=False
    )
    axes[0, 1].set_title("SHAP Dependence: DTR (colored by Elevation)", fontsize=11, fontweight='bold')
    
    # Distance to Fault (index 9) vs Rainfall (index 10)
    shap.dependence_plot(
        9, shap_values.values, X_test.values, feature_names=feature_names,
        interaction_index=10, ax=axes[1, 0], show=False
    )
    axes[1, 0].set_title("SHAP Dependence: Fault Proximity (colored by Rainfall)", fontsize=11, fontweight='bold')
    
    # Annual Rainfall (index 10) vs TWI (index 6)
    shap.dependence_plot(
        10, shap_values.values, X_test.values, feature_names=feature_names,
        interaction_index=6, ax=axes[1, 1], show=False
    )
    axes[1, 1].set_title("SHAP Dependence: Annual Rainfall (colored by TWI)", fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig("outputs/shap_dependence_grid.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved outputs/shap_dependence_grid.png")
    
    # 4. Local Cell-Level Waterfall Explanations
    print("\n=== Step 4: Generating Local Cell-Level SHAP Waterfall Explanations ===")
    
    # (a) Very High Hazard Cell (Gorge Corridor)
    vh_cells = df[(df['susceptibility_zone'] == 'Very High') & (df['model_eligible'] == True)]
    vh_sample = vh_cells.iloc[10]
    vh_X = vh_sample[feature_cols].values.reshape(1, -1)
    vh_shap = explainer(vh_X)
    vh_shap.feature_names = feature_names
    
    plt.figure(figsize=(10, 6))
    shap.plots.waterfall(vh_shap[0], max_display=10, show=False)
    plt.title(f"Local SHAP: Very High Risk Cell ({vh_sample['cell_id']} near {vh_sample.get('nearest_settlement_name', 'Sikkim')})\nPredicted LSI: {vh_sample['lsi_ensemble']:.3f}", fontsize=12, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig("outputs/shap_waterfall_very_high_cell.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved outputs/shap_waterfall_very_high_cell.png")
    
    # (b) Very Low Hazard Cell (Valley Bottom / Flat Terrace)
    vl_cells = df[(df['susceptibility_zone'] == 'Very Low') & (df['model_eligible'] == True)]
    vl_sample = vl_cells.iloc[10]
    vl_X = vl_sample[feature_cols].values.reshape(1, -1)
    vl_shap = explainer(vl_X)
    vl_shap.feature_names = feature_names
    
    plt.figure(figsize=(10, 6))
    shap.plots.waterfall(vl_shap[0], max_display=10, show=False)
    plt.title(f"Local SHAP: Very Low Risk Cell ({vl_sample['cell_id']} near {vl_sample.get('nearest_settlement_name', 'Sikkim')})\nPredicted LSI: {vl_sample['lsi_ensemble']:.3f}", fontsize=12, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig("outputs/shap_waterfall_very_low_cell.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved outputs/shap_waterfall_very_low_cell.png")
    
    # (c) Moderate Hazard Transition Cell
    mod_cells = df[(df['susceptibility_zone'] == 'Moderate') & (df['model_eligible'] == True)]
    mod_sample = mod_cells.iloc[5]
    mod_X = mod_sample[feature_cols].values.reshape(1, -1)
    mod_shap = explainer(mod_X)
    mod_shap.feature_names = feature_names
    
    plt.figure(figsize=(10, 6))
    shap.plots.waterfall(mod_shap[0], max_display=10, show=False)
    plt.title(f"Local SHAP: Moderate Risk Cell ({mod_sample['cell_id']} near {mod_sample.get('nearest_settlement_name', 'Sikkim')})\nPredicted LSI: {mod_sample['lsi_ensemble']:.3f}", fontsize=12, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig("outputs/shap_waterfall_moderate_cell.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved outputs/shap_waterfall_moderate_cell.png")
    
    print("\nAll SHAP analysis artifacts generated successfully!")

if __name__ == '__main__':
    main()
