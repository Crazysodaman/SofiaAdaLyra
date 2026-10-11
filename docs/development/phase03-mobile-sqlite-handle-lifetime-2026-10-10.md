# Mobile sensor SQLite handle-ownership audit

Prior to this change, `MobileSensorStore.__init__`, `record`, and `latest`
used `with sqlite3.Connection as db`. Python's SQLite context manager only
commits or rolls back a transaction; it does **not close** the connection.
A continuously running Android sensor bridge could therefore accumulate
unclosed file handles until garbage collection, complicating Windows
backup, shutdown, file relocation, and `WinError 32` diagnosis.

All three sensor-store access paths now use `contextlib.closing`; write
contexts additionally preserve the actual transaction commit/rollback.
The canonical `mode=rw` no-create policy is retained, and this does not
introduce a new store, worker, or database. A regression case uses an
actual SQLite Connection subclass with tracked `close()` calls to verify
both the read and write paths deterministically release handles.
Tests were authored but not executed; no live Windows host modified.
