//! Authority-free Artifact Library display snapshots.
//! Read ONLY from a separately authenticated Team A Platform service adapter.
//! This code NEVER verifies a publisher signature, authenticates a socket,
//! accepts owner permission, performs transfer, or changes B1 installation.
//! No live library service is wired; the only supplied reader is offline.

use crate::control_center::{LinkState, SafeState};
use crate::control_center_session::ReadFailure;
use std::collections::HashSet;
use std::time::{Duration, Instant};

pub const LIBRARY_DISPLAY_MAX_AGE: Duration = Duration::from_secs(5);

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CatalogProvenance {
    pub signer_key_id: String,
    pub index_sha256: String,
    pub signed_index_revision: u64,
    pub source_identity: String,
}

/// A receipt reference from the *already-verified* service. This object
/// carries no signature bytes or authority; it must not be user-created
/// and then interpreted as proof of installation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DisplayReceipt {
    pub reference: String,
    /// Issuer identified by A/B/D evidence, not a UI approval.
    pub issuer_identity: String,
    pub target_platform_id: String,
    pub content_sha256: String,
    /// CURRENT service verification context; original signed receipt
    /// generation, revision and creation time remain B/D-owned history.
    pub evidence_generation: u64,
    pub evidence_revision: u64,
    pub evidence_observed_unix_ms: u64,
}

/// Each stage needs its own service-verified receipt; an earlier stage
/// never implies a later one. None means NOT OBSERVED, not false or zero.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ArtifactStages {
    pub content_sha256: String,
    pub downloaded: Option<DisplayReceipt>,
    pub verified: Option<DisplayReceipt>,
    pub staged: Option<DisplayReceipt>,
    pub installed: Option<DisplayReceipt>,
    pub active: Option<DisplayReceipt>,
    pub rollback_pinned: Option<DisplayReceipt>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransferProgress {
    pub job_id: String,
    pub source_identity: String,
    pub received_bytes: u64,
    pub verified_bytes: u64,
    pub total_bytes: u64,
}

/// Source-verified data supplied by Team A's separately enrolled client.
/// This is a NORMALIZED UI shape, NOT D028's application/wire schema.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LibraryObservation {
    pub platform_id: String,
    pub generation: u64,
    pub state_revision: u64,
    pub sequence: u64,
    /// External service observation time, never a UI clock approval.
    pub observed_unix_ms: u64,
    pub safe: SafeState,
    pub catalog: Option<CatalogProvenance>,
    pub artifact: Option<ArtifactStages>,
    pub transfer: Option<TransferProgress>,
}

/// This is an adapter seam, not a transport implementation or trust proof.
/// Only an A-approved enrolled client may ever implement a nonoffline reader.
pub trait LibraryObservationSource {
    /// Read a verified, correlated, fresh Platform observation.
    ///
    /// # Errors
    /// Returns a non-authorizing failure on unavailable or rejected service.
    fn next(&mut self) -> Result<LibraryObservation, ReadFailure>;
}

#[derive(Default)]
pub struct OfflineLibraryReader;

impl LibraryObservationSource for OfflineLibraryReader {
    fn next(&mut self) -> Result<LibraryObservation, ReadFailure> {
        Err(ReadFailure::Offline)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LibraryDisplayError {
    InvalidIdentity,
    PlatformChanged,
    GenerationRegressed,
    RevisionRegressed,
    TimeRegressed,
    SequenceReplayed,
    InvalidProvenance,
    InvalidStageReceipt,
    InvalidTransfer,
    UnexpectedSafeState,
}

#[derive(Debug)]
pub struct LibraryDisplaySession {
    pinned_platform_id: Option<String>,
    generation: u64,
    revision: u64,
    sequence: u64,
    observed_unix_ms: u64,
    last_observed: Option<Instant>,
    link: LinkState,
    last_snapshot: Option<LibraryObservation>,
}

impl Default for LibraryDisplaySession {
    fn default() -> Self {
        Self {
            pinned_platform_id: None,
            generation: 0,
            revision: 0,
            sequence: 0,
            observed_unix_ms: 0,
            last_observed: None,
            link: LinkState::Offline,
            last_snapshot: None,
        }
    }
}

impl LibraryDisplaySession {
    #[must_use]
    pub fn link(&self) -> LinkState {
        self.link
    }

    /// The previous snapshot is retained for internal reconciliation only.
    /// It is never current proof when the read session is unavailable.
    #[must_use]
    pub fn current(&self) -> Option<&LibraryObservation> {
        if self.link == LinkState::Observed {
            self.last_snapshot.as_ref()
        } else {
            None
        }
    }

    #[must_use]
    pub fn status_label(&self) -> &'static str {
        match self.link {
            LinkState::Observed if self.current().is_some() => "OBSERVED_READ_ONLY",
            LinkState::Offline => "OFFLINE",
            LinkState::Connecting => "CONNECTING",
            LinkState::Stale => "STALE",
            LinkState::Restarting => "RESTARTING",
            LinkState::Revoked => "REVOKED",
            LinkState::Stopped => "STOP_ACTIVE",
            LinkState::AccessDenied => "DENIED",
            LinkState::UnknownGeneration => "UNKNOWN_GENERATION",
            LinkState::Observed | LinkState::Unverified => "UNVERIFIED",
        }
    }

    #[must_use]
    pub fn stage_label(&self, stage: &str) -> &'static str {
        let Some(current) = self.current() else {
            return "NOT_CURRENTLY_VERIFIED";
        };
        let Some(artifact) = &current.artifact else {
            return "NOT_OBSERVED";
        };
        let receipt = match stage {
            "downloaded" => artifact.downloaded.as_ref(),
            "verified" => artifact.verified.as_ref(),
            "staged" => artifact.staged.as_ref(),
            "installed" => artifact.installed.as_ref(),
            "active" => artifact.active.as_ref(),
            "rollback_pinned" => artifact.rollback_pinned.as_ref(),
            _ => return "UNKNOWN_STAGE",
        };
        if receipt.is_some() {
            "RECEIPT_REFERENCE_NOT_AUTHORITY"
        } else {
            "NOT_OBSERVED"
        }
    }

    #[must_use]
    pub fn progress_label(&self) -> &'static str {
        let Some(current) = self.current() else {
            return "NOT_CURRENTLY_VERIFIED";
        };
        match current.transfer.as_ref() {
            Some(_) => "BYTES_OBSERVED_NOT_INSTALL_OR_SIGNATURE_PROOF",
            None => "NOT_OBSERVED",
        }
    }

    /// Observe from an independently OS-authenticated, correlated A client.
    /// This function itself NEVER verifies sender, receipts or permission.
    ///
    /// # Errors
    /// Rejects stale/cross-host snapshots, contradictory progress or claimed
    /// lifecycle receipts with mismatched target or content digest.
    pub fn refresh(
        &mut self,
        source: &mut impl LibraryObservationSource,
        now: Instant,
    ) -> Result<(), LibraryDisplayError> {
        match source.next() {
            Ok(observation) => self.accept(observation, now),
            Err(reason) => {
                self.fail(reason);
                Ok(())
            }
        }
    }

    pub fn fail(&mut self, reason: ReadFailure) {
        self.link = match reason {
            ReadFailure::Offline => LinkState::Offline,
            ReadFailure::Connecting => LinkState::Connecting,
            ReadFailure::Unverified => LinkState::Unverified,
            ReadFailure::Stale => LinkState::Stale,
            ReadFailure::Restarting => LinkState::Restarting,
            ReadFailure::Revoked => LinkState::Revoked,
            ReadFailure::Stopped => LinkState::Stopped,
            ReadFailure::Denied => LinkState::AccessDenied,
            ReadFailure::UnknownGeneration => LinkState::UnknownGeneration,
        };
        self.last_observed = None;
    }

    pub fn expire_at(&mut self, now: Instant) {
        if self.link == LinkState::Observed
            && self.last_observed.is_none_or(|received| {
                now.checked_duration_since(received)
                    .is_none_or(|elapsed| elapsed > LIBRARY_DISPLAY_MAX_AGE)
            })
        {
            self.fail(ReadFailure::Stale);
        }
    }

    fn accept(
        &mut self,
        incoming: LibraryObservation,
        now: Instant,
    ) -> Result<(), LibraryDisplayError> {
        let identity = valid_id(&incoming.platform_id);
        if !identity
            || incoming.generation == 0
            || incoming.sequence == 0
            || incoming.observed_unix_ms == 0
        {
            self.fail(ReadFailure::UnknownGeneration);
            return Err(LibraryDisplayError::InvalidIdentity);
        }
        if self
            .pinned_platform_id
            .as_ref()
            .is_some_and(|old| old != &incoming.platform_id)
        {
            self.fail(ReadFailure::Unverified);
            return Err(LibraryDisplayError::PlatformChanged);
        }
        if incoming.generation < self.generation {
            self.fail(ReadFailure::Stale);
            return Err(LibraryDisplayError::GenerationRegressed);
        }
        if incoming.state_revision < self.revision {
            self.fail(ReadFailure::Stale);
            return Err(LibraryDisplayError::RevisionRegressed);
        }
        if incoming.observed_unix_ms < self.observed_unix_ms {
            self.fail(ReadFailure::Stale);
            return Err(LibraryDisplayError::TimeRegressed);
        }
        if incoming.generation == self.generation && incoming.sequence <= self.sequence {
            self.fail(ReadFailure::Stale);
            return Err(LibraryDisplayError::SequenceReplayed);
        }
        if incoming.safe != SafeState::Clear {
            self.fail(if incoming.safe == SafeState::StopActive {
                ReadFailure::Stopped
            } else {
                ReadFailure::Unverified
            });
            return Err(LibraryDisplayError::UnexpectedSafeState);
        }
        if incoming.catalog.as_ref().is_some_and(|catalog| {
            !valid_id(&catalog.signer_key_id)
                || !valid_id(&catalog.source_identity)
                || !valid_digest(&catalog.index_sha256)
                || catalog.signed_index_revision == 0
        }) {
            self.fail(ReadFailure::Unverified);
            return Err(LibraryDisplayError::InvalidProvenance);
        }
        if incoming.artifact.as_ref().is_some_and(|artifact| {
            !valid_digest(&artifact.content_sha256)
                || !stage_receipts_match(artifact, &incoming)
                || (artifact.active.is_some() && artifact.installed.is_none())
        }) {
            self.fail(ReadFailure::Unverified);
            return Err(LibraryDisplayError::InvalidStageReceipt);
        }
        if incoming.transfer.as_ref().is_some_and(|transfer| {
            !valid_id(&transfer.job_id)
                || !valid_id(&transfer.source_identity)
                || transfer.verified_bytes > transfer.received_bytes
                || transfer.received_bytes > transfer.total_bytes
        }) {
            self.fail(ReadFailure::Unverified);
            return Err(LibraryDisplayError::InvalidTransfer);
        }
        self.generation = incoming.generation;
        self.revision = incoming.state_revision;
        self.sequence = incoming.sequence;
        self.observed_unix_ms = incoming.observed_unix_ms;
        self.pinned_platform_id = Some(incoming.platform_id.clone());
        self.last_observed = Some(now);
        self.last_snapshot = Some(incoming);
        self.link = LinkState::Observed;
        Ok(())
    }
}

fn valid_id(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 160
        && id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b':' | b'_' | b'-' | b'.'))
}

fn valid_digest(digest: &str) -> bool {
    digest.len() == 64
        && digest
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
}

fn stage_receipts_match(artifact: &ArtifactStages, observation: &LibraryObservation) -> bool {
    let mut seen = HashSet::new();
    [
        &artifact.downloaded,
        &artifact.verified,
        &artifact.staged,
        &artifact.installed,
        &artifact.active,
        &artifact.rollback_pinned,
    ]
    .into_iter()
    .flatten()
    .all(|receipt| {
        valid_id(&receipt.reference)
            && valid_id(&receipt.issuer_identity)
            && seen.insert(receipt.reference.as_str())
            && receipt.target_platform_id == observation.platform_id
            && receipt.content_sha256 == artifact.content_sha256
            && receipt.evidence_generation == observation.generation
            && receipt.evidence_revision == observation.state_revision
            && receipt.evidence_observed_unix_ms == observation.observed_unix_ms
    })
}

#[cfg(test)]
mod tests {
    use super::{
        ArtifactStages, CatalogProvenance, DisplayReceipt, LibraryDisplayError,
        LibraryDisplaySession, LibraryObservation, LibraryObservationSource, OfflineLibraryReader,
        TransferProgress, LIBRARY_DISPLAY_MAX_AGE,
    };
    use crate::control_center::{LinkState, SafeState};
    use crate::control_center_session::ReadFailure;
    use std::time::{Duration, Instant};

    struct Stub(Result<LibraryObservation, ReadFailure>);

    impl LibraryObservationSource for Stub {
        fn next(&mut self) -> Result<LibraryObservation, ReadFailure> {
            self.0.clone()
        }
    }

    fn receipt(stage: &str, artifact: &str, generation: u64, revision: u64) -> DisplayReceipt {
        DisplayReceipt {
            reference: format!("receipt:{stage}:1"),
            issuer_identity: "issuer:b1".into(),
            target_platform_id: "platform:alpha".into(),
            content_sha256: artifact.into(),
            evidence_generation: generation,
            evidence_revision: revision,
            evidence_observed_unix_ms: 1_000_000,
        }
    }

    fn snapshot(generation: u64, revision: u64, sequence: u64) -> LibraryObservation {
        LibraryObservation {
            platform_id: "platform:alpha".into(),
            generation,
            state_revision: revision,
            sequence,
            observed_unix_ms: 1_000_000,
            safe: SafeState::Clear,
            catalog: Some(CatalogProvenance {
                signer_key_id: "publisher:approved".into(),
                index_sha256: "a".repeat(64),
                signed_index_revision: 7,
                source_identity: "source:local".into(),
            }),
            artifact: Some(ArtifactStages {
                content_sha256: "b".repeat(64),
                downloaded: Some(receipt("downloaded", &"b".repeat(64), generation, revision)),
                verified: None,
                staged: None,
                installed: None,
                active: None,
                rollback_pinned: None,
            }),
            transfer: Some(TransferProgress {
                job_id: "job:transfer:1".into(),
                source_identity: "source:local".into(),
                received_bytes: 4096,
                verified_bytes: 0,
                total_bytes: 4096,
            }),
        }
    }

    #[test]
    fn no_service_no_current_catalog_or_lifecycle_claims() {
        let mut ui = LibraryDisplaySession::default();
        ui.refresh(&mut OfflineLibraryReader, Instant::now())
            .unwrap();
        assert_eq!(ui.status_label(), "OFFLINE");
        assert_eq!(ui.stage_label("installed"), "NOT_CURRENTLY_VERIFIED");
        assert!(ui.current().is_none());
    }

    #[test]
    fn received_bytes_equal_total_does_not_prove_verification_install_or_activation() {
        let mut ui = LibraryDisplaySession::default();
        ui.refresh(&mut Stub(Ok(snapshot(3, 7, 1))), Instant::now())
            .unwrap();
        assert_eq!(
            ui.stage_label("downloaded"),
            "RECEIPT_REFERENCE_NOT_AUTHORITY"
        );
        assert_eq!(ui.stage_label("verified"), "NOT_OBSERVED");
        assert_eq!(ui.stage_label("installed"), "NOT_OBSERVED");
        assert_eq!(ui.stage_label("active"), "NOT_OBSERVED");
        assert_eq!(
            ui.progress_label(),
            "BYTES_OBSERVED_NOT_INSTALL_OR_SIGNATURE_PROOF"
        );
    }

    #[test]
    fn receipts_are_distinct_and_host_scoped() {
        let t = Instant::now();
        let mut ui = LibraryDisplaySession::default();
        let mut valid = snapshot(3, 7, 1);
        let artifact = valid.artifact.as_mut().unwrap();
        artifact.verified = Some(receipt("verified", &"b".repeat(64), 3, 7));
        artifact.staged = Some(receipt("staged", &"b".repeat(64), 3, 7));
        artifact.installed = Some(receipt("installed", &"b".repeat(64), 3, 7));
        artifact.active = Some(receipt("active", &"b".repeat(64), 3, 7));
        ui.refresh(&mut Stub(Ok(valid)), t).unwrap();
        assert_eq!(
            ui.stage_label("verified"),
            "RECEIPT_REFERENCE_NOT_AUTHORITY"
        );
        assert_eq!(ui.stage_label("active"), "RECEIPT_REFERENCE_NOT_AUTHORITY");
        let mut forged = snapshot(3, 8, 2);
        let artifact = forged.artifact.as_mut().unwrap();
        artifact.installed = Some(DisplayReceipt {
            target_platform_id: "platform:other".into(),
            ..receipt("installed", &"b".repeat(64), 3, 8)
        });
        assert_eq!(
            ui.refresh(&mut Stub(Ok(forged)), t),
            Err(LibraryDisplayError::InvalidStageReceipt)
        );
        assert_eq!(ui.status_label(), "UNVERIFIED");
        assert_eq!(ui.stage_label("installed"), "NOT_CURRENTLY_VERIFIED");
        let mut duplicate = snapshot(3, 9, 3);
        duplicate.artifact.as_mut().unwrap().verified =
            Some(receipt("downloaded", &"b".repeat(64), 3, 9));
        assert_eq!(
            ui.refresh(&mut Stub(Ok(duplicate)), t),
            Err(LibraryDisplayError::InvalidStageReceipt)
        );
    }

    #[test]
    fn forged_receipt_issuer_target_digest_generation_revision_and_time_are_denied() {
        let now = Instant::now();
        for tamper in 0..6 {
            let mut incoming = snapshot(3, 7, 1);
            let receipt = incoming
                .artifact
                .as_mut()
                .unwrap()
                .downloaded
                .as_mut()
                .unwrap();
            match tamper {
                0 => receipt.issuer_identity = String::new(),
                1 => receipt.target_platform_id = "platform:attacker".into(),
                2 => receipt.content_sha256 = "c".repeat(64),
                3 => receipt.evidence_generation = 4,
                4 => receipt.evidence_revision = 8,
                _ => receipt.evidence_observed_unix_ms = 999_999,
            }
            let mut ui = LibraryDisplaySession::default();
            assert_eq!(
                ui.refresh(&mut Stub(Ok(incoming)), now),
                Err(LibraryDisplayError::InvalidStageReceipt),
                "forged receipt vector {tamper}"
            );
            assert_eq!(ui.status_label(), "UNVERIFIED");
            assert!(ui.current().is_none());
        }
    }

    #[test]
    fn observation_time_cannot_regress_on_fresh_sequence() {
        let now = Instant::now();
        let mut ui = LibraryDisplaySession::default();
        ui.refresh(&mut Stub(Ok(snapshot(3, 7, 1))), now).unwrap();
        let mut backward = snapshot(3, 8, 2);
        backward.observed_unix_ms = 999_999;
        assert_eq!(
            ui.refresh(&mut Stub(Ok(backward)), now),
            Err(LibraryDisplayError::TimeRegressed)
        );
        assert_eq!(ui.status_label(), "STALE");
        assert!(ui.current().is_none());
    }

    #[test]
    fn revision_and_generation_replay_fail_closed_across_reconnect() {
        let t = Instant::now();
        let mut ui = LibraryDisplaySession::default();
        ui.refresh(&mut Stub(Ok(snapshot(4, 8, 5))), t).unwrap();
        ui.fail(ReadFailure::Restarting);
        ui.refresh(&mut Stub(Ok(snapshot(5, 9, 1))), t).unwrap();
        assert_eq!(
            ui.refresh(&mut Stub(Ok(snapshot(4, 10, 6))), t),
            Err(LibraryDisplayError::GenerationRegressed)
        );
        assert_eq!(
            ui.refresh(&mut Stub(Ok(snapshot(5, 8, 2))), t),
            Err(LibraryDisplayError::RevisionRegressed)
        );
        assert_eq!(
            ui.refresh(&mut Stub(Ok(snapshot(5, 9, 1))), t),
            Err(LibraryDisplayError::SequenceReplayed)
        );
    }

    #[test]
    fn stop_revoke_denied_and_stale_erase_current_trust_not_history() {
        let t = Instant::now();
        let mut ui = LibraryDisplaySession::default();
        ui.refresh(&mut Stub(Ok(snapshot(2, 3, 1))), t).unwrap();
        for (failure, label) in [
            (ReadFailure::Stopped, "STOP_ACTIVE"),
            (ReadFailure::Revoked, "REVOKED"),
            (ReadFailure::Denied, "DENIED"),
            (ReadFailure::Stale, "STALE"),
        ] {
            ui.fail(failure);
            assert_eq!(ui.status_label(), label);
            assert!(ui.current().is_none());
            assert_eq!(ui.stage_label("verified"), "NOT_CURRENTLY_VERIFIED");
        }
        ui.refresh(&mut Stub(Ok(snapshot(2, 3, 2))), t).unwrap();
        ui.expire_at(t + LIBRARY_DISPLAY_MAX_AGE + Duration::from_millis(1));
        assert_eq!(ui.link(), LinkState::Stale);
        assert!(ui.current().is_none());
    }

    #[test]
    fn library_stop_cannot_be_a_successful_observation() {
        let t = Instant::now();
        let mut ui = LibraryDisplaySession::default();
        let mut stopped = snapshot(2, 3, 1);
        stopped.safe = SafeState::StopActive;
        assert_eq!(
            ui.refresh(&mut Stub(Ok(stopped)), t),
            Err(LibraryDisplayError::UnexpectedSafeState)
        );
        assert_eq!(ui.status_label(), "STOP_ACTIVE");
        assert!(ui.current().is_none());
    }

    #[test]
    fn invalid_catalog_transfer_and_active_without_install_are_rejected() {
        let t = Instant::now();
        let mut ui = LibraryDisplaySession::default();
        let mut wrong_source = snapshot(2, 3, 1);
        wrong_source.catalog.as_mut().unwrap().signer_key_id = "unsafe/path".into();
        assert_eq!(
            ui.refresh(&mut Stub(Ok(wrong_source)), t),
            Err(LibraryDisplayError::InvalidProvenance)
        );
        let mut transfer = snapshot(2, 3, 1);
        transfer.transfer.as_mut().unwrap().verified_bytes = 4097;
        assert_eq!(
            ui.refresh(&mut Stub(Ok(transfer)), t),
            Err(LibraryDisplayError::InvalidTransfer)
        );
        let mut invalid_stage = snapshot(2, 3, 1);
        invalid_stage.artifact.as_mut().unwrap().active =
            Some(receipt("active", &"b".repeat(64), 2, 3));
        assert_eq!(
            ui.refresh(&mut Stub(Ok(invalid_stage)), t),
            Err(LibraryDisplayError::InvalidStageReceipt)
        );
    }
}
