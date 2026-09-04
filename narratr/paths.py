"""Where things live.

The package is installed editable, so ROOT is the repository checkout.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
SCHEMA = ROOT / "schemas" / "scenes.schema.json"
VOICES = ROOT / "assets" / "voices"
