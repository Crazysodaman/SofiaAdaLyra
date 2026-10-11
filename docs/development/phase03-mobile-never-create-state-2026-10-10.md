# Phase 03: never bootstrap an alternate SQLite writer from mobile

The owner has explicitly left the canonical single-writer host undecided.
This does NOT permit Sofía's mobile and environmental components to create
a new `sofia.db` at whatever location happens to be configured.

Audited defect: `MobileSensorStore` unconditionally created its parent
directory and called `sqlite3.connect(path)`, which silently creates a
missing database. `MobileCompanionGateway.__init__` constructed that store
BEFORE checking for existing canonical state in `MobileDeviceCredentialStore`.
Consequently a misconfigured or temporarily missing writer path could result
in a new empty database and an apparently healthy mobile gateway.

Production repair:
- `MobileCompanionGateway` validates canonical state through existing
  credential-store ownership before any sensor/notification/schema work.
- `MobileSensorStore` refuses missing, directory, and symlinked state paths
  without creating parents or a database.
- The mobile sensor, notification, credential, and gateway SQLite connection
  factories now use explicit `mode=rw` with SQLite URI paths. If canonical
  state disappears after startup, subsequent calls fail closed rather than
  silently recreating a second, empty database.
- The independent signed state-home pointer, writer-fence and failover
  controller remain untouched and cannot be bypassed by a mobile request.

Authored but NOT executed regression cases cover no parent creation and
non-resurrection after deletion. Real host migration, Windows handle tests,
Android builds, and Fleet acceptance remain pending operator permission.
