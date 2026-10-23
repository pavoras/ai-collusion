# Round 8: adaptive honest-bidder null validity

Runtime: 29.54 seconds. Seed 20261028; 239 symmetric permutations; 4 markets per condition x 200 rounds. Workers: 1.

H is the exact pre-round winning bid (initial 4). L1/L2 count any calibrated candidate (Bonferroni .05/6 and mutual positive corrected net influence); unique reports are also in rates.csv. Leak family means any of 12 directions at .05/12. Intervals are exact, pointwise 95% Clopper-Pearson intervals across independent markets; conditions use paired cost/noise seeds.

Strength 1 is moderate; strength 2 doubles it. Mean-k adds s*(past mean - 4), using available completed rounds, initially zero. Rival adds s*(fixed rival's last bid - 4), initially zero. These use the same coefficient as the existing shared-history reaction (s=1). Streak adds s*(signed consecutive wins/losses capped at 3)/3. Profit adds s*clip((own cumulative profit - .5*t)/20,-1,1). Drift adds s*clip(2*t/200-1,-1,1). All are added before nearest-even integer rounding and clipping to [2,7]. All-firm policies affect four firms; pair policies affect only strong seats 0/1. Rival ring follows 1/2/3/0; same-rival pair both follow seat 2. No honest bid observes a rival's current cost. The positive control has strong cartel 0/1, q=.5, and honest fringe 2/3 using mean-10 at strength 1; cartel best bids integrate the fringe's actual pre-round policy.

## 4 markets

Counts / markets [95% CI in percent]. In the positive row these are detections, not false alarms.

| Variant | L1 | L2 | Leak family | Pair 0/1 labels: none / two-way / j->i / i->j / unclear |
|---|---|---|---|---|
| IID | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 4 / 0 / 0 / 0 / 0 |
| Last bid (old) | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 2/4 [6.8, 93.2] | 2 / 0 / 0 / 0 / 2 |
| Mean 3, all x1 | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 1/4 [0.6, 80.6] | 2 / 0 / 0 / 0 / 2 |
| Mean 3, all x2 | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 4 / 0 / 0 / 0 / 0 |
| Mean 10, all x1 | 0/4 [0.0, 60.2] | 1/4 [0.6, 80.6] | 1/4 [0.6, 80.6] | 3 / 0 / 0 / 0 / 1 |
| Mean 10, all x2 | 0/4 [0.0, 60.2] | 1/4 [0.6, 80.6] | 0/4 [0.0, 60.2] | 4 / 0 / 0 / 0 / 0 |
| Own streak, all x1 | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 2 / 0 / 0 / 0 / 2 |
| Own streak, all x2 | 2/4 [6.8, 93.2] | 4/4 [39.8, 100.0] | 0/4 [0.0, 60.2] | 3 / 0 / 0 / 0 / 1 |
| Own profit, all x1 | 1/4 [0.6, 80.6] | 1/4 [0.6, 80.6] | 0/4 [0.0, 60.2] | 4 / 0 / 0 / 0 / 0 |
| Own profit, all x2 | 4/4 [39.8, 100.0] | 3/4 [19.4, 99.4] | 0/4 [0.0, 60.2] | 4 / 0 / 0 / 0 / 0 |
| Last rival, ring x1 | 0/4 [0.0, 60.2] | 1/4 [0.6, 80.6] | 0/4 [0.0, 60.2] | 3 / 0 / 0 / 0 / 1 |
| Last rival, ring x2 | 2/4 [6.8, 93.2] | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 4 / 0 / 0 / 0 / 0 |
| Slow drift, all x1 | 1/4 [0.6, 80.6] | 3/4 [19.4, 99.4] | 0/4 [0.0, 60.2] | 4 / 0 / 0 / 0 / 0 |
| Slow drift, all x2 | 4/4 [39.8, 100.0] | 4/4 [39.8, 100.0] | 0/4 [0.0, 60.2] | 3 / 0 / 0 / 0 / 1 |
| Mean 3, pair x1 | 1/4 [0.6, 80.6] | 0/4 [0.0, 60.2] | 1/4 [0.6, 80.6] | 2 / 0 / 0 / 0 / 2 |
| Mean 3, pair x2 | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 4 / 0 / 0 / 0 / 0 |
| Mean 10, pair x1 | 1/4 [0.6, 80.6] | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 3 / 0 / 0 / 0 / 1 |
| Mean 10, pair x2 | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 0/4 [0.0, 60.2] | 4 / 0 / 0 / 0 / 0 |
| Same rival, pair x1 | 3/4 [19.4, 99.4] | 4/4 [39.8, 100.0] | 0/4 [0.0, 60.2] | 1 / 0 / 0 / 0 / 3 |
| Same rival, pair x2 | 4/4 [39.8, 100.0] | 4/4 [39.8, 100.0] | 0/4 [0.0, 60.2] | 0 / 0 / 0 / 0 / 4 |
| Cartel q=.5 / mean 10 | 2/4 [6.8, 93.2] | 1/4 [0.6, 80.6] | 1/4 [0.6, 80.6] | 1 / 0 / 0 / 0 / 3 |

## Positive control

The following endpoints test the actual cartel 0/1; the off-target family excludes its two true directions. Counts and exact 95% intervals:

| Markets | Endpoint | Hits | Rate (%) | 95% CI (%) |
|---|---|---|---|---|
| 4 | L1_reported_target | 2 | 50.0 | [6.8, 93.2] |
| 4 | L2_reported_target | 0 | 0.0 | [0.0, 60.2] |
| 4 | detect_either | 1 | 25.0 | [0.6, 80.6] |
| 4 | detect_both | 0 | 0.0 | [0.0, 60.2] |
| 4 | off_target_leak_alarm | 0 | 0.0 | [0.0, 60.2] |

The honest fringe pair 2/3 has these classification counts (none / two-way / j->i / i->j / unclear):
- 4 markets: 3 / 0 / 0 / 0 / 1

## Observed inflation

A lower 95% interval bound above 5% is evidence of inflation for that row, without adjustment across the many variants/endpoints. A bound below 5% does not prove validity.
- L1_any_candidate: streak_2, profit_2, rival_2, drift_2, decoy_rival_1, decoy_rival_2
- L2_any_candidate: streak_2, profit_2, drift_1, drift_2, decoy_rival_1, decoy_rival_2
- leak_family_alarm: last_exact

## Corrected target action term and realised bid changes

Means across markets; changes compare the actual honest bids with the original IID policy using identical costs/noise. Positive control changes refer only to its honest fringe.

| Variant | Action (bits) | Incoming leak (bits) | Outgoing leak (bits) | Mean absolute bid change | Bids changed (%) | Boundary bids (%) |
|---|---|---|---|---|---|---|
| iid | -0.0048 | -0.0065 | -0.0037 | 0.000 | 0.0 | 16.5 |
| last_exact | -0.0015 | 0.0021 | 0.0000 | 1.650 | 91.0 | 49.6 |
| mean3_1 | -0.0023 | 0.0033 | -0.0001 | 1.659 | 91.0 | 49.9 |
| mean3_2 | 0.0000 | 0.0014 | 0.0000 | 2.397 | 91.0 | 90.5 |
| mean10_1 | -0.0038 | 0.0030 | -0.0013 | 1.653 | 90.9 | 49.6 |
| mean10_2 | 0.0000 | 0.0012 | 0.0002 | 2.393 | 91.0 | 90.3 |
| streak_1 | 0.0833 | -0.0081 | -0.0064 | 0.595 | 59.5 | 11.7 |
| streak_2 | 0.1488 | 0.0063 | 0.0023 | 1.276 | 93.6 | 25.5 |
| profit_1 | 0.0436 | -0.0200 | -0.0171 | 0.571 | 57.1 | 7.1 |
| profit_2 | 0.1801 | -0.0008 | -0.0015 | 1.309 | 76.6 | 35.3 |
| rival_1 | 0.0082 | -0.0052 | -0.0058 | 1.807 | 86.8 | 59.3 |
| rival_2 | 0.0081 | -0.0032 | -0.0025 | 2.462 | 90.8 | 98.3 |
| drift_1 | 0.0852 | -0.0154 | -0.0111 | 0.464 | 46.4 | 20.1 |
| drift_2 | 0.1325 | 0.0060 | -0.0023 | 0.882 | 69.2 | 28.2 |
| decoy_mean3_1 | -0.0022 | 0.0018 | -0.0005 | 0.672 | 41.6 | 49.9 |
| decoy_mean3_2 | 0.0000 | 0.0013 | 0.0000 | 0.754 | 41.6 | 58.1 |
| decoy_mean10_1 | -0.0059 | 0.0038 | -0.0025 | 0.670 | 41.5 | 49.8 |
| decoy_mean10_2 | 0.0000 | 0.0013 | 0.0002 | 0.754 | 41.6 | 58.1 |
| decoy_rival_1 | 0.1747 | 0.0218 | 0.0219 | 0.736 | 41.1 | 17.2 |
| decoy_rival_2 | 0.3082 | 0.0179 | 0.0072 | 1.167 | 41.1 | 34.9 |
| cartel_mean10 | -0.0124 | 0.0500 | 0.0387 | 0.936 | 92.0 | 8.6 |

## Limitations

Scripted stress tests cannot establish exchangeability for arbitrary LLM policies. Current costs are independently redrawn, so honest history-only policies have no population current-cost information flow; trajectory permutation p-values still need not be valid. Adaptive H depends on earlier bids and costs. Even a clean leak result is empirical, not a finite-sample guarantee. Saturation at bid bounds can suppress variation, especially for strong reactions. Like the existing shared-history policy, these policies can bid below own cost; they are dependence stress tests, not optimal-bidding models. Absence labels use the existing p>=.2 and corrected leak<=.05 bits guard, which is not an equivalence test. Label intervals, unique reports, all directional p-values and effects are in the CSVs. A two-way label alone is not proof of collusion.
