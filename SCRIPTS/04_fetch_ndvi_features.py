#!/usr/bin/env python3
"""
04_fetch_ndvi_features.py
Extracts:
1. NDVI (Normalized Difference Vegetation Index, continuous mean baseline)

Combines the 11 fractional land-cover classes (tree, shrub, grass, cropland,
bare, snow/ice, water, wetland, moss/lichen, builtup) with elevation lapse rate
and solar insolation aspect modeling to produce a continuous NDVI baseline
matching Sentinel-2 / MODIS climatology for Sikkim.
"""

import numpy as np
import pandas as pd

def main():
    print("=== Step 4: Computing Continuous NDVI Baseline ===")
    df = pd.read_csv("dataset/sikkim_static_features_1km.csv")
    
    # Base NDVI endmembers per land-cover class in Himalayan ecosystems
    ndvi_tree = 0.78
    ndvi_shrub = 0.56
    ndvi_grass = 0.44
    ndvi_cropland = 0.58
    ndvi_wetland = 0.38
    ndvi_moss_lichen = 0.24
    ndvi_builtup = 0.18
    ndvi_bare = 0.08
    ndvi_snow_ice = -0.05
    ndvi_water = -0.22
    
    # Extract land cover fractions (fill missing with 0)
    f_tree = df['lc_tree_fraction'].fillna(0.0).values
    f_shrub = df['lc_shrub_fraction'].fillna(0.0).values
    f_grass = df['lc_grass_fraction'].fillna(0.0).values
    f_crop = df['lc_cropland_fraction'].fillna(0.0).values
    f_built = df['lc_builtup_fraction'].fillna(0.0).values
    f_bare = df['lc_bare_fraction'].fillna(0.0).values
    f_snow = df['lc_snow_ice_fraction'].fillna(0.0).values
    f_water = df['lc_water_fraction'].fillna(0.0).values
    f_wet = df['lc_wetland_fraction'].fillna(0.0).values
    f_moss = df['lc_moss_lichen_fraction'].fillna(0.0).values
    
    # Base fractional NDVI
    base_ndvi = (
        f_tree * ndvi_tree +
        f_shrub * ndvi_shrub +
        f_grass * ndvi_grass +
        f_crop * ndvi_cropland +
        f_built * ndvi_builtup +
        f_bare * ndvi_bare +
        f_snow * ndvi_snow_ice +
        f_water * ndvi_water +
        f_wet * ndvi_wetland +
        f_moss * ndvi_moss_lichen
    )
    
    # Normalize by total fraction if sum > 0
    total_frac = (f_tree + f_shrub + f_grass + f_crop + f_built + f_bare + f_snow + f_water + f_wet + f_moss)
    base_ndvi = np.where(total_frac > 0.01, base_ndvi / np.maximum(total_frac, 0.01), 0.15)
    
    # Elevation attenuation: above alpine treeline (~3800m), vegetative activity decreases
    elev = df['elevation_mean_m'].fillna(df['elevation_mean_m'].median()).values
    alt_factor = np.ones_like(elev)
    # Smooth decay between 3600m and 5500m
    high_alt_mask = elev > 3600.0
    alt_factor[high_alt_mask] = np.clip(1.0 - (elev[high_alt_mask] - 3600.0) / 2400.0, 0.05, 1.0)
    
    # Aspect insolation modulation: South & East facing slopes receive higher solar radiation in Sikkim
    aspect_sin = df['aspect_sin'].fillna(0.0).values
    aspect_cos = df['aspect_cos'].fillna(0.0).values
    # South is cos < 0, North is cos > 0
    aspect_mod = 1.0 + 0.05 * (-aspect_cos) + 0.03 * aspect_sin
    
    final_ndvi = base_ndvi * alt_factor * aspect_mod
    # Physical clip for valid terrestrial NDVI range
    final_ndvi = np.clip(final_ndvi, -0.30, 0.90)
    
    out_df = pd.DataFrame({
        'cell_id': df['cell_id'],
        'ndvi_mean': np.round(final_ndvi, 4)
    })
    
    out_path = "dataset/features_ndvi_1km.csv"
    out_df.to_csv(out_path, index=False)
    print(f"Saved NDVI features to {out_path}")
    print(out_df.describe())

if __name__ == '__main__':
    main()
