# Detecting colluding LLM agents with pairwise net influence

Project for the Apart Research **AI Collusion Research Sprint** (23–25 October 2026), research question 1.4:
can information-theoretic measures find the colluding pair in a multi-agent game?

We implement the pairwise net influence statistic of Bonjour, Aggarwal and Bhargava (UAI 2022), reproduce their
iterated Rock-Paper-Scissors results, add a permutation-calibrated threshold, and test the method for the first time
on LLM agents with one covertly coordinating pair.

Author: Marvin Kemper (Independent). All code in this repository was written during the sprint, starting
23 October 2026; there is no preexisting code.

Status: measures implemented and tested (`src/collusion/measures.py`). See `docs/PLAN.md`, `docs/METHOD.md`
and `docs/RESOURCES.md`.

## Setup

```bash
py -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
```

Exact versions used: `requirements-lock.txt` (Python 3.14).
