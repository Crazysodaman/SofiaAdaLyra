//! Bounded broker-only journal for a trusted, protected local directory.
//!
//! This is not canonical Core storage, an authentication source, or an OS UI
//! adapter. The Platform must provision the directory and authenticate calls.
//! The checksum detects corruption, not hostile replacement by its owner.
//! An independently retained minimum revision detects an older valid snapshot.
//! Filesystem durability is implemented only on Unix; other platforms fail
//! closed until their directory-flush/replacement contract is implemented.

use crate::{Admission, Appearance, BrokerError, BrokerState, OsSignals, SlotState};
use fs2::FileExt;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

const MAX_BYTES: u64 = 4 * 1024 * 1024;
const MAX_RECORDS: usize = 4096;
const SCHEMA: &str = "aegis.ui-broker.journal.v1";
const SNAPSHOT: &str = "broker-ledger.json";
const STAGING: &str = "broker-ledger.pending";

#[derive(Debug)]
pub enum JournalError {
    Io(std::io::Error),
    InvalidSnapshot,
    WrongIdentity,
    StaleRevision,
    StaleGeneration,
    UnsafeStorage,
    UnsupportedPlatform,
    Policy(BrokerError),
    Unavailable,
}

impl From<std::io::Error> for JournalError {
    fn from(error: std::io::Error) -> Self {
        Self::Io(error)
    }
}

impl From<BrokerError> for JournalError {
    fn from(error: BrokerError) -> Self {
        Self::Policy(error)
    }
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Record {
    request_id: String,
    local_day: String,
    host_id: String,
    session_id: String,
    generation: u64,
    state: String,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Payload {
    schema: String,
    platform_id: String,
    revision: u64,
    generation: u64,
    last_accepted_day: String,
    owner_hidden: bool,
    records: Vec<Record>,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Snapshot {
    payload: Payload,
    checksum: String,
}

fn checksum(payload: &Payload) -> Result<String, JournalError> {
    let encoded = serde_json::to_vec(payload).map_err(|_| JournalError::InvalidSnapshot)?;
    Ok(format!("{:x}", Sha256::digest(encoded)))
}

fn private_regular_file(file: &File) -> Result<(), JournalError> {
    let metadata = file.metadata()?;
    if !metadata.is_file() {
        return Err(JournalError::UnsafeStorage);
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::{MetadataExt, PermissionsExt};
        if metadata.permissions().mode() & 0o077 != 0 || metadata.nlink() != 1 {
            return Err(JournalError::UnsafeStorage);
        }
    }
    Ok(())
}

fn private_create(path: &Path) -> Result<File, JournalError> {
    let mut options = OpenOptions::new();
    options.write(true).read(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let file = options.open(path)?;
    private_regular_file(&file)?;
    Ok(file)
}

fn open_existing(path: &Path) -> Result<File, JournalError> {
    let metadata = fs::symlink_metadata(path)?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(JournalError::UnsafeStorage);
    }
    let file = File::open(path)?;
    private_regular_file(&file)?;
    Ok(file)
}

/// Single-process writer. Every admitted transition is flushed before it is
/// exposed. OS advisory locking prevents two cooperating broker writers; the
/// Platform must prevent untrusted programs from accessing this directory.
/// A failed persistence attempt poisons the handle, because commit outcome may
/// be unknown. Drop it and recover with a fresh generation before further use.
pub struct DurableBroker {
    directory: PathBuf,
    platform_id: String,
    revision: u64,
    state: BrokerState,
    healthy: bool,
    _lock: WriterLock,
}

struct WriterLock(File);

impl Drop for WriterLock {
    fn drop(&mut self) {
        // Unlock the open-file description explicitly. A concurrently spawned
        // child may briefly inherit an FD between fork and exec; closing only
        // our descriptor would otherwise leave the lock held until its exec.
        let _ = FileExt::unlock(&self.0);
    }
}

impl DurableBroker {
    fn acquire(directory: &Path) -> Result<WriterLock, JournalError> {
        if !cfg!(unix) {
            return Err(JournalError::UnsupportedPlatform);
        }
        let metadata = fs::symlink_metadata(directory)?;
        if metadata.file_type().is_symlink() || !metadata.is_dir() {
            return Err(JournalError::UnsafeStorage);
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            if metadata.permissions().mode() & 0o077 != 0 {
                return Err(JournalError::UnsafeStorage);
            }
        }
        let path = directory.join("broker-writer.lock");
        let lock = match private_create(&path) {
            Ok(file) => file,
            Err(JournalError::Io(error)) if error.kind() == std::io::ErrorKind::AlreadyExists => {
                // Open read/write for an exclusive Windows-compatible lock.
                let metadata = fs::symlink_metadata(&path)?;
                if metadata.file_type().is_symlink() {
                    return Err(JournalError::UnsafeStorage);
                }
                OpenOptions::new().read(true).write(true).open(&path)?
            }
            Err(error) => return Err(error),
        };
        private_regular_file(&lock)?;
        lock.try_lock_exclusive()?;
        Ok(WriterLock(lock))
    }

    /// Explicit first-install operation. Never use as a fallback for failed
    /// recovery. Existing snapshots or interrupted staging files are rejected.
    ///
    /// # Errors
    /// Reject unsafe/unsupported storage, duplicate initialization, malformed
    /// identities, policy state, or any failed durability operation.
    pub fn initialize(
        directory: &Path,
        platform_id: String,
        generation: u64,
        day: String,
    ) -> Result<Self, JournalError> {
        if !crate::valid_appearance_id(&platform_id) {
            return Err(JournalError::WrongIdentity);
        }
        let lock = Self::acquire(directory)?;
        for name in [SNAPSHOT, STAGING] {
            match fs::symlink_metadata(directory.join(name)) {
                Ok(_) => return Err(JournalError::InvalidSnapshot),
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                Err(error) => return Err(error.into()),
            }
        }
        let mut broker = Self {
            directory: directory.into(),
            platform_id,
            revision: 0,
            state: BrokerState::new(generation, day)?,
            healthy: true,
            _lock: lock,
        };
        broker.persist(broker.state.clone())?;
        Ok(broker)
    }

    /// Restore a complete snapshot, fence old receipts, and durably publish the
    /// new generation before returning. Missing/corrupt state never creates a
    /// new empty quota. `minimum_revision` comes from the trusted Platform's
    /// independently retained checkpoint, not a renderer/client message.
    ///
    /// # Errors
    /// Reject wrong identity, rollback revision/generation, unsafe storage,
    /// invalid or oversized snapshots, and failed persistence.
    pub fn recover(
        directory: &Path,
        platform_id: String,
        generation: u64,
        minimum_revision: u64,
    ) -> Result<Self, JournalError> {
        let lock = Self::acquire(directory)?;
        let mut raw = Vec::new();
        open_existing(&directory.join(SNAPSHOT))?
            .take(MAX_BYTES + 1)
            .read_to_end(&mut raw)?;
        if raw.len() as u64 > MAX_BYTES {
            return Err(JournalError::InvalidSnapshot);
        }
        let document: Snapshot =
            serde_json::from_slice(&raw).map_err(|_| JournalError::InvalidSnapshot)?;
        let payload = document.payload;
        if payload.schema != SCHEMA
            || payload.records.len() > MAX_RECORDS
            || payload.revision == 0
            || payload.generation == 0
            || checksum(&payload)? != document.checksum
        {
            return Err(JournalError::InvalidSnapshot);
        }
        if payload.platform_id != platform_id || !crate::valid_appearance_id(&platform_id) {
            return Err(JournalError::WrongIdentity);
        }
        if minimum_revision == 0 || payload.revision < minimum_revision {
            return Err(JournalError::StaleRevision);
        }
        if generation <= payload.generation {
            return Err(JournalError::StaleGeneration);
        }
        let records = payload
            .records
            .into_iter()
            .map(|record| {
                if record.generation > payload.generation {
                    return Err(JournalError::InvalidSnapshot);
                }
                let state = match record.state.as_str() {
                    "reserved" => SlotState::Reserved,
                    "visible" => SlotState::Visible,
                    "uncertain" => SlotState::Uncertain,
                    "released" => SlotState::Released,
                    _ => return Err(JournalError::InvalidSnapshot),
                };
                Ok(Appearance {
                    request_id: record.request_id,
                    local_day: record.local_day,
                    host_id: record.host_id,
                    session_id: record.session_id,
                    broker_generation: record.generation,
                    state,
                })
            })
            .collect::<Result<Vec<_>, JournalError>>()?;
        let state = BrokerState::restore(
            generation,
            payload.last_accepted_day,
            payload.owner_hidden,
            records,
        )?;
        let mut broker = Self {
            directory: directory.into(),
            platform_id,
            revision: payload.revision,
            state,
            healthy: true,
            _lock: lock,
        };
        // A prior interrupted write is never replayed. The committed snapshot
        // remains authoritative; the fresh fenced generation is persisted.
        let staging = broker.directory.join(STAGING);
        match fs::symlink_metadata(&staging) {
            Ok(metadata) if metadata.is_file() && !metadata.file_type().is_symlink() => {
                fs::remove_file(staging)?;
            }
            Ok(_) => return Err(JournalError::UnsafeStorage),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(error.into()),
        }
        broker.persist(broker.state.clone())?;
        Ok(broker)
    }

    fn persist(&mut self, next: BrokerState) -> Result<(), JournalError> {
        if !self.healthy {
            return Err(JournalError::Unavailable);
        }
        self.healthy = false;
        let revision = self
            .revision
            .checked_add(1)
            .ok_or(JournalError::StaleRevision)?;
        if next.reservations.len() > MAX_RECORDS {
            return Err(JournalError::InvalidSnapshot);
        }
        let payload = Payload {
            schema: SCHEMA.into(),
            platform_id: self.platform_id.clone(),
            revision,
            generation: next.generation,
            last_accepted_day: next.last_accepted_day.clone(),
            owner_hidden: next.owner_hidden,
            records: next
                .reservations
                .values()
                .map(|item| Record {
                    request_id: item.request_id.clone(),
                    local_day: item.local_day.clone(),
                    host_id: item.host_id.clone(),
                    session_id: item.session_id.clone(),
                    generation: item.broker_generation,
                    state: match item.state {
                        SlotState::Reserved => "reserved",
                        SlotState::Visible => "visible",
                        SlotState::Uncertain => "uncertain",
                        SlotState::Released => "released",
                    }
                    .into(),
                })
                .collect(),
        };
        let checksum = checksum(&payload)?;
        let bytes = serde_json::to_vec(&Snapshot { payload, checksum })
            .map_err(|_| JournalError::InvalidSnapshot)?;
        if bytes.len() as u64 > MAX_BYTES {
            return Err(JournalError::InvalidSnapshot);
        }
        let staging = self.directory.join(STAGING);
        let mut file = private_create(&staging)?;
        file.write_all(&bytes)?;
        file.sync_all()?;
        drop(file);
        fs::rename(staging, self.directory.join(SNAPSHOT))?;
        #[cfg(unix)]
        File::open(&self.directory)?.sync_all()?;
        self.state = next;
        self.revision = revision;
        self.healthy = true;
        Ok(())
    }

    /// Reserve and durably flush quota before a caller may create a window.
    /// Suppressed/duplicate requests cannot consume additional quota.
    ///
    /// # Errors
    /// Reject invalid policy requests and fail closed on storage errors.
    pub fn reserve_autonomous(
        &mut self,
        request: Appearance,
        os: OsSignals,
    ) -> Result<Admission, JournalError> {
        if !self.healthy {
            return Err(JournalError::Unavailable);
        }
        let mut next = self.state.clone();
        let admission = next.reserve_autonomous(request, os)?;
        if admission == Admission::Reserved {
            self.persist(next)?;
        }
        Ok(admission)
    }

    /// Called only by the owner-authenticated Platform settings boundary.
    ///
    /// # Errors
    /// Fail closed if the latch cannot be durably stored.
    pub fn set_manual_hide(&mut self, hidden: bool) -> Result<(), JournalError> {
        let mut next = self.state.clone();
        next.set_manual_hide(hidden);
        self.persist(next)
    }

    #[must_use]
    pub fn state(&self) -> Option<&BrokerState> {
        self.healthy.then_some(&self.state)
    }

    #[must_use]
    pub fn revision(&self) -> u64 {
        self.revision
    }
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use crate::{SlotState, Suppression, DAILY_AUTONOMOUS_LIMIT};
    use std::os::unix::fs::{DirBuilderExt, PermissionsExt};
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT: AtomicU64 = AtomicU64::new(0);
    struct Directory(PathBuf);
    impl Directory {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "aegis-broker-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            fs::DirBuilder::new().mode(0o700).create(&path).unwrap();
            Self(path)
        }
    }
    impl Drop for Directory {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }
    const IDLE: OsSignals = OsSignals {
        session_locked: false,
        do_not_disturb: false,
    };
    fn appearance(index: usize, generation: u64) -> Appearance {
        Appearance {
            request_id: format!("request:{index}"),
            local_day: "2026-11-05".into(),
            host_id: "host:synthetic".into(),
            session_id: "session:synthetic".into(),
            broker_generation: generation,
            state: SlotState::Reserved,
        }
    }
    fn initialize(directory: &Directory) -> DurableBroker {
        DurableBroker::initialize(
            &directory.0,
            "platform:synthetic".into(),
            1,
            "2026-11-05".into(),
        )
        .unwrap()
    }
    fn recover(
        directory: &Directory,
        generation: u64,
        minimum: u64,
    ) -> Result<DurableBroker, JournalError> {
        DurableBroker::recover(
            &directory.0,
            "platform:synthetic".into(),
            generation,
            minimum,
        )
    }

    #[test]
    fn restart_keeps_quota_hide_and_fences_previous_generation() {
        let directory = Directory::new();
        let mut broker = initialize(&directory);
        for i in 0..DAILY_AUTONOMOUS_LIMIT {
            assert_eq!(
                broker.reserve_autonomous(appearance(i, 1), IDLE).unwrap(),
                Admission::Reserved
            );
        }
        broker.set_manual_hide(true).unwrap();
        let revision = broker.revision();
        drop(broker);
        let mut restarted = recover(&directory, 2, revision).unwrap();
        let state = restarted.state().unwrap();
        assert!(state.owner_hidden());
        assert_eq!(state.reserved_or_uncertain_count("2026-11-05"), 5);
        assert!(state
            .reservations()
            .iter()
            .all(|record| record.state == SlotState::Uncertain));
        restarted.set_manual_hide(false).unwrap();
        assert_eq!(
            restarted
                .reserve_autonomous(appearance(8, 2), IDLE)
                .unwrap(),
            Admission::Suppressed(Suppression::DailyLimit)
        );
        assert!(matches!(
            restarted.reserve_autonomous(appearance(9, 1), IDLE),
            Err(JournalError::Policy(BrokerError::StaleGeneration))
        ));
    }

    #[test]
    fn missing_truncated_corrupt_and_oversized_snapshots_never_reset_quota() {
        let directory = Directory::new();
        assert!(matches!(
            recover(&directory, 2, 1),
            Err(JournalError::Io(_))
        ));
        let broker = initialize(&directory);
        drop(broker);
        let path = directory.0.join(SNAPSHOT);
        let original = fs::read(&path).unwrap();
        for bytes in [
            Vec::new(),
            original[..original.len() / 2].to_vec(),
            b"{}".to_vec(),
            vec![b' '; usize::try_from(MAX_BYTES).unwrap() + 1],
        ] {
            fs::write(&path, bytes).unwrap();
            assert!(matches!(
                recover(&directory, 2, 1),
                Err(JournalError::InvalidSnapshot)
            ));
        }
        let mut snapshot: Snapshot = serde_json::from_slice(&original).unwrap();
        snapshot.payload.owner_hidden = true;
        fs::write(&path, serde_json::to_vec(&snapshot).unwrap()).unwrap();
        assert!(matches!(
            recover(&directory, 2, 1),
            Err(JournalError::InvalidSnapshot)
        ));
    }

    #[test]
    fn stale_revision_generation_and_wrong_platform_are_rejected() {
        let directory = Directory::new();
        let broker = initialize(&directory);
        drop(broker);
        assert!(matches!(
            recover(&directory, 1, 1),
            Err(JournalError::StaleGeneration)
        ));
        assert!(matches!(
            recover(&directory, 2, 2),
            Err(JournalError::StaleRevision)
        ));
        assert!(matches!(
            DurableBroker::recover(&directory.0, "platform:other".into(), 2, 1),
            Err(JournalError::WrongIdentity)
        ));
        assert!(matches!(
            DurableBroker::initialize(
                &directory.0,
                "platform:synthetic".into(),
                2,
                "2026-11-05".into()
            ),
            Err(JournalError::InvalidSnapshot)
        ));
    }

    #[test]
    fn lock_prevents_second_writer_and_drop_releases_os_lock() {
        let directory = Directory::new();
        let broker = initialize(&directory);
        assert!(matches!(
            recover(&directory, 2, 1),
            Err(JournalError::Io(_))
        ));
        drop(broker);
        assert!(recover(&directory, 2, 1).is_ok());
    }

    #[test]
    fn failed_write_returns_no_admission_and_poisoned_handle_cannot_continue() {
        let directory = Directory::new();
        let mut broker = initialize(&directory);
        fs::write(directory.0.join(STAGING), b"interrupted old write").unwrap();
        assert!(matches!(
            broker.reserve_autonomous(appearance(1, 1), IDLE),
            Err(JournalError::Io(_))
        ));
        assert!(broker.state().is_none());
        assert!(matches!(
            broker.reserve_autonomous(appearance(2, 1), IDLE),
            Err(JournalError::Unavailable)
        ));
        drop(broker);
        let recovered = recover(&directory, 2, 1).unwrap();
        assert_eq!(
            recovered
                .state()
                .unwrap()
                .reserved_or_uncertain_count("2026-11-05"),
            0
        );
        assert!(!directory.0.join(STAGING).exists());
    }

    #[test]
    fn interrupted_staging_cannot_replace_committed_quota() {
        let directory = Directory::new();
        let mut broker = initialize(&directory);
        broker.reserve_autonomous(appearance(1, 1), IDLE).unwrap();
        let minimum = broker.revision();
        drop(broker);
        fs::write(directory.0.join(STAGING), b"torn write").unwrap();
        let recovered = recover(&directory, 2, minimum).unwrap();
        assert_eq!(
            recovered
                .state()
                .unwrap()
                .reserved_or_uncertain_count("2026-11-05"),
            1
        );
    }

    #[test]
    fn public_storage_and_redirected_snapshots_are_rejected() {
        let directory = Directory::new();
        fs::set_permissions(&directory.0, fs::Permissions::from_mode(0o755)).unwrap();
        assert!(matches!(
            DurableBroker::initialize(&directory.0, "platform:test".into(), 1, "2026-11-05".into()),
            Err(JournalError::UnsafeStorage)
        ));
        fs::set_permissions(&directory.0, fs::Permissions::from_mode(0o700)).unwrap();
        let broker = initialize(&directory);
        drop(broker);
        fs::rename(directory.0.join(SNAPSHOT), directory.0.join("redirected")).unwrap();
        std::os::unix::fs::symlink(directory.0.join("redirected"), directory.0.join(SNAPSHOT))
            .unwrap();
        assert!(matches!(
            recover(&directory, 2, 1),
            Err(JournalError::UnsafeStorage)
        ));
    }

    #[test]
    fn older_valid_snapshot_cannot_bypass_external_revision_checkpoint() {
        let directory = Directory::new();
        let mut broker = initialize(&directory);
        let old = fs::read(directory.0.join(SNAPSHOT)).unwrap();
        broker.reserve_autonomous(appearance(1, 1), IDLE).unwrap();
        let minimum = broker.revision();
        drop(broker);
        fs::write(directory.0.join(SNAPSHOT), old).unwrap();
        assert!(matches!(
            recover(&directory, 2, minimum),
            Err(JournalError::StaleRevision)
        ));
        assert!(matches!(
            recover(&directory, 2, 0),
            Err(JournalError::StaleRevision)
        ));
    }

    #[test]
    fn checksum_does_not_replace_semantic_generation_and_schema_validation() {
        let directory = Directory::new();
        let mut broker = initialize(&directory);
        broker.reserve_autonomous(appearance(1, 1), IDLE).unwrap();
        drop(broker);
        let path = directory.0.join(SNAPSHOT);
        let original = fs::read(&path).unwrap();
        for change in 0..3 {
            let mut snapshot: Snapshot = serde_json::from_slice(&original).unwrap();
            match change {
                0 => snapshot.payload.records[0].generation = 2,
                1 => snapshot.payload.records[0].state = "unrecognized".into(),
                _ => snapshot.payload.schema = "unknown.schema".into(),
            }
            snapshot.checksum = checksum(&snapshot.payload).unwrap();
            fs::write(&path, serde_json::to_vec(&snapshot).unwrap()).unwrap();
            assert!(matches!(
                recover(&directory, 3, 1),
                Err(JournalError::InvalidSnapshot)
            ));
        }
    }

    #[test]
    fn process_exit_fixture() {
        let Some(directory) = std::env::var_os("AEGIS_BROKER_EXIT_FIXTURE") else {
            return;
        };
        let mut broker = DurableBroker::initialize(
            Path::new(&directory),
            "platform:synthetic".into(),
            1,
            "2026-11-05".into(),
        )
        .unwrap();
        broker.reserve_autonomous(appearance(1, 1), IDLE).unwrap();
        broker.set_manual_hide(true).unwrap();
        // Deliberately bypass Rust destructors, as on abrupt broker exit.
        std::process::exit(23);
    }

    #[test]
    fn abrupt_process_exit_releases_lock_and_preserves_flushed_admission() {
        let directory = Directory::new();
        let status = std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "journal::tests::process_exit_fixture"])
            .env("AEGIS_BROKER_EXIT_FIXTURE", &directory.0)
            .status()
            .unwrap();
        assert_eq!(status.code(), Some(23));
        let broker = recover(&directory, 2, 3).unwrap();
        assert_eq!(
            broker
                .state()
                .unwrap()
                .reserved_or_uncertain_count("2026-11-05"),
            1
        );
        assert!(broker.state().unwrap().owner_hidden());
    }
}

#[cfg(all(test, not(unix)))]
mod unsupported_tests {
    use super::*;
    #[test]
    fn unsupported_filesystem_durability_fails_closed() {
        assert!(matches!(
            DurableBroker::initialize(
                Path::new("unused"),
                "platform:test".into(),
                1,
                "2026-11-05".into()
            ),
            Err(JournalError::UnsupportedPlatform)
        ));
    }
}
