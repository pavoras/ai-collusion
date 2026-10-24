# Final analysis report (Round 14)

The manuscript uses `results/analysis/final_v1/results.json`, amendment freeze
`4c4b6f1`, executed at `7ca459c` with the documented loader fix (deviation 5g).
Results, Discussion, Conclusion and Abstract now use the final numbers.

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
author-year citations. MiKTeX timed out after 60 seconds in this sandbox before
producing a PDF; BibTeX could not be reached. The main-text estimate is 6?7 pages
excluding references and appendix, but the eight-page cap must be checked in a
working TeX installation. No compiled report PDF is supplied. Figure PDFs exist.

Verification: the renderer ran; full/quick numerical files agree byte-for-byte;
all 134 plotted values and interval endpoints match their cited JSON paths;
all 1,872 markdown rows agree with JSON flow counts; static LaTeX checks pass.
The targeted in-memory analysis statistics suite passed 11 tests in 19.30 seconds.
The full suite was not run: its input tests write outside this round's scope.
Both PNG figures were visually inspected after correcting a label collision.

Remaining editorial items: exact Modal billing, release URLs, existing incomplete
bibliography metadata, and Marvin's final substantive review. Remaining scientific
limits: anti-conservative probe leak inference, failure-conditioned judge subsets,
and the unaudited bias/Monte Carlo contributions to fingerprint intervals.
