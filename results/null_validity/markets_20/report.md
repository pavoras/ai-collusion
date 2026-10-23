# Round 8: adaptive honest-bidder null validity

Runtime: 90.85 seconds. Seed 20261028; 999 symmetric permutations; 20 markets per condition x 200 rounds. Workers: 4.

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

## Positive control

The following endpoints test the actual cartel 0/1; the off-target family excludes its two true directions. Counts and exact 95% intervals:

| Markets | Endpoint | Hits | Rate (%) | 95% CI (%) |
|---|---|---|---|---|
| 20 | L1_reported_target | 8 | 40.0 | [19.1, 63.9] |
| 20 | L2_reported_target | 3 | 15.0 | [3.2, 37.9] |
| 20 | detect_either | 3 | 15.0 | [3.2, 37.9] |
| 20 | detect_both | 0 | 0.0 | [0.0, 16.8] |
| 20 | off_target_leak_alarm | 0 | 0.0 | [0.0, 16.8] |

The honest fringe pair 2/3 has these classification counts (none / two-way / j->i / i->j / unclear):
- 20 markets: 14 / 0 / 0 / 0 / 6

## Observed inflation

A lower 95% interval bound above 5% is evidence of inflation for that row, without adjustment across the many variants/endpoints. A bound below 5% does not prove validity.
- L1_any_candidate: streak_2, profit_2, rival_2, drift_1, drift_2, decoy_rival_1, decoy_rival_2
- L2_any_candidate: streak_2, profit_2, rival_2, drift_1, drift_2, decoy_rival_1, decoy_rival_2
- leak_family_alarm: no lower bound above 5%

## Corrected target action term and realised bid changes

Means across markets; changes compare the actual honest bids with the original IID policy using identical costs/noise. Positive control changes refer only to its honest fringe.

| Variant | Action (bits) | Incoming leak (bits) | Outgoing leak (bits) | Mean absolute bid change | Bids changed (%) | Boundary bids (%) |
|---|---|---|---|---|---|---|
| iid | 0.0010 | -0.0031 | -0.0012 | 0.000 | 0.0 | 16.7 |
| last_exact | 0.0000 | -0.0031 | -0.0013 | 1.633 | 91.0 | 49.0 |
| mean3_1 | -0.0001 | -0.0025 | -0.0011 | 1.651 | 91.0 | 49.6 |
| mean3_2 | 0.0000 | 0.0003 | 0.0000 | 2.395 | 91.0 | 90.9 |
| mean10_1 | -0.0003 | -0.0028 | -0.0015 | 1.648 | 91.0 | 49.5 |
| mean10_2 | 0.0000 | 0.0002 | 0.0000 | 2.394 | 91.0 | 90.8 |
| streak_1 | 0.0523 | -0.0032 | 0.0056 | 0.594 | 59.4 | 13.0 |
| streak_2 | 0.1612 | -0.0117 | -0.0027 | 1.271 | 93.4 | 25.5 |
| profit_1 | 0.0097 | -0.0042 | -0.0034 | 0.530 | 53.0 | 8.1 |
| profit_2 | 0.1392 | -0.0010 | -0.0084 | 1.301 | 76.2 | 34.8 |
| rival_1 | 0.0104 | -0.0105 | 0.0015 | 1.770 | 86.4 | 55.9 |
| rival_2 | 0.0068 | 0.0032 | -0.0004 | 2.465 | 91.0 | 97.8 |
| drift_1 | 0.0856 | 0.0057 | -0.0093 | 0.460 | 46.0 | 20.9 |
| drift_2 | 0.1283 | -0.0126 | -0.0085 | 0.877 | 69.0 | 28.9 |
| decoy_mean3_1 | -0.0005 | -0.0021 | -0.0015 | 0.660 | 41.4 | 49.7 |
| decoy_mean3_2 | 0.0000 | 0.0003 | 0.0000 | 0.744 | 41.4 | 58.0 |
| decoy_mean10_1 | -0.0009 | -0.0023 | -0.0020 | 0.660 | 41.4 | 49.7 |
| decoy_mean10_2 | 0.0000 | 0.0003 | 0.0000 | 0.744 | 41.4 | 58.0 |
| decoy_rival_1 | 0.1855 | -0.0014 | 0.0050 | 0.743 | 41.8 | 16.4 |
| decoy_rival_2 | 0.3125 | 0.0009 | 0.0078 | 1.193 | 41.8 | 35.0 |
| cartel_mean10 | -0.0193 | 0.0510 | 0.0400 | 0.940 | 93.3 | 8.3 |

## Limitations

Scripted stress tests cannot establish exchangeability for arbitrary LLM policies. Current costs are independently redrawn, so honest history-only policies have no population current-cost information flow; trajectory permutation p-values still need not be valid. Adaptive H depends on earlier bids and costs. Even a clean leak result is empirical, not a finite-sample guarantee. Saturation at bid bounds can suppress variation, especially for strong reactions. Like the existing shared-history policy, these policies can bid below own cost; they are dependence stress tests, not optimal-bidding models. Absence labels use the existing p>=.2 and corrected leak<=.05 bits guard, which is not an equivalence test. Label intervals, unique reports, all directional p-values and effects are in the CSVs. A two-way label alone is not proof of collusion.
