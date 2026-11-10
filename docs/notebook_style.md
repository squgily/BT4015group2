# Notebook conventions for this repository

The course asks for *readable* code: "commenting, formatting & documenting; use comments to explain why
things are happening." Every analysis is a Jupyter notebook that has been executed top to bottom, with
its outputs saved, so a reader can follow the work without running anything. The style copies the
BT4222 Group 6 repository (`2_EDA/impression_analysis.ipynb` there).

## Layout of a notebook

1. **Title cell (markdown).** `# <stage>.<n> <Title>`, one paragraph on the question this notebook
   answers and where it sits in the pipeline, then two short lists: **Inputs** (file, producer) and
   **Outputs** (file, consumer). Name the original author if the code came from a teammate's script.
2. **Setup cell (code).** Imports, then the root finder and the shared paths:
   ```python
   import sys
   from pathlib import Path
   ROOT = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "src" / "bt4015").is_dir())
   sys.path.insert(0, str(ROOT / "src"))
   from bt4015.paths import DATA, OUT, FIG, LARGE
   ```
   Constants (thresholds, seeds, file names) go here with a one-line comment each. This is the only
   cell a reader should need to edit.
3. **Numbered sections.** A markdown heading (`## 1. Load the HDB blocks`) that says what the section
   does and, where the result matters, what it found. Then one or two code cells with **numbered step
   comments** (`# 1. ...`, `# 2. ...`) that explain *why*, not what the pandas call does.
   Each cell prints the numbers it produces (row counts, match rates, statistics) so the saved output
   is the evidence. One plot per cell; `plt.show()` after `savefig`.
4. **Closing cell.** Prints the files written, with row counts.

## Code

- pandas / geopandas / numpy / matplotlib only, plus pyogrio for I/O and esda/libpysal for Moran's I.
  No `argparse`, no `def main()`, no `if __name__`. Functions are allowed when the same step runs for
  several inputs; define them in the cell before their first use with a docstring.
- Short cells. If a cell scrolls past one screen, split it at the next numbered step.
- Variable names say what the table holds (`blocks`, `centres`, `subzones`), not `df`, `df2`.
- Paths through `DATA`, `OUT`, `FIG`, `LARGE`; never absolute paths or `..`.
- Seeds fixed (4015). Permutation counts as in the original script.
- Keep teammates' logic unchanged. Comments and structure are what we add; if a line is changed for a
  real reason (a bug, a stale path) say so in a comment: `# changed 2026-11-10: ...`.
- Figures: categorical colours in fixed order blue `#2a78d6`, orange `#eb6834`, aqua `#1baf7a`,
  yellow `#eda100`; sequential = single-hue blues; LISA HH `#e34948`, LL `#2a78d6`, HL `#f3b3b2`,
  LH `#b7d3f6`, not significant `#efeeea`. Text in dark grey, never in the series colour.

## Execution

From the notebook's folder:
`jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=3600 <name>.ipynb`

Notebooks that need a service that is not always available (OSRM on port 5001, the OneMap API) say
so in their title cell and in the stage README, and keep the outputs of their last full run.

## Stage README

Each stage folder has a `README.md` with: one paragraph on the stage; a table `Notebook | What it does |
Inputs | Outputs | Runtime`; a short "Findings" or "Decisions" list if the stage produced any; and the
run order. Link notebooks with relative links.
