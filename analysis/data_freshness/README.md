# Cadence-aware environmental data freshness evaluation

This offline evaluation separates first-acquisition timing from conservative
operational freshness bounds during log-supported active collection. It uses each
source's own temporal semantics. **Observation age is not an API speed or reliability
ranking.** Dataset refresh, observation timestamp progression, aggregation period,
provider update metadata, and local polling are separate quantities. No nominal
update interval is treated as a maximum-delay SLA or a pass/fail threshold.

## Reproduce and validate

From the repository root with Python 3.11+ and the existing Matplotlib dependency:

```sh
.venv/bin/python analysis/data_freshness/analyze.py
.venv/bin/python -m pytest -q analysis/data_freshness
```

The script uses only local CSVs and configuration. It imports no application
modules, makes no network requests, and writes only its analysis outputs. It uses
an isolated temporary plotting cache. Documentation review is manual; reproducing
the figures does not fetch documentation or environmental endpoints.

Source CSV hashes are pinned in `audited_input_sha256.json`, copied unchanged from
the preceding audit manifest. The script fails if these hashes differ, if inputs
change during execution, if selected observation keys repeat, or if observation
ages are invalid/negative. Prior first-collection counts/statistics must still match
the original audit to two decimals. `verification.json` retains the same six source
hashes and adds cadence/revision diagnostics, all-interval and screened statistics,
cutoff sensitivity, missing/negative checks, and environment versions. Configuration
and `data/runtime/ingestion_runs.csv` are additionally pinned in `audited_session_inputs_sha256.json` and rechecked
before and after analysis. All first acquisitions must match unique successful
source run intervals and reconcile with logged insertion counts. Operational
counters and active-group statistics must agree with the completed inactivity audit.
Provider offsets are allowed to be negative in diagnostics so a future anomaly would remain visible rather than being clipped or discarded.

## Official documentation verified on 29 October 2026

| Source | Advertised dataset update | Measurement/reporting definition | Evidence |
|---|---|---|---|
| Rainfall | 5 min | Station precipitation; collector/payload contract is a 5-minute total | [Government rainfall dataset][rain] |
| WBGT | 15 min | Average over the preceding 15 minutes | [Government WBGT dataset][wbgt] |
| PM2.5 | 15 min | One-hour concentration; NEA describes hourly reporting | [Government PM2.5 dataset][pm25], [NEA FAQ, section C7][faq] |
| PSI | 15 min | Rolling 24-hour index, reported hourly by NEA | [Government PSI dataset][psi], [NEA monitoring description][monitoring] |

The rainfall landing page verifies the update interval; its aggregation wording
above additionally relies on the existing parser/payload contract, not an invented
landing-page definition. The 15-minute air-quality dataset labels do not imply new
15-minute observation timestamps. The NEA measurement definitions and the dataset
refresh labels address different parts of the data service. A rolling index is not
an instantaneous concentration. We do not independently reconstruct PSI components.

[Official PM2.5 developer documentation][pm25docs] places `timestamp`,
`updatedTimestamp`, and `readings` in the same returned item. The reviewed official
pages do not establish that `updatedTimestamp` is the exact instant a value became
publicly retrievable, or that it changes only when the measured value changes.
No interactive API examples or live environmental endpoints were executed.
Documentation describes current standards; it is not an archived contractual
record proving the exact API behavior throughout the October collection period.

## Exact local inputs

All paths are relative to the repository root:

| Source / metric | Revision history | Current observations |
|---|---|---|
| Rainfall / `rainfall` | `data/runtime/weather_observation_versions.csv` | `data/runtime/weather_observations.csv` |
| WBGT / `wbgt` | `data/runtime/heat_stress_observation_versions.csv` | `data/runtime/heat_stress_observations.csv` |
| PM2.5 / `pm25` | `data/runtime/air_quality_observation_versions.csv` | `data/runtime/air_quality_observations.csv` |
| PSI / `psi` | `data/runtime/air_quality_observation_versions.csv` | `data/runtime/air_quality_observations.csv` |

`data/runtime/ingestion_runs.csv` supplies source run IDs, start/finish times,
status and acquisition counters. The latest `collection_worker.json` is not used
to reconstruct historical sessions because it is an overwritten status snapshot.

`config/environment.toml` supplies local polling policy: rainfall every 300 seconds;
WBGT, PM2.5 and PSI every 900 seconds when collection operates. Scheduler ticks,
retries, response duration and source spacing can change actual request spacing.
These settings do not determine provider observation or publication cadence.

Only `source_kind=live` and the four specified metrics are selected. Heat-stress
category and PM10 rows are excluded to avoid duplicating timing evidence. The
frozen snapshot overlaps runtime data and is not pooled. No repository adapter is
instantiated and no pending transaction is replayed. The previously recorded
18-row wind-direction history discrepancy concerns a metric excluded here.

## Timestamp definitions and formulas

CSV v3 timestamps use Singapore-local `YYYY-MM-DDTHH:MM:SS`, without an offset.
The analysis explicitly attaches `Asia/Singapore` to every parsed time; none is
interpreted as UTC. Storage has second precision.

- `observed_at`: provider observation timestamp, from station `timestamp`, WBGT
  record `datetime`, or air-quality item `timestamp`.
- `source_updated_at`: optional provider `updatedTimestamp`, from the same parsed
  record/item as the returned readings. It is not a local fetch timestamp.
- `fetched_at`: local clock after response receipt, status checking, JSON decoding
  and HTTP-client context exit; before endpoint-specific normalization. It is not
  exact response receipt or HTTP latency.
- `first_fetched_at`: first acquisition of that retained revision. A new revision
  resets it; it is not necessarily first acquisition of the original observation.

```text
observation_age_minutes = (fetched_at - observed_at).total_seconds() / 60
provider_update_to_fetch_minutes = (fetched_at - source_updated_at).total_seconds() / 60
```

The second formula is evaluated only when provider metadata is present, using the
update timestamp from that same revision-1 row. No missing timestamps are filled.
The provider offset can be described as a returned-record metadata-to-fetch offset;
its interpretation as exact publication-to-acquisition latency is unverified.

Code tracing: `outdoorwise/collectors/base.py:17-22,52-65`,
`outdoorwise/collectors/wbgt.py:7-18`, `outdoorwise/collectors/pm25.py:7-11`,
`outdoorwise/collectors/psi.py:7-13`, and
`outdoorwise/storage/repository.py:139-168`. Parsers attach readings and update
metadata from the same item/record. Existing historical raw payloads are not
available for every collection, so this structural association is not independent
proof of atomic version/publication semantics across sources.

## Selection, grouping and cadence design

**First acquisition:** use revision 1 from history, where `fetched_at` equals
`first_fetched_at`. Group rows by source and exact fetch timestamp, take the median
row age within each group, and weight group medians equally. Large station
responses therefore do not automatically receive more weight. Groups can contain
only stations first seen in that response, and timestamps are proxies rather than
stored request IDs. The full acquisition records remain in the exports. Figure 1
uses only the explicit active/date display selection described below; every
eligible point and genuine temporal gap in that view is preserved.

**Revision-history evaluation:** current observation tables retain the latest
revision; unchanged polls overwrite `fetched_at` without appending history. Apply
the same grouping separately to current rows. The resulting comparison describes
two retention views of the same collection history, not independent interventions.

**Timestamp cadence:** use all selected revisions, deduplicate timestamps across
stations and revisions within each source, sort distinct `observed_at` or nonempty
`source_updated_at`, and difference consecutive timestamps. All revisions are
necessary to expose air-quality update metadata between hourly observations.

**Long-gap exclusion rule (analysis choice):** exclude intervals strictly greater
than 120 minutes from typical cadence statistics. Keep intervals exactly 120
minutes. This transparent screen removes long gaps from the cadence estimate;
it does not prove a collector was inactive throughout every excluded interval.
Shorter missed polls and gaps can remain. All intervals, including excluded ones,
are saved in `cadence_interval_distribution.csv`; ages/plot points are never
filtered by this rule. Verification also reports results at 60- and 180-minute
cutoffs. Observed-timestamp medians/modes remain 5/15/60/60 minutes at all three
cutoffs. These are empirical retained-timestamp patterns, not a complete measure
of provider publication regularity or availability.

Median/mean use the usual sample definitions; P90 linearly interpolates at sorted
zero-based position `(n - 1) * 0.9`. Modes use exact second-resolution intervals,
retain ties, and do not round intervals into bins. Provider update modes near
14.983333 minutes mean 14 min 59 sec. Summary-age statistics operate on group
medians; cadence statistics operate on distinct timestamp differences. A maximum
age is the maximum group median. No normalized cross-source score is used because
one scalar denominator would conceal differences in timestamp meaning and
aggregation. In particular, age is never divided by 15 minutes on the assumption
that air-quality observation timestamps advance every 15 minutes.

## Collection-session classification

Let I be the configured source polling interval. Gaps measure the next source run
start minus the previous source run finish, using **all attempts**, including
failures. A regular-success link permits a gap at most 2I + 0.5 minutes. A gap
strictly above 4I + 0.5 minutes starts a new log segment. Thus regular/extended
limits are 10.5/20.5 minutes for rainfall and 30.5/60.5 for the other sources.
The 0.5-minute grace is an analysis allowance based on the documented 30-second
worker tick, not a claim that every historical invocation used that tick.

- **Log-supported active collection:** third and later consecutive successes with
  regular links and acceptable run durations. Failed attempts break the chain.
- **After extended collection gap:** the segment's first successful source run,
  provided it passes the duration screen. A plotted first-acquisition point gets
  this label only if it was introduced by that run. A post-gap run returning only
  existing observations creates no first-acquisition point.
- **Other/uncertain:** the initial observed run, warm-up successes, irregular
  intervals, or long-running successes. If a segment's first success is long,
  it remains uncertain; the post-gap label is not shifted to a later success.

The duration screen is 151.5 seconds, computed as three configured 20-second
request allowances, two maximum 30-second retry delays, 1.5-second source spacing,
and 30-second scheduling grace. This is a conservative diagnostic screen, not an
HTTP deadline: transport timeouts have phase-specific semantics. Possible
in-request interruptions are therefore kept out of the active sample without
asserting their cause. Session labels are not recorded process lifetimes and do
not prove that the laptop was continuously awake. Stricter/looser regular limits
of 1.5I + 0.5 and 3I + 0.5 minutes are reproduced in `session_sensitivity.csv`.

Temporal association uses `started_at <= fetched_at <= finished_at`, matching
source and `live` data kind. Every selected first-fetch group must match exactly
one successful run; overlapping source intervals, ambiguous joins, missing joins
or inconsistent counters cause analysis to fail. All 2,675 groups (166,842 rows)
match and reconcile in the audited data. WBGT/category and PSI/PM10 are paired
metrics in their respective collectors, so selected-metric insertion counts are
half the source-level counts; rainfall and PM2.5 counts match directly. These
verified temporal matches are not an explicit observation-to-run foreign key.

## Operational freshness: bounds rather than reconstructed payloads

Revision-1 selection does **not** contain every successful response: unchanged
polls update current `fetched_at` and leave no separate history row. Consequently,
Figure 1 and first-acquisition maxima cannot describe the complete freshness of
successfully retrieved responses. Operational denominators instead use all
qualifying active successful runs with nonempty responses, including unchanged
polls. `operational_freshness.csv` reports those denominators explicitly; no
unsupported percentages or independent-outage counts are calculated.

The inference follows the actual ingestion rules:

1. Each new observation key, which includes `observed_at`, creates a revision-1 row.
   Reconcile every successful run's first introductions against its insert counter.
   Also verify received = inserted + revised + unchanged and unique run IDs.
2. For each run r, determine M_r, the newest selected observation timestamp first
   introduced up to and including that run. Including current introductions avoids
   overstating a bound if this response introduces a newer observation.
3. All returned selected observation keys must be represented by that introduction
   history. Their observation times are no later than M_r. Because acquisition is
   after run start s_r, each returned age is at least s_r - M_r.

The algorithm uses run **start**, not finish, because exact receipt/fetch times
are not retained for every unchanged response. It does not use future
introductions to freshen past responses. It depends on complete retained
introduction history, the traced counter/key semantics, and consistent local
clock timestamps. No exact discarded payload is invented. A negative/low bound
proves nothing about a response's age; a bound strictly over 60 minutes is a
minimum demonstrated case under the chosen diagnostic. Zero demonstrated cases
is not proof that all responses were fresh. The maximum bound in the operational
table covers every qualifying active run, not only >60-minute cases.

**60 minutes is an analysis diagnostic, not a government API SLA.** Repeated old
responses can belong to one episode and must not be counted as independent outage
events. The results establish a limitation of using successful retrieval as a
freshness signal; they do not establish government API failure, transport latency,
continuous collector reliability, or improved source freshness.

## Verified cadence results

Intervals below are minutes, after the >120-minute screen. Grid alignment means
retained observation timestamps are at multiples of the stated cadence in local
time; it does not establish SLA compliance or absence of missed updates.

| Source | Unique observation times | Retained intervals | Median / mode / P90 | Excluded intervals | Observation grid alignment |
|---|---:|---:|---|---:|---|
| Rainfall | 1,638 | 1,630 | 5 / 5 / 10 | 7 | 1,638/1,638 on 5-minute grid |
| WBGT | 636 | 628 | 15 / 15 / 30 | 7 | 636/636 on quarter hours |
| PM2.5 | 198 | 191 | 60 / 60 / 60 | 6 | 198/198 on whole hours |
| PSI | 198 | 191 | 60 / 60 / 60 | 6 | 198/198 on whole hours |

| Source | Unique provider update times | Retained intervals | Median / mode / P90 | Excluded intervals |
|---|---:|---:|---|---:|
| Rainfall | 0 | 0 | Unavailable | 0 |
| WBGT | 636 | 628 | 15 / 15 / 30 | 7 |
| PM2.5 | 647 | 637 | 15 / 14.983333 / 29.796667 | 9 |
| PSI | 645 | 636 | 15 / 14.983333 / 29.933333 | 8 |

The retained patterns are consistent with 5-minute rainfall, 15-minute WBGT and
hourly air-quality observation labels. PM2.5 and PSI have hourly `observed_at`
changes alongside approximately quarter-hourly update metadata; those are not
contradictory. Missing slots or a doubled interval cannot identify government API
outages given incomplete local collection.

## Supplementary baseline and provider metadata checks

The original all-recorded first-acquisition statistics remain in `summary.csv`
for audit continuity. The main evaluation uses session-conditioned statistics and
operational bounds in [RESULTS.md](RESULTS.md), rather than ranking sources by
those unconditioned ages. The following metadata diagnostics remain descriptive;
they do not establish a common publication-latency scale.

Rainfall is missing provider update times in all 145,782 first-acquisition rows.
WBGT (19,080), PM2.5 (990), and PSI (990) first-acquisition rows have complete
provider metadata. No negative provider offsets or provider updates preceding
observation labels occur. The respective provider-offset group counts are 636,
198, and 198; P90 offsets are 13.775, 13.465, and 13.765 minutes, and maxima are
15.35, 14.983333, and 14.933333 minutes. These ordering checks support arithmetic
consistency, not publication/version guarantees.

Across retained revision transitions, all 2,245 PM2.5 and 2,235 PSI transitions
change only provider update metadata while the measurement fields remain equal.
No backwards provider-update transitions occur. WBGT and rainfall have no later
revisions for the selected metrics. This demonstrates that an advancing update
field does not necessarily identify a newly measured value. PM2.5 and PSI share
an item-level field structure, but neither their metadata offsets nor WBGT's
record-level offset are used for cross-source performance comparisons.

## Figures and reproducible outputs

- `figures/figure_1_observation_age_over_collection_time.{png,pdf}` is the sole main
  figure: **Environmental Data Freshness During Active Collection**. It displays
  only existing `active` first-acquisition groups collected from October 8 through
  17, 2026, inclusive in Asia/Singapore. Post-gap, uncertain and out-of-window
  acquisitions are excluded from this view, not removed from any dataset. The
  existing classification rules are reused unchanged. Every active acquisition
  within the window is plotted, including legitimate active outliers; gaps remain
  empty. There is no interpolation, smoothing or connection between scatter points.
  Simplified panel titles give source, observation cadence and filtered n. Source
  colors are consistent, panel y-limits are recomputed from the displayed points,
  and detailed definitions are in the caption rather than the plot. The hourly
  PM2.5/PSI observation labels do not mean hourly dataset refresh: their official
  dataset refresh remains 15 minutes.
- `figure_1_display_summary.csv` separately records displayed n, record counts,
  selected and actual timestamp ranges, median/mean/P90/maximum age for each source.
  These filtered summaries do not replace any verified full-period statistics.
- `figure_1_display_points.csv` exports exactly the displayed subset of the full
  first-acquisition groups, with their existing states and matched run IDs.
- `RESULTS.md` is generated from measured results and contains the final IEEE
  A–D results/discussion, primary caption, active-age table and operational table.
- `summary.csv` preserves preceding baseline/cadence fields and adds active age,
  classification counts and operational counts/bounds.
- `session_summary.csv` compares all, active, post-gap and uncertain first-fetch
  groups, including provider metadata offsets where available.
- `first_acquisition_samples.csv` retains **all full-period** first acquisitions,
  including post-gap and uncertain groups, with age, observation range, state and
  temporally matched run ID/log line. It is unchanged by the display filters.
- `operational_freshness.csv` reports qualifying active-run denominators,
  demonstrably >60-minute run counts, maximum age bounds and source cadence.
- `session_run_audit.csv` preserves the complete selected-source attempt ledger
  with classifications, counters and inferred bounds, including failed/uncertain
  attempts. Bound fields are explicitly labelled as inference rather than direct
  retained payload measurements.
- `session_sensitivity.csv` varies the regular-gap tolerance while retaining the
  three-success requirement and duration screen.
- `cadence_interval_distribution.csv` retains all distinct timestamp interval
  counts, including long gaps excluded only from typical-cadence statistics.
- `verification.json`, `audited_input_sha256.json`, and
  `audited_session_inputs_sha256.json` preserve reproducibility checks and hashes.

PNG figures use 300 DPI; PDFs retain vector marks/text and embedded TrueType fonts.
Figure 1 uses IEEE double-column width (7.16 inches) and a compact 6.6-inch height
for four aligned panels. It has no category legend or maximum-value annotations.
The x-axis spans October 8–17 with shared date ticks. Full-period analyses,
post-gap/uncertain statistics, operational bounds and Figure 2 remain available
and unchanged. The date/active selection examines normal active operation; it is
not evidence that the excluded observations never occurred.

**Figure 1 caption:** Environmental observation age during log-supported active
collection from October 8 to 17, 2026 (Singapore time). Each point represents the
median observation age within a first-acquisition fetch-timestamp group. Only
acquisitions associated with regular successful polling sequences are included.
Repeated retrievals of unchanged observations are excluded. Rainfall and WBGT
observation timestamps typically advance every 5 and 15 minutes, respectively,
whereas PM2.5 and PSI observation timestamps advance hourly. These observation
intervals are distinct from the official dataset refresh schedules. Panel y-axis
ranges differ; all active acquisitions within the selected dates are retained.

Figure 1 is not a complete history of successful API responses. Unchanged repeat
retrievals are absent from revision-1 records. Operational freshness from ingestion
logs is evaluated separately over its original full-period scope. Neither the
figure nor the display selection measures HTTP latency or government API response
performance.

## Supplementary retention-history figure — excluded from main evaluation

`figures/figure_2_first_collection_vs_latest_retained_fetch.{png,pdf}` and its
underlying baseline statistics are preserved and regenerated for reproducibility.
They are **supplementary only** and do not appear as performance evidence in
`RESULTS.md`. Their predictable difference follows from retaining later metadata
revisions and unchanged retrievals of hourly observations. It is neither a novel
collection-performance improvement nor an improvement in source freshness.

The earlier direct age comparison could mislead because observation-label cadence,
aggregation, acquisition phase, local inactivity and retention history all affect
raw age. The final interpretation and explicit limitations are authoritative in
[RESULTS.md](RESULTS.md); the source definitions and reproducible methods are here.

[rain]: https://data.gov.sg/datasets/d_6580738cdd7db79374ed3152159fbd69/view
[wbgt]: https://data.gov.sg/datasets/d_87884af1f85d702d4f74c6af13b4853d/view
[pm25]: https://data.gov.sg/datasets/d_e1058d6974c877257e32048ab128ad83/view
[psi]: https://data.gov.sg/datasets/d_fe37906a0182569d891506e815e819b7/view
[faq]: https://www.nea.gov.sg/our-services/pollution-control/air-pollution/faqs
[monitoring]: https://www.nea.gov.sg/our-services/pollution-control
[pm25docs]: https://developers.data.gov.sg/datasets?formats=API&resultId=d_e1058d6974c877257e32048ab128ad83
