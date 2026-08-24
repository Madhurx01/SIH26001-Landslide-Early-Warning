#!/usr/bin/env python3
"""
03_derive_dem_morphometry.py
Extracts:
1. CONV (Convergence Index / Plan Curvature)
2. TWI (Topographic Wetness Index)
3. STI (Sediment Transport Index)
4. GEOM (Geomorphological Landform Classification based on TPI)

Uses the 1-km elevation matrix in UTM 45N to compute hydraulic and topographic
derivatives matching the methodology in Roy et al. (2025).
"""

import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter, generic_filter

def fill_nan_nearest(arr):
    """Fill NaN values in 2D array using nearest valid neighbor."""
    mask = np.isnan(arr)
    if not np.any(mask):
        return arr.copy()
    from scipy.ndimage import distance_transform_edt
    indices = distance_transform_edt(mask, return_distances=False, return_indices=True)
    return arr[tuple(indices)]

def main():
    print("=== Step 3: Deriving DEM Morphometry & Hydro-morphological Features ===")
    df = pd.read_csv("dataset/sikkim_static_features_1km.csv")
    
    x_min, x_max = df['centroid_x'].min(), df['centroid_x'].max()
    y_min, y_max = df['centroid_y'].min(), df['centroid_y'].max()
    cell_size = 1000.0  # 1 km
    
    cols = int(round((x_max - x_min) / cell_size)) + 1
    rows = int(round((y_max - y_min) / cell_size)) + 1
    print(f"Grid dimensions: {rows} rows x {cols} cols ({rows * cols} cells total)")
    
    col_idx = ((df['centroid_x'] - x_min) / cell_size).round().astype(int).values
    row_idx = ((rows - 1) - ((df['centroid_y'] - y_min) / cell_size).round().astype(int)).values
    
    # 1. Place elevation on regular 2D grid
    grid_z = np.full((rows, cols), np.nan)
    grid_z[row_idx, col_idx] = df['elevation_mean_m'].values
    grid_z_filled = fill_nan_nearest(grid_z)
    
    # 2. Convergence Index / Plan Curvature (CONV)
    # Plan Curvature: horizontal curvature orthogonal to slope gradient
    h = cell_size
    # Gradients with central differences
    dz_dx, dz_dy = np.gradient(grid_z_filled, h, h)
    d2z_dx2, d2z_dxdy = np.gradient(dz_dx, h, h)
    d2z_dydx, d2z_dy2 = np.gradient(dz_dy, h, h)
    
    p = dz_dx
    q = dz_dy
    r = d2z_dx2
    t = d2z_dy2
    s = 0.5 * (d2z_dxdy + d2z_dydx)
    
    denom = (p**2 + q**2)**1.5 + 1e-7
    # Standard Plan Curvature formula (Zevenbergen & Thorne / Roy et al. 2025)
    plan_curv = (q**2 * r - 2 * p * q * s + p**2 * t) / denom
    # Convergence Index: positive in valleys (flow convergence), negative on ridges (flow divergence)
    conv_index = -plan_curv * 1000.0
    
    # 3. Flow Accumulation & Hydrological Indices (TWI & STI)
    # D8 flow routing across the 2D DEM
    acc = np.zeros((rows, cols), dtype=float)
    # Sort flat cells by elevation descending
    flat_indices = np.argsort(-grid_z_filled.ravel())
    
    # D8 neighbor offsets (dr, dc) and distances
    d8_neighbors = [
        (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
        (-1, -1, math_sqrt2 := np.sqrt(2)), (-1, 1, math_sqrt2),
        (1, -1, math_sqrt2), (1, 1, math_sqrt2)
    ]
    
    for idx in flat_indices:
        r_i, c_i = divmod(idx, cols)
        z_curr = grid_z_filled[r_i, c_i]
        
        best_drop = 0.0
        best_nr, best_nc = None, None
        
        for dr, dc, dist in d8_neighbors:
            nr, nc = r_i + dr, c_i + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                drop = (z_curr - grid_z_filled[nr, nc]) / (dist * h)
                if drop > best_drop:
                    best_drop = drop
                    best_nr, best_nc = nr, nc
                    
        if best_nr is not None:
            acc[best_nr, best_nc] += acc[r_i, c_i] + 1.0
            
    # Specific Catchment Area As (m^2 / m)
    As = (acc + 1.0) * cell_size
    
    # Slope angle in radians from the dataset
    slope_deg = df['slope_mean_deg'].fillna(df['slope_mean_deg'].median()).values
    # Clamp slope to avoid division by zero on flat terrain
    slope_deg_clamped = np.clip(slope_deg, 0.1, 85.0)
    slope_rad = np.radians(slope_deg_clamped)
    
    # Sample As, conv_index to cell locations
    cell_As = As[row_idx, col_idx]
    cell_conv = conv_index[row_idx, col_idx]
    
    # TWI = ln(As / tan(slope))
    twi = np.log(cell_As / np.tan(slope_rad))
    twi = np.clip(twi, 2.0, 25.0)  # Standard physical range for TWI
    
    # STI = (As / 22.13)^0.6 * (sin(slope) / 0.0896)^1.3 (Moore & Burch 1986, Roy et al. 2025)
    sti = ((cell_As / 22.13) ** 0.6) * ((np.sin(slope_rad) / 0.0896) ** 1.3)
    sti = np.clip(sti, 0.0, 500.0)
    
    # 4. Topographic Position Index (TPI) & Geomorphological Classification (GEOM)
    # TPI with 3x3 window (3 km scale) and 5x5 window (5 km scale)
    tpi_3 = grid_z_filled - uniform_filter(grid_z_filled, size=3, mode='nearest')
    cell_tpi = tpi_3[row_idx, col_idx]
    tpi_std = np.nanstd(cell_tpi)
    tpi_z = (cell_tpi - np.nanmean(cell_tpi)) / (tpi_std if tpi_std > 0 else 1.0)
    
    # Classify landform (Weiss 2001 / Jenness 2006):
    # 1: Canyon / Deep Valley (TPI <= -1.0)
    # 2: Shallow Valley (-1.0 < TPI <= -0.5)
    # 3: Lower Slope (-0.5 < TPI < 0, slope > 5 deg)
    # 4: Flat Plains (-0.5 <= TPI <= 0.5, slope <= 5 deg)
    # 5: Open Mid-Slope (-0.5 <= TPI <= 0.5, slope > 5 deg)
    # 6: Upper Slope (0.5 < TPI <= 1.0)
    # 7: Ridge / High Peak (TPI > 1.0)
    geom_class = np.zeros(len(df), dtype=int)
    geom_name = np.empty(len(df), dtype=object)
    
    for i in range(len(df)):
        z_score = tpi_z[i]
        s_val = slope_deg[i]
        
        if z_score <= -1.0:
            geom_class[i] = 1
            geom_name[i] = "Deep Valley / Canyon"
        elif z_score <= -0.5:
            geom_class[i] = 2
            geom_name[i] = "Shallow Valley"
        elif z_score < 0.0:
            if s_val > 5.0:
                geom_class[i] = 3
                geom_name[i] = "Lower Slope"
            else:
                geom_class[i] = 4
                geom_name[i] = "Flat Plains"
        elif z_score <= 0.5:
            if s_val <= 5.0:
                geom_class[i] = 4
                geom_name[i] = "Flat Plains"
            else:
                geom_class[i] = 5
                geom_name[i] = "Open Mid-Slope"
        elif z_score <= 1.0:
            geom_class[i] = 6
            geom_name[i] = "Upper Slope"
        else:
            geom_class[i] = 7
            geom_name[i] = "Ridge / Peak"
            
    out_df = pd.DataFrame({
        'cell_id': df['cell_id'],
        'conv_index': np.round(cell_conv, 4),
        'twi': np.round(twi, 3),
        'sti': np.round(sti, 3),
        'geom_class': geom_class,
        'geom_name': geom_name
    })
    
    out_path = "dataset/features_morphometry_1km.csv"
    out_df.to_csv(out_path, index=False)
    print(f"Saved morphometric & hydro-morphological features to {out_path}")
    print(out_df.describe())
    print("\nGeomorphological class distribution:")
    print(out_df['geom_name'].value_counts())

if __name__ == '__main__':
    main()
