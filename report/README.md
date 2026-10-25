# Final analysis report (Round 14)

The manuscript uses `results/analysis/final_v1/results.json`, amendment freeze
`4c4b6f1`, executed at `7ca459c` with the documented loader fix (deviation 5g).
Results, Discussion, Conclusion and Abstract now use the final numbers.

Two pre-registered addenda were added after the final analysis (`docs/PREREG.md`,
Addenda v2.2 and v2.3, deviation 7): an out-of-sample replication of E1, C2 and
C1-SS on markets 20-39 and a 24,000-token judge check. Their statistics come from
the frozen analysis code run as separate cohorts:

```powershell
.venv/Scripts/python experiments/analyze_llm.py --unblind --input results --run-index results/analysis_runs_v22.json --manifest experiments/manifests/collection_v2.json --analysis-freeze-commit 4c4b6f1911486d479bd043e3590e9e0f90f6a42d --name replication_v22 --workers 3
.venv/Scripts/python experiments/analyze_llm.py --unblind --input results --run-index results/analysis_runs_v23.json --manifest experiments/manifests/collection_v2.json --analysis-freeze-commit 4c4b6f1911486d479bd043e3590e9e0f90f6a42d --judges results/llm/judge_index_24k.json --name judge24k_v23 --workers 3
.venv/Scripts/python experiments/addendum_summary.py --replication results/analysis/replication_v22/results.json --judge results/analysis/judge24k_v23/results.json --out results/analysis/addendum_summary
```

The last command writes `results/analysis/addendum_summary/summary.json` and the
LaTeX tables `sections/addendum_table.tex` (Table 1) and
`sections/addendum_full_table.tex` (Appendix E.7).

The five plain-language main-text figures (design; alarm outcomes; information-flow
direction; net influence vs. correlation; quiet cartel and AI judge) are rendered from
the same frozen outputs, without refitting:

```powershell
.venv/Scripts/python experiments/key_figures.py
```

It writes `results/report_figures/figure_1.*` to `figure_5.*` and
`key_figure_numbers.csv` (every plotted value with its JSON path). Figures A/B of
`report_figures.py` are in Appendix D.

From the repository root:

```powershell
.venv/Scripts/python experiments/report_figures.py
```

`--quick` renders identical frozen results. The script does not make model or
network calls and does not refit any statistic. It writes Figure A/B as PDF and
PNG, copies PDFs to `report/figures/`, and generates the numerical LaTeX tables.
The figure CSV/JSON includes every plotted point, interval, denominator and
source path. `results/report_figures/number_sources.csv` connects manuscript
numbers to their source annotations. `SOURCE_AUDIT.md` explains the claim limits.

From `report/`, with a working offline TeX installation:

```powershell
pdflatex --disable-installer -interaction=nonstopmode -halt-on-error main.tex
bibtex --disable-installer main
pdflatex --disable-installer -interaction=nonstopmode -halt-on-error main.tex
pdflatex --disable-installer -interaction=nonstopmode -halt-on-error main.tex
```

Times text/math, Helvetica sans and Courier mono are requested, with plainnat
author-year citations. Built with MiKTeX on 24 Oct 2026 (pdflatex + bibtex): main text
pages 1-8, references page 9, appendix after that (34 pages in total).

Verification: the renderer ran; full/quick numerical files agree byte-for-byte;
all plotted values and interval endpoints match their cited JSON paths (134 in Round 14; 130 after the Figure B update of 24 Oct, re-checked automatically);
all 1,872 markdown rows agree with JSON flow counts; static LaTeX checks pass.
The targeted in-memory analysis statistics suite passed 11 tests in 19.30 seconds.
The full suite was not run: its input tests write outside this round's scope.
Both PNG figures were visually inspected after correcting a label collision.

Bibliography: every entry was checked on 24 Oct 2026 against the publisher page,
the arXiv API, Crossref or the GitHub API. The sprint repository listed in the outline as
`soumya-nayak-commits/collusion-sprint` returned 404; the matching public repository of that
account (`collusion-detetction`, Question 1.4) is cited with commit and access date.

Modal billing: USD 70.35 before the addenda, USD 76.30 metered after them
(USD 76.03 from credits). Remaining editorial items: release URLs and Marvin's
final substantive review. Remaining scientific
limits: anti-conservative probe leak inference, failure-conditioned judge subsets,
and the unaudited bias/Monte Carlo contributions to fingerprint intervals.
