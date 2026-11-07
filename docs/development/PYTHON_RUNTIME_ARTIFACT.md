# Neutral CPython runtime artifact

`sofia.sdk.python_runtime` defines `aegis.python-runtime.v1`: a bounded,
canonical inventory of CPython 3.12 code for Windows x86-64 or Debian 12 x86-64.
It contains neither an installed Platform identity nor a Core definition.

`sofia.platform.verify.python_runtime.build_python_runtime` prepares a
reproducible ZIP from a caller-vetted full CPython prefix. It excludes installed
site-packages, distribution packages, bytecode caches and standard-library test
trees. The upstream interpreter and its operating-system libraries must already
be trusted. Native header checks establish declared architecture, not health.
The builder does not execute its input interpreter.

`verify_python_runtime` checks one bounded immutable archive snapshot against
an expected artifact reference, target, patch version and exact per-file
inventory. It rejects redirected source paths, duplicate or additional ZIP
members, unsafe file modes, and changed member bytes. Empty standard-library
files are supported; existing release/Core artifact references retain their
positive size requirements.

`materialize_python_runtime` writes the verified snapshot into a new private
candidate directory. It refuses existing destinations and leaves any partial
failure quarantined. It does not select a release, register a service, create
Platform state or authorize installation. The outer signed Platform release
must authenticate the expected artifact reference before installation; constructing
an ArtifactReference or manifest does not grant authority.

`probe_materialized_python` rechecks the candidate inventory before executing
it as the current user with a restricted environment. It verifies actual native
relocation, version/prefix, TLS, SQLite, ctypes, venv, and absence of Core and
Ollama packages. It is suitable only for already trusted code. Its receipt is
not owner approval, cross-platform certification or release acceptance.

The Platform-only CI gate requires the actual runtime probe on Windows and
Debian. The disposable Debian VM recipe additionally builds and materializes
the runtime inside Debian 12, creates the wheel environment at guest paths,
and verifies that the supervised worker executes the bundled binary during
its two offline boots. This remains a test-image assembly path, not the signed
production installer. Windows service installation, release activation,
upgrade/rollback, uninstall/reinstall and installed-host release acceptance
remain separate gates.
