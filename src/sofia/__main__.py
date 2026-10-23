"""Module entrypoint: `python -m sofia`.

The application launcher implementation lives on Core
(`sofia.core.launcher`) since the Core 1.0 restructure; this module
remains the stable command surface.
"""
from sofia.core.launcher import main

if __name__ == "__main__":
    raise SystemExit(main())
