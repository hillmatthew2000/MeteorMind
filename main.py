"""Run MeteorMind straight from a source checkout: ``python main.py [options]``.

Installing the package (``pip install -e .``) provides the ``meteormind`` and
``meteormind-gui`` commands instead; this shim just makes ``src/`` importable.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from meteormind.__main__ import main  # noqa: E402  (import after sys.path setup)

if __name__ == "__main__":
    sys.exit(main())
