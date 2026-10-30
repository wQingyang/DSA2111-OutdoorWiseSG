# Evaluation findings

## Environmental risk and eligibility

The controlled sweeps reproduce nondecreasing risk within fixed selected-input
branches and saturation at rainfall 10 mm/5 min, WBGT 35 °C, PM2.5 350 µg/m³ and
PSI 400. Varying one component from the zero-risk reference yields maximum total
risk 35 for rainfall/heat and 25 for air. PSI has no effect while PM2.5 is usable;
missing PM2.5 activates the PSI branch. These results validate implementation
behavior, not physical independence of environmental variables.

All **75 explicit boundary scenarios pass**. The default policy has no hard blocks;
even saturated controlled inputs yield caution, not blocked. Synthetic in-memory
rules verify inclusive blocking, rejection of stale blocking evidence, precedence
over incomplete totals, and explicit authorization for approximate station evidence.
Observed zeros remain complete; missing observations remain unknown. Categorical
heat and PSI fallbacks produce caution. Missing wind prevents an aggregate even
with neutral wind scoring. The maximum default aggregate is 95. Risk is rounded
to two decimals before thresholding; this explains caution for a pre-rounding
value immediately below 40. These are conformance findings, not supervised
classification metrics or externally validated safety thresholds.

## Catalog ranking

All methods use the same 12 routes, target distance 5 km, target difficulty 3,
no starting location, no forecast and identical production generic difficulties.
The environmental-term ablation retains distance/access/difficulty contributions
and all eligibility rules. It is not wholly environment-free because difficulty
also uses environmental inputs.

| Snapshot/scenario | Complete routes | Top-3 mean reported risk: distance | No explicit environment term | Full ranking | Full/distance shared Top-3 |
|---|---:|---:|---:|---:|---:|
| Oct 9, 2026 12:00 SGT, archived | 12 | 29.47 | 29.47 | 25.99 | 2/3 |
| Oct 10, 2026 12:00 SGT, archived | 12 | 28.84 | 28.84 | 28.84 | 3/3 |
| Oct 15, 2026 12:00 SGT, archived | 0 | Unknown | Unknown | Unknown | 3/3 |
| Controlled heterogeneous fixture | 12 | 52.17 | 52.17 | 0.00 | 0/3 |

On October 9 the distance-only and ablated Top-3 are Pasir Ris Park, Bishan–AMK
and Botanic Gardens. Full ranking selects Pasir Ris Park, Botanic Gardens and West
Coast. Their mean WBGT changes from 30.13 to 29.53 °C and mean recorded PM2.5 from
147.33 to 135.33 µg/m³; rainfall is zero in both sets. PSI changes from 168.33 to
165.33 but is not used in these scores because PM2.5 is usable. These are coarse
station/region indicators with differing measurement windows.

On October 10 only the order of the Top-3 changes: Pasir Ris Park, Botanic Gardens,
then Bishan–AMK under full ranking. Top-3 membership and average indicators do not
change. On October 15, rainfall, wind and heat are stale for every route. No
aggregate risk is assigned; all methods return the same distance-based discovery
order. This does not establish safe conditions or a provider outage.

The controlled scenario demonstrates that the implemented preference can change
membership substantially, but was deliberately constructed for that purpose. Lower
internal risk among routes chosen using that risk is not independent evidence of
safer outcomes, better predictions or clinically meaningful benefit.

## Weight perturbation and limitations

For environmental recommendation weights .30 and .60 relative to default .45,
Top-3 Jaccard overlaps are .50/.50 on Oct 9, 1.00/.50 on Oct 10, 1.00/1.00 in
the all-unknown Oct 15 fallback, and .20/1.00 in the controlled fixture. The two
assessed archived snapshots therefore retain two or three default Top-3 members
under these perturbations. Default weights are not shown to be optimal. Stability
under all-unknown conditions reflects fallback, not robustness of environmental scoring.

Only three archived times and one artificial scenario are evaluated. The retrospective
reader uses current station metadata, catalog and configuration; original historical
decisions may differ. Local acquisition was intermittent. Start-point stations and
coarse regions do not measure entire routes. Scores and confidence bands are
provisional; route geometries still require visual review. Generic difficulty uses
raw inputs without its own freshness check and remains fixed across methods. There
are no external safety outcomes, user utility labels or validated exposure targets.

## Figure captions

**Figure 1.** Controlled sensitivity of the implemented environmental risk score.
Each panel varies one input while other selected components have zero risk and
all observations are fresh at a supported station distance. Colored lines show
selected component risk and dashed lines the weighted total. PSI contributes only
when PM2.5 is unavailable; with usable PM2.5 = 0, varying PSI leaves total risk zero.
Input units retain their respective aggregation windows. These are rule transfer
functions, not predictions or clinical response curves.

**Figure 2.** Catalog ranking positions for the same 12 routes under distance-only,
no explicit environmental recommendation term, and full ranking. Shading marks
positions 1–3. Panels use three archived as-of snapshots and one labelled controlled
scenario. The October 15 panel contains only unknown assessments and shows
discovery fallback. Route labels are abbreviated for readability; complete IDs
and per-route inputs are available in the CSV outputs.
