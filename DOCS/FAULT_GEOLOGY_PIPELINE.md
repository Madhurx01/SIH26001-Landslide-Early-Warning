# Provenance-safe drainage and active-fault distance pipeline

SCRIPTS/02_fetch_hydrology_faults.py builds the two compatible distance
features consumed by the existing 13-factor pipeline:

- distance_to_drainage_km
- distance_to_fault_km

The output remains one ordered row for each of the unchanged 7,390 square
1 km Sikkim analysis cells. The source vectors do not have 1 km native
resolution; only the analysis unit is 1 km.

## Fault source

The fault source is the GEM Global Active Faults Database harmonized GeoJSON:

- Provider: Global Earthquake Model (GEM) Foundation
- Dataset: GEM Global Active Faults Database
- Immutable Git revision:
  56816508ad92fd6846dad1163b1c8c01376a2cd1
- Pinned file:
  geojson/gem_active_faults_harmonized.geojson
- Pinned file SHA-256:
  37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1
- License: CC BY-SA 4.0

The raw URL contains the full Git commit rather than the moving master
branch. The downloaded bytes are SHA-256 hashed and the revision, URL, source
feature counts, used geometry counts, byte count, license, and access date are
recorded in the metadata sidecar.

GEM is used as an **active-fault proxy/source**. It is not Geological Survey
of India lithology, a complete geological map, or a complete inventory of every
fault, thrust, shear zone, or remotely sensed lineament in Sikkim. No lithology
model feature is introduced by this workflow.

## Drainage source

Drainage is taken from real OpenStreetMap ways tagged:

- waterway=river
- waterway=stream
- waterway=canal

The data are requested from a public Overpass API. Several public endpoints
are tried in order for service availability, but a response is accepted only
when it is valid JSON, has no Overpass error remark, includes at least the
configured minimum number of valid ways, and retains that minimum after
geospatial filtering. The selected endpoint, query, OSM base timestamp,
response SHA-256, response size, source counts, used geometry counts, OSM
way-ID range, access date, and ODbL attribution are recorded.

There is no synthesized river fallback. Failure of every endpoint leaves any
previously trusted outputs untouched and terminates the run.

## Geometry and distance processing

1. Read the canonical grid from
   DATA/PROCESSED/GRID/sikkim_grid_1km.gpkg.
2. Verify exactly 7,390 ordered identifiers, SKM_00001 through
   SKM_07390, one-square-kilometre geometry, and exact alignment with the
   static feature table.
3. Read the real Sikkim boundary and create documented source-search buffers:
   100 km for regional active faults and 10 km for drainage by default.
4. Reproject both source layers from WGS84 to EPSG:32645.
5. Repair invalid source geometry when Shapely can do so, retain only valid
   LineString components intersecting the relevant buffer, and record repairs.
6. Calculate exact Shapely point-to-LineString nearest distance from each
   canonical cell centroid in metres, then convert to kilometres.

The implementation does not densify lines or use a sampled-point KDTree.

## Outputs and atomicity

Run from the project environment:

    python SCRIPTS/02_fetch_hydrology_faults.py

The successful run writes:

- dataset/features_hydrology_faults_1km.csv
- dataset/features_hydrology_faults_1km.metadata.json

The CSV retains exactly these columns:

1. cell_id
2. distance_to_drainage_km
3. distance_to_fault_km

Both destinations are first written to unique temporary files in the output
directory. The complete CSV is hashed, the sidecar is written with that hash,
and only then are the destinations atomically replaced. A source, parsing,
geometry, validation, or distance error occurs before replacement.

The metadata records source URLs and revisions, access date, source and used
geometry counts, CRS, buffers, distance definition, output row and unique-ID
counts, ordered-cell validation, missing-value counts, distance summaries, and
the output CSV SHA-256.

## Merge-time fail-closed gate

SCRIPTS/05_merge_all_features.py refuses the feature file unless all of the
following are true:

- The metadata sidecar exists and is valid JSON.
- The data origin is authoritative geospatial vectors.
- Both synthetic_fallback_used and manual_geometry_used are false.
- The fault source is the approved immutable GEM commit above.
- The drainage source is OpenStreetMap through an Overpass endpoint.
- Both source records report at least one real LineString geometry.
- Processing used EPSG:32645 and exact point-to-LineString distance.
- The CSV checksum matches the sidecar.
- Columns are exact, distances are finite and non-negative, and cell IDs are
  unique and exactly aligned in canonical order.
- Row/grid metadata agrees with the current base table and unchanged grid.

Missing, stale, manually edited, synthetic, misaligned, malformed, or
checksum-mismatched data therefore cannot silently enter the merged training
dataset.

## Limitations

- GEM maps active faults of seismogenic concern. It is not a substitute for a
  detailed GSI geological, lithological, shear-zone, or lineament survey.
- OSM is community-maintained; waterway completeness and positional accuracy
  can vary.
- The configured buffers limit the downloaded working set. They are recorded
  so a deliberate future change remains auditable.
- Distances are static spatial proxies. They do not establish fault activity at
  a specific cell or time.
- No missing values are invented or imputed by this step.
