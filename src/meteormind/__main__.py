"""Entry point for ``python -m meteormind`` and the ``meteormind`` command."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
