"""Launch the independent SDK Validation Core from any working directory.

The script directory is added explicitly because isolated subprocess runs do
not prepend it to ``sys.path``.  Only the sibling ``runtime`` module and its
public ``sofia.sdk`` facades are loaded; the portable ``sofia.sdk.runtime``
facade owns wire validation, deadlines, outcomes and lifecycle dispatch.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from runtime import main

if __name__ == "__main__":
    raise SystemExit(main())
