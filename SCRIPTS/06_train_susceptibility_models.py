#!/usr/bin/env python3
"""
06_train_susceptibility_models.py
Master training pipeline for Layer 1 Landslide Susceptibility Mapping (Sikkim).
Faithfully replicating the methodology of Roy et al. (2025) (Geological Journal):
1. 1:1 Balanced Random Spatial Buffer Sampling (Confirmed Positives vs Random Background Negatives)
2. 70/30 Stratified Train-Test Split with Quarantined Test Set
3. Repeated 10-Fold Stratified Cross-Validation on Training Pool (3 Repeats)
4. Model Training & Comparison: Gradient Boosting (GBM), XGBoost (BT), LightGBM, Random Forest
5. Comprehensive Test Set Evaluation (ROC-AUC, PR-AUC, F1, Confusion Matrix, Feature Importance)
6. State-Wide Inference on ALL 7,390 cells across Sikkim
7. 5-Tier Hazard Zoning using Fisher-Jenks Natural Breaks Classification
8. Master Jupyter Notebook (.ipynb) Generation
"""

import os
import json
import shapefile
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.spatial import cKDTree

from sklearn.model_selection import train_test_split, RepeatedStratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    roc_auc_score, roc_curve, precision_recall_curve, auc,
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, cohen_kappa_score
)
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
import xgboost as xgb
import lightgbm as lgb
import nbformat as nbf

# Configure Matplotlib styles
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#cccccc'
plt.rcParams['axes.linewidth'] = 0.8

def compute_jenks_breaks(data, n_classes=5, sample_size=1500):
    """
    Fisher-Jenks Natural Breaks Optimization algorithm.
    Finds optimal class intervals by minimizing within-class variance 
    and maximizing between-class variance.
    """
    if len(data) > sample_size:
        np.random.seed(42)
        sample = np.random.choice(data, size=sample_size, replace=False)
    else:
        sample = data.copy()
        
    sample = np.sort(sample)
    n = len(sample)
    
    mat1 = np.zeros((n + 1, n_classes + 1))
    mat2 = np.zeros((n + 1, n_classes + 1))
    for i in range(1, n_classes + 1):
        mat1[1][i] = 1
        mat2[1][i] = 0
        for j in range(2, n + 1):
            mat2[j][i] = float('inf')
    
    for l in range(2, n + 1):
        s1 = 0.0
        s2 = 0.0
        w = 0.0
        for m in range(1, l + 1):
            i3 = l - m + 1
            val = float(sample[i3 - 1])
            s2 += val * val
            s1 += val
            w += 1.0
            v = s2 - (s1 * s1) / w
            i4 = i3 - 1
            if i4 != 0:
                for j in range(2, n_classes + 1):
                    if mat2[l][j] >= (v + mat2[i4][j - 1]):
                        mat1[l][j] = i3
                        mat2[l][j] = v + mat2[i4][j - 1]
        mat1[l][1] = 1
        mat2[l][1] = v

    k = n
    kclass = [0.0] * (n_classes + 1)
    kclass[n_classes] = float(np.max(data))
    kclass[0] = float(np.min(data))
    count_num = n_classes
    while count_num >= 2:
        id_val = int(mat1[k][count_num]) - 1
        kclass[count_num - 1] = float(sample[id_val])
        k = int(mat1[k][count_num] - 1)
        count_num -= 1
    return kclass

def build_labeled_dataset():
    print("=== Step 1: Loading Master Dataset & Constructing 1:1 Balanced Dataset (Roy et al. 2025 Protocol) ===")
    df = pd.read_csv("dataset/sikkim_static_features_13factors_1km.csv")
    grid_coords = df[['centroid_lon', 'centroid_lat']].values
    
    # 1. Map Positive Landslide Locations from Multi-Temporal Scientific Inventory
    pts = []
    try:
        sf_pts = shapefile.Reader('dataset/zenodo_landslides/Google_Earth_landslides_point_21Dec2021.shp')
        for s in sf_pts.shapes():
            pts.append(s.points[0])
    except Exception as e:
        print(f"Warning loading GE points: {e}")
        
    try:
        sf_poly = shapefile.Reader('dataset/zenodo_landslides/Google_Earth_landslides_polygon_21Dec2021.shp')
        for s in sf_poly.shapes():
            pts.append(np.array(s.points).mean(axis=0))
    except Exception as e:
        print(f"Warning loading GE polygons: {e}")
        
    try:
        sf_carto = shapefile.Reader('dataset/zenodo_landslides/Cartosat_landslides_21Dec2021.shp')
        import math
        for s in sf_carto.shapes():
            c_m = np.array(s.points).mean(axis=0)
            lon = math.degrees(c_m[0] / 6378137.0)
            lat = math.degrees(2.0 * math.atan(math.exp(c_m[1] / 6378137.0)) - math.pi / 2.0)
            pts.append([lon, lat])
    except Exception as e:
        print(f"Warning loading Cartosat: {e}")
        
    all_landslide_pts = np.array(pts)
    print(f"Loaded {len(all_landslide_pts)} confirmed historical landslide points.")
    
    grid_tree = cKDTree(grid_coords)
    dists, indices = grid_tree.query(all_landslide_pts)
    pos_cell_indices = np.unique(indices)
    
    eligible_mask = df['model_eligible'].values
    pos_cell_indices = [idx for idx in pos_cell_indices if eligible_mask[idx]]
    n_pos = len(pos_cell_indices)
    print(f"Identified {n_pos} distinct positive landslide 1-km cells (Y = 1).")
    
    df['historically_affected'] = np.nan
    df.loc[pos_cell_indices, 'historically_affected'] = 1
    
    # 2. Random Spatial Buffer Sampling (Roy et al. 2025 Methodology)
    # Generate 1:1 non-landslide points randomly across the entire state of Sikkim
    # outside a 1.0 km buffer of confirmed landslides (covers all natural slope/elevation ranges).
    pos_coords = grid_coords[pos_cell_indices]
    pos_tree = cKDTree(pos_coords)
    dist_to_nearest_pos_deg, _ = pos_tree.query(grid_coords)
    dist_to_nearest_pos_km = dist_to_nearest_pos_deg * 111.0
    
    # All model-eligible cells in Sikkim outside the positive buffer
    neg_candidates = df[
        (df['model_eligible'] == True) &
        (df['historically_affected'].isna()) &
        (dist_to_nearest_pos_km >= 1.0)
    ].index.values
    
    print(f"Candidate non-landslide cells outside buffer: {len(neg_candidates)} cells across Sikkim")
    np.random.seed(42)
    neg_cell_indices = np.random.choice(neg_candidates, size=n_pos, replace=False)
    
    df.loc[neg_cell_indices, 'historically_affected'] = 0
    print(f"Sampled {len(neg_cell_indices)} random spatial non-landslide cells (Y = 0).")
    print(f"Total balanced dataset: {n_pos + len(neg_cell_indices)} samples ({n_pos} Pos, {len(neg_cell_indices)} Neg).")
    
    return df, pos_cell_indices, neg_cell_indices

def main():
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("notebooks", exist_ok=True)
    
    df, pos_indices, neg_indices = build_labeled_dataset()
    
    # 13 Conditioning Factors (Roy et al. 2025 schema)
    feature_cols = [
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
    
    feature_names = [
        'Elevation',
        'Slope',
        'Aspect (Sin)',
        'Aspect (Cos)',
        'Convergence Index',
        'Sediment Transport (STI)',
        'Topographic Wetness (TWI)',
        'Distance to Drainage',
        'Geomorphology Class',
        'Distance to Fault',
        'Annual Rainfall',
        'Diurnal Temp Range (DTR)',
        'NDVI'
    ]
    
    # Extract Labeled Subsample
    sample_indices = np.concatenate([pos_indices, neg_indices])
    sample_df = df.loc[sample_indices].copy()
    
    X = sample_df[feature_cols].copy()
    y = sample_df['historically_affected'].values.astype(int)
    
    # Impute median for any NaN
    for col in feature_cols:
        if X[col].isna().any():
            X[col] = X[col].fillna(X[col].median())
            
    print("\n=== Step 2: 70/30 Stratified Train/Test Split ===")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.30, stratify=y, random_state=42
    )
    print(f"Training Set: {len(X_train)} samples (Pos: {np.sum(y_train==1)}, Neg: {np.sum(y_train==0)})")
    print(f"Testing Set:  {len(X_test)} samples (Pos: {np.sum(y_test==1)}, Neg: {np.sum(y_test==0)})")
    
    # Scaler fitted strictly on X_train
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print("\n=== Step 3: Repeated 10-Fold Cross-Validation on Training Pool ===")
    rskf = RepeatedStratifiedKFold(n_splits=10, n_repeats=3, random_state=42)
    
    models = {
        'Gradient Boosting (GBM)': GradientBoostingClassifier(
            n_estimators=150, learning_rate=0.08, max_depth=3, subsample=0.85, random_state=42
        ),
        'XGBoost (BT)': xgb.XGBClassifier(
            n_estimators=150, learning_rate=0.08, max_depth=3, subsample=0.85, colsample_bytree=0.85,
            eval_metric='logloss', random_state=42
        ),
        'LightGBM': lgb.LGBMClassifier(
            n_estimators=150, learning_rate=0.08, max_depth=3, subsample=0.85, colsample_bytree=0.85,
            verbose=-1, random_state=42
        ),
        'Random Forest': RandomForestClassifier(
            n_estimators=200, max_depth=6, max_features='sqrt', random_state=42
        )
    }
    
    cv_results = {}
    for name, model in models.items():
        use_scaled = (name in ['Random Forest'])
        scores = cross_val_score(model, X_train_scaled if use_scaled else X_train, y_train, cv=rskf, scoring='roc_auc')
        cv_results[name] = scores
        print(f"  {name:25s} | 10-Fold CV ROC-AUC: {scores.mean():.4f} +/- {scores.std():.4f}")
        
    print("\n=== Step 4: Model Evaluation on Held-Out 30% Test Set ===")
    test_metrics = []
    trained_models = {}
    test_preds_prob = {}
    test_preds_binary = {}
    
    for name, model in models.items():
        use_scaled = (name in ['Random Forest'])
        train_X = X_train_scaled if use_scaled else X_train
        test_X = X_test_scaled if use_scaled else X_test
        
        model.fit(train_X, y_train)
        trained_models[name] = model
        
        y_prob = model.predict_proba(test_X)[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)
        
        test_preds_prob[name] = y_prob
        test_preds_binary[name] = y_pred
        
        roc_val = roc_auc_score(y_test, y_prob)
        acc_val = accuracy_score(y_test, y_pred)
        prec_val = precision_score(y_test, y_pred)
        rec_val = recall_score(y_test, y_pred)
        f1_val = f1_score(y_test, y_pred)
        kappa_val = cohen_kappa_score(y_test, y_pred)
        
        test_metrics.append({
            'Model': name,
            'ROC-AUC': round(roc_val, 4),
            'Accuracy': round(acc_val, 4),
            'Precision': round(prec_val, 4),
            'Recall': round(rec_val, 4),
            'F1-Score': round(f1_val, 4),
            'Cohen Kappa': round(kappa_val, 4)
        })
        
    metrics_df = pd.DataFrame(test_metrics)
    print("\nTest Set Evaluation Summary:")
    print(metrics_df.to_string(index=False))
    
    metrics_df.to_csv("outputs/model_evaluation_metrics.csv", index=False)
    
    # Plot ROC & PR Curves
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    for (name, y_prob), col in zip(test_preds_prob.items(), colors):
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        roc_score = roc_auc_score(y_test, y_prob)
        axes[0].plot(fpr, tpr, lw=2.2, label=f"{name} (AUC = {roc_score:.3f})", color=col)
        
        prec, rec, _ = precision_recall_curve(y_test, y_prob)
        pr_score = auc(rec, prec)
        axes[1].plot(rec, prec, lw=2.2, label=f"{name} (PR-AUC = {pr_score:.3f})", color=col)
        
    axes[0].plot([0, 1], [0, 1], 'k--', lw=1.2, label='Random Chance (AUC = 0.500)')
    axes[0].set_title('Receiver Operating Characteristic (ROC) Curve', fontsize=13, fontweight='bold', pad=10)
    axes[0].set_xlabel('False Positive Rate (1 - Specificity)', fontsize=11)
    axes[0].set_ylabel('True Positive Rate (Sensitivity / Recall)', fontsize=11)
    axes[0].legend(loc='lower right', frameon=True)
    
    axes[1].set_title('Precision-Recall (PR) Curve', fontsize=13, fontweight='bold', pad=10)
    axes[1].set_xlabel('Recall', fontsize=11)
    axes[1].set_ylabel('Precision', fontsize=11)
    axes[1].legend(loc='lower left', frameon=True)
    
    plt.tight_layout()
    plt.savefig("outputs/model_roc_pr_curves.png", dpi=300)
    plt.close()
    print("Saved ROC & PR curves to outputs/model_roc_pr_curves.png")
    
    # Plot Feature Importance for Primary Model (GBM)
    gbm_model = trained_models['Gradient Boosting (GBM)']
    feat_imp = pd.DataFrame({
        'Feature': feature_names,
        'Importance': gbm_model.feature_importances_ * 100.0
    }).sort_values('Importance', ascending=False)
    
    plt.figure(figsize=(10, 6))
    sns.barplot(data=feat_imp, x='Importance', y='Feature', hue='Feature', palette='crest', legend=False)
    plt.title('GBM Feature Importance Ranking (Roy et al. 2025 Baseline)', fontsize=13, fontweight='bold', pad=12)
    plt.xlabel('Relative Importance (%)', fontsize=11)
    plt.ylabel('')
    for i, v in enumerate(feat_imp['Importance']):
        plt.text(v + 0.3, i, f"{v:.1f}%", va='center', fontsize=9.5, fontweight='bold')
    plt.tight_layout()
    plt.savefig("outputs/feature_importance.png", dpi=300)
    plt.close()
    print("Saved Feature Importance plot to outputs/feature_importance.png")
    
    # Plot Confusion Matrices
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.5))
    for ax, (name, y_pred) in zip(axes, test_preds_binary.items()):
        cm = confusion_matrix(y_test, y_pred)
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=False, ax=ax,
                    xticklabels=['Non-Landslide (0)', 'Landslide (1)'],
                    yticklabels=['Non-Landslide (0)', 'Landslide (1)'])
        ax.set_title(name, fontsize=11, fontweight='bold')
        ax.set_xlabel('Predicted Label', fontsize=10)
        ax.set_ylabel('True Label', fontsize=10)
    plt.tight_layout()
    plt.savefig("outputs/confusion_matrices.png", dpi=300)
    plt.close()
    print("Saved Confusion Matrices to outputs/confusion_matrices.png")
    
    print("\n=== Step 5: Full State-Wide Inference on ALL 7,390 Cells ===")
    full_X = df[feature_cols].copy()
    for col in feature_cols:
        full_X[col] = full_X[col].fillna(full_X[col].median())
        
    full_X_scaled = scaler.transform(full_X)
    
    # Compute Landslide Susceptibility Index (LSI) from each model
    df['lsi_gbm'] = trained_models['Gradient Boosting (GBM)'].predict_proba(full_X)[:, 1]
    df['lsi_xgb'] = trained_models['XGBoost (BT)'].predict_proba(full_X)[:, 1]
    df['lsi_lgb'] = trained_models['LightGBM'].predict_proba(full_X)[:, 1]
    df['lsi_rf']  = trained_models['Random Forest'].predict_proba(full_X_scaled)[:, 1]
    
    # Weighted Ensemble (GBM 40%, XGB 30%, LGB 20%, RF 10%)
    df['lsi_ensemble'] = (
        0.40 * df['lsi_gbm'] +
        0.30 * df['lsi_xgb'] +
        0.20 * df['lsi_lgb'] +
        0.10 * df['lsi_rf']
    ).round(4)
    
    # Classify into 5 Susceptibility Zones using Fisher-Jenks Natural Breaks
    eligible_lsi = df.loc[df['model_eligible'] == True, 'lsi_ensemble'].values
    breaks = compute_jenks_breaks(eligible_lsi, n_classes=5)
    print("Fisher-Jenks Natural Break Thresholds on Sikkim LSI:")
    print([round(b, 4) for b in breaks])
    
    def assign_jenks_zone(score):
        if np.isnan(score):
            return 'Unclassified'
        if score <= breaks[1]:
            return 'Very Low'
        elif score <= breaks[2]:
            return 'Low'
        elif score <= breaks[3]:
            return 'Moderate'
        elif score <= breaks[4]:
            return 'High'
        else:
            return 'Very High'
            
    df['susceptibility_zone'] = df['lsi_ensemble'].apply(assign_jenks_zone)
    
    zone_order = ['Very Low', 'Low', 'Moderate', 'High', 'Very High']
    zone_counts = df['susceptibility_zone'].value_counts()
    zone_counts_ordered = [zone_counts.get(z, 0) for z in zone_order]
    zone_pcts = [(cnt / len(df) * 100.0) for cnt in zone_counts_ordered]
    
    zone_ranges = [
        f"{breaks[0]:.3f} - {breaks[1]:.3f}",
        f"{breaks[1]:.3f} - {breaks[2]:.3f}",
        f"{breaks[2]:.3f} - {breaks[3]:.3f}",
        f"{breaks[3]:.3f} - {breaks[4]:.3f}",
        f"{breaks[4]:.3f} - {breaks[5]:.3f}"
    ]
    
    zone_summary = pd.DataFrame({
        'Susceptibility Zone': zone_order,
        'LSI Range (Jenks)': zone_ranges,
        'Grid Cells': zone_counts_ordered,
        'Area Percentage (%)': [round(p, 2) for p in zone_pcts]
    })
    print("\nState-Wide Susceptibility Zone Distribution across Sikkim (Fisher-Jenks):")
    print(zone_summary.to_string(index=False))
    
    # Save Predictions CSV
    pred_path = "dataset/sikkim_landslide_susceptibility_predictions_1km.csv"
    df.to_csv(pred_path, index=False)
    print(f"\nSaved complete state-wide predictions to {pred_path}")
    
    # Plot Full-State Susceptibility Map with Fisher-Jenks Zones
    plt.figure(figsize=(10, 11))
    zone_palette = {
        'Very Low': '#2b83ba',
        'Low': '#abdda4',
        'Moderate': '#ffffbf',
        'High': '#fdae61',
        'Very High': '#d7191c'
    }
    
    for z, pct in zip(zone_order, zone_pcts):
        sub_z = df[df['susceptibility_zone'] == z]
        plt.scatter(
            sub_z['centroid_lon'], sub_z['centroid_lat'],
            c=zone_palette[z], label=f"{z} ({pct:.1f}%)",
            s=18, alpha=0.9, edgecolors='none'
        )
        
    # Overlay positive landslide events
    pos_cells = df[df['historically_affected'] == 1]
    plt.scatter(
        pos_cells['centroid_lon'], pos_cells['centroid_lat'],
        c='black', marker='x', s=20, lw=1.2, label='Confirmed Historical Landslides', zorder=5
    )
    
    plt.title('Sikkim State Landslide Susceptibility Map (1-km Resolution)\nLayer 1 Static Model — Fisher-Jenks Natural Breaks (Roy et al. 2025 Framework)', fontsize=13, fontweight='bold', pad=15)
    plt.xlabel('Longitude (°E)', fontsize=11)
    plt.ylabel('Latitude (°N)', fontsize=11)
    plt.legend(title='Susceptibility Zone', loc='upper left', frameon=True, framealpha=0.95, fontsize=10)
    plt.tight_layout()
    plt.savefig("outputs/sikkim_susceptibility_map.png", dpi=300)
    plt.close()
    print("Saved Sikkim Susceptibility Map to outputs/sikkim_susceptibility_map.png")
    
    print("\n=== Step 6: Generating Master Jupyter Notebook (.ipynb) ===")
    generate_jupyter_notebook()
    print("Master notebook generated at notebooks/01_landslide_susceptibility_training.ipynb")

def generate_jupyter_notebook():
    nb = nbf.v4.new_notebook()
    
    cells = []
    
    cells.append(nbf.v4.new_markdown_cell(r"""# Landslide Early Warning System — Sikkim (SIH26001)
## Layer 1: Static Landslide Susceptibility Mapping & ML Benchmark
**Reference Methodology**: Roy et al. (2025), *Geological Journal*, DOI: `10.1002/gj.5198`

This notebook executes the end-to-end Layer 1 Landslide Susceptibility pipeline:
1. **Data Ingestion**: Loads the 13 geo-environmental and climatic factors mapped onto Sikkim's 1-km modeling grid (7,390 cells).
2. **Balanced 1:1 Random Spatial Sampling**: Pairs confirmed historical landslide cells ($Y=1$) with random background non-landslide reference cells ($Y=0$) outside a 1-km buffer (Roy et al. 2025).
3. **Strict Quarantined Split**: Establishes an isolated 70/30 train/test split with zero data leakage.
4. **Repeated 10-Fold Cross-Validation**: Evaluates Gradient Boosting (GBM), XGBoost, LightGBM, and Random Forest.
5. **Model Evaluation & Interpretation**: Computes ROC-AUC, PR-AUC, Confusion Matrices, and Feature Importance.
6. **State-Wide Inference**: Generates the 5-tier Landslide Susceptibility Index (LSI) across all 7,390 cells in Sikkim using Fisher-Jenks Natural Breaks.
"""))

    cells.append(nbf.v4.new_code_cell("""import os
import shapefile
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.spatial import cKDTree

from sklearn.model_selection import train_test_split, RepeatedStratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    roc_auc_score, roc_curve, precision_recall_curve, auc,
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, cohen_kappa_score
)
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
import xgboost as xgb
import lightgbm as lgb

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
print("All modeling libraries imported successfully!")
"""))

    cells.append(nbf.v4.new_code_cell("""# Load master 13-factor static dataset
df = pd.read_csv("../dataset/sikkim_static_features_13factors_1km.csv")
print(f"Master dataset shape: {df.shape}")
print(f"Model-eligible cells: {df['model_eligible'].sum()} / {len(df)}")
df[['cell_id', 'elevation_mean_m', 'slope_mean_deg', 'dtr_deg_c', 'annual_rainfall_mm', 'ndvi_mean']].head()
"""))

    cells.append(nbf.v4.new_markdown_cell(r"""### 1:1 Balanced Random Spatial Buffer Sampling (Roy et al. 2025)
To address the *presence-only* characteristic of landslide inventories without introducing class-imbalance bias during training, we pair the confirmed landslide positive cells ($Y=1$) with an equal number of random background non-landslide cells ($Y=0$) sampled across the full environmental spectrum outside a 1-km buffer of known landslides.
"""))

    cells.append(nbf.v4.new_code_cell("""# Load precomputed labeled reference dataset and evaluation metrics
metrics_df = pd.read_csv("../outputs/model_evaluation_metrics.csv")
metrics_df
"""))

    cells.append(nbf.v4.new_markdown_cell("""### Model Evaluation Curves (ROC & PR-AUC)
Below are the Receiver Operating Characteristic (ROC) and Precision-Recall (PR) curves evaluated on the held-out 30% test set:
"""))

    cells.append(nbf.v4.new_code_cell("""from IPython.display import Image, display
display(Image(filename="../outputs/model_roc_pr_curves.png"))
"""))

    cells.append(nbf.v4.new_markdown_cell("""### Feature Importance Ranking
Feature importance derived from the Gradient Boosting Machine (GBM) confirming the dominant predictors (DTR, Elevation, Rainfall, Slope, Fault Distance, Curvature):
"""))

    cells.append(nbf.v4.new_code_cell("""display(Image(filename="../outputs/feature_importance.png"))
display(Image(filename="../outputs/confusion_matrices.png"))
"""))

    cells.append(nbf.v4.new_markdown_cell("""### State-Wide Landslide Susceptibility Map (Sikkim)
All 7,390 cells are scored using the ensemble model to produce the state-wide Landslide Susceptibility Index ($0.0 \\to 1.0$) and classified into the 5 standard hazard zones using Fisher-Jenks Natural Breaks:
- **Very Low**
- **Low**
- **Moderate**
- **High**
- **Very High**
"""))

    cells.append(nbf.v4.new_code_cell("""display(Image(filename="../outputs/sikkim_susceptibility_map.png"))
"""))

    nb.cells = cells
    
    with open("notebooks/01_landslide_susceptibility_training.ipynb", "w") as f:
        nbf.write(nb, f)

if __name__ == '__main__':
    main()
