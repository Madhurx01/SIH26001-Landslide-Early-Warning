# Real satellite NDVI pipeline

`SCRIPTS/04_fetch_ndvi_features.py` replaces the former synthetic land-cover
lookup with NDVI calculated from real Sentinel-2 observations. It does not use
ESA WorldCover classes, elevation, aspect, constants, interpolation, or any
other invented fallback to fill NDVI.

## Source and temporal period

- Product: Copernicus Sentinel-2 MSI Level-2A surface reflectance.
- Access: Microsoft Planetary Computer public STAC collection
  [`sentinel-2-l2a`](https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a).
- Default acquisition period: 2021-10-01 through 2021-11-30, inclusive. This
  post-monsoon window gives a lower-cloud vegetation baseline while remaining a
  historical, fixed, reproducible period. It is not a current/live NDVI layer.
- Catalog screen: `eo:cloud_cover <= 30%` for each source tile. This admits
  locally clear pixels from partly cloudy 100 km tiles; the strict pixel-level
  SCL filter remains authoritative because tile-level cloud percentage is not
  spatially specific enough.
- Credentials: none. Internet access to the Planetary Computer API and its
  signed Azure Blob GeoTIFF URLs is required.

The period and cloud threshold can be changed with `--start-date`, `--end-date`,
and `--max-cloud-cover`. Those parameters and the actual source item IDs are
recorded in the generated metadata sidecar.

## Native data and NDVI calculation

- Red: B04 Level-2A surface reflectance, native 10 m pixel spacing.
- Near infrared: B08 Level-2A surface reflectance, native 10 m pixel spacing.
- Quality layer: Scene Classification Layer (SCL), native 20 m pixel spacing.
- Formula: `(B08 - B04) / (B08 + B04)` after applying the product radiometric
  scale and offset. Processing Baseline 04.00+ products use the documented
  `BOA_ADD_OFFSET=-1000` and `QUANTIFICATION_VALUE=10000` when STAC does not
  supply explicit raster scale/offset metadata.

The implementation reads only relevant Cloud-Optimized GeoTIFF windows in
bounded chunks; it does not fabricate API responses or NDVI values.

## Cloud, quality, and nodata handling

SCL is nearest-neighbour resampled to the 10 m B04/B08 grid. Only SCL classes 4
(vegetation), 5 (not vegetated), 6 (water), and 7 (unclassified) are retained.
Classes 0 (nodata), 1 (saturated/defective), 2 (cast shadow), 3 (cloud shadow),
8/9 (cloud), 10 (cirrus), and 11 (snow/ice) are excluded. DN zero, source nodata,
negative reflectance, non-finite values, and invalid NDVI denominators are also
excluded.

A cell/acquisition is accepted only when at least 20% of its Sikkim-intersection
area has valid 10 m observations by default. If no acquisition qualifies, the
cell's `ndvi_mean` is left blank/NaN. There is no imputation in this step.

## Aggregation to the unchanged 1 km grid

The script reads the canonical square grid from
`DATA/PROCESSED/GRID/sikkim_grid_1km.gpkg`. It validates the 7,390 ordered IDs
`SKM_00001` through `SKM_07390` against the static feature table and never
recreates or changes the grid.

For each acquisition, valid native 10 m NDVI pixels are spatially averaged in
each analysis cell after clipping partial edge cells to the Sikkim boundary.
Where same-acquisition MGRS tiles overlap, the tile result with the most valid
pixels is retained to prevent double counting. The final value is the temporal
median of accepted per-acquisition cell means. The legacy field name
`ndvi_mean` is retained strictly for downstream compatibility.

The resulting value is an aggregate assigned to a 1 km analysis cell. Sentinel-2
NDVI does **not** have 1 km native resolution.

## Outputs and fail-safe provenance

Run from any working directory with the project environment:

```powershell
python SCRIPTS/04_fetch_ndvi_features.py
```

Use `--catalog-only` to validate local inputs and the live catalog without
reading imagery or writing outputs.

The full run writes:

- `dataset/features_ndvi_1km.csv` with exactly `cell_id,ndvi_mean`.
- `dataset/features_ndvi_1km.metadata.json` with the product, dates, items,
  filtering, aggregation, QA counts, missing-value count, and CSV SHA-256.

`SCRIPTS/05_merge_all_features.py` requires this metadata, verifies that it says
the source is a real Sentinel-2 observation workflow, checks the CSV checksum,
and enforces exact ordered `cell_id` alignment. An old synthetic or manually
modified NDVI CSV therefore fails closed instead of silently entering training.

## Limitations

- SCL can leave residual haze/cloud or remove valid terrain in steep Himalayan
  conditions; cast-shadow pixels are intentionally excluded.
- A two-month historical composite does not represent seasonal or current
  vegetation conditions. Use explicit alternate dates for another scientific
  objective and retain the generated metadata.
- The scene-level cloud threshold can reject a tile even when a small part of
  Sikkim is clear. Conversely, accepted tiles still need the pixel-level mask.
- Temporal medians of per-acquisition spatial means are robust summaries, not a
  pixel-level phenology model.
- Missing cells remain missing. Any future model imputation policy must be
  explicit and belongs to a separate model-training change.

Primary product references: the [Sentinel-2 mission band resolutions](https://sentiwiki.copernicus.eu/web/s2-mission)
and [Level-2A processing/SCL definitions](https://sentiwiki.copernicus.eu/web/s2-processing).
