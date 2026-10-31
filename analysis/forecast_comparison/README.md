# Historical Forecasting and Model Comparison

This directory compares prediction methods for PM2.5, rainfall and WBGT using historical data saved in the project. It contains the code, results and figures used in our report and presentation.

The analysis covers PM2.5, rainfall and WBGT. It reuses the existing research
methods and historical dataset. 

## 1. Files and outputs

```text
forecast_comparison/
├── README.md
├── compare_pm25.py
├── compare_rainfall_wbgt.py
├── figures/
│   ├── pm25_comparison.png
│   ├── pm25_comparison.pdf
│   ├── rainfall_comparison.png
│   ├── rainfall_comparison.pdf
│   ├── wbgt_comparison.png
│   └── wbgt_comparison.pdf
└── results/
    ├── pm25_metrics.csv
    ├── rainfall/
    │   ├── interval_metrics.csv
    │   ├── test_predictions.csv
    │   ├── station_neighbors.csv
    │   └── summary.json
    ├── wbgt/
    │   ├── horizon_metrics.csv
    │   ├── station_horizon_metrics.csv
    │   ├── test_predictions.csv
    │   ├── backtest_models.json
    │   └── summary.json
    └── all_verification.json
```

PNG figures are convenient for slides. PDF figures provide vector graphics
for the report.

## 2. Data and time resolution

The research scripts read the frozen snapshot under:

```text
data/datasets/snapshot_20261015/
```

| Variable | Input file | Main observation interval |
|---|---|---|
| PM2.5 | `air_quality_observations.csv` | 60 minutes |
| Rainfall | `weather_observations.csv` | 5 minutes |
| WBGT | `heat_stress_observations.csv` | 15 minutes |

These intervals describe the observation timestamps in the snapshot, not
the frequency at which the collector requests the APIs.

The dataset contains missing periods. Observations are therefore not
available at every expected timestamp.

## 3. Reproduce the analysis

Use Python 3.11 or later and the project dependencies.

Run the following commands from the repository root.

### PM2.5 comparison

```bash
./.venv/bin/python analysis/forecast_comparison/compare_pm25.py
```

This script reads the existing recorded evaluation from
`docs/forecast_evaluation.json`. It does not retrain the PM2.5 model.

It checks that the recorded dataset and model hashes match the supplied
files before generating the table and figure.

### Rainfall and WBGT comparisons

Run both analyses:

```bash
./.venv/bin/python analysis/forecast_comparison/compare_rainfall_wbgt.py
```

Run rainfall only:

```bash
./.venv/bin/python analysis/forecast_comparison/compare_rainfall_wbgt.py --task rainfall
```

Run WBGT only:

```bash
./.venv/bin/python analysis/forecast_comparison/compare_rainfall_wbgt.py --task wbgt
```

Reproduce both analyses in a separate output directory:

```bash
./.venv/bin/python analysis/forecast_comparison/compare_rainfall_wbgt.py --output-dir /tmp/outdoorwise-forecast-comparison
```

These commands perform offline training and evaluation through the existing
research scripts. Their outputs are redirected into this analysis directory,
rather than replacing the original research results.

They do not start the application or collect live observations.

## 4. Evaluation design

The original research code uses chronological validation windows before
the holdout boundary of **14 October 2026, 00:00 SGT**.

Training labels must be available before the relevant training boundary.
Preprocessing is fitted using training data. Model selection uses
pre-holdout validation rather than holdout performance.

Within each target interval or forecast horizon, the compared methods use
the same test samples. Sample sets can differ across horizons because
input and target availability differ.

These dates have been examined in earlier experiments. The comparisons
are exploratory reused-holdout results, not a new independent test.

## 5. PM2.5 comparison

### Methods

- **Persistence:** repeats the latest available PM2.5 reading.
- **Frozen linear model:** uses saved coefficients with the latest reading
  and the previous two consecutive hourly readings.

All 15 saved region/horizon selections in the supplied artifact use the
linear method. The plotting script checks this before labelling the
recorded frozen predictions as linear.

The evaluation pools results across five Singapore regions.

### Results

Errors are in **µg/m³**. Lower MAE and RMSE are better.

| Horizon | Test samples | Persistence MAE | Linear MAE | Persistence RMSE | Linear RMSE |
|---|---:|---:|---:|---:|---:|
| 60 min | 120 | 24.000 | 24.707 | 35.339 | 36.660 |
| 120 min | 115 | 32.678 | 32.541 | 46.335 | 46.561 |
| 180 min | 115 | 42.130 | 40.279 | 56.473 | 54.457 |

- At 60 minutes, the linear model has higher MAE and RMSE.
- At 120 minutes, it has slightly lower MAE but higher RMSE.
- At 180 minutes, it has lower MAE and RMSE.

**Conclusion:** the linear model does not consistently outperform persistence.

## 6. Rainfall comparison

### Target and methods

The target is whether rain occurs within a future 15-minute interval.

The selected intervals are:

- 0–15 minutes after the forecast origin.
- 15–30 minutes after the forecast origin.
- 45–60 minutes after the forecast origin.

These are separate intervals. The 45–60-minute target does not mean
cumulative rainfall over the entire first hour.

The figure compares:

- **Always dry:** assigns zero rain probability.
- **Persistence:** repeats the latest observed wet/dry state.
- **Local logistic regression:** uses recent local rainfall, input age
  and time-of-day features.
- **Neighbour logistic regression:** adds nearby-station rainfall features.

The original experiment also saves training-frequency and
validation-selected method results in the CSV files.

The classification threshold is fixed at **0.5**. Median imputation and
standardisation are fitted using training data. CSV status columns
identify any insufficient-class prior fallback.

### Sample construction

This comparison uses the existing neighbour experiment's recent-input
rules and requires complete target intervals.

Its sample set differs from the strict-history rainfall baseline in
`docs/forecast_evaluation.json`. Results from those two sample sets should
not be treated as directly matched comparisons.

| Target interval | Test samples | Rainy samples |
|---|---:|---:|
| 0–15 min | 3,026 | 140 |
| 15–30 min | 2,937 | 134 |
| 45–60 min | 3,204 | 185 |

### Metrics

- **Brier score:** measures probability error; lower is better.
- **Average precision (AP):** evaluates how well higher probabilities rank
  rainy samples ahead of dry samples; higher is better.
- **Recall:** measures the fraction of rainy samples detected at the fixed
  threshold; higher is better.

Undefined metrics remain unavailable rather than being replaced with zero.
An all-dry test set cannot establish rain-detection skill.

### Findings

- For 0–15 minutes, neighbour logistic regression has the highest AP among
  the plotted methods, approximately **0.423**. Persistence has the lowest
  Brier score.
- At the 0.5 threshold, neighbour logistic regression detects only **3.6%**
  of rainy samples in that interval, compared with **32.1%** for persistence.
- For 15–30 minutes, neighbour logistic regression has the lowest Brier
  score among the plotted methods, but lower AP and recall than persistence.
- For 45–60 minutes, neighbour logistic regression shows no consistent
  advantage and its recall is zero.

**Conclusion:** neighbour features improve ranking in the nearest forecast
interval, but do not consistently improve probability error or rain detection.

## 7. WBGT comparison

### Methods

- **Persistence:** repeats the latest available WBGT reading.
- **Linear regression:** uses five consecutive 15-minute readings,
  observation age and time-of-day features.

The analysis reuses the station-specific research models and evaluates
15-, 30- and 60-minute forecasts.

### Results

Errors are in **°C**. Lower MAE and RMSE are better.

| Horizon | Test samples | Stations | Persistence MAE | Linear MAE | Persistence RMSE | Linear RMSE |
|---|---:|---:|---:|---:|---:|---:|
| 15 min | 930 | 30 | 0.406 | 0.469 | 0.605 | 0.690 |
| 30 min | 930 | 30 | 0.494 | 0.540 | 0.710 | 0.801 |
| 60 min | 990 | 30 | 0.550 | 0.595 | 0.782 | 0.851 |

**Conclusion:** persistence outperforms the linear model on both metrics
at all three evaluated horizons in this historical holdout.

## 8. Limitations and application boundary

- The historical dataset is short and contains gaps.
- Rainy samples form a small proportion of the rainfall test data.
- Nearby stations and overlapping forecast windows create dependent samples.
  Sample counts do not represent independent weather events.
- Sample sets differ across horizons. Cross-horizon changes cannot be
  attributed only to forecast length.
- These results do not establish statistical superiority, probability
  calibration or performance on later unseen weather conditions.
- Offline forecast horizons are different from the interface's departure
  offsets. PM2.5 hourly targets must not be relabelled to match quarter-hour
  departure times.
- Forecast error is not an environmental risk score, and point forecasts
  do not establish continuous conditions throughout a run.
- Running these scripts does not enable trained models in the application
  or change its unavailable-data and fallback behaviour.

The rainfall/WBGT script checks protected input hashes before and after
execution. Verification records are saved alongside the results.