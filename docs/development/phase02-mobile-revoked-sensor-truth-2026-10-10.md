# Phase 02 / 08: revoked mobile sensors are no longer current evidence

The per-device authentication rollout protected HTTP sensor submission but
older mobile sensor rows remained stored in `mobile_sensor_latest`, where
`MobileSensorProvider` selected the latest row regardless of current
credential revocation. That let a revoked phone continue influencing
ENVIRONMENT location, activity and resource decisions until the old reading
expired, even though the owner had withdrawn the device's access.

`MobileSensorStore.record` now performs a current active-enrollment check
inside the same canonical SQLite write transaction before accepting a source
observation. `MobileSensorStore.latest` joins the already-existing
`mobile_device_credential` owner table and considers only active enrolled
device IDs. Revocation removes old observations from the *current* eligible
environment projection immediately without deleting their historical
original records or inventing a second authority. Credential rotation for
an active enrolled device keeps that same device's observations eligible.

Standalone sensor-store clients require the canonical enrollment schema
but do not create a new state database or enroll any device themselves.
The previously installed `mode=rw` no-create SQLite and deterministic
connection close rules remain intact. Both HTTP-originated and internal
source updates are protected. Regression cases cover revocation, stale
evidence exclusion, and unpaired internal insertion denial, unexecuted
pending the owner-approved final verification campaign.
