"""Operator-only mobile enrollment and revocation command.

Invoke from the canonical writer host: python -m sofia.mobile --help
No remote endpoint, no model command and no implicit state relocation.
"""
from .pairing import main

if __name__ == "__main__":
    raise SystemExit(main())
