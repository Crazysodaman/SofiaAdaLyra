//! Authority-free UI *presentation* for Aegis Platform status and actions.
//! Only Team A's authenticated management service may decide operations.
//! These labels are never grants, credentials, receipts or service commands.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LinkState {
    Offline,
    Connecting,
    Unverified,
    Stale,
    Restarting,
    AccessDenied,
    Observed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SafeState {
    Unknown,
    Clear,
    StopActive,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PermissionState {
    Unknown,
    Denied,
    MayRequest,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InstallationState {
    Unknown,
    Absent,
    Installed,
    Removing,
    Removed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProposedAction {
    Inspect,
    SaveSettings,
    RestartCore,
    InstallModule,
    UninstallModule,
    ReinstallModule,
    UpdatePlatform,
    RollbackPlatform,
    RequestApproval,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActionHint {
    /// The view cannot even offer a service request.
    Blocked(&'static str),
    /// Present an existing authenticated observation; no privileged operation.
    ReadOnly,
    /// Merely show a request pathway once Team A's client exists.
    /// The service must recheck current SAFE/STOP, principal, generation,
    /// revocation, signed target, approval and operation-specific authority.
    RecheckWithService,
}

/// Immutable view of already authenticated observations supplied by a
/// separately reviewed Platform IPC adapter. Construction is NOT verification.
/// No UI may use this value to authorize work or bypass Platform IPC.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ControlCenterView {
    pub link: LinkState,
    pub safe: SafeState,
    pub permission: PermissionState,
    pub installation: InstallationState,
    pub platform_generation: Option<u64>,
    pub settings_revision: Option<u64>,
    pub effective_settings_revision: Option<u64>,
}

impl Default for ControlCenterView {
    fn default() -> Self {
        Self {
            link: LinkState::Offline,
            safe: SafeState::Unknown,
            permission: PermissionState::Unknown,
            installation: InstallationState::Unknown,
            platform_generation: None,
            settings_revision: None,
            effective_settings_revision: None,
        }
    }
}

impl ControlCenterView {
    #[must_use]
    pub fn offline() -> Self {
        Self::default()
    }

    /// Observed status never follows simply from launching a UI process.
    #[must_use]
    pub fn service_label(&self) -> &'static str {
        match self.link {
            LinkState::Offline => "UNAVAILABLE",
            LinkState::Connecting => "CONNECTING",
            LinkState::Unverified => "UNVERIFIED",
            LinkState::Stale => "STALE",
            LinkState::Restarting => "RESTARTING",
            LinkState::AccessDenied => "ACCESS_DENIED",
            LinkState::Observed => "OBSERVED",
        }
    }

    #[must_use]
    pub fn source_label(&self) -> &'static str {
        match self.link {
            LinkState::Observed => "SERVICE_OBSERVED",
            LinkState::Stale => "STALE_OBSERVATION",
            LinkState::AccessDenied => "DENIED",
            _ => "UNVERIFIED",
        }
    }

    /// A previously installed component must never become REMOVED simply
    /// because its service disconnected, restarted or timed out.
    #[must_use]
    pub fn installation_label(&self) -> &'static str {
        if self.link != LinkState::Observed {
            return "NOT_CURRENTLY_VERIFIED";
        }
        match self.installation {
            InstallationState::Unknown => "UNKNOWN",
            InstallationState::Absent => "NOT_INSTALLED",
            InstallationState::Installed => "INSTALLED",
            InstallationState::Removing => "REMOVAL_PENDING",
            InstallationState::Removed => "REMOVED_WITH_RECEIPT",
        }
    }

    /// Separate saved revision from effective revision. A revision difference
    /// is a UI warning, NOT proof the settings update or apply succeeded.
    #[must_use]
    pub fn settings_label(&self) -> &'static str {
        if self.link != LinkState::Observed {
            return "UNKNOWN_UNVERIFIED";
        }
        match (self.settings_revision, self.effective_settings_revision) {
            (Some(saved), Some(applied)) if applied == saved => "SAVED_EQUALS_EFFECTIVE",
            (Some(saved), Some(applied)) if applied < saved => "PENDING_APPLY",
            _ => "UNKNOWN_INCONSISTENT",
        }
    }

    /// An editor must be discarded/reviewed if the Platform generation, saved
    /// or applied revisions, installation, trust or permission changed.
    #[must_use]
    pub fn editor_needs_review(&self, opened: &Self) -> bool {
        self.link != LinkState::Observed
            || opened.link != LinkState::Observed
            || self.safe != SafeState::Clear
            || self.permission != PermissionState::MayRequest
            || self.platform_generation.is_none()
            || self.platform_generation != opened.platform_generation
            || self.settings_revision != opened.settings_revision
            || self.effective_settings_revision != opened.effective_settings_revision
            || self.installation != opened.installation
    }

    /// UI guidance only: even RecheckWithService is *not* permission to execute.
    #[must_use]
    pub fn action_hint(&self, action: ProposedAction) -> ActionHint {
        if self.link != LinkState::Observed {
            return ActionHint::Blocked(match self.link {
                LinkState::Offline => "PLATFORM_OFFLINE",
                LinkState::Connecting => "AUTHENTICATION_PENDING",
                LinkState::Unverified => "SOURCE_UNVERIFIED",
                LinkState::Stale => "OBSERVATION_STALE",
                LinkState::Restarting => "SERVICE_RESTARTING",
                LinkState::AccessDenied => "ACCESS_DENIED",
                LinkState::Observed => unreachable!(),
            });
        }
        if action == ProposedAction::Inspect {
            return ActionHint::ReadOnly;
        }
        if self.safe == SafeState::StopActive {
            return ActionHint::Blocked("SAFE_STOP_ACTIVE");
        }
        if self.safe != SafeState::Clear {
            return ActionHint::Blocked("SAFE_STATE_UNKNOWN");
        }
        if self.permission == PermissionState::Denied {
            return ActionHint::Blocked("PERMISSION_DENIED");
        }
        if self.permission != PermissionState::MayRequest {
            return ActionHint::Blocked("PERMISSION_NOT_EVALUATED");
        }
        if self.platform_generation.is_none_or(|generation| generation == 0) {
            return ActionHint::Blocked("GENERATION_NOT_OBSERVED");
        }
        match action {
            ProposedAction::InstallModule if self.installation != InstallationState::Absent => {
                ActionHint::Blocked("INSTALL_TARGET_NOT_VERIFIED_ABSENT")
            }
            ProposedAction::UninstallModule if self.installation != InstallationState::Installed => {
                ActionHint::Blocked("UNINSTALL_TARGET_NOT_VERIFIED_INSTALLED")
            }
            ProposedAction::ReinstallModule if self.installation != InstallationState::Removed => {
                ActionHint::Blocked("REINSTALL_REQUIRES_VERIFIED_REMOVAL")
            }
            ProposedAction::SaveSettings
                if self.settings_revision.is_none()
                    || self.effective_settings_revision.is_none() =>
            {
                ActionHint::Blocked("SETTINGS_REVISION_UNKNOWN")
            }
            _ => ActionHint::RecheckWithService,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{
        ActionHint, ControlCenterView, InstallationState, LinkState, PermissionState,
        ProposedAction, SafeState,
    };

    fn observed() -> ControlCenterView {
        ControlCenterView {
            link: LinkState::Observed,
            safe: SafeState::Clear,
            permission: PermissionState::MayRequest,
            installation: InstallationState::Installed,
            platform_generation: Some(9),
            settings_revision: Some(4),
            effective_settings_revision: Some(3),
        }
    }

    #[test]
    fn offline_is_unknown_not_not_installed_or_healthy() {
        let view = ControlCenterView::offline();
        assert_eq!(view.service_label(), "UNAVAILABLE");
        assert_eq!(view.source_label(), "UNVERIFIED");
        assert_eq!(view.installation_label(), "NOT_CURRENTLY_VERIFIED");
        assert_eq!(view.settings_label(), "UNKNOWN_UNVERIFIED");
        assert_eq!(
            view.action_hint(ProposedAction::RestartCore),
            ActionHint::Blocked("PLATFORM_OFFLINE")
        );
    }

    #[test]
    fn stale_and_restart_do_not_erase_installed_state_or_offer_actions() {
        let mut view = observed();
        for (link, expected) in [
            (LinkState::Stale, "OBSERVATION_STALE"),
            (LinkState::Restarting, "SERVICE_RESTARTING"),
            (LinkState::Unverified, "SOURCE_UNVERIFIED"),
            (LinkState::Connecting, "AUTHENTICATION_PENDING"),
        ] {
            view.link = link;
            assert_eq!(view.installation_label(), "NOT_CURRENTLY_VERIFIED");
            assert_eq!(view.action_hint(ProposedAction::UninstallModule),
                       ActionHint::Blocked(expected));
        }
    }

    #[test]
    fn stop_denied_and_unknown_authority_fail_closed() {
        let mut view = observed();
        view.safe = SafeState::StopActive;
        assert_eq!(view.action_hint(ProposedAction::UpdatePlatform),
                   ActionHint::Blocked("SAFE_STOP_ACTIVE"));
        view.safe = SafeState::Unknown;
        assert_eq!(view.action_hint(ProposedAction::UpdatePlatform),
                   ActionHint::Blocked("SAFE_STATE_UNKNOWN"));
        view.safe = SafeState::Clear;
        view.permission = PermissionState::Denied;
        assert_eq!(view.action_hint(ProposedAction::RestartCore),
                   ActionHint::Blocked("PERMISSION_DENIED"));
        view.permission = PermissionState::Unknown;
        assert_eq!(view.action_hint(ProposedAction::RestartCore),
                   ActionHint::Blocked("PERMISSION_NOT_EVALUATED"));
        view.link = LinkState::AccessDenied;
        assert_eq!(view.action_hint(ProposedAction::Inspect),
                   ActionHint::Blocked("ACCESS_DENIED"));
    }

    #[test]
    fn lifecycle_actions_need_exact_current_state_then_service_decision() {
        let mut view = observed();
        assert_eq!(view.action_hint(ProposedAction::UninstallModule),
                   ActionHint::RecheckWithService);
        assert_eq!(view.action_hint(ProposedAction::InstallModule),
                   ActionHint::Blocked("INSTALL_TARGET_NOT_VERIFIED_ABSENT"));
        view.installation = InstallationState::Absent;
        assert_eq!(view.action_hint(ProposedAction::InstallModule),
                   ActionHint::RecheckWithService);
        view.installation = InstallationState::Removed;
        assert_eq!(view.action_hint(ProposedAction::ReinstallModule),
                   ActionHint::RecheckWithService);
        assert_eq!(view.action_hint(ProposedAction::UninstallModule),
                   ActionHint::Blocked("UNINSTALL_TARGET_NOT_VERIFIED_INSTALLED"));
        assert_eq!(view.action_hint(ProposedAction::Inspect),
                   ActionHint::ReadOnly);
    }

    #[test]
    fn settings_edits_require_review_on_generation_revision_or_trust_change() {
        let start = observed();
        assert_eq!(start.settings_label(), "PENDING_APPLY");
        assert!(!start.editor_needs_review(&start));
        let mut changed = start.clone();
        changed.settings_revision = Some(5);
        assert!(changed.editor_needs_review(&start));
        changed = start.clone();
        changed.platform_generation = Some(10);
        assert!(changed.editor_needs_review(&start));
        changed = start.clone();
        changed.effective_settings_revision = Some(4);
        assert!(changed.editor_needs_review(&start));
        assert_eq!(changed.settings_label(), "SAVED_EQUALS_EFFECTIVE");
        changed = start.clone();
        changed.link = LinkState::Offline;
        assert!(changed.editor_needs_review(&start));
        changed = start.clone();
        changed.installation = InstallationState::Removed;
        assert!(changed.editor_needs_review(&start));
    }

    #[test]
    fn no_display_snapshot_can_execute_or_grant_without_service_recheck() {
        let view = observed();
        for action in [
            ProposedAction::SaveSettings,
            ProposedAction::RestartCore,
            ProposedAction::UpdatePlatform,
            ProposedAction::RollbackPlatform,
            ProposedAction::RequestApproval,
        ] {
            assert_eq!(view.action_hint(action), ActionHint::RecheckWithService);
        }
        let mut bad = view;
        bad.platform_generation = None;
        assert_eq!(bad.action_hint(ProposedAction::RestartCore),
                   ActionHint::Blocked("GENERATION_NOT_OBSERVED"));
    }
}
