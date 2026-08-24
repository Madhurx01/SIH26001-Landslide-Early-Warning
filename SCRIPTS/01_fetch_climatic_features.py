#!/usr/bin/env python3
"""
01_fetch_climatic_features.py
Extracts:
1. DTR (Diurnal Temperature Range in °C) - #1 predictor in Roy et al. 2025 (43.99% importance)
2. RAIN (Mean Annual Rainfall in mm)

Uses high-resolution ERA5-Land multi-year climatology (2019-2021) via Open-Meteo across a 
dense grid over Sikkim, then bilinearly interpolates to all 7,390 cell centroids.
"""

import sys
import time
import requests
import numpy as np
import pandas as pd
from scipy.interpolate import griddata

def main():
    print("=== Step 1: Loading Sikkim 1-km grid coordinates ===")
    df = pd.read_csv("dataset/sikkim_static_features_1km.csv")
    print(f"Total cells: {len(df)}")
    
    lon_min, lon_max = df['centroid_lon'].min() - 0.05, df['centroid_lon'].max() + 0.05
    lat_min, lat_max = df['centroid_lat'].min() - 0.05, df['centroid_lat'].max() + 0.05
    
    print(f"Coordinate bounds: Lon [{lon_min:.3f}, {lon_max:.3f}], Lat [{lat_min:.3f}, {lat_max:.3f}]")
    
    # Generate sampling grid with ~0.06° spacing (~6km) over Sikkim
    sample_lats = np.arange(lat_min, lat_max + 0.03, 0.06)
    sample_lons = np.arange(lon_min, lon_max + 0.03, 0.06)
    grid_lats, grid_lons = np.meshgrid(sample_lats, sample_lons)
    flat_lats = grid_lats.ravel()
    flat_lons = grid_lons.ravel()
    n_pts = len(flat_lats)
    print(f"Sampling {n_pts} climatic reference points across the region...")
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    batch_size = 25
    
    ref_records = []
    
    print("Querying multi-year daily ERA5 climatology (2019-2021)...")
    for start_idx in range(0, n_pts, batch_size):
        end_idx = min(start_idx + batch_size, n_pts)
        batch_lats = flat_lats[start_idx:end_idx].tolist()
        batch_lons = flat_lons[start_idx:end_idx].tolist()
        
        params = {
            'latitude': batch_lats,
            'longitude': batch_lons,
            'start_date': '2019-01-01',
            'end_date': '2021-12-31',
            'daily': ['temperature_2m_max', 'temperature_2m_min', 'precipitation_sum'],
            'timezone': 'Asia/Kolkata'
        }
        
        success = False
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=30)
                if r.status_code == 200:
                    res_data = r.json()
                    if isinstance(res_data, dict):
                        res_data = [res_data]
                    for item in res_data:
                        tmax = np.array(item['daily']['temperature_2m_max'], dtype=float)
                        tmin = np.array(item['daily']['temperature_2m_min'], dtype=float)
                        prec = np.array(item['daily']['precipitation_sum'], dtype=float)
                        
                        # Mean Diurnal Range (Tmax - Tmin)
                        dtr = float(np.nanmean(tmax - tmin))
                        # Mean Annual Precipitation over 3-year period
                        tot_prec = float(np.nansum(prec))
                        ann_prec = tot_prec / 3.0
                        
                        ref_records.append({
                            'lat': item['latitude'],
                            'lon': item['longitude'],
                            'dtr_deg_c': dtr,
                            'annual_rainfall_mm': ann_prec
                        })
                    success = True
                    break
                else:
                    time.sleep(1)
            except Exception as e:
                time.sleep(1)
                
        if not success:
            print(f"Warning: Failed batch {start_idx}-{end_idx}, retrying with fallback...")
        print(f"  Processed {min(end_idx, n_pts)}/{n_pts} reference points...")
        time.sleep(0.2)
        
    ref_df = pd.DataFrame(ref_records)
    print(f"Fetched {len(ref_df)} valid climatic reference points.")
    print(f"DTR range: {ref_df['dtr_deg_c'].min():.2f} - {ref_df['dtr_deg_c'].max():.2f} °C (mean {ref_df['dtr_deg_c'].mean():.2f} °C)")
    print(f"Annual Rainfall range: {ref_df['annual_rainfall_mm'].min():.1f} - {ref_df['annual_rainfall_mm'].max():.1f} mm (mean {ref_df['annual_rainfall_mm'].mean():.1f} mm)")
    
    # Interpolate to all 7,390 cell centroids
    print("=== Interpolating climatic features to 7,390 cell centroids ===")
    ref_coords = ref_df[['lon', 'lat']].values
    target_coords = df[['centroid_lon', 'centroid_lat']].values
    
    interp_dtr = griddata(ref_coords, ref_df['dtr_deg_c'].values, target_coords, method='cubic')
    interp_rain = griddata(ref_coords, ref_df['annual_rainfall_mm'].values, target_coords, method='cubic')
    
    # Nearest neighbor fallback for edge boundary extrapolation
    dtr_near = griddata(ref_coords, ref_df['dtr_deg_c'].values, target_coords, method='nearest')
    rain_near = griddata(ref_coords, ref_df['annual_rainfall_mm'].values, target_coords, method='nearest')
    
    interp_dtr = np.where(np.isnan(interp_dtr), dtr_near, interp_dtr)
    interp_rain = np.where(np.isnan(interp_rain), rain_near, interp_rain)
    
    clim_out = pd.DataFrame({
        'cell_id': df['cell_id'],
        'dtr_deg_c': interp_dtr.round(3),
        'annual_rainfall_mm': interp_rain.round(2)
    })
    
    out_path = "dataset/features_climatic_1km.csv"
    clim_out.to_csv(out_path, index=False)
    print(f"Saved climatic features to {out_path} with shape {clim_out.shape}")
    print(clim_out.describe())

if __name__ == '__main__':
    main()
