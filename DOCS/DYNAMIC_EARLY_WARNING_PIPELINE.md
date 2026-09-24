# Dynamic Early-Warning Pipeline

## Scope and interpretation

The live layer is a transparent **Operational Risk Index prototype** for
decision support. It combines the existing per-cell static susceptibility with
a spatially varying Dynamic Trigger Index derived from operational weather
model/API data. Neither index is a calibrated probability of landslide
occurrence. A forecast index is not an observed event or a guaranteed
prediction, and this layer must not be the sole basis for evacuation, road
closure, or emergency dispatch.

Open-Meteo Forecast API is the current prototype weather source. Its
precipitation and model-derived 0–7 cm volumetric soil moisture are **not NASA
IMERG rainfall and not NASA SMAP soil moisture**. Future production adapters
are described below.

## Spatial weather sampling and interpolation

For each run, the updater derives the geographic extent from the 7,390 ordered
canonical cell centroids and constructs a deterministic rectangular sampling
lattice. With the present grid extent this is 6 rows by 5 columns, or 30
Open-Meteo query points. The requested maximum spacing is 0.25 degrees; the
current fitted spacing is about 23.0 km north–south and 22.3 km east–west.
Coordinates, bounds, shape, requested and fitted spacing, and successful and
failed point counts are written to output metadata.

Every weather variable is interpolated to all canonical 1 km cell centroids by
four-neighbour inverse-distance weighting (IDW) with power 2. Distances use a
local equirectangular kilometre approximation at Sikkim's mean latitude. Exact
source-point coincidences are stabilized with a very small positive distance.
The same neighbour selection and weights are applied independently to each
variable. This produces a reproducible spatial weather layer, but it does
**not** make the weather data native 1 km observations or resolve mountain
microclimates at 1 km.

The updater validates the complete 30-point response before interpolation. It
does not substitute a statewide mean or fabricate missing values.

## Weather windows

Open-Meteo is requested with seven past days and four forecast days at hourly
resolution. At each source point the updater validates timestamps, array
lengths, finite non-negative precipitation, and soil moisture in the physical
range 0–1 m³/m³, then derives:

- prior/current 24-hour precipitation (`rainfall_1d_mm`);
- antecedent 48-, 72-, 96-, and 168-hour precipitation, of which the 3-day and
  7-day totals are displayed;
- current 0–7 cm volumetric soil moisture;
- cumulative forecast precipitation through +24, +48, and +72 hours; and
- forecast 0–7 cm soil moisture at +24, +48, and +72 hours.

The current index includes the next-24-hour rainfall forecast as a near-term
trigger. Forecast indices project the rolling windows at +24, +48, and +72
hours by adding forecast precipitation and removing elapsed antecedent
precipitation where the available windows permit it. They use forecast soil
moisture at the corresponding horizon.

## Static inputs

Static inputs are joined one-to-one on the canonical ordered `cell_id`
contract:

- the existing 7,390-cell uncalibrated static susceptibility output;
- SRTM-derived slope/elevation and OSM road/settlement proximity;
- provenance-validated GEM active-fault proxy and OSM drainage distances; and
- Sentinel-2 L2A NDVI, preserving unavailable (`NaN`) observations.

Duplicate, missing, reordered, or unexpected canonical IDs fail the update.
NDVI remains unavailable when no valid satellite observation exists and is
omitted from the corresponding factor explanation.

## Dynamic Trigger Index

Dynamic Trigger Index version `dti-v2-spatial-forecast` is a documented
prototype rule, not a fitted model and not SHAP or learned feature importance.
For each cell and horizon, each component is clipped to 0–1:

```text
R1 = rainfall_1d / 100 mm
R3 = rainfall_3d / 200 mm
R7 = rainfall_7d / 350 mm
SM = (soil_moisture - 0.15) / 0.30 m³/m³
F  = cumulative forecast rainfall / horizon threshold

Dynamic Trigger Index = 100 × (
    0.35 × R1 +
    0.25 × R3 +
    0.10 × R7 +
    0.20 × SM +
    0.10 × F
)
```

The forecast rainfall thresholds are 100 mm at current/+24 h, 160 mm at +48
h, and 220 mm at +72 h. The precipitation thresholds represent conservative
prototype intensity/accumulation scales selected for transparent screening;
they have not been calibrated against a Sikkim landslide-event catalogue.
Recent rainfall receives the greatest weight, followed by the three-day
accumulation and soil wetness; seven-day and forward rainfall terms provide
antecedent and near-future context.

## Operational Risk Index and categories

Operational Risk Index version `ori-v2-65-static-35-trigger` is:

```text
Operational Risk Index =
    0.65 × static susceptibility + 0.35 × Dynamic Trigger Index
```

Both inputs and the result use a 0–100 scale. Static susceptibility preserves
the spatial baseline while weather can raise or lower the operational index.
The same formula is applied to current, +24 h, +48 h, and +72 h triggers.

The fixed screening categories are:

| Category | Operational Risk Index |
|---|---:|
| LOW | 0 to less than 20 |
| MODERATE | 20 to less than 50 |
| HIGH | 50 to less than 75 |
| SEVERE | 75 to 100 |

These thresholds are operational prototype bands, not probability cutoffs.
They are fixed in code and are not adjusted per run to force class coverage.
The dashboard's `risk_factors` are contextual inputs only and do not claim
causal attribution or unsupported geology such as bedrock stability or shear
stress.

## Provenance, freshness, and fail-closed behavior

Output metadata records source and fetch timestamps, freshness, every source
coordinate, point counts and failures, sampling-grid geometry, interpolation
method and parameters, missing-data state, and both formula/version strings.
The current maximum source age is three hours.

If any source point fails or returns incomplete, invalid, stale, or
future-dated data, the live updater fails closed. It does not recompute any
index, insert default weather, or partially accept the spatial field. The last
trusted cell/weather values remain in place and metadata marks telemetry
unavailable/stale with the failed fetch details. Static provenance/checksum
failure, duplicate IDs, misalignment, or missing required fault distances also
aborts before output replacement.

Successful and failed-status writes use a same-directory temporary file and
atomic replace. Road and settlement exposure counts remain unavailable until
a real spatial exposure calculation is connected.

## Demonstration modes and limitations

`--mode storm`, `--mode dry`, and historical timeline snapshots are explicitly
labelled simulations. Their uniform weather assumptions never share live
provenance.

Open-Meteo is a temporary operational prototype source. Its underlying model
grid, terrain representation, update cycle, and forecast uncertainty are not
equivalent to rain gauges or in-situ soil sensors. IDW smooths between sparse
samples and cannot reproduce orographic gradients, convective cells, snowmelt,
sub-grid drainage, soil depth, or localized saturation. Forecast uncertainty
generally increases from 24 to 72 hours. The formulas and thresholds require
validation against independent observations and a landslide-event catalogue
before operational safety use.

Planned adapters should ingest independently quality-controlled IMD rain-gauge
or gridded rainfall, NASA GPM IMERG precipitation, and NASA SMAP or another
validated soil-moisture product. Each adapter must preserve native product
identity, resolution, timestamps, quality flags, uncertainty, missing values,
and provenance rather than relabelling or filling absent observations.
