"""Repository paths used by every notebook.

Every notebook starts with:
    import sys; from pathlib import Path
    ROOT = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p / "src" / "bt4015").is_dir())
    sys.path.insert(0, str(ROOT / "src"))
    from bt4015.paths import DATA, OUT, FIG, LARGE
so it runs from any working directory (Jupyter, VS Code, nbconvert).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"           # raw downloads, never edited
OUT = ROOT / "output"          # derived tables and GeoPackage layers, shared by all stages
FIG = ROOT / "figures"         # figures used in the report and slides
LARGE = ROOT / "large_data"    # git-ignored: OSRM graph, OSM extract, walk matrices (parquet)
for _d in (OUT, FIG):
    _d.mkdir(exist_ok=True)
