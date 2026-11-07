"""Where the repository and its folders are: one place for every script in tools/.

Scripts import these instead of working the paths out again, so moving a folder
changes one line. Paths are absolute, so a script works from any directory.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
