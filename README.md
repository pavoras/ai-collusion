# Detecting colluding LLM agents with pairwise net influence

Project for the Apart Research **AI Collusion Research Sprint** (23–25 October 2026), research question 1.4:
can information-theoretic measures find the colluding pair in a multi-agent game?
Repository: https://github.com/pavoras/ai-collusion

We implement the pairwise net influence statistic of Bonjour, Aggarwal and Bhargava (UAI 2022), reproduce their
iterated Rock-Paper-Scissors results, add a permutation-calibrated threshold, and test the method on LLM bidders in a
repeated procurement auction with an instructed cartel or a spy, each matched to an honest twin market.

Author: Marvin Kemper (Independent). All code in this repository was written during the sprint, starting
23 October 2026; there is no preexisting code.

Status: collection, pre-registered analysis (`results/analysis/final_v1/`) and two pre-registered addenda
(replication on fresh markets, `results/analysis/replication_v22/`; judge token limit,
`results/analysis/judge24k_v23/`) are complete. The report is `report/main.pdf`; build and provenance notes are in
`report/README.md` and `report/SOURCE_AUDIT.md`. Design and deviations: `docs/PREREG.md`; method: `docs/METHOD.md`;
log: `docs/PLAN.md`.

Main findings (report, Sections 4-5):
- From bids alone, a permutation-calibrated net-influence alarm named the colluding pair in 49 of 60 markets with a
  chatting cartel, never a wrong pair, with 1 false alarm in 40 honest markets; the published fixed threshold flagged
  24 of 40 honest markets.
- With private costs, pooled evidence shows the direction of information flow (two-way cartel, one-way spy), but
  single-market alarms almost never caught the spy, which barely used the stolen cost.
- A plain correlation detects chatting cartels at least as well (pre-registered AUROC 0.865, p = 0.00002, vs. 0.9975);
  net influence ranks spy markets higher (replicated on fresh markets).
- The most profitable cartel (no chat) kept a fixed price of 3 and stayed almost invisible; a 9B AI judge picked the
  strong firms rather than the colluders.
- Post-hoc analyses: `experiments/quiet_cartel_bids.py`, `experiments/cartel_mechanics.py`,
  `experiments/spy_behaviour.py` (report Appendix F).

## Setup

```bash
py -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
```

Exact versions used: `requirements-lock.txt` (Python 3.14).
