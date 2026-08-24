# Two-layer Sikkim landslide-risk MVP

This pipeline separates **where terrain is susceptible** from **when real
rainfall and soil-moisture conditions are strong**. Its outputs are decision
support scores, not calibrated landslide probabilities.

## Static susceptibility (where)

Random Forest and XGBoost use the existing 1-km static feature table and the
GSI inventory-derived `historically_affected` label. A zero label is a
background/pseudo-negative, not a confirmed landslide-free cell. Numeric
missing values are median-imputed inside each model. Imbalance is handled with
Random Forest class weights and XGBoost `scale_pos_weight`; no row-level
oversampling is used.

Evaluation uses a deterministic, spatially grouped three-way design based on
approximately 10-km blocks. An outer grouped split reserves an untouched TEST
set. The remaining development rows are split again into TRAIN and VALIDATION
with disjoint spatial groups. Random Forest and XGBoost are trained only on
TRAIN and compared using VALIDATION PR-AUC, then recall and F1 as tie-breakers.
The selected model is evaluated exactly once on TEST; TEST results do not
participate in model selection. Precision, recall, F1, PR-AUC (average
precision), ROC-AUC, confusion matrix, and secondary accuracy for the untouched
TEST set are saved in `static_model_metrics.json`, together with validation
metrics for both candidates and explicit group-overlap checks. After evaluation,
the selected model is refit on TRAIN + VALIDATION, excluding TEST, to generate
the full-grid 0–100 uncalibrated susceptibility scores.

## Dynamic trigger (when)

IMERG daily precipitation (0.1 degree, approximately 10 km) and SMAP enhanced
soil moisture (approximately 9 km) are mapped by nearest native observation to
the 1-km analysis-cell representative point. This is not downscaling: multiple
1-km cells intentionally share one coarse observation. SMAP AM and PM values
are retained separately. A retrieval is accepted only when the quality flag is
0 or 8 and soil moisture is in [0, 1]; the daily value is the mean of valid AM
and PM, or the one valid orbit.

Each component is clipped and normalized between its dataset-wide 5th and 95th
percentiles. The trigger formula is:

`D = 100 * (0.35*R1 + 0.25*R3 + 0.20*R7 + 0.20*SM)`

where components are P5–P95 normalized to [0, 1]. If quality filtering removes
soil moisture, available weights are renormalized. The first two/six dates have
partial 3-day/7-day accumulation windows because pre-window rainfall is not
available; explicit `days_available` columns prevent these from being mistaken
for complete windows.

## Final risk

Let `S = static_susceptibility / 100` and `D = dynamic_trigger_score / 100`:

`final_risk_score = 100 * (0.35*S + 0.25*D + 0.40*S*D)`

The interaction term makes severe risk require susceptible terrain and a
strong trigger. Operational MVP categories are LOW [0,30), MODERATE [30,50),
HIGH [50,70), and SEVERE [70,100]. These thresholds are transparent demo
thresholds, not scientifically calibrated alert thresholds.

## Rerun

From the repository root:

```powershell
.\venv\Scripts\python.exe ML\run_landslide_mvp.py
```
