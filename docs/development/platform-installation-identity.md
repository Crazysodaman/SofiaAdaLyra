# Explicit Platform installation identity

`companion-runtime identity-init --home /absolute/private/parent/installation`
creates one new Platform UUID and Ed25519 key pair. The parent must be private
to the current user; the installation directory must not already contain
incomplete state. Repeating initialization validates and reuses existing state.
`identity-show` reads public UUID, full serial, creation time and public-key
fingerprint. Neither command loads or changes a Core identity.

The private PKCS8 key and signed manifest live in owner-private files. Windows
uses the shared native DACL checks (Platform declares pywin32); POSIX requires
owner-only permissions and matching current UID. Filesystem redirection is
rejected and reads are bounded. An exclusive directory creator allocates the
key; concurrent callers either observe the same completed identity or refuse
incomplete state. Interrupted initialization preserves its partial state for
operator investigation. Missing, damaged or inconsistent files never trigger
replacement identity generation. This does not implement approved recovery.

Setting `AEGIS_PLATFORM_IDENTITY_HOME` explicitly selects this identity for
Platform status and the Core-worker Platform instance ID. An independently set
`SOFIA_PLATFORM_INSTANCE_ID` must match its canonical UUID. Without the new
setting, existing profiles retain their existing behavior. Status does not
create state. The bootstrap presentation starts with UNASSIGNED and no selected
Core; it does not represent a persistent callsign registry or Core Link state.

The local self-signature binds the manifest to its private key within the
owner-private filesystem boundary. It is not external enrollment evidence.
UUIDs, serials, public fingerprints and bootstrap output grant no permissions,
owner authority or remote trust. No owner credentials, pairing, registry,
service processes or network endpoints are created. OS key-store protection,
approved recovery and full first-install service composition remain separate
work. Existing Sofía identity and memory assets are untouched.
