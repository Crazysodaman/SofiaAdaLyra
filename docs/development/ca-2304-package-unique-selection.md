# V18 CA-2304 / CA-3006 marker reconciliation (source-only)

The current `test/conftest.py` ALREADY includes both
`MODULE_PACKAGE_MARKERS["body"] = ("pkg_body",)` and the explicit
`test_body_` filename ownership rule. Therefore the originally reported
zero BODY selection issue is repaired **in current source**. Do not claim
the original failing CI run was green, or relabel test files to hide it.

Production verification receipts now report the difference between:
- number of *distinct pytest item IDs* selected,
- number of distinct test source root files,
- each package marker's selected tests and unique source roots, and
- pytest items carrying multiple genuine package markers.

The proof uses pytest's actual fully selected items, not approximate grep
matching. A check for empty or duplicate node IDs fails closed, and the
`pkg_body` rule remains strict. Individual package CI jobs still run their
same real test selectors, with no test masking or denominator inflation.

Tests were authored but intentionally NOT run. CA-2304 and CA-3006 remain
unaccepted until all package CI jobs, including BODY, run and publish
exact-SHA receipts. The earlier zero-tests failure remains factual history.
