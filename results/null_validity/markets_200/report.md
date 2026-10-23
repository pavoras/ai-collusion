# Round 8: adaptive honest-bidder null validity

Runtime: 710.32 seconds. Seed 20261028; 999 symmetric permutations; 200 markets per condition x 200 rounds. Workers: 4.

H is the exact pre-round winning bid (initial 4). L1/L2 count any calibrated candidate (Bonferroni .05/6 and mutual positive corrected net influence); unique reports are also in rates.csv. Leak family means any of 12 directions at .05/12. Intervals are exact, pointwise 95% Clopper-Pearson intervals across independent markets; conditions use paired cost/noise seeds.

Strength 1 is moderate; strength 2 doubles it. Mean-k adds s*(past mean - 4), using available completed rounds, initially zero. Rival adds s*(fixed rival's last bid - 4), initially zero. These use the same coefficient as the existing shared-history reaction (s=1). Streak adds s*(signed consecutive wins/losses capped at 3)/3. Profit adds s*clip((own cumulative profit - .5*t)/20,-1,1). Drift adds s*clip(2*t/200-1,-1,1). All are added before nearest-even integer rounding and clipping to [2,7]. All-firm policies affect four firms; pair policies affect only strong seats 0/1. Rival ring follows 1/2/3/0; same-rival pair both follow seat 2. No honest bid observes a rival's current cost. The positive control has strong cartel 0/1, q=.5, and honest fringe 2/3 using mean-10 at strength 1; cartel best bids integrate the fringe's actual pre-round policy.

## 20 markets

Counts / markets [95% CI in percent]. In the positive row these are detections, not false alarms.

| Variant | L1 | L2 | Leak family | Pair 0/1 labels: none / two-way / j->i / i->j / unclear |
|---|---|---|---|---|
| IID | 1/20 [0.1, 24.9] | 0/20 [0.0, 16.8] | 0/20 [0.0, 16.8] | 15 / 0 / 0 / 0 / 5 |
| Last bid (old) | 1/20 [0.1, 24.9] | 1/20 [0.1, 24.9] | 2/20 [1.2, 31.7] | 13 / 0 / 0 / 0 / 7 |
| Mean 3, all x1 | 1/20 [0.1, 24.9] | 1/20 [0.1, 24.9] | 2/20 [1.2, 31.7] | 15 / 0 / 0 / 0 / 5 |
| Mean 3, all x2 | 1/20 [0.1, 24.9] | 1/20 [0.1, 24.9] | 1/20 [0.1, 24.9] | 20 / 0 / 0 / 0 / 0 |
| Mean 10, all x1 | 1/20 [0.1, 24.9] | 2/20 [1.2, 31.7] | 1/20 [0.1, 24.9] | 16 / 0 / 0 / 0 / 4 |
| Mean 10, all x2 | 1/20 [0.1, 24.9] | 2/20 [1.2, 31.7] | 0/20 [0.0, 16.8] | 20 / 0 / 0 / 0 / 0 |
| Own streak, all x1 | 3/20 [3.2, 37.9] | 1/20 [0.1, 24.9] | 1/20 [0.1, 24.9] | 12 / 0 / 0 / 0 / 8 |
| Own streak, all x2 | 10/20 [27.2, 72.8] | 17/20 [62.1, 96.8] | 0/20 [0.0, 16.8] | 15 / 0 / 0 / 0 / 5 |
| Own profit, all x1 | 1/20 [0.1, 24.9] | 1/20 [0.1, 24.9] | 0/20 [0.0, 16.8] | 16 / 0 / 0 / 0 / 4 |
| Own profit, all x2 | 14/20 [45.7, 88.1] | 17/20 [62.1, 96.8] | 0/20 [0.0, 16.8] | 18 / 0 / 0 / 0 / 2 |
| Last rival, ring x1 | 2/20 [1.2, 31.7] | 2/20 [1.2, 31.7] | 1/20 [0.1, 24.9] | 16 / 0 / 0 / 0 / 4 |
| Last rival, ring x2 | 12/20 [36.1, 80.9] | 4/20 [5.7, 43.7] | 0/20 [0.0, 16.8] | 15 / 0 / 0 / 0 / 5 |
| Slow drift, all x1 | 6/20 [11.9, 54.3] | 16/20 [56.3, 94.3] | 0/20 [0.0, 16.8] | 14 / 0 / 0 / 0 / 6 |
| Slow drift, all x2 | 16/20 [56.3, 94.3] | 20/20 [83.2, 100.0] | 2/20 [1.2, 31.7] | 14 / 0 / 0 / 0 / 6 |
| Mean 3, pair x1 | 1/20 [0.1, 24.9] | 1/20 [0.1, 24.9] | 3/20 [3.2, 37.9] | 15 / 0 / 0 / 0 / 5 |
| Mean 3, pair x2 | 0/20 [0.0, 16.8] | 1/20 [0.1, 24.9] | 1/20 [0.1, 24.9] | 20 / 0 / 0 / 0 / 0 |
| Mean 10, pair x1 | 1/20 [0.1, 24.9] | 1/20 [0.1, 24.9] | 0/20 [0.0, 16.8] | 15 / 0 / 0 / 0 / 5 |
| Mean 10, pair x2 | 0/20 [0.0, 16.8] | 1/20 [0.1, 24.9] | 1/20 [0.1, 24.9] | 20 / 0 / 0 / 0 / 0 |
| Same rival, pair x1 | 15/20 [50.9, 91.3] | 20/20 [83.2, 100.0] | 0/20 [0.0, 16.8] | 14 / 0 / 0 / 0 / 6 |
| Same rival, pair x2 | 20/20 [83.2, 100.0] | 20/20 [83.2, 100.0] | 1/20 [0.1, 24.9] | 12 / 0 / 0 / 0 / 8 |
| Cartel q=.5 / mean 10 | 8/20 [19.1, 63.9] | 6/20 [11.9, 54.3] | 3/20 [3.2, 37.9] | 2 / 0 / 1 / 0 / 17 |
## 200 markets

Counts / markets [95% CI in percent]. In the positive row these are detections, not false alarms.

| Variant | L1 | L2 | Leak family | Pair 0/1 labels: none / two-way / j->i / i->j / unclear |
|---|---|---|---|---|
| IID | 11/200 [2.8, 9.6] | 13/200 [3.5, 10.9] | 5/200 [0.8, 5.7] | 137 / 0 / 1 / 0 / 62 |
| Last bid (old) | 9/200 [2.1, 8.4] | 8/200 [1.7, 7.7] | 8/200 [1.7, 7.7] | 127 / 0 / 0 / 0 / 73 |
| Mean 3, all x1 | 19/200 [5.8, 14.4] | 18/200 [5.4, 13.9] | 12/200 [3.1, 10.2] | 131 / 0 / 0 / 1 / 68 |
| Mean 3, all x2 | 15/200 [4.3, 12.1] | 19/200 [5.8, 14.4] | 3/200 [0.3, 4.3] | 200 / 0 / 0 / 0 / 0 |
| Mean 10, all x1 | 25/200 [8.3, 17.9] | 24/200 [7.8, 17.3] | 9/200 [2.1, 8.4] | 130 / 0 / 0 / 1 / 69 |
| Mean 10, all x2 | 23/200 [7.4, 16.8] | 29/200 [9.9, 20.2] | 2/200 [0.1, 3.6] | 200 / 0 / 0 / 0 / 0 |
| Own streak, all x1 | 16/200 [4.6, 12.7] | 26/200 [8.7, 18.5] | 8/200 [1.7, 7.7] | 137 / 0 / 0 / 0 / 63 |
| Own streak, all x2 | 104/200 [44.8, 59.1] | 145/200 [65.8, 78.6] | 8/200 [1.7, 7.7] | 136 / 0 / 0 / 1 / 63 |
| Own profit, all x1 | 16/200 [4.6, 12.7] | 24/200 [7.8, 17.3] | 8/200 [1.7, 7.7] | 142 / 0 / 1 / 1 / 56 |
| Own profit, all x2 | 141/200 [63.7, 76.7] | 188/200 [89.8, 96.9] | 14/200 [3.9, 11.5] | 129 / 0 / 0 / 1 / 70 |
| Last rival, ring x1 | 11/200 [2.8, 9.6] | 15/200 [4.3, 12.1] | 9/200 [2.1, 8.4] | 133 / 0 / 0 / 1 / 66 |
| Last rival, ring x2 | 97/200 [41.4, 55.7] | 39/200 [14.2, 25.7] | 5/200 [0.8, 5.7] | 156 / 0 / 0 / 0 / 44 |
| Slow drift, all x1 | 81/200 [33.6, 47.7] | 160/200 [73.8, 85.3] | 7/200 [1.4, 7.1] | 120 / 0 / 1 / 0 / 79 |
| Slow drift, all x2 | 169/200 [78.7, 89.2] | 199/200 [97.2, 100.0] | 7/200 [1.4, 7.1] | 124 / 0 / 0 / 0 / 76 |
| Mean 3, pair x1 | 11/200 [2.8, 9.6] | 12/200 [3.1, 10.2] | 16/200 [4.6, 12.7] | 131 / 0 / 1 / 0 / 68 |
| Mean 3, pair x2 | 5/200 [0.8, 5.7] | 7/200 [1.4, 7.1] | 4/200 [0.5, 5.0] | 200 / 0 / 0 / 0 / 0 |
| Mean 10, pair x1 | 19/200 [5.8, 14.4] | 17/200 [5.0, 13.3] | 11/200 [2.8, 9.6] | 134 / 0 / 0 / 2 / 64 |
| Mean 10, pair x2 | 6/200 [1.1, 6.4] | 11/200 [2.8, 9.6] | 3/200 [0.3, 4.3] | 200 / 0 / 0 / 0 / 0 |
| Same rival, pair x1 | 154/200 [70.5, 82.6] | 189/200 [90.4, 97.2] | 7/200 [1.4, 7.1] | 130 / 0 / 0 / 0 / 70 |
| Same rival, pair x2 | 200/200 [98.2, 100.0] | 200/200 [98.2, 100.0] | 6/200 [1.1, 6.4] | 135 / 0 / 0 / 0 / 65 |
| Cartel q=.5 / mean 10 | 112/200 [48.8, 63.0] | 62/200 [24.7, 37.9] | 46/200 [17.4, 29.5] | 13 / 3 / 7 / 5 / 172 |

## Positive control

The following endpoints test the actual cartel 0/1; the off-target family excludes its two true directions. Counts and exact 95% intervals:

| Markets | Endpoint | Hits | Rate (%) | 95% CI (%) |
|---|---|---|---|---|
| 20 | L1_reported_target | 8 | 40.0 | [19.1, 63.9] |
| 20 | L2_reported_target | 3 | 15.0 | [3.2, 37.9] |
| 20 | detect_either | 3 | 15.0 | [3.2, 37.9] |
| 20 | detect_both | 0 | 0.0 | [0.0, 16.8] |
| 20 | off_target_leak_alarm | 0 | 0.0 | [0.0, 16.8] |
| 200 | L1_reported_target | 107 | 53.5 | [46.3, 60.6] |
| 200 | L2_reported_target | 48 | 24.0 | [18.3, 30.5] |
| 200 | detect_either | 38 | 19.0 | [13.8, 25.1] |
| 200 | detect_both | 3 | 1.5 | [0.3, 4.3] |
| 200 | off_target_leak_alarm | 8 | 4.0 | [1.7, 7.7] |

The honest fringe pair 2/3 has these classification counts (none / two-way / j->i / i->j / unclear):
- 20 markets: 14 / 0 / 0 / 0 / 6
- 200 markets: 131 / 0 / 2 / 0 / 67

## Observed inflation

A lower 95% interval bound above 5% is evidence of inflation for that row, without adjustment across the many variants/endpoints. A bound below 5% does not prove validity.
- L1_any_candidate: mean3_1, mean10_1, mean10_2, streak_2, profit_2, rival_2, drift_1, drift_2, decoy_mean10_1, decoy_rival_1, decoy_rival_2
- L2_any_candidate: mean3_1, mean3_2, mean10_1, mean10_2, streak_1, streak_2, profit_1, profit_2, rival_2, drift_1, drift_2, decoy_mean10_1, decoy_rival_1, decoy_rival_2
- leak_family_alarm: no lower bound above 5%

## Corrected target action term and realised bid changes

Means across markets; changes compare the actual honest bids with the original IID policy using identical costs/noise. Positive control changes refer only to its honest fringe.

| Variant | Action (bits) | Incoming leak (bits) | Outgoing leak (bits) | Mean absolute bid change | Bids changed (%) | Boundary bids (%) |
|---|---|---|---|---|---|---|
| iid | -0.0008 | 0.0007 | -0.0016 | 0.000 | 0.0 | 16.8 |
| last_exact | 0.0001 | -0.0001 | -0.0000 | 1.630 | 90.9 | 48.9 |
| mean3_1 | 0.0022 | 0.0001 | -0.0002 | 1.646 | 90.9 | 49.4 |
| mean3_2 | 0.0002 | -0.0000 | -0.0000 | 2.395 | 91.0 | 90.8 |
| mean10_1 | 0.0038 | 0.0000 | 0.0001 | 1.642 | 90.9 | 49.3 |
| mean10_2 | 0.0005 | -0.0001 | -0.0000 | 2.393 | 91.0 | 90.7 |
| streak_1 | 0.0506 | -0.0033 | 0.0013 | 0.595 | 59.5 | 12.9 |
| streak_2 | 0.1558 | -0.0046 | 0.0002 | 1.266 | 93.2 | 25.6 |
| profit_1 | 0.0041 | -0.0032 | -0.0027 | 0.516 | 51.6 | 8.5 |
| profit_2 | 0.1526 | 0.0007 | -0.0009 | 1.301 | 76.3 | 34.7 |
| rival_1 | 0.0037 | -0.0031 | 0.0011 | 1.770 | 86.5 | 56.0 |
| rival_2 | 0.0083 | 0.0010 | -0.0008 | 2.464 | 90.8 | 97.9 |
| drift_1 | 0.0857 | 0.0033 | -0.0003 | 0.459 | 45.9 | 20.9 |
| drift_2 | 0.1159 | 0.0001 | 0.0016 | 0.875 | 68.8 | 29.3 |
| decoy_mean3_1 | 0.0026 | -0.0002 | -0.0002 | 0.658 | 41.3 | 49.6 |
| decoy_mean3_2 | 0.0002 | -0.0000 | -0.0000 | 0.744 | 41.3 | 58.1 |
| decoy_mean10_1 | 0.0041 | -0.0002 | 0.0001 | 0.656 | 41.3 | 49.5 |
| decoy_mean10_2 | 0.0005 | -0.0001 | -0.0000 | 0.744 | 41.3 | 58.1 |
| decoy_rival_1 | 0.1878 | 0.0027 | -0.0013 | 0.736 | 41.5 | 16.8 |
| decoy_rival_2 | 0.3074 | -0.0002 | -0.0050 | 1.179 | 41.5 | 34.9 |
| cartel_mean10 | -0.0185 | 0.0484 | 0.0484 | 0.935 | 92.4 | 8.6 |

## Limitations

Scripted stress tests cannot establish exchangeability for arbitrary LLM policies. Current costs are independently redrawn, so honest history-only policies have no population current-cost information flow; trajectory permutation p-values still need not be valid. Adaptive H depends on earlier bids and costs. Even a clean leak result is empirical, not a finite-sample guarantee. Saturation at bid bounds can suppress variation, especially for strong reactions. Like the existing shared-history policy, these policies can bid below own cost; they are dependence stress tests, not optimal-bidding models. Absence labels use the existing p>=.2 and corrected leak<=.05 bits guard, which is not an equivalence test. Label intervals, unique reports, all directional p-values and effects are in the CSVs. A two-way label alone is not proof of collusion.
