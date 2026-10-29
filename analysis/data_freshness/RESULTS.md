# Data Freshness Evaluation — report-ready results and discussion

## A. Experimental Setup and Collection-Session Classification

We evaluated existing local environmental observations and ingestion logs from
October 2026 without making new provider requests. Source-specific observation
cadence, dataset refresh and aggregation were distinguished: rainfall station
updates occur every five minutes; WBGT is a 15-minute average updated every
15 minutes; PM2.5 is a one-hour concentration reported hourly; and PSI is a
rolling 24-hour index reported hourly. The PM2.5 and PSI datasets advertise
15-minute refreshes, which do not imply 15-minute observation labels. Official
citations and timestamp definitions are provided in the [methodology](README.md).

Observation age was calculated as fetch time minus observation time, interpreting
CSV timestamps in Singapore local time. Revision-1 records identify first recorded
acquisition. We linked all **2,675 first-fetch groups (166,842 records)**
to unique successful same-source run intervals and reconciled their record counts
with insertion counters. Each fetch-timestamp group contributes its median age,
avoiding automatic weighting by station count.

The configured polling interval I is 5 minutes for rainfall and 15 minutes for
WBGT, PM2.5 and PSI. A run is log-supported active from the third consecutive
success when gaps from the previous completion to the next start are at most
2I + 0.5 minutes. A gap above 4I + 0.5 minutes starts a new log segment; its first
successful acquisition is post-gap if it passes the duration screen. Failed runs interrupt success chains.
Initial observations, warm-up, irregular polling and runs exceeding the 151.5-second
duration screen are classified as other/uncertain. These configuration-based
screening rules do not prove continuous laptop wakefulness or identify why a gap
occurred. Figure 1 applies only a display selection to the existing classification:
active first acquisitions collected from October 8 through 17, 2026, inclusive
(Asia/Singapore). No classification rules or original records are changed. The
full-period results, post-gap and uncertain acquisitions remain available.

## B. Observation Freshness During Active Collection

Table 1 reports unchanged **full-period** fetch-group statistics. The source-specific ages characterize our
pipeline's recorded first-acquisition timing; they are not comparable API speed
scores. Median/mode observation spacing in the retained history was 5, 15, 60 and
60 minutes for rainfall, WBGT, PM2.5 and PSI respectively.

| Source | Dataset refresh (min) | Observation cadence (min) | Active first-fetch groups | All-sample median age (min) | Active median age (min) | Active P90 age (min) |
|---|---:|---:|---:|---:|---:|---:|
| Rainfall | 5 | 5 | 1,552 | 9.10 | 9.08 | 11.12 |
| WBGT | 15 | 15 | 555 | 17.00 | 16.88 | 23.80 |
| PM2.5 | 15 | 60 | 158 | 10.40 | 9.19 | 14.83 |
| PSI | 15 | 60 | 157 | 10.22 | 9.50 | 15.07 |

Figure 1 displays only the October 8–17 active subset. Its displayed counts and
statistics are recalculated after both filters and stored separately in
`figure_1_display_summary.csv`; Table 1 and operational results retain their
original full-period scope.

| Source | Displayed first-fetch groups | Displayed median age (min) | Displayed P90 age (min) | Displayed maximum age (min) |
|---|---:|---:|---:|---:|
| Rainfall | 1,488 | 9.10 | 11.13 | 16.93 |
| WBGT | 532 | 17.20 | 23.80 | 25.22 |
| PM2.5 | 152 | 9.00 | 14.81 | 27.30 |
| PSI | 151 | 9.32 | 15.07 | 27.72 |

The **379.03-minute rainfall outlier** was observed at
2026-10-13T22:05:00+08:00 and first fetched at 2026-10-14T04:24:02+08:00; it is
classified as post-gap and excluded from Figure 1. It remains in the unmodified
full-period acquisition records and statistics. Removing post-gap and uncertain samples
particularly reduces the air-quality age tails. This is conditioning on collection
state, not an improvement attributable to the collector. Varying the regular-gap
tolerance from 1.5I + 0.5 to 3I + 0.5 minutes yields active median ranges of
9.08 minutes for rainfall, 16.83–16.88 for WBGT, 9.19–9.20 for PM2.5 and
9.48–9.50 for PSI.

**Figure 1 caption.** Environmental observation age during log-supported active
collection from October 8 to 17, 2026 (Singapore time). Each point represents the
median observation age within a first-acquisition fetch-timestamp group. Only
acquisitions associated with regular successful polling sequences are included.
Repeated retrievals of unchanged observations are excluded. Rainfall and WBGT
observation timestamps typically advance every 5 and 15 minutes, respectively,
whereas PM2.5 and PSI observation timestamps advance hourly. These observation
intervals are distinct from the official dataset refresh schedules. Panel y-axis
ranges differ; all active acquisitions within the selected dates are retained.

This display selection examines normal active operation; it is not evidence that
excluded acquisitions never occurred. Genuine temporal gaps remain empty, with
no interpolation, smoothing or connected scatter points.

## C. Stale Observations Despite Successful Polling

First-acquisition selection omits successful polls that return existing records.
We therefore separately evaluated all qualifying active successful runs with
nonempty responses. These denominators include unchanged polls and are distinct
from Table 1's first-fetch group counts.

For each run r, let M_r be the newest observation timestamp introduced in the
complete revision-1 history up to and including that run. Reconciliation against
every successful run's insertion counter checks completeness of introductions.
Any observation returned in that run has a timestamp no later than M_r. Since
fetching occurs after the logged run start s_r, its age is at least s_r - M_r.
Including introductions within the current run makes this bound conservative.
The calculation bounds returned ages; it does not reconstruct discarded payloads.

| Source | Official observation cadence (min) | Qualifying active successful runs | Runs demonstrably >60 min old | Maximum demonstrated age lower bound (min) |
|---|---:|---:|---:|---:|
| Rainfall | 5 | 1,755 | 16 | 144.02 |
| WBGT | 15 | 558 | 0 | 25.18 |
| PM2.5 | 60 | 598 | 13 | 135.80 |
| PSI | 60 | 594 | 12 | 136.27 |

The 60-minute cutoff is an analysis diagnostic, **not an official API SLA**. Counts
are minimum demonstrated cases under the conservative bound, not complete stale
response prevalence. Zero WBGT cases do not prove that every WBGT response was
recent. The maximum column covers all qualifying runs, including those below
60 minutes. Consecutive old responses are correlated and are not counted as
independent outage events.

For example, the rainfall run at **2026-10-14T00:14:01 SGT** logged
89 unchanged records, only 5.22 minutes after
the preceding success. Its newest known observation was
2026-10-13T21:50:00+08:00, giving an age lower bound of
**144.02 minutes** (ingestion-log line 8644).
Thus, successful HTTP retrieval alone is insufficient to establish the recency
of the environmental measurements used by our pipeline.

## D. Limitations

Collection was intermittent on a local MacBook. Log-derived states cannot identify
sleep, shutdown or continuous wakefulness, and do not establish intended uptime.
The 379-minute post-gap outlier must not be attributed to government API failure.
The first-acquisition statistics omit unchanged repeat responses; the operational
bounds address some of that missing evidence but do not recover exact payloads or
full response-age distributions. Their validity relies on the retained history,
counter semantics and consistent local timestamps; historical raw responses are
not available for independent verification of every request.
Figure 1 is a date-restricted active first-acquisition view, not a complete history
of every successful API response. Operational freshness is evaluated separately
from the full ingestion logs in Section C.

Source reporting schedules, aggregation periods, polling phase and metadata updates
also differ. Nominal cadence is not a maximum-age guarantee. Provider update
timestamps are not verified exact publication times, so their fetch offsets are
descriptive only. No HTTP latency, government API availability, causal performance
improvement or improvement in source freshness is claimed. The first-versus-latest
retention comparison is preserved as supplementary reproducibility evidence and
excluded from the main evaluation: its difference is largely explained by
metadata-only revisions and repeated retrieval of unchanged hourly observations.
