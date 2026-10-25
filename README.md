# Detecting colluding LLM agents with pairwise net influence

Project for the Apart Research **AI Collusion Research Sprint** (23–25 October 2026), research question 1.4:
can information-theoretic measures find the colluding pair in a multi-agent game?
Repository: https://github.com/pavoras/ai-collusion

We implement the pairwise net influence statistic of Bonjour, Aggarwal and Bhargava (UAI 2022), reproduce their
iterated Rock-Paper-Scissors results, add a permutation-calibrated threshold, and test the method for the first time
on LLM agents with one covertly coordinating pair.

Author: Marvin Kemper (Independent). All code in this repository was written during the sprint, starting
23 October 2026; there is no preexisting code.

Status: collection, pre-registered analysis (`results/analysis/final_v1/`) and two pre-registered addenda
(replication on fresh markets, `results/analysis/replication_v22/`; judge token budget,
`results/analysis/judge24k_v23/`) are complete. The report is `report/main.pdf`; build and provenance notes are in
`report/README.md` and `report/SOURCE_AUDIT.md`. Design and deviations: `docs/PREREG.md`; method: `docs/METHOD.md`;
log: `docs/PLAN.md`.

Main findings: net influence detects the instructed cartel (pre-registered AUROC 0.865, p = 0.00002) but a plain
correlation of the same data does at least as well; net influence adds information when one firm secretly sees a
rival's cost (replicated on fresh markets); the most profitable cartel (no private channel) was the hardest to
detect.

## Setup

```bash
py -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
```

Exact versions used: `requirements-lock.txt` (Python 3.14).
