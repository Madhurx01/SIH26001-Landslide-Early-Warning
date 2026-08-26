# 🏛️ AAPTIRAKSHAK (SIH26001) — Codebase Architecture & Technical Guide

This document provides a comprehensive, file-by-file breakdown of the **AAPTIRAKSHAK Landslide Early Warning & Tactical Command System** codebase.

---

# 🗺️ 1. High-Level System Architecture

```text
 ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   END-TO-END DATA & CODE FLOW                               │
 ├─────────────────────────────────────────────────────────────────────────────────────────────┤
 │                                                                                             │
 │   1. SATELLITE & GIS INGESTION                                                              │
 │   ├── ALOS PALSAR 30m DEM ──────┐                                                           │
 │   ├── GSI Lithology & Faults ───┼──> [PREPROCESSING 01-08] ──> 2,984 Static Grid Cells      │
 │   └── Open-Meteo / NASA Radar ──┘                                      │                    │
 │                                                                        ▼                    │
 │   2. MACHINE LEARNING ENGINE                                                                │
 │   ├── Cost-Sensitive XGBoost (scale_pos_weight=14.2) ────────> [SCRIPTS 09-11]              │
 │   └── TreeSHAP Game-Theoretic Factor Decomposition                     │                    │
 │                                                                        ▼                    │
 │   3. REAL-TIME CLOUD WORKER                                                                 │
 │   └── [12_hourly_cloud_updater.py] ──> Vectorized 36ms Inference ──> realRiskData.json      │
 │                                                                        │                    │
 │   4. CLOUD & CLIENT PLATFORM                                           ▼                    │
 │   ├── Google Firebase Realtime Database <────> [FRONTEND/src/services/reports.js]           │
 │   └── React + Leaflet GIS Dashboard <────────> [FRONTEND/src/App.jsx]                      │
 │                                                                                             │
 └─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

# 📂 2. Repository Directory Structure

```text
SIH26001-Landslide-Early-Warning/
├── PREPROCESSING/                   # Raw GIS extraction & spatial factor pipelines
│   ├── 01_dem_processing.py         # Derives Slope, Aspect, Curvature from 30m DEM
│   ├── 02_hydrology_twi.py          # Topographic Wetness (TWI) & Stream Transport (STI)
│   ├── 03_faults_geology.py         # Distance to Faults & GSI Lithology rasterization
│   ├── 04_infrastructure.py        # Distance to Roads (Toe cuts) & Distance to Railways
│   ├── 05_environmental_ndvi.py     # Sentinel-2 NDVI canopy & LULC classification
│   ├── 06_grid_generator.py         # Generates 2,984 hexagonal monitoring cells
│   ├── 07_feature_merger.py         # Fuses 13 static conditioning factors into tabular matrix
│   └── 08_temporal_weather.py       # Ingests NASA GPM IMERG 1d, 3d, 7d rainfall series
│
├── SCRIPTS/                         # Model training, SHAP, and automated cloud worker
│   ├── 09_train_static_model.py     # Random Forest / LightGBM Layer 1 Susceptibility
│   ├── 10_train_dynamic_xgboost.py  # Cost-Sensitive XGBoost Layer 2 Trigger (scale_pos_weight=14.2)
│   ├── 11_generate_shap_values.py   # TreeSHAP exact polynomial factor decomposition
│   └── 12_hourly_cloud_updater.py   # Automated serverless hourly worker (36ms inference)
│
├── FRONTEND/                        # React 18 + Vite + Leaflet Tactical Command Console
│   ├── api/                         # Vercel Serverless Function proxy
│   │   ├── reports.js               # Serverless HTTPS proxy to Firebase Realtime DB
│   │   └── ip.js                    # Client IP detection for Master Admin IP Guard
│   │
│   ├── src/
│   │   ├── components/              # 11 Modular Dashboard Components
│   │   │   ├── AlertsPanel.jsx              # Active Warnings & NDMA 4-color broadcast
│   │   │   ├── AuthModal.jsx                # Multi-tier RBAC login & Master IP override
│   │   │   ├── CitizenReportModal.jsx       # GPS auto-detect & 35KB canvas photo compressor
│   │   │   ├── DataSourceStatus.jsx         # Live satellite feed health monitor
│   │   │   ├── EmergencyPriorityPanel.jsx   # Tactical SDRF dispatch vs Citizen Helplines
│   │   │   ├── Header.jsx                   # Live IST timestamp, user profile badge, language
│   │   │   ├── HighwayInspectorModal.jsx    # NH-10 & highway elevation profile deep-dive
│   │   │   ├── ReportVerificationPanel.jsx  # Admin incident queue with photo lightbox
│   │   │   ├── RiskLegend.jsx               # NDMA 4-color threshold breakdown
│   │   │   ├── RiskMap.jsx                  # Leaflet 2,984-cell vector layer & road overlay
│   │   │   ├── RoadRiskPanel.jsx            # Real-time highway transit clearance table
│   │   │   ├── SelectedCellPanel.jsx        # TreeSHAP diverging horizontal factor bars
│   │   │   ├── SeverityBadge.jsx            # Dynamic color-coded risk badge (Green/Yellow/Orange/Red)
│   │   │   ├── SummaryCards.jsx             # Top KPI operational metric grid
│   │   │   └── WeatherRiskPanel.jsx         # Hydrological gauges & hourly rain bar chart
│   │   │
│   │   ├── data/
│   │   │   ├── realRiskData.json            # Master 2,984-cell state matrix (Live/Storm cache)
│   │   │   └── mockRiskData.js              # Severity color configurations and schema bindings
│   │   │
│   │   ├── services/
│   │   │   ├── auth.js                      # JWT token auth, IP guard, and 3-tier user presets
│   │   │   ├── reports.js                   # Permanent Google Firebase Realtime DB sync client
│   │   │   └── api.js                       # HTTP client wrapper
│   │   │
│   │   ├── App.jsx                          # Main application state, mode toggle & 3s polling loop
│   │   ├── index.css                        # High-contrast military command dark theme
│   │   └── main.jsx                         # React DOM mount point
│   │
│   ├── index.html                           # Single-page HTML root
│   ├── package.json                         # Node dependencies (Leaflet, Lucide, React 18)
│   ├── vercel.json                          # Vercel deployment routes and serverless headers
│   └── vite.config.js                       # Vite bundler configuration & local dev proxy
│
└── SERVER/                          # Dedicated Node.js fallback storage server
    ├── storageServer.js                     # Express-free lightweight HTTP storage daemon (Port 4000)
    └── reports_db.json                      # Local file persistence database
```

---

# ⚙️ 3. Detailed Component & Pipeline Breakdown

---

### 🔹 Part A: Data Extraction & Preprocessing (`PREPROCESSING/`)
* **`01_dem_processing.py`:** Loads ALOS PALSAR 30m DEM GeoTIFF. Computes directional gradients using Sobel spatial convolution filters to extract slope gradient ($^\circ$), profile curvature (acceleration), and planform curvature (flow convergence).
* **`02_hydrology_twi.py`:** Calculates upstream contributing catchment area ($A_s$) via D8 flow routing to generate the Topographic Wetness Index: $\text{TWI} = \ln(A_s / \tan \beta)$ and Stream Transport Index (STI).
* **`03_faults_geology.py` & `04_infrastructure.py`:** Computes Euclidean distance fields to the Main Central Thrust (MCT) tectonic fault lines, NH-10 road toe cuts, and railway alignments.
* **`06_grid_generator.py`:** Discretizes Sikkim ($7,096\text{ km}^2$) into **2,984 regular hexagonal spatial cells** with fixed centroids and bounding polygons.
* **`07_feature_merger.py`:** Samples the 13 rasters at each cell centroid, producing the static feature matrix ($2984 \times 13$).

---

### 🔹 Part B: Machine Learning & Cloud Worker (`SCRIPTS/`)
* **`09_train_static_model.py`:** Trains Random Forest on historical GSI landslide scars to establish the baseline susceptibility $LSI_{\text{static}} \in [0.0, 1.0]$.
* **`10_train_dynamic_xgboost.py`:** Trains Cost-Sensitive XGBoost (`scale_pos_weight = 14.2`, `max_depth = 5`, `learning_rate = 0.03`) coupling $LSI_{\text{static}}$ with antecedent rainfall ($R_{1\text{d}}, R_{3\text{d}}$) and root-zone soil saturation ($\theta_{\text{soil}}$).
* **`11_generate_shap_values.py`:** Executes TreeSHAP in $O(TLD^2)$ time to pre-compute game-theoretic feature attribution matrices ($\phi_i$).
* **`12_hourly_cloud_updater.py`:**
  * Connects to Open-Meteo REST APIs for Gangtok, Mangan, Namchi, and Geyzing.
  * Ingests 24h accumulated rain and NASA SMAP root-zone soil moisture.
  * Executes vectorized NumPy array inference across all 2,984 cells in **$36.07\text{ ms}$**.
  * Writes current Indian Standard Time (IST) timestamp and exports updated state to `realRiskData.json`.

---

### 🔹 Part C: Frontend React Dashboard (`FRONTEND/src/`)

#### 1. Core Logic & State Management
* **[`App.jsx`](file:///home/arjun/Landslide_prediction_sikkim/SIH26001-Landslide-Early-Warning/FRONTEND/src/App.jsx):**
  * Manages global state: `telemetryMode` (`'live'` vs `'storm'`), `selectedCell`, `currentUser` (Admin/Analyst/Viewer), `citizenReports`, and `timelineStep`.
  * Runs a **3-second background auto-polling loop** querying Google Firebase Realtime DB to detect incoming citizen ground reports in real time.
* **[`services/reports.js`](file:///home/arjun/Landslide_prediction_sikkim/SIH26001-Landslide-Early-Warning/FRONTEND/src/services/reports.js):**
  * Direct client connection to `https://sih-26001-default-rtdb.firebaseio.com/reports`.
  * Implements atomic keyed writes (`PUT /reports/CR-XXXX.json`) to prevent multi-user race conditions, with automatic JSON dictionary normalization.
* **[`services/auth.js`](file:///home/arjun/Landslide_prediction_sikkim/SIH26001-Landslide-Early-Warning/FRONTEND/src/services/auth.js):**
  * Role-Based Access Control (RBAC) with 3 presets:
    1. `admin`: Col. D. S. Rawat (State Disaster Commander)
    2. `analyst`: Dr. P. Roy (Lead Geotechnical Scientist)
    3. `viewer`: Tenzing Lepcha (Citizen / Traveler)
  * **Master Admin IP Guard:** Automatically detects client public IP; if it does not match `47.29.188.162`, prompts for master override passcode (`SIH2026-SDMA-MASTER`).

#### 2. Visual & Interactive UI Components
* **[`RiskMap.jsx`](file:///home/arjun/Landslide_prediction_sikkim/SIH26001-Landslide-Early-Warning/FRONTEND/src/components/RiskMap.jsx):**
  * Renders 2,984 vector hexagons on Leaflet with GPU-accelerated canvas rendering.
  * Overlays Sikkim district boundaries, national highway lines (NH-10), settlements, and historical GSI landslide markers.
* **[`SelectedCellPanel.jsx`](file:///home/arjun/Landslide_prediction_sikkim/SIH26001-Landslide-Early-Warning/FRONTEND/src/components/SelectedCellPanel.jsx):**
  * Displays cell telemetry (Slope, Elevation, 3-day Rain, Soil Saturation).
  * Renders **TreeSHAP Diverging Horizontal Bars** showing the exact mathematical risk contribution of each physical factor.
* **[`ReportVerificationPanel.jsx`](file:///home/arjun/Landslide_prediction_sikkim/SIH26001-Landslide-Early-Warning/FRONTEND/src/components/ReportVerificationPanel.jsx):**
  * Displays crowd-sourced ground observations with live Firebase connection indicator.
  * Admin human-in-the-loop action buttons: **"✅ Verify & Alert BRO"** and **"❌ Dismiss"**.
* **[`CitizenReportModal.jsx`](file:///home/arjun/Landslide_prediction_sikkim/SIH26001-Landslide-Early-Warning/FRONTEND/src/components/CitizenReportModal.jsx):**
  * Mobile-ready PWA report form with HTML5 Geolocation auto-detection.
  * Client-side HTML5 canvas image downscaling compressing high-res photos to $\approx 35\text{ KB}$ in $< 10\text{ ms}$ for instant 2G/3G transmission.

---

# 🚀 4. How to Run Locally

### Start Frontend Dev Server:
```bash
cd SIH26001-Landslide-Early-Warning/FRONTEND
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```
*Access in browser at:* `http://localhost:5173/`

### Run Hourly Python Satellite Updater:
```bash
cd SIH26001-Landslide-Early-Warning
python SCRIPTS/12_hourly_cloud_updater.py --mode live
```
