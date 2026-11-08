//! Fail-closed status, reconnect and settings-edit display session.
//! Not a wire schema, transport, source verifier, permission service or grant.
//! A future Team A reviewed OS-authenticated reader must validate the source,
//! correlation, freshness and receipt before producing any trusted snapshot.

use crate::control_center::{
    ControlCenterView, InstallationState, LinkState, PermissionState, SafeState,
};
use std::time::{Duration, Instant};

pub const MAX_DISPLAY_AGE: Duration = Duration::from_secs(15);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReadFailure {
    Offline,
    Connecting,
    Unverified,
    Stale,
    Restarting,
    Revoked,
    Stopped,
    Denied,
    UnknownGeneration,
}

impl ReadFailure {
    fn link(self) -> LinkState {
        match self {
            Self::Offline => LinkState::Offline,
            Self::Connecting => LinkState::Connecting,
            Self::Unverified => LinkState::Unverified,
            Self::Stale => LinkState::Stale,
            Self::Restarting => LinkState::Restarting,
            Self::Revoked => LinkState::Revoked,
            Self::Stopped => LinkState::Stopped,
            Self::Denied => LinkState::AccessDenied,
            Self::UnknownGeneration => LinkState::UnknownGeneration,
        }
    }
}

/// Already validated by the separate service client, NEVER raw JSON.
/// A field declaring a receipt verified cannot itself verify a signature.
#[derive(Debug, Clone)]
pub struct DisplaySnapshot {
    pub platform_id: String,
    pub generation: u64,
    pub sequence: u64,
    pub safe: SafeState,
    pub permission: PermissionState,
    pub installation: InstallationState,
    pub saved_revision: Option<u64>,
    pub applied_revision: Option<u64>,
    pub removal_receipt_verified: bool,
}

/// Map canonical management v1 denial codes after independent authenticated
/// transport, response correlation, generation and freshness validation.
/// This method does not parse JSON or confer owner/service permission.
#[must_use]
pub fn from_verified_denial(code: &str) -> Option<ReadFailure> {
    match code {
        "NOT_PERMITTED" => Some(ReadFailure::Denied),
        "REVOKED" => Some(ReadFailure::Revoked),
        "STOPPED" => Some(ReadFailure::Stopped),
        "STALE_GENERATION" => Some(ReadFailure::UnknownGeneration),
        "EXPIRED" => Some(ReadFailure::Stale),
        "UNAVAILABLE" => Some(ReadFailure::Offline),
        _ => None,
    }
}

/// Injection seam for a future *approved* authenticated Platform client.
/// This trait authenticates NOTHING, and has no mutation or approval methods.
pub trait DisplayReadSource {
    /// Read a service-verified view; never a raw, self-authenticating payload.
    ///
    /// # Errors
    /// Unavailable, revoked, stale, or unverified reads fail closed.
    fn next(&mut self) -> Result<DisplaySnapshot, ReadFailure>;
}

/// The sole currently wired production reader: no unauthenticated probing.
#[derive(Debug, Default)]
pub struct OfflineReader;

impl DisplayReadSource for OfflineReader {
    fn next(&mut self) -> Result<DisplaySnapshot, ReadFailure> {
        Err(ReadFailure::Offline)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DisplayError {
    InvalidIdentity,
    PlatformChanged,
    GenerationRegressed,
    SequenceReplayed,
    SettingsRegressed,
    InvalidRevisions,
    InvalidReceipt,
}

#[derive(Debug, Default)]
pub struct DisplaySession {
    platform_id: Option<String>,
    generation: u64,
    sequence: u64,
    last_observed: Option<Instant>,
    view: ControlCenterView,
}

impl DisplaySession {
    #[must_use]
    pub fn view(&self) -> &ControlCenterView {
        &self.view
    }

    #[must_use]
    pub fn platform_id(&self) -> Option<&str> {
        self.platform_id.as_deref()
    }

    /// Caller must use ONLY a Team A approved authenticated reader. This
    /// projection cannot authenticate responses or authorize operations.
    ///
    /// # Errors
    /// Rejects invalid identity, generation, sequence, revisions or receipt
    /// presentation; no error can create an approval or perform a write.
    pub fn refresh(
        &mut self,
        source: &mut impl DisplayReadSource,
        at: Instant,
    ) -> Result<(), DisplayError> {
        match source.next() {
            Ok(snapshot) => self.accept(snapshot, at),
            Err(failure) => {
                self.fail(failure);
                Ok(())
            }
        }
    }

    pub fn fail(&mut self, failure: ReadFailure) {
        self.view.link = failure.link();
        self.view.permission = PermissionState::Unknown;
        // STOPPED is a separately OS-authenticated, correlated Team A denial.
        // A display reason is not owner approval or a lifecycle receipt.
        self.view.safe = if failure == ReadFailure::Stopped {
            SafeState::StopActive
        } else {
            SafeState::Unknown
        };
        self.view.removal_receipt_verified = false;
        self.last_observed = None;
    }

    pub fn expire_at(&mut self, at: Instant) {
        if self.view.link == LinkState::Observed
            && self.last_observed.is_none_or(|received| {
                at.checked_duration_since(received)
                    .is_none_or(|age| age > MAX_DISPLAY_AGE)
            })
        {
            self.fail(ReadFailure::Stale);
        }
    }

    fn accept(&mut self, incoming: DisplaySnapshot, at: Instant) -> Result<(), DisplayError> {
        if !valid_id(&incoming.platform_id) || incoming.generation == 0 || incoming.sequence == 0 {
            self.fail(ReadFailure::UnknownGeneration);
            return Err(DisplayError::InvalidIdentity);
        }
        if self
            .platform_id
            .as_ref()
            .is_some_and(|old| old != &incoming.platform_id)
        {
            self.fail(ReadFailure::Unverified);
            return Err(DisplayError::PlatformChanged);
        }
        if incoming.generation < self.generation {
            self.fail(ReadFailure::Stale);
            return Err(DisplayError::GenerationRegressed);
        }
        if incoming.generation == self.generation && incoming.sequence <= self.sequence {
            self.fail(ReadFailure::Stale);
            return Err(DisplayError::SequenceReplayed);
        }
        if !valid_revisions(incoming.saved_revision, incoming.applied_revision) {
            self.fail(ReadFailure::Unverified);
            return Err(DisplayError::InvalidRevisions);
        }
        if self
            .view
            .settings_revision
            .zip(incoming.saved_revision)
            .is_some_and(|(old, new)| new < old)
        {
            self.fail(ReadFailure::Stale);
            return Err(DisplayError::SettingsRegressed);
        }
        if incoming.removal_receipt_verified && incoming.installation != InstallationState::Removed
        {
            self.fail(ReadFailure::Unverified);
            return Err(DisplayError::InvalidReceipt);
        }
        self.platform_id = Some(incoming.platform_id);
        self.generation = incoming.generation;
        self.sequence = incoming.sequence;
        self.last_observed = Some(at);
        self.view = ControlCenterView {
            link: LinkState::Observed,
            safe: incoming.safe,
            permission: incoming.permission,
            installation: incoming.installation,
            platform_generation: Some(incoming.generation),
            settings_revision: incoming.saved_revision,
            effective_settings_revision: incoming.applied_revision,
            removal_receipt_verified: incoming.removal_receipt_verified,
        };
        Ok(())
    }
}

fn valid_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 160
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.' | b':'))
}

fn valid_revisions(saved: Option<u64>, applied: Option<u64>) -> bool {
    match (saved, applied) {
        (None, None) => true,
        (Some(saved), Some(applied)) => applied <= saved,
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::{
        from_verified_denial, DisplayError, DisplayReadSource, DisplaySession, DisplaySnapshot,
        OfflineReader, ReadFailure, MAX_DISPLAY_AGE,
    };
    use crate::control_center::{
        ActionHint, InstallationState, LinkState, PermissionState, ProposedAction, SafeState,
    };
    use std::time::{Duration, Instant};

    struct Fixed(Result<DisplaySnapshot, ReadFailure>);

    impl DisplayReadSource for Fixed {
        fn next(&mut self) -> Result<DisplaySnapshot, ReadFailure> {
            self.0.clone()
        }
    }

    fn observed(generation: u64, sequence: u64) -> DisplaySnapshot {
        DisplaySnapshot {
            platform_id: "platform:local".into(),
            generation,
            sequence,
            safe: SafeState::Clear,
            permission: PermissionState::MayRequest,
            installation: InstallationState::Installed,
            saved_revision: Some(5),
            applied_revision: Some(4),
            removal_receipt_verified: false,
        }
    }

    #[test]
    fn canonical_v1_denial_codes_map_only_after_trust_check() {
        for (wire, state) in [
            ("NOT_PERMITTED", ReadFailure::Denied),
            ("REVOKED", ReadFailure::Revoked),
            ("STOPPED", ReadFailure::Stopped),
            ("STALE_GENERATION", ReadFailure::UnknownGeneration),
            ("EXPIRED", ReadFailure::Stale),
            ("UNAVAILABLE", ReadFailure::Offline),
        ] {
            assert_eq!(from_verified_denial(wire), Some(state));
        }
        for invalid in ["", "STOP", "stopped", "OWNER_APPROVED", "HEALTHY"] {
            assert_eq!(from_verified_denial(invalid), None);
        }
    }

    #[test]
    fn authenticated_stopped_denial_is_visible_and_blocks_actions() {
        let mut session = DisplaySession::default();
        session.fail(ReadFailure::Stopped);
        assert_eq!(session.view().service_label(), "STOP_ACTIVE");
        assert_eq!(session.view().safe_label(), "STOP_ACTIVE");
        assert_eq!(session.view().installation_label(), "NOT_CURRENTLY_VERIFIED");
        assert_eq!(session.view().permission_label(), "UNKNOWN");
        assert_eq!(
            session.view().action_hint(ProposedAction::InstallModule),
            ActionHint::Blocked("SAFE_STOP_ACTIVE")
        );
    }

    #[test]
    fn offline_reader_cannot_claim_health_or_execute() {
        let mut session = DisplaySession::default();
        session.refresh(&mut OfflineReader, Instant::now()).unwrap();
        assert_eq!(session.view().link, LinkState::Offline);
        assert_eq!(
            session.view().action_hint(ProposedAction::RestartCore),
            ActionHint::Blocked("PLATFORM_OFFLINE")
        );
    }

    #[test]
    fn reconnect_keeps_installed_lifecycle_but_invalidates_editor() {
        let t = Instant::now();
        let mut session = DisplaySession::default();
        session.refresh(&mut Fixed(Ok(observed(1, 1))), t).unwrap();
        let old_editor = session.view().clone();
        session.fail(ReadFailure::Offline);
        assert_eq!(session.view().installation, InstallationState::Installed);
        assert_eq!(
            session.view().installation_label(),
            "NOT_CURRENTLY_VERIFIED"
        );
        assert!(session.view().editor_needs_review(&old_editor));
        session
            .refresh(&mut Fixed(Ok(observed(1, 2))), t + Duration::from_secs(1))
            .unwrap();
        assert_eq!(session.view().installation_label(), "INSTALLED");
        assert_eq!(session.view().settings_label(), "PENDING_APPLY");
    }

    #[test]
    fn generation_and_replay_fencing_survive_restart() {
        let t = Instant::now();
        let mut session = DisplaySession::default();
        session.refresh(&mut Fixed(Ok(observed(2, 44))), t).unwrap();
        let editor = session.view().clone();
        session.fail(ReadFailure::Restarting);
        session.refresh(&mut Fixed(Ok(observed(3, 1))), t).unwrap();
        assert!(session.view().editor_needs_review(&editor));
        assert_eq!(
            session.refresh(&mut Fixed(Ok(observed(2, 45))), t),
            Err(DisplayError::GenerationRegressed)
        );
        assert_eq!(
            session.refresh(&mut Fixed(Ok(observed(3, 1))), t),
            Err(DisplayError::SequenceReplayed)
        );
        assert_eq!(session.view().link, LinkState::Stale);
    }

    #[test]
    fn wrong_platform_and_settings_regression_fail_closed() {
        let t = Instant::now();
        let mut session = DisplaySession::default();
        session.refresh(&mut Fixed(Ok(observed(1, 1))), t).unwrap();
        let mut regressed = observed(1, 2);
        regressed.saved_revision = Some(4);
        assert_eq!(
            session.refresh(&mut Fixed(Ok(regressed)), t),
            Err(DisplayError::SettingsRegressed)
        );
        let mut other = observed(2, 1);
        other.platform_id = "platform:foreign".into();
        assert_eq!(
            session.refresh(&mut Fixed(Ok(other)), t),
            Err(DisplayError::PlatformChanged)
        );
        assert_eq!(session.view().source_label(), "UNVERIFIED");
    }

    #[test]
    fn rejected_generation_revisions_and_removal_claim() {
        let t = Instant::now();
        let mut session = DisplaySession::default();
        assert_eq!(
            session.refresh(&mut Fixed(Ok(observed(0, 1))), t),
            Err(DisplayError::InvalidIdentity)
        );
        assert_eq!(session.view().link, LinkState::UnknownGeneration);
        let mut invalid = observed(1, 1);
        invalid.applied_revision = Some(7);
        assert_eq!(
            session.refresh(&mut Fixed(Ok(invalid)), t),
            Err(DisplayError::InvalidRevisions)
        );
        let mut forged = observed(1, 1);
        forged.removal_receipt_verified = true;
        assert_eq!(
            session.refresh(&mut Fixed(Ok(forged)), t),
            Err(DisplayError::InvalidReceipt)
        );
    }

    #[test]
    fn revoked_denied_stop_stale_and_clock_rollback_block_operations() {
        let t = Instant::now();
        let mut session = DisplaySession::default();
        let mut stopped = observed(1, 1);
        stopped.safe = SafeState::StopActive;
        session.refresh(&mut Fixed(Ok(stopped)), t).unwrap();
        assert_eq!(
            session.view().action_hint(ProposedAction::SaveSettings),
            ActionHint::Blocked("SAFE_STOP_ACTIVE")
        );
        for state in [
            ReadFailure::Revoked,
            ReadFailure::Stopped,
            ReadFailure::Denied,
            ReadFailure::Stale,
            ReadFailure::UnknownGeneration,
        ] {
            session.fail(state);
            assert!(matches!(
                session.view().action_hint(ProposedAction::UninstallModule),
                ActionHint::Blocked(_)
            ));
        }
        session.refresh(&mut Fixed(Ok(observed(1, 2))), t).unwrap();
        session.expire_at(t + MAX_DISPLAY_AGE + Duration::from_nanos(1));
        assert_eq!(session.view().link, LinkState::Stale);
        session.refresh(&mut Fixed(Ok(observed(1, 3))), t).unwrap();
        session.expire_at(t.checked_sub(Duration::from_secs(1)).unwrap());
        assert_eq!(session.view().link, LinkState::Stale);
    }

    #[test]
    fn reinstall_requires_receipt_and_service_recheck() {
        let t = Instant::now();
        let mut session = DisplaySession::default();
        let mut removed = observed(1, 1);
        removed.installation = InstallationState::Removed;
        session.refresh(&mut Fixed(Ok(removed)), t).unwrap();
        assert_eq!(
            session.view().action_hint(ProposedAction::ReinstallModule),
            ActionHint::Blocked("REINSTALL_REQUIRES_VERIFIED_REMOVAL")
        );
        let mut receipt = observed(1, 2);
        receipt.installation = InstallationState::Removed;
        receipt.removal_receipt_verified = true;
        session.refresh(&mut Fixed(Ok(receipt)), t).unwrap();
        assert_eq!(
            session.view().action_hint(ProposedAction::ReinstallModule),
            ActionHint::RecheckWithService
        );
        session.fail(ReadFailure::Revoked);
        assert!(matches!(
            session.view().action_hint(ProposedAction::ReinstallModule),
            ActionHint::Blocked(_)
        ));
    }
}
