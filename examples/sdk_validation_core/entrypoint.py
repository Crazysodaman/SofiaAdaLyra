"""Launch the independent SDK Validation Core from any working directory.

The script directory is added explicitly because the validation run uses
``python -I``, which does not prepend the script directory to ``sys.path``.
Only the sibling ``runtime`` module and its public SDK imports are loaded.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from runtime import main

if __name__ == "__main__":
    raise SystemExit(main())
