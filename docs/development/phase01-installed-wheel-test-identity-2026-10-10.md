# Phase 01: execute release tests against the installed wheel

The existing release build exported source outside Git checkout and installed
a release wheel. However, the revision-bound test gate ran from the original
checkout, whose `pyproject.toml` contained `pythonpath=[".", "src"]`.
Consequently pytest could import the checkout's `src/sofia` instead of
the installed wheel. A green test result under that configuration would not
prove that the wheel to be shipped behaved the same way.

The production release workflow now explicitly runs
`sofia.verify.gate --installed-wheel-only --repo <checkout>`.
The gate rejects nonvirtualenv and editable/checkout `sofia` origins, keeps
its revision and file checks grounded to the true checkout, and excludes any
inherited `PYTHONPATH` for release command subprocesses. Installed-only
pytest runs override just the source-injecting `pythonpath` setting, while
keeping the canonical tests and other pytest options intact.
The existing test conftest now fails a release session if the package origin
resolves outside the Python release venv or if checkout `src/` is exposed as
a Python import root. This applies both to the full test suite and the
nonempty-marker collection proof. Ordinary editable/dev runs are unaffected.

Only a source audit and regression case authoring were performed.
CI, clean Windows wheel build, signature verification, focused tests
and exact-source live acceptance remain deferred by user instruction.
This is a production path correction for CA-3004, not evidence that Phase 01
has passed.
