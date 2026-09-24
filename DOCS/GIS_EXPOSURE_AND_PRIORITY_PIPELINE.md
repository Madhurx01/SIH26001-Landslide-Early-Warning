# GIS Exposure and Emergency-Priority Pipeline

## Purpose and scope

The exposure stage converts the current 7,390-cell Operational Risk Index into
asset-level decision-support context using the existing processed OpenStreetMap
(OSM) road and settlement geometries. It reports **potential GIS exposure**.
It does not assert that a road is blocked or damaged, that a settlement is
affected, or that evacuation is required.

The stage runs only after a complete operational weather/risk update succeeds.
It does not change the canonical grid, static susceptibility, weather
interpolation, Dynamic Trigger Index, Operational Risk Index, NDVI,
fault/drainage, or model-training logic.

## Authoritative inputs

- `DATA/PROCESSED/STATIC/OSM/sikkim_roads.gpkg`, layer `sikkim_roads`;
- `DATA/PROCESSED/STATIC/OSM/sikkim_settlements.gpkg`, layer
  `sikkim_settlements`;
- `DATA/PROCESSED/GRID/sikkim_grid_1km.gpkg`, layer `sikkim_grid_1km`; and
- the complete, ordered 7,390-cell current/24h/48h/72h operational-risk layer
  produced in memory by `SCRIPTS/12_hourly_cloud_updater.py`.

All spatial calculations use EPSG:32645 so lengths are measured in metres. The
output metadata records source paths, SHA-256 checksums, feature counts, CRS,
methods, rules, and run timestamp. Missing/empty/invalid GIS inputs, incomplete
cell coverage, duplicate/reordered IDs, invalid risk categories, or indices
outside 0–100 abort the update instead of creating fallback exposure.

## Road exposure

Every one of the 8,879 processed OSM road features is evaluated. For each of
the current, +24h, +48h, and +72h risk layers, the engine:

1. selects canonical cells categorized HIGH or SEVERE;
2. performs an exact spatial intersection between each OSM
   LineString/MultiLineString and the square cell polygons;
3. discards zero-length boundary touches;
4. counts distinct intersected HIGH and SEVERE cells; and
5. sums the intersected line length as approximate exposed road length.

Named road entities are grouped only when they share actual OSM `ref` and/or
`name` tags. Unnamed roads remain individual OSM features and are displayed as
`Unnamed OSM road`; no highway or corridor name is inferred from location.

Operational status rules are fixed:

| Status | Rule |
|---|---|
| CRITICAL | At least one current SEVERE cell intersects the road entity |
| HIGH RISK | At least one current HIGH cell and no current SEVERE cell intersects it |
| WATCH | No current HIGH/SEVERE intersection, but at least one forecast HIGH/SEVERE intersection at +24h, +48h, or +72h |
| NORMAL | No current or forecast HIGH/SEVERE intersection |

These are screening statuses, not traffic-control or physical-condition
reports. `CRITICAL` never means confirmed blocked.

The segment-level audit CSV retains every road feature. To keep the interactive
map responsive, the dashboard displays all entities carrying an actual OSM
name/reference plus the 200 highest-ranked exposed unnamed entities. Summary
counts continue to cover the complete road dataset.

## Settlement exposure

Every processed OSM settlement point is assigned to its containing canonical
cell. A deterministic lowest-`cell_id` tie-break handles a point exactly on a
cell boundary; nearest-cell assignment is used only when no containing square
is found. Each record carries current and +24h/+48h/+72h Operational Risk
Index/category fields and explicit potential-exposure booleans.

OSM population tags are retained only when actually present and positive.
Missing population remains unavailable; the pipeline never estimates or
fabricates population exposure.

## Emergency prioritization

The unit of prioritization is a canonical risk cell. The fixed rules are:

| Priority | Rule |
|---|---|
| P1 | Current SEVERE with mapped road or settlement exposure; or a verified geo-tagged report in a current HIGH/SEVERE cell |
| P2 | Current HIGH with mapped road or settlement exposure |
| P3 | Current SEVERE without mapped road or settlement exposure |

Records are ordered by P1, P2, P3; then descending current Operational Risk
Index; then canonical `cell_id`. Reasons enumerate mapped exposure and any
verified-report boost. Recommendations request human review, monitoring, or
field verification and are not automatic government orders.

The dashboard shows the top 50 records for usability; the generated priority
CSV retains the complete ranked list.

## Citizen and field reports

Only records explicitly marked `VERIFIED` and carrying parseable geographic
coordinates may boost priority. Pending, dismissed, ungeoreferenced, or
malformed reports have no effect. A verified report can confirm an incident
for prioritization, but the pipeline does not copy a reporter's blockage claim
into road status and never triggers evacuation or dispatch automatically.

The current checked-in report pool contains no verified reports, so the present
run has no report-based boosts.

## Outputs and integrity

Successful runs atomically replace:

- `FRONTEND/src/data/realRiskData.json` with road, settlement, alert, priority,
  summary, and provenance fields;
- `dataset/road_exposure_current.csv` with all OSM road-feature results;
- `dataset/settlement_exposure_current.csv` with all mapped settlements;
- `dataset/emergency_priorities_current.csv` with the full ranked queue; and
- `dataset/exposure_current.metadata.json` with provenance and output SHA-256
  checksums.

The legacy `SCRIPTS/08_generate_dashboard_integration_data.py` entry point is a
compatibility wrapper only. Its former manually authored roads, settlements,
population estimates, exposure counts, geological claims, and priority queue
have been removed; invoking it now delegates to the same provenance-safe live
pipeline.

The dashboard's road and settlement layers use actual OSM coordinates. Terms
such as `potentially exposed`, `high-risk corridor`, and `field confirmation
required` distinguish model/GIS screening from confirmed operational impacts.

## Limitations

OSM completeness, tagging, geometry age, and positional accuracy vary. A road
intersection with a 1 km HIGH/SEVERE cell does not prove the road itself crosses
the unstable portion of that cell. Summed intersection length is an
approximation at the analysis-grid scale and is not a surveyed damaged length.
Settlement points represent mapped places, not building footprints or
population distribution. Forecast exposure inherits all limitations and
uncertainty of the Open-Meteo spatial interpolation and prototype index.
