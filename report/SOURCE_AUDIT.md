# Round 14 source and claim audit

All final LLM numbers come from `results/analysis/final_v1/results.json`.
Its SHA-256 is `36804b9c365f98bb03bc92d7ab44b403a1ed6a6cf274339a968e035df5fdc672`.
This report uses the binding Round 13 review and the Round 14 wording decisions.
No analysis outputs, source modules, collection files or preregistration were edited.

## Complete numerical provenance

- `results/report_figures/figure_numbers.csv` and `.json`: every plotted estimate,
  interval endpoint, denominator, subset and exact zero-based JSON path (130 rows since 24 Oct; the middle row of Figure B now compares the registered 12k judge with the 24k judge cohort `results/analysis/judge24k_v23/results.json`, source file named per row).
- `results/report_figures/number_sources.csv`: printed manuscript/table content
  alongside its source annotations, including the full appendix.
- Every numerical LaTeX table row and each quantitative prose paragraph has a
  `% source:` annotation. Array indices below are zero-based. Prefix is 200 and
  mask is `complete` unless stated otherwise.
- Replication tables use the existing `results/rps/cda.csv` and `calibration.csv`;
  these are scripted development results, not final LLM observations.
- Design constants retain their preregistration/method sources. Digests are actual
  SHA-256 file-byte calculations, separately labelled from canonical manifest hashes.

## Numbers used in the main quantitative narrative

All paths in this table are within the final `results.json` named above.
The generated behaviour table and both figures have their complete numbers in
the numerical ledgers; the table below covers the prose, including repeated
abstract values. The Discussion and Conclusion introduce no new empirical numbers.

| Printed numbers | Meaning | JSON source |
|---|---|---|
| 0.865; [0.734, 0.968]; p=0.00002; 20 | Primary L2 net AUROC, descriptive interval, paired-label p and blocks | `primary`; `all_cells[206].auroc` |
| 0.9875 / 0.9975; ?0.1325 [?0.2647, ?0.0309] | C1-SS correlation L1/L2 and L2 net-minus-correlation | `all_cells[196,202].auroc`; `contrasts[95].result` |
| 0.6100 / 0.4625; +0.1475 [?0.1818, 0.4422] | C2 L1 net/correlation and difference | `all_cells[268,266].auroc`; `contrasts[204].result` |
| 0.6550 / 0.4950; +0.1600 [?0.1250, 0.4531] | C2 L2 net/correlation and difference | `all_cells[274,271].auroc`; `contrasts[208].result` |
| 0.6750 / 0.4825; +0.1925 [0.0222, 0.3599] | E1 L1 net/correlation and difference | `all_cells[334,332].auroc`; `contrasts[259].result` |
| 0.7000 / 0.4150; +0.2850 [0.0620, 0.5150] | E1 L2 net/correlation and difference | `all_cells[340,337].auroc`; `contrasts[263].result` |
| 0.7025 [0.5737, 0.8360]; 20 | E1 leak AUROC and matched blocks | `all_cells[339].auroc` |
| SF 1.00/0.80 vs 1.00/0.90; FF 1.00/1.00; strength zero | Net/correlation top-1 L1/L2 and strength baseline | `all_cells[398,400,402,403,406,408,464,466,468,469,472,474].top1` |
| 0.70; 0.25; 0.75; zero wrong | C1-SS L2 net ranking, correct unique report, abstention, wrong-pair report | `all_cells[206].top1,correct_unique,abstention,wrong_pair` |
| 0/40; upper bound 0.0881 | N0 designated-reference net alarms, both levels | `all_cells[55,62].designated_alarm` |
| 1/40; 3/40; 4/40 | N0 L1 net, L2 net, L2 leak any/unique alarms | `all_cells[55,62,61].any_candidate,exactly_one_report` |
| 40/40 | N0 L2 paper any/unique alarms | `all_cells[63].any_candidate,exactly_one_report` |
| 0.8875; 0/20 correct; 20/20 wrong | C2 paper continuous raw-score AUROC and threshold-rule reports | `all_cells[275].auroc,correct_unique,wrong_pair,coverage` |
| +0.0975 [?0.0051, 0.2300] | A1 NW-minus-SS L2 net AUROC | `addendum.A1.auroc_differences.L2:net` |
| fall 0.3478 [0.2921, 0.4015]; fall 0.3335 [0.2753, 0.3925] | A1 joint-profit and winning-price decreases (sign reversed for ?fall?) | `addendum.A1.behaviour_NW_minus_SS.joint_profit,winning_price` |
| C1-SS 0/0/8/12; E1 0/4/8/8 | Both / one reverse weak / neither both weak / unclear designated-flow counts | `all_cells[206,340].label:*` |
| 322/600; 53.67%; 1?8 blocks | Invalid Qwen judgement count/rate and matched AUROC range | `judgments` grouped by model/status/failure; `judge_comparisons[*].judge_auroc.n_blocks` |
| 5/40 valid; no matched AUROC | Gemma counter-judge coverage | `judgments` grouped by model/status; `all_cells[197,203].auroc` |
| Gemma-E4B 0/0; Ministral-3B 0/2 | Eligible N0/C1 markets, not negative detection results | `all_cells[934,1000,1066,1132].eligible` |
| Seven endpoints; zero Holm rejections; 0.03771 ? 0.26397 | A2 family and leak raw/adjusted p | `addendum.A2.endpoints`; `endpoints.L2:leak.test.p_value,holm_p_value` |
| 0.01347 [?0.00353, 0.03195]; 199 | Exploratory slope and complete contexts | `probes.summaries[0].slope,complete_contexts` |
| 0.08879 bits; p=0.001; 2,997 | Exploratory corrected leak, implemented p and observed bids | `probes.summaries[0].leak` |

The 12,000-token per-attempt judge limit and the five-bid message bundle are
registered design/implementation facts (`docs/PREREG.md` ??8?9 and
`experiments/run_llm.py`). ?Most failed calls ended with length? is attributed
to the Round 14 raw-log observation; no independent full raw-log cause audit
was performed here. It is not inferred from `invalid_judge_json`.

## Addenda v2.2-v2.3 (added 24 Oct 2026, after Round 14)

These numbers come from separate cohorts analysed with the frozen code
(`docs/PREREG.md` Addenda v2.2-v2.3, deviation 7). Paths are zero-based within
the named file. Commands are in `report/README.md` and Appendix E.7.

| Printed numbers | Meaning | Source |
|---|---|---|
| E1 0.680 / 0.415; +0.265 [0.070, 0.445]; leak 0.745 | Replication E1 L2 net/correlation, difference (R1), leak | `replication_v22/results.json` `all_cells[1990,1987,1989].auroc`; `contrasts[501].result` |
| +0.095 [−0.1125, 0.315] | Replication E1 L1 net minus correlation (R1b, not replicated) | `replication_v22/results.json` `contrasts[498].result` |
| +0.283 [0.179, 0.371] | Replication C2 joint-profit uplift over N0 (R2) | `replication_v22/results.json` `behaviour[40].paired_difference` |
| 0.753 / 0.630; difference interval includes 0 | Replication C2 L2 net/correlation (R3) | `replication_v22/results.json` `all_cells[2056,2053].auroc`; `contrasts[555].result` |
| 0.9075 [0.8025, 0.985]; 0.995; −0.0875 [−0.19, −0.015] | Replication C1-SS L2 net (R4), correlation, difference | `replication_v22/results.json` `all_cells[2122,2119].auroc`; `contrasts[609].result` |
| −0.155 [−0.30, −0.01]; −0.365 [−0.59, −0.16] | Replication C1-SS minus C2, L2 net and correlation | `replication_v22/results.json` contrasts "C1-SS minus C2 L2:net", "L2:correlation" |
| 54/60 vs 27/60; 31 above 12,000 tokens | Judge valid output at 24k vs registered 12k on the same markets; valid answers over the old limit | `addendum_summary/summary.json` `judge_budget`; raw call records of the `__deviation_judge24k` runs |
| 0.625 [0.424, 0.808]; 17 blocks; net 0.907; correlation 1.000 | Judge 24k C1-SS vs N0 AUROC and same-block comparators | `judge24k_v23/results.json` `all_cells[138]` (judge:qwen-9b); `judge_comparisons[0,1,4,5]` |
| top-1 0.92 / 0.90 / 0.02; net 0.93 | Judge 24k top-1 in C1-SS, N0 reference pair, C1-SF; net on the same SF markets | `judge24k_v23/results.json` `all_cells[138,60,206].top1`; `judge_comparisons[4]` |
| 70.35; 76.30; 76.03 | Modal billing before/after the addenda; part paid from credits | Modal dashboard (Marvin, 24 Oct); `modal billing summary` 24 Oct 2026 21:43 |

Table 1 and the Appendix E.7 tables are generated by `experiments/addendum_summary.py`
from these files; they are not typed by hand.

## Claim boundaries implemented

Only the primary within-block label-exchangeability test is confirmatory.
Baseline differences are descriptive with pointwise intervals; A2 is the
separate preregistered secondary Holm family; probes are exploratory.
E1 concerns unilateral information access, not a collusion positive.
No universal advantage, equivalence, incremental predictive value, causal
probe transmission, judge internal heuristic or model-size effect is claimed.

The N0 reference-pair ranking is explicitly not localisation accuracy.
Continuous score AUROC, top-1 ranking, unique/wrong reports, abstention and
market-level alarms are distinguished. Judge comparisons use identical
successful matched blocks; treatment-only summaries are labelled separately.
The comprehensive table retains every registered cell and all flow categories.

Ten frozen fingerprint point estimates fall outside their percentile intervals.
The exact paths are in `results/report_figures/provenance.json`; the appendix
flags each one. The report preserves the estimates and does not claim the
bootstrap-bias or permutation-noise explanation has been verified.

## Verification and remaining limits

The renderer and `--quick` both ran successfully. Numerical CSV/JSON output was
byte-identical across modes. All plotted triples matched their JSON paths (134 in Round 14; 130 re-checked on 24 Oct after the Figure B update);
all 1,872 markdown rows and label counts agreed with JSON. Complete-mask flow
counts balance against eligibility. TeX inputs, environments and reference
labels passed static checks. Both PNGs were viewed; the central-label collision
in the first localisation draft was fixed and the revised PNG was inspected.

Targeted test command (bytecode/cache writes disabled to respect the scope):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.venv/Scripts/python -B -m pytest -q -p no:cacheprovider tests/test_analysis_statistics.py
```

Result: **11 passed in 19.30s**. The full suite was not run because
`tests/test_analysis_inputs.py` explicitly creates directories under the
out-of-scope `results/analysis_dev/` tree. No new tests were added.

MiKTeX produced no PDF before the 60-second timeout. The process was stopped;
BibTeX was therefore not reached. Main-text length is estimated at **6?7 pages**,
excluding bibliography/appendix, from approximately 3,000 whitespace-delimited source words (including
LaTeX commands) plus the three displays. The hard eight-page cap and PDF font
embedding still require a working LaTeX build. Times, Helvetica and Courier
are requested; figure PDFs use embedded TrueType fonts. Plainnat remains.

Update 24 Oct 2026: MiKTeX now builds the report (main text pages 1-8,
references page 9); bibliography metadata verified (see README); billing
entered from Modal (USD 70.35 before, 76.30 after the addenda).
Open items: release URLs; Marvin's final review; probe inference; fingerprint
interval audit. No billing figure or citation metadata has been invented.
