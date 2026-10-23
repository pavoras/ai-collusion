# Rules for Codex in this repository

Project: Apart Research AI Collusion Sprint, question 1.4 (pairwise net influence, Bonjour et al. 2022).
Read `docs/DESIGN.md` and `docs/METHOD.md` for the science; `docs/PLAN.md` for the schedule.

- Code, comments and docstrings in English. Match the style of `src/collusion/measures.py`: small functions,
  numpy-vectorised, short docstrings, no needless abstraction.
- Python via `.venv/Scripts/python` (Windows, Python 3.14). Tests: `.venv/Scripts/python -m pytest -q`.
- Every experiment script writes its numbers (CSV/JSON) and figures to `results/<name>/`, is seeded, has a
  `--quick` flag, and can be rerun to reproduce every number. Figures use `collusion.plotting` (apply_style,
  BLUE/ORANGE/AQUA, no dual axes, legends present, nothing overlapping).
- Honesty: never invent numbers; report what the code actually printed.
- Never commit, push or rewrite git history. Never read or write secrets (`*.env`, `~/.modal.toml`).
- No LLM or network calls, no Modal runs. Do not edit `docs/`, `cloud/`, `CLAUDE.md`, `AGENTS.md`.
- Final answer: what changed (files, net lines), test result, key numbers, open questions, anything you doubt.
