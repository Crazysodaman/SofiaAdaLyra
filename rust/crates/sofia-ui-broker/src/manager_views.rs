//! Read-only operator views for Core, Module, Fleet, Security, Updates and
//! Diagnostics, plus mutation review labels.
//!
//! A snapshot is supplied only by a separately authenticated management
//! client. This module never reads a socket, database, service, approval or
//! owner secret, and it never performs a mutation. Every protected action is
//! shown as a preview requiring owner approval and a fresh service decision.

use crate::connection_state::ConnectionState;
use crate::control_center::{ActionHint, ControlCenterView, LinkState, ProposedAction};
use crate::platform_status::{ModuleHealth, ModuleLifecycle, ObservationFreshness};
use std::collections::BTreeMap;
use std::fmt::Write as _;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum ManagerPage {
    Cores,
    Modules,
    Fleet,
    Security,
    Updates,
    Diagnostics,
}

impl ManagerPage {
    pub const ALL: [Self; 6] = [
        Self::Cores,
        Self::Modules,
        Self::Fleet,
        Self::Security,
        Self::Updates,
        Self::Diagnostics,
    ];
}

/// Truthful per-page observation state. A page is never assumed observed just
/// because the surrounding connection is current; a failed read is not an
/// empty inventory and a denial is not an empty list.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SectionTruth {
    Observed,
    NotObserved,
    Stale,
    Offline,
    Revoked,
    Stop,
    Denied,
    Unknown,
}

impl SectionTruth {
    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            Self::Observed => "OBSERVED",
            Self::NotObserved => "NOT_OBSERVED",
            Self::Stale => "STALE",
            Self::Offline => "OFFLINE",
            Self::Revoked => "REVOKED",
            Self::Stop => "STOP",
            Self::Denied => "DENIED",
            Self::Unknown => "UNKNOWN",
        }
    }

    #[must_use]
    pub fn is_current(self) -> bool {
        self == Self::Observed
    }
}

impl ManagerPage {
    #[must_use]
    pub fn heading(self) -> &'static str {
        match self {
            Self::Cores => "Core Manager",
            Self::Modules => "Module Manager",
            Self::Fleet => "Fleet Manager",
            Self::Security => "Security and Approvals",
            Self::Updates => "Updates and Recovery",
            Self::Diagnostics => "Diagnostics",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CoreLifecycle {
    Installed,
    Active,
    Paused,
    Disabled,
    Unavailable,
}

impl CoreLifecycle {
    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            Self::Installed => "INSTALLED",
            Self::Active => "ACTIVE",
            Self::Paused => "PAUSED",
            Self::Disabled => "DISABLED",
            Self::Unavailable => "UNAVAILABLE",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ManagedHealth {
    VerifiedHealthy,
    VerifiedUnhealthy,
    Unknown,
}

impl ManagedHealth {
    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            Self::VerifiedHealthy => "VERIFIED_HEALTHY",
            Self::VerifiedUnhealthy => "VERIFIED_UNHEALTHY",
            Self::Unknown => "UNKNOWN",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CoreObservation {
    pub core_id: String,
    pub lifecycle: CoreLifecycle,
    pub health: ManagedHealth,
    pub generation: u64,
    /// Present only for the legacy verified-health Core inventory projection.
    pub source_digest: Option<String>,
    /// Platform startup Core inventory fields. Absent means `NOT_OBSERVED`.
    pub installed: Option<bool>,
    pub enabled: Option<bool>,
    pub startup_mode: Option<String>,
    pub observed_state: Option<String>,
    pub last_error_code: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StartupState {
    ZeroCoreHealthy,
    CoresRunning,
    CoresDisabled,
    Degraded,
    Unknown,
}

impl StartupState {
    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            Self::ZeroCoreHealthy => "ZERO_CORE_HEALTHY",
            Self::CoresRunning => "CORES_RUNNING",
            Self::CoresDisabled => "CORES_DISABLED",
            Self::Degraded => "DEGRADED",
            Self::Unknown => "UNKNOWN",
        }
    }
}

/// Reviewed Platform startup projection. This is a display observation, not a
/// Core health or lifecycle receipt.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StartupObservation {
    pub core_started: bool,
    pub core_count: u64,
    pub active_core_count: u64,
    pub startup_state: StartupState,
    pub autostart_enabled_count: u64,
    pub autostart_reconciled_at: Option<String>,
    pub management_listening: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ModuleView {
    pub module_id: String,
    pub lifecycle: ModuleLifecycle,
    pub health: ModuleHealth,
    pub publisher: String,
    pub generation: u64,
    pub settings_revision: u64,
    pub blocked_reinstall: bool,
    pub removal_receipt_id: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FleetTrust {
    Enrolled,
    Candidate,
    Stale,
    Unreachable,
    Quarantined,
}

impl FleetTrust {
    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            Self::Enrolled => "ENROLLED",
            Self::Candidate => "CANDIDATE",
            Self::Stale => "STALE",
            Self::Unreachable => "UNREACHABLE",
            Self::Quarantined => "QUARANTINED",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FleetPeer {
    pub peer_id: String,
    pub callsign: String,
    pub trust: FleetTrust,
    pub last_observed: String,
    pub scope: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ApprovalState {
    Pending,
    Approved,
    Denied,
    Expired,
    Revoked,
}

impl ApprovalState {
    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            Self::Pending => "PENDING",
            Self::Approved => "APPROVED",
            Self::Denied => "DENIED",
            Self::Expired => "EXPIRED",
            Self::Revoked => "REVOKED",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ApprovalView {
    pub approval_id: String,
    pub operation: String,
    pub state: ApprovalState,
    pub expires_at: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct SecurityObservation {
    pub approvals: Vec<ApprovalView>,
    pub grants: Vec<String>,
    pub stop_active: bool,
    pub revoked: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct UpdatesObservation {
    pub current_release: Option<String>,
    pub available_release: Option<String>,
    pub rollback_eligible: bool,
    pub staged_receipt: Option<String>,
    pub last_outcome: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DiagnosticsObservation {
    pub service_id: String,
    pub process_observed: bool,
    pub release_digest: String,
    pub missing_prerequisites: Vec<String>,
    pub freshness: ObservationFreshness,
}

impl Default for DiagnosticsObservation {
    fn default() -> Self {
        Self {
            service_id: "UNKNOWN".to_owned(),
            process_observed: false,
            release_digest: "UNKNOWN".to_owned(),
            missing_prerequisites: Vec::new(),
            freshness: ObservationFreshness::Stale,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ManagerSnapshot {
    pub freshness: ObservationFreshness,
    pub platform_id: Option<String>,
    pub platform_generation: Option<u64>,
    /// Current service mutation-receipt revision when separately observed.
    /// It is NEVER inferred from a display name, settings revision or launch.
    pub platform_revision: Option<u64>,
    pub startup: Option<StartupObservation>,
    pub sections: BTreeMap<ManagerPage, SectionTruth>,
    pub cores: Vec<CoreObservation>,
    pub modules: Vec<ModuleView>,
    pub fleet: Vec<FleetPeer>,
    pub security: Option<SecurityObservation>,
    pub updates: Option<UpdatesObservation>,
    pub diagnostics: Option<DiagnosticsObservation>,
}

impl ManagerSnapshot {
    #[must_use]
    pub fn section(&self, page: ManagerPage) -> SectionTruth {
        self.sections
            .get(&page)
            .copied()
            .unwrap_or(SectionTruth::NotObserved)
    }

    pub fn mark(&mut self, page: ManagerPage, truth: SectionTruth) {
        self.sections.insert(page, truth);
    }
}

impl Default for ManagerSnapshot {
    fn default() -> Self {
        Self {
            freshness: ObservationFreshness::Stale,
            platform_id: None,
            platform_generation: None,
            platform_revision: None,
            startup: None,
            sections: BTreeMap::new(),
            cores: Vec::new(),
            modules: Vec::new(),
            fleet: Vec::new(),
            security: None,
            updates: None,
            diagnostics: None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MutationReviewState {
    ReadOnly,
    PreviewRequiresOwnerApproval,
    Blocked(&'static str),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MutationReview {
    pub state: MutationReviewState,
    pub operation: &'static str,
}

impl MutationReview {
    #[must_use]
    pub fn label(self) -> String {
        match self.state {
            MutationReviewState::ReadOnly => {
                "READ_ONLY / NO_MUTATION / NO_APPROVAL_REQUESTED".to_owned()
            }
            MutationReviewState::PreviewRequiresOwnerApproval => format!(
                "PREVIEW_REQUIRED / REQUIRES_OWNER_APPROVAL / OPERATION: {} / SERVICE_RECHECK_AND_EXECUTION_RECEIPT_REQUIRED",
                self.operation
            ),
            MutationReviewState::Blocked(reason) => {
                format!("BLOCKED / REASON: {reason} / NO_MUTATION_SUBMITTED")
            }
        }
    }
}

#[must_use]
pub fn is_current_observation(view: &ControlCenterView) -> bool {
    view.link == LinkState::Observed
        && view.platform_generation.is_some()
        && view.safe == crate::control_center::SafeState::Clear
}

#[must_use]
pub fn proposed_action(page: ManagerPage) -> ProposedAction {
    match page {
        ManagerPage::Cores => ProposedAction::RestartCore,
        ManagerPage::Modules => ProposedAction::InstallModule,
        ManagerPage::Security => ProposedAction::RequestApproval,
        ManagerPage::Updates => ProposedAction::UpdatePlatform,
        ManagerPage::Fleet | ManagerPage::Diagnostics => ProposedAction::Inspect,
    }
}

#[must_use]
pub fn mutation_review(
    page: ManagerPage,
    view: &ControlCenterView,
    snapshot: Option<&ManagerSnapshot>,
) -> MutationReview {
    let operation = match page {
        ManagerPage::Cores => "core.restart",
        ManagerPage::Modules => "module.install",
        ManagerPage::Fleet => "fleet.inspect",
        ManagerPage::Security => "security.approval.request",
        ManagerPage::Updates => "platform.update",
        ManagerPage::Diagnostics => "diagnostics.inspect",
    };
    if matches!(page, ManagerPage::Fleet | ManagerPage::Diagnostics) {
        return MutationReview {
            state: MutationReviewState::ReadOnly,
            operation,
        };
    }
    if is_current_observation(view) && snapshot.is_none() {
        return MutationReview {
            state: MutationReviewState::Blocked("MANAGER_SNAPSHOT_NOT_OBSERVED"),
            operation,
        };
    }
    if is_current_observation(view)
        && snapshot.is_some_and(|value| {
            value.freshness == ObservationFreshness::Stale || !value.section(page).is_current()
        })
    {
        return MutationReview {
            state: MutationReviewState::Blocked("MANAGER_OBSERVATION_STALE"),
            operation,
        };
    }
    match view.action_hint(proposed_action(page)) {
        ActionHint::Blocked(reason) => MutationReview {
            state: MutationReviewState::Blocked(reason),
            operation,
        },
        ActionHint::ReadOnly => MutationReview {
            state: MutationReviewState::ReadOnly,
            operation,
        },
        ActionHint::RecheckWithService => MutationReview {
            state: MutationReviewState::PreviewRequiresOwnerApproval,
            operation,
        },
    }
}

/// Render the reviewed Platform startup projection without claiming Core
/// health. Absent observations remain explicitly `NOT_OBSERVED`.
#[must_use]
pub fn startup_lines(snapshot: Option<&ManagerSnapshot>) -> Vec<String> {
    let Some(startup) = snapshot.and_then(|snapshot| snapshot.startup.as_ref()) else {
        return vec![
            "STARTUP: NOT_OBSERVED / NO_CURRENT_AUTHENTICATED_STARTUP_PROJECTION".to_owned(),
        ];
    };
    vec![format!(
        "STARTUP: state={} core_started={} core_count={} active_core_count={} autostart_enabled={} management_listening={} reconciled_at={}",
        startup.startup_state.label(),
        if startup.core_started { "YES" } else { "NO" },
        startup.core_count,
        startup.active_core_count,
        startup.autostart_enabled_count,
        if startup.management_listening {
            "YES"
        } else {
            "NO"
        },
        startup.autostart_reconciled_at.as_deref().unwrap_or("NEVER")
    )]
}

/// Render bounded, ASCII-safe manager observations. No ANSI escapes are
/// emitted here; terminal color is applied only by an interactive renderer.
#[must_use]
pub fn manager_lines(
    page: ManagerPage,
    view: &ControlCenterView,
    snapshot: Option<&ManagerSnapshot>,
) -> Vec<String> {
    let mut lines = vec![
        format!("CONNECTION: {}", ConnectionState::from_view(view).label()),
        format!(
            "MANAGER OBSERVATION: {}",
            if is_current_observation(view) {
                "CURRENT"
            } else {
                "NOT_CURRENTLY_VERIFIED"
            }
        ),
    ];
    if !is_current_observation(view) {
        lines.push(format!(
            "SERVICE: {} / SOURCE: {}",
            view.service_label(),
            view.source_label()
        ));
        lines.push("CACHED VALUES: NOT_CURRENT".to_owned());
    } else if let Some(snapshot) = snapshot {
        lines.extend(startup_lines(Some(snapshot)));
        lines.push(format!(
            "SNAPSHOT TARGET: {} / GENERATION: {} / MUTATION REVISION: {}",
            snapshot.platform_id.as_deref().unwrap_or("UNKNOWN"),
            snapshot
                .platform_generation
                .map_or_else(|| "UNKNOWN".to_owned(), |value| value.to_string()),
            snapshot
                .platform_revision
                .map_or_else(|| "NOT_OBSERVED".to_owned(), |value| value.to_string())
        ));
        if snapshot.freshness == ObservationFreshness::Stale {
            lines.push(
                "SNAPSHOT: STALE / CACHED VALUES NOT CURRENT / HEALTH AND TARGETS NOT VERIFIED"
                    .to_owned(),
            );
        }
        let truth = snapshot.section(page);
        if truth.is_current() {
            match page {
                ManagerPage::Cores => render_cores(&mut lines, snapshot),
                ManagerPage::Modules => render_modules(&mut lines, snapshot),
                ManagerPage::Fleet => render_fleet(&mut lines, snapshot),
                ManagerPage::Security => render_security(&mut lines, view, snapshot),
                ManagerPage::Updates => render_updates(&mut lines, snapshot),
                ManagerPage::Diagnostics => render_diagnostics(&mut lines, snapshot),
            }
        } else {
            lines.push(format!(
                "{}: {} / NO_CURRENT_AUTHENTICATED_OBSERVATION / NO_EMPTY_OR_HEALTH_CLAIM",
                page.heading().to_uppercase(),
                truth.label()
            ));
        }
    } else {
        lines.push(
            "MANAGER OBSERVATION: NOT_OBSERVED / NO_AUTHENTICATED_MANAGER_SNAPSHOT".to_owned(),
        );
    }
    let review = mutation_review(page, view, snapshot);
    lines.push(format!("ACTION REVIEW: {}", review.label()));
    lines
}

fn render_cores(lines: &mut Vec<String>, snapshot: &ManagerSnapshot) {
    if snapshot.cores.is_empty() {
        lines.push("CORES: NONE_INSTALLED / CORE: UNAVAILABLE".to_owned());
        return;
    }
    lines.push(format!("CORES: {} OBSERVED", snapshot.cores.len()));
    for core in &snapshot.cores {
        let mut line = format!(
            "CORE {} lifecycle={} health={} generation={}",
            core.core_id,
            core.lifecycle.label(),
            if snapshot.freshness == ObservationFreshness::Stale {
                ManagedHealth::Unknown.label()
            } else {
                core.health.label()
            },
            core.generation,
        );
        if let Some(digest) = &core.source_digest {
            let _ = write!(line, " source_digest={digest}");
        }
        if let Some(installed) = core.installed {
            let _ = write!(line, " installed={}", if installed { "YES" } else { "NO" });
        }
        if let Some(enabled) = core.enabled {
            let _ = write!(line, " enabled={}", if enabled { "YES" } else { "NO" });
        }
        if let Some(mode) = &core.startup_mode {
            let _ = write!(line, " startup_mode={mode}");
        }
        if let Some(state) = &core.observed_state {
            let _ = write!(line, " observed_state={state}");
        }
        if let Some(code) = &core.last_error_code {
            let _ = write!(line, " last_error_code={code}");
        }
        lines.push(line);
    }
    lines.push("CORE TARGET IDENTITY IS REQUIRED; A NICKNAME IS NOT AUTHORITY".to_owned());
}

fn render_modules(lines: &mut Vec<String>, snapshot: &ManagerSnapshot) {
    if snapshot.modules.is_empty() {
        lines.push("MODULES: NONE_INSTALLED".to_owned());
        return;
    }
    lines.push(format!("MODULES: {} OBSERVED", snapshot.modules.len()));
    for module in &snapshot.modules {
        let health = if snapshot.freshness == ObservationFreshness::Stale {
            ModuleHealth::Unknown
        } else {
            module.health
        };
        lines.push(format!(
            "MODULE {} lifecycle={} health={} publisher={} generation={} settings_revision={} blocked_reinstall={} removal_receipt={}",
            module.module_id,
            module_lifecycle_label(module.lifecycle),
            module_health_label(health),
            module.publisher,
            module.generation,
            module.settings_revision,
            if module.blocked_reinstall { "YES" } else { "NO" },
            module.removal_receipt_id.as_deref().unwrap_or("NONE")
        ));
    }
    lines.push("INSTALLED LIFECYCLE IS NOT RUNTIME HEALTH".to_owned());
}

fn render_fleet(lines: &mut Vec<String>, snapshot: &ManagerSnapshot) {
    let count = |trust: FleetTrust| {
        snapshot
            .fleet
            .iter()
            .filter(|peer| peer.trust == trust)
            .count()
    };
    lines.push(format!(
        "FLEET: ENROLLED={} CANDIDATE={} STALE={} UNREACHABLE={} QUARANTINED={}",
        count(FleetTrust::Enrolled),
        count(FleetTrust::Candidate),
        count(FleetTrust::Stale),
        count(FleetTrust::Unreachable),
        count(FleetTrust::Quarantined)
    ));
    for peer in &snapshot.fleet {
        lines.push(format!(
            "PEER {} callsign={} trust={} last_observed={} scope={}",
            peer.peer_id,
            peer.callsign,
            peer.trust.label(),
            peer.last_observed,
            peer.scope
        ));
    }
    lines.push("DISCOVERY_IS_NOT_PERMISSION / CALLSIGN_IS_NOT_AUTHORITY".to_owned());
}

fn render_security(lines: &mut Vec<String>, view: &ControlCenterView, snapshot: &ManagerSnapshot) {
    lines.push(format!(
        "SECURITY: SAFE={} STOP={} PERMISSION={} REVOKED={}",
        view.safe_label(),
        if snapshot
            .security
            .as_ref()
            .is_some_and(|security| security.stop_active)
        {
            "OBSERVED_ACTIVE"
        } else {
            "NOT_OBSERVED"
        },
        view.permission_label(),
        if snapshot
            .security
            .as_ref()
            .is_some_and(|security| security.revoked)
        {
            "YES"
        } else {
            "NO"
        }
    ));
    match snapshot.security.as_ref() {
        None => lines.push("APPROVALS: NOT_OBSERVED".to_owned()),
        Some(security) if security.approvals.is_empty() => {
            lines.push("APPROVALS: NONE_OBSERVED".to_owned());
        }
        Some(security) => {
            for approval in &security.approvals {
                lines.push(format!(
                    "APPROVAL {} operation={} state={} expires_at={}",
                    approval.approval_id,
                    approval.operation,
                    approval.state.label(),
                    approval.expires_at
                ));
            }
        }
    }
    if let Some(security) = &snapshot.security {
        if security.grants.is_empty() {
            lines.push("GRANTS: NONE_OBSERVED".to_owned());
        } else {
            for grant in &security.grants {
                lines.push(format!("GRANT {grant}"));
            }
        }
    }
    lines.push(
        "APPROVAL DECISIONS REQUIRE ATTENDED OWNER PROOF; UI INPUT IS NOT AUTHORIZATION".to_owned(),
    );
}

fn render_updates(lines: &mut Vec<String>, snapshot: &ManagerSnapshot) {
    match snapshot.updates.as_ref() {
        None => lines.push("UPDATES: NOT_OBSERVED".to_owned()),
        Some(updates) => {
            lines.push(format!(
                "UPDATES: CURRENT_RELEASE={} AVAILABLE_RELEASE={} ROLLBACK_ELIGIBLE={} STAGED_RECEIPT={} LAST_OUTCOME={}",
                updates.current_release.as_deref().unwrap_or("UNKNOWN"),
                updates.available_release.as_deref().unwrap_or("UNKNOWN"),
                if updates.rollback_eligible { "YES" } else { "NO" },
                updates.staged_receipt.as_deref().unwrap_or("NONE"),
                updates.last_outcome.as_deref().unwrap_or("UNKNOWN")
            ));
        }
    }
    lines.push("A RELEASE PREVIEW IS NOT INSTALLATION OR ROLLBACK AUTHORITY".to_owned());
}

fn render_diagnostics(lines: &mut Vec<String>, snapshot: &ManagerSnapshot) {
    match snapshot.diagnostics.as_ref() {
        None => lines.push("DIAGNOSTICS: NOT_OBSERVED".to_owned()),
        Some(diagnostics) => {
            lines.push(format!(
                "DIAGNOSTICS: service_id={} process={} release_digest={} freshness={}",
                diagnostics.service_id,
                if diagnostics.process_observed {
                    "OBSERVED"
                } else {
                    "NOT_OBSERVED"
                },
                diagnostics.release_digest,
                if diagnostics.freshness == ObservationFreshness::Fresh {
                    "FRESH"
                } else {
                    "STALE"
                }
            ));
            if diagnostics.missing_prerequisites.is_empty() {
                lines.push("MISSING_PREREQUISITES: NONE_OBSERVED".to_owned());
            } else {
                for prerequisite in &diagnostics.missing_prerequisites {
                    lines.push(format!("MISSING_PREREQUISITE {prerequisite}"));
                }
            }
        }
    }
    lines.push("DIAGNOSTICS ARE READ_ONLY / PROCESS EXISTENCE IS NOT SERVICE HEALTH".to_owned());
}

fn module_lifecycle_label(lifecycle: ModuleLifecycle) -> &'static str {
    match lifecycle {
        ModuleLifecycle::Installed => "INSTALLED",
        ModuleLifecycle::Disabled => "DISABLED",
        ModuleLifecycle::Activating => "ACTIVATING",
        ModuleLifecycle::Active => "ACTIVE",
        ModuleLifecycle::Paused => "PAUSED",
        ModuleLifecycle::Quarantined => "QUARANTINED",
        ModuleLifecycle::Removed => "REMOVED",
    }
}

fn module_health_label(health: ModuleHealth) -> &'static str {
    match health {
        ModuleHealth::VerifiedHealthy => "VERIFIED_HEALTHY",
        ModuleHealth::VerifiedUnhealthy => "VERIFIED_UNHEALTHY",
        ModuleHealth::Unknown => "UNKNOWN",
    }
}

#[cfg(test)]
mod tests {
    use super::{
        manager_lines, mutation_review, CoreLifecycle, CoreObservation, DiagnosticsObservation,
        FleetPeer, FleetTrust, ManagedHealth, ManagerPage, ManagerSnapshot, MutationReviewState,
        SecurityObservation, UpdatesObservation,
    };
    use crate::control_center::{
        ControlCenterView, InstallationState, LinkState, PermissionState, SafeState,
    };
    use crate::platform_status::{ModuleHealth, ModuleLifecycle, ObservationFreshness};

    fn current() -> ControlCenterView {
        ControlCenterView {
            link: LinkState::Observed,
            safe: SafeState::Clear,
            permission: PermissionState::MayRequest,
            installation: InstallationState::Installed,
            platform_generation: Some(9),
            settings_revision: Some(4),
            effective_settings_revision: Some(4),
            removal_receipt_verified: false,
        }
    }

    fn snapshot() -> ManagerSnapshot {
        ManagerSnapshot {
            freshness: ObservationFreshness::Fresh,
            platform_id: Some("platform:alpha".into()),
            platform_generation: Some(9),
            platform_revision: Some(6),
            startup: Some(super::StartupObservation {
                core_started: true,
                core_count: 1,
                active_core_count: 1,
                startup_state: super::StartupState::CoresRunning,
                autostart_enabled_count: 1,
                autostart_reconciled_at: Some("2026-11-08T04:00:00Z".into()),
                management_listening: true,
            }),
            sections: ManagerPage::ALL
                .iter()
                .copied()
                .map(|page| (page, super::SectionTruth::Observed))
                .collect(),
            cores: vec![CoreObservation {
                core_id: "core:primary".into(),
                lifecycle: CoreLifecycle::Active,
                health: ManagedHealth::VerifiedHealthy,
                generation: 3,
                source_digest: Some("a".repeat(64)),
                installed: None,
                enabled: None,
                startup_mode: None,
                observed_state: None,
                last_error_code: None,
            }],
            modules: vec![super::ModuleView {
                module_id: "module:demo".into(),
                lifecycle: ModuleLifecycle::Active,
                health: ModuleHealth::VerifiedHealthy,
                publisher: "publisher:demo".into(),
                generation: 2,
                settings_revision: 5,
                blocked_reinstall: false,
                removal_receipt_id: None,
            }],
            fleet: vec![FleetPeer {
                peer_id: "peer:one".into(),
                callsign: "One".into(),
                trust: FleetTrust::Candidate,
                last_observed: "2026-11-08T04:00:00Z".into(),
                scope: "local".into(),
            }],
            security: Some(SecurityObservation {
                approvals: Vec::new(),
                grants: Vec::new(),
                stop_active: false,
                revoked: false,
            }),
            updates: Some(UpdatesObservation::default()),
            diagnostics: Some(DiagnosticsObservation {
                service_id: "service:aegis".into(),
                process_observed: true,
                release_digest: "b".repeat(64),
                missing_prerequisites: Vec::new(),
                freshness: ObservationFreshness::Fresh,
            }),
        }
    }

    #[test]
    fn every_manager_page_is_reachable_and_truthful_without_a_snapshot() {
        for page in [
            ManagerPage::Cores,
            ManagerPage::Modules,
            ManagerPage::Fleet,
            ManagerPage::Security,
            ManagerPage::Updates,
            ManagerPage::Diagnostics,
        ] {
            let lines = manager_lines(page, &current(), None).join("\n");
            assert!(lines.contains("MANAGER OBSERVATION: NOT_OBSERVED"));
            assert!(lines.contains("CONNECTION: CONNECTED"));
            assert!(!lines.contains('\x1b'));
            assert!(!lines.contains("VERIFIED_HEALTHY"));
        }
    }

    #[test]
    fn stale_or_disconnected_views_never_render_cached_values_as_current() {
        for view in {
            let mut stale = current();
            stale.link = LinkState::Stale;
            let mut stopped = current();
            stopped.safe = SafeState::StopActive;
            [stale, stopped]
        } {
            let lines = manager_lines(ManagerPage::Cores, &view, Some(&snapshot())).join("\n");
            assert!(lines.contains("CACHED VALUES: NOT_CURRENT"));
            assert!(!lines.contains("core:primary"));
            assert!(!lines.contains("PLATFORM GENERATION: 9"));
        }
    }

    #[test]
    fn fresh_snapshot_preserves_lifecycle_health_and_identity() {
        let lines = manager_lines(ManagerPage::Modules, &current(), Some(&snapshot())).join("\n");
        assert!(lines.contains("MODULE module:demo"));
        assert!(lines.contains("lifecycle=ACTIVE"));
        assert!(lines.contains("health=VERIFIED_HEALTHY"));
        assert!(lines.contains("publisher=publisher:demo"));
    }

    #[test]
    fn stale_snapshot_preserves_lifecycle_but_hides_health() {
        let mut value = snapshot();
        value.freshness = ObservationFreshness::Stale;
        let lines = manager_lines(ManagerPage::Modules, &current(), Some(&value)).join("\n");
        assert!(lines.contains("SNAPSHOT: STALE"));
        assert!(lines.contains("lifecycle=ACTIVE"));
        assert!(lines.contains("health=UNKNOWN"));
        assert!(!lines.contains("health=VERIFIED_HEALTHY"));
    }

    #[test]
    fn fleet_discovery_is_never_displayed_as_permission() {
        let lines = manager_lines(ManagerPage::Fleet, &current(), Some(&snapshot())).join("\n");
        assert!(lines.contains("CANDIDATE=1"));
        assert!(lines.contains("DISCOVERY_IS_NOT_PERMISSION"));
        assert!(lines.contains("CALLSIGN_IS_NOT_AUTHORITY"));
        assert!(!lines.contains("AUTHORIZED_BY_NAME"));
    }

    #[test]
    fn mutation_pages_show_preview_and_owner_approval_not_read_only() {
        let mut installable = current();
        installable.installation = InstallationState::Absent;
        for (page, view) in [
            (ManagerPage::Cores, current()),
            (ManagerPage::Modules, installable),
            (ManagerPage::Security, current()),
            (ManagerPage::Updates, current()),
        ] {
            let review = mutation_review(page, &view, Some(&snapshot()));
            assert_eq!(
                review.state,
                MutationReviewState::PreviewRequiresOwnerApproval
            );
            let line = review.label();
            assert!(line.contains("PREVIEW_REQUIRED"));
            assert!(line.contains("REQUIRES_OWNER_APPROVAL"));
            assert!(line.contains("EXECUTION_RECEIPT_REQUIRED"));
        }
        for page in [ManagerPage::Fleet, ManagerPage::Diagnostics] {
            assert_eq!(
                mutation_review(page, &current(), Some(&snapshot())).state,
                MutationReviewState::ReadOnly
            );
        }
    }

    #[test]
    fn offline_revoked_stop_and_stale_snapshot_block_mutations() {
        let mut offline = current();
        offline.link = LinkState::Offline;
        assert!(matches!(
            mutation_review(ManagerPage::Cores, &offline, None).state,
            MutationReviewState::Blocked("PLATFORM_OFFLINE")
        ));
        let mut revoked = current();
        revoked.link = LinkState::Revoked;
        assert!(matches!(
            mutation_review(ManagerPage::Modules, &revoked, None).state,
            MutationReviewState::Blocked("OWNER_REVOKED")
        ));
        let mut stopped = current();
        stopped.safe = SafeState::StopActive;
        assert!(matches!(
            mutation_review(ManagerPage::Updates, &stopped, None).state,
            MutationReviewState::Blocked("SAFE_STOP_ACTIVE")
        ));
        let mut stale = snapshot();
        stale.freshness = ObservationFreshness::Stale;
        assert!(matches!(
            mutation_review(ManagerPage::Modules, &current(), Some(&stale)).state,
            MutationReviewState::Blocked("MANAGER_OBSERVATION_STALE")
        ));
    }

    #[test]
    fn diagnostics_and_security_are_truthful_about_missing_approvals() {
        let lines = manager_lines(ManagerPage::Security, &current(), Some(&snapshot())).join("\n");
        assert!(lines.contains("APPROVALS: NONE_OBSERVED"));
        assert!(lines.contains("APPROVAL DECISIONS REQUIRE ATTENDED OWNER PROOF"));
        let diagnostics =
            manager_lines(ManagerPage::Diagnostics, &current(), Some(&snapshot())).join("\n");
        assert!(diagnostics.contains("process=OBSERVED"));
        assert!(diagnostics.contains("READ_ONLY"));
        assert!(!diagnostics.contains("VERIFIED_HEALTHY"));
    }
}
