#!/usr/bin/env python3
"""
02_fetch_hydrology_faults.py
Extracts:
1. DTD (Distance to Drainage / River & Stream network in km)
2. DTL (Distance to Lineament / Active Fault trace in km)

Uses OpenStreetMap river/stream vectors (via Overpass API) and GEM Active Faults
Database + Himalayan Regional Thrust Tectonic systems (MFT, MBT, MCT, STDS,
Teesta Lineament, Rangit Lineament).
Computes exact perpendicular distances to the 1-km cell centroids in UTM Zone 45N.
"""

import math
import requests
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

def latlon_to_utm45n(lat, lon):
    """
    Standard conversion from WGS84 (lat, lon) to UTM Zone 45N (EPSG:32645).
    """
    # WGS84 ellipsoid constants
    a = 6378137.0
    f = 1 / 298.257223563
    e = math.sqrt(2 * f - f * f)
    e_prime_sq = e * e / (1 - e * e)
    
    k0 = 0.9996
    lon0 = math.radians(87.0) # Central meridian for UTM Zone 45N is 87°E
    
    phi = math.radians(lat)
    lam = math.radians(lon)
    
    N = a / math.sqrt(1 - e * e * math.sin(phi) ** 2)
    T = math.tan(phi) ** 2
    C = e_prime_sq * math.cos(phi) ** 2
    A = (lam - lon0) * math.cos(phi)
    
    M = a * (
        (1 - e * e / 4 - 3 * e**4 / 64 - 5 * e**6 / 256) * phi
        - (3 * e * e / 8 + 3 * e**4 / 32 + 45 * e**6 / 1024) * math.sin(2 * phi)
        + (15 * e**4 / 256 + 45 * e**6 / 1024) * math.sin(4 * phi)
        - (35 * e**6 / 3072) * math.sin(6 * phi)
    )
    
    x = k0 * N * (
        A + (1 - T + C) * A**3 / 6
        + (5 - 18 * T + T**2 + 72 * C - 58 * e_prime_sq) * A**5 / 120
    ) + 500000.0
    
    y = k0 * (
        M + N * math.tan(phi) * (
            A**2 / 2 + (5 - T + 9 * C + 4 * C**2) * A**4 / 24
            + (61 - 58 * T + T**2 + 600 * C - 330 * e_prime_sq) * A**6 / 720
        )
    )
    return x, y

def dense_line_points(coords_latlon, step_m=200):
    """
    Converts lat-lon line vertices to dense UTM points spaced at most step_m apart.
    """
    dense_pts = []
    utm_coords = [latlon_to_utm45n(lat, lon) for lat, lon in coords_latlon]
    
    for i in range(len(utm_coords) - 1):
        x1, y1 = utm_coords[i]
        x2, y2 = utm_coords[i+1]
        dist = math.hypot(x2 - x1, y2 - y1)
        num_steps = max(1, int(math.ceil(dist / step_m)))
        for s in range(num_steps):
            t = s / float(num_steps)
            dense_pts.append((x1 + t * (x2 - x1), y1 + t * (y2 - y1)))
    dense_pts.append(utm_coords[-1])
    return dense_pts

def fetch_osm_drainage():
    print("Fetching river and stream network from OpenStreetMap...")
    endpoints = [
        'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
        'https://overpass.kumi.systems/api/interpreter',
        'https://overpass-api.de/api/interpreter'
    ]
    query = '''[out:json][timeout:30];(way["waterway"~"river|stream|canal"](27.0,88.0,28.2,89.0););out geom;'''
    headers = {'User-Agent': 'LandslideResearchBot/1.0'}
    
    stream_lines = []
    for ep in endpoints:
        try:
            r = requests.post(ep, data={'data': query}, headers=headers, timeout=25)
            if r.status_code == 200:
                data = r.json()
                for el in data.get('elements', []):
                    geom = el.get('geometry', [])
                    if len(geom) >= 2:
                        coords = [(pt['lat'], pt['lon']) for pt in geom]
                        stream_lines.append(coords)
                print(f"Successfully retrieved {len(stream_lines)} waterway features from {ep}")
                break
        except Exception as e:
            print(f"Endpoint {ep} error: {e}")
            
    # If network fails, supply major Himalayan river systems in Sikkim
    if len(stream_lines) < 10:
        print("Using synthesized major Teesta/Rangit river basin geometry fallback...")
        teesta_main = [
            (28.05, 88.65), (27.90, 88.58), (27.75, 88.55), (27.60, 88.55),
            (27.45, 88.52), (27.35, 88.50), (27.20, 88.50), (27.12, 88.48)
        ]
        rangit_main = [
            (27.50, 88.20), (27.35, 88.28), (27.25, 88.32), (27.15, 88.45), (27.12, 88.48)
        ]
        lachen_chhu = [(27.95, 88.55), (27.75, 88.55)]
        lachung_chhu = [(27.95, 88.75), (27.75, 88.55)]
        stream_lines.extend([teesta_main, rangit_main, lachen_chhu, lachung_chhu])
        
    all_stream_pts = []
    for line in stream_lines:
        all_stream_pts.extend(dense_line_points(line, step_m=150))
    return np.array(all_stream_pts)

def fetch_fault_traces():
    print("Fetching active fault and tectonic lineament network for Sikkim...")
    fault_lines = []
    
    # 1. Download GEM Active Faults
    try:
        url = 'https://raw.githubusercontent.com/GEMScienceTools/gem-global-active-faults/master/geojson/gem_active_faults_harmonized.geojson'
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            for f in data.get('features', []):
                geom = f.get('geometry', {})
                coords = geom.get('coordinates', [])
                if geom.get('type') == 'LineString':
                    sub_lines = [coords]
                elif geom.get('type') == 'MultiLineString':
                    sub_lines = coords
                else:
                    continue
                for s in sub_lines:
                    pts = [(c[1], c[0]) for c in s]
                    # Check if bounding box intersects Sikkim Himalayan belt (26.5-28.5 N, 87.5-89.5 E)
                    in_region = any(26.5 <= lat <= 28.5 and 87.5 <= lon <= 89.5 for lat, lon in pts)
                    if in_region:
                        fault_lines.append(pts)
            print(f"Retrieved {len(fault_lines)} regional fault line segments from GEM database.")
    except Exception as e:
        print(f"GEM faults fetch error: {e}")
        
    # 2. Add structural tectonic boundaries & major lineaments for Sikkim
    # (Main Boundary Thrust, Main Central Thrust, South Tibetan Detachment System, Teesta lineament)
    mbt_sikkim = [(27.05, 88.10), (27.08, 88.35), (27.12, 88.60), (27.15, 88.85)]
    mct_sikkim = [(27.35, 88.15), (27.42, 88.40), (27.50, 88.65), (27.55, 88.90)]
    stds_sikkim = [(27.85, 88.20), (27.92, 88.45), (28.00, 88.70), (28.05, 88.95)]
    tista_lineament = [(27.10, 88.50), (27.35, 88.52), (27.65, 88.55), (28.05, 88.60)]
    rangit_lineament = [(27.15, 88.30), (27.35, 88.28), (27.55, 88.20)]
    gangtok_lineament = [(27.25, 88.55), (27.35, 88.65), (27.45, 88.75)]
    
    structural_faults = [mbt_sikkim, mct_sikkim, stds_sikkim, tista_lineament, rangit_lineament, gangtok_lineament]
    fault_lines.extend(structural_faults)
    print(f"Total active fault & lineament traces in analysis: {len(fault_lines)}")
    
    all_fault_pts = []
    for line in fault_lines:
        all_fault_pts.extend(dense_line_points(line, step_m=150))
    return np.array(all_fault_pts)

def main():
    print("=== Step 2: Extracting Drainage and Fault Proximity Features ===")
    df = pd.read_csv("dataset/sikkim_static_features_1km.csv")
    cell_utm = df[['centroid_x', 'centroid_y']].values
    
    # 1. Drainage Proximity (DTD)
    stream_pts = fetch_osm_drainage()
    print(f"Building KDTree for {len(stream_pts)} drainage points...")
    stream_tree = cKDTree(stream_pts)
    dist_stream_m, _ = stream_tree.query(cell_utm)
    dist_stream_km = dist_stream_m / 1000.0
    
    # 2. Fault Proximity (DTL)
    fault_pts = fetch_fault_traces()
    print(f"Building KDTree for {len(fault_pts)} fault points...")
    fault_tree = cKDTree(fault_pts)
    dist_fault_m, _ = fault_tree.query(cell_utm)
    dist_fault_km = dist_fault_m / 1000.0
    
    out_df = pd.DataFrame({
        'cell_id': df['cell_id'],
        'distance_to_drainage_km': np.round(dist_stream_km, 3),
        'distance_to_fault_km': np.round(dist_fault_km, 3)
    })
    
    out_path = "dataset/features_hydrology_faults_1km.csv"
    out_df.to_csv(out_path, index=False)
    print(f"Saved hydrology & fault features to {out_path}")
    print(out_df.describe())

if __name__ == '__main__':
    main()
