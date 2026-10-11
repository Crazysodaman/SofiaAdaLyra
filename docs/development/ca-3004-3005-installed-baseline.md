# CA-3004/3005: wheel-origin verification and Windows baseline teardown

The existing Cognition v2 baseline verifier resolved `PROJECT_ROOT` from
`cognition_v2_baseline.py`'s filesystem position and then loaded resources
from `PROJECT_ROOT/src/sofia`. In an installed wheel this points into the
site-packages ancestry instead of the exact imported package. An installed-
wheel verification gate could therefore fail for a missing checkout layout
or accidentally read different source assets from a nearby editable tree.

The baseline now obtains constitution, identity and avatar fixture resources
from the **actual imported Sofía package root**. It explicitly refuses
missing installed resources. The distribution packaging config explicitly
ships those four required assets inside the wheel. `PROJECT_ROOT` for Git
revision provenance is the caller's current checkout directory, and the
fixture's filesystem work root is its own bounded temporary directory.

The temporary baseline application's startup is now inside the same
`try/finally` that invokes shutdown before deleting the temporary SQLite
database. Previously an exception in `application.start()` bypassed the
shutdown call and could leave Windows file handles open. Existing explicit
SQLite closing for query snapshots is preserved.

The original historical Windows `WinError 32` is NOT claimed reproduced
or resolved here. Partial constructor failures and other RUN/background
owners still require exact-Windows runner/host evidence. Package/wheel
build, hash and signing proof require future acceptance execution. Source
tests were authored but not run.
