# Dynamic Early-Warning Pipeline

## Current scope

The live layer is an **Operational Risk Index prototype** for decision support. It
combines the existing per-cell static susceptibility score with recent
precipitation and shallow soil-moisture triggers. The 0–100 result is not a
calibrated probability of landslide occurrence and must not be used as a sole
basis for evacuation, road closure, or emergency dispatch.

The current operational weather adapter is the public Open-Meteo Forecast API.
It obtains model/API precipitation and model-derived 0–7 cm volumetric soil
moisture at Gangtok, Mangan, Namchi, and Gyalshing. These values are **not NASA
IMERG rainfall and not NASA SMAP soil moisture**. They are point samples, not a
spatially complete observation grid; each displayed analysis cell currently
uses its nearest reference location.

## Inputs and index

Static inputs are joined one-to-one on the canonical ordered `cell_id` contract:

- the existing 7,390-cell uncalibrated static susceptibility output;
- SRTM-derived slope/elevation and OSM road/settlement proximity;
- provenance-validated GEM active-fault proxy and OSM drainage distances; and
- Sentinel-2 L2A NDVI, preserving unavailable (`NaN`) observations.

The dynamic trigger is a transparent heuristic combination of capped terms:

- 45%: 24-hour precipitation relative to 100 mm;
- 30%: 3-day precipitation relative to 200 mm;
- 10%: 7-day precipitation relative to 350 mm; and
- 15%: 0–7 cm volumetric soil moisture scaled between 0.15 and 0.45 m³/m³.

The index retains the static susceptibility baseline and allows the trigger to
raise the remaining distance to 100 by at most 55%. These design weights are
prototype decision rules, not learned coefficients and not SHAP values.

Categories are:

| Category | Operational Risk Index |
|---|---:|
| LOW | 0 to less than 20 |
| MODERATE | 20 to less than 50 |
| HIGH | 50 to less than 75 |
| SEVERE | 75 to 100 |

The dashboard's `risk_factors` list reports contextual input values only. It
does not claim causal attribution, feature importance, or geological conditions
such as bedrock stability or shear stress.

## Telemetry validation and freshness

Live mode requests a complete rolling 168-hour history from all four reference
locations. It validates array lengths, timestamps, finite/non-negative rainfall,
physical soil-moisture bounds, and a maximum age of three hours. Output metadata
records the source, fetch attempt and source timestamps, freshness, successful
and failed locations, missing-data state, and the last trusted fetch time.

If any location fails or returns incomplete, invalid, stale, or future-dated
data, the updater fails closed. It inserts no default rainfall or soil moisture,
does not recompute the index, preserves the last trusted cell/weather values,
marks telemetry unavailable/stale, and writes the status atomically. Static
input duplication, misalignment, checksum failure, or missing required fault
distances also aborts the update before output replacement.

All successful and failed-status JSON replacements use a same-directory
temporary file followed by an atomic replace, preventing a partial dashboard
file. Road and settlement exposure counts remain unavailable until a real
spatial exposure calculation is connected.

## Demonstration modes and limitations

`--mode storm`, `--mode dry`, and the historical timeline are explicitly
labelled simulations. Their weather values are scenario assumptions and never
share live provenance. Open-Meteo itself remains a temporary prototype source:
mountain microclimates, gauge bias, model resolution, snow processes, and local
soil properties are not resolved by four reference points.

Planned production adapters should ingest independently quality-controlled IMD
rain-gauge or gridded rainfall, NASA GPM IMERG precipitation, and NASA SMAP or
another validated soil-moisture product. Each adapter must retain native
product identity, resolution, timestamps, quality flags, missing values, and
provenance rather than relabelling or filling absent observations.
