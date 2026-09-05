"""Where things live.

The package is installed editable, so ROOT is the repository checkout.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
# Artifacts live outside the run directory and are named by content, so an
# edited scene reuses everything it did not change -- across runs, not just
# within one.
STORE = ROOT / "store"
SCHEMA = ROOT / "schemas" / "scenes.schema.json"
VOICES = ROOT / "assets" / "voices"
