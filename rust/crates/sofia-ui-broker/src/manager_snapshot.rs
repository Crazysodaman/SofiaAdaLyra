//! Bounded read-only manager snapshot reader over the existing authenticated
//! native management channel.
//!
//! This module performs no authentication itself. Every observation must come
//! from a separately reviewed, peer-bound native client. Unknown shapes,
//! unsupported operations, denials, stale data and inconsistent identities
//! are recorded per page as `NOT_OBSERVED`/`STALE`/`DENIED`/`OFFLINE`/
//! `REVOKED`/`STOP`/`UNKNOWN`. Empty arrays are only legitimate when an
//! authenticated service explicitly answered with an empty list. This module
//! never writes, approves, starts a service or turns a display name into
//! authority.

use crate::control_center_session::ReadFailure;
use crate::manager_views::{
    ApprovalState, ApprovalView, CoreLifecycle, CoreObservation, DiagnosticsObservation, FleetPeer,
    FleetTrust, ManagedHealth, ManagerPage, ManagerSnapshot, ModuleView, SectionTruth,
    SecurityObservation, StartupObservation, StartupState, UpdatesObservation,
};
use crate::platform_status::{ModuleHealth, ModuleLifecycle, ObservationFreshness};
use serde_json::{Map, Value};

/// One already authenticated operation observation. The transport peer/session
/// boundary is responsible for proving the sender before this value exists.
#[derive(Debug, Clone, PartialEq)]
pub struct AuthenticatedObservation {
    pub platform_id: String,
    pub platform_generation: u64,
    pub data: Value,
}

/// Replaceable integration seam. It authenticates nothing by itself.
pub trait AuthenticatedManagerSnapshotSource {
    /// Read one reviewed read-only management operation.
    ///
    /// # Errors
    /// Unavailable, offline, denied, revoked, stopped or stale transport reads
    /// must fail closed rather than return cached or fabricated data.
    fn observe_operation(
        &mut self,
        operation: &str,
    ) -> Result<AuthenticatedObservation, ReadFailure>;
}

impl<T: AuthenticatedManagerSnapshotSource + ?Sized> AuthenticatedManagerSnapshotSource for &mut T {
    fn observe_operation(
        &mut self,
        operation: &str,
    ) -> Result<AuthenticatedObservation, ReadFailure> {
        (**self).observe_operation(operation)
    }
}

pub const MANAGER_OPERATIONS: [(ManagerPage, &str); 6] = [
    (ManagerPage::Cores, "core.list"),
    (ManagerPage::Modules, "module.list"),
    (ManagerPage::Fleet, "fleet.list"),
    (ManagerPage::Security, "security.status"),
    (ManagerPage::Updates, "updates.status"),
    (ManagerPage::Diagnostics, "diagnostics.summary"),
];

const STARTUP_OPERATION: &str = "startup.status";
const REVISION_OPERATION: &str = "jobs.list";

/// Read every manager page independently and retain the honest state of pages
/// that could not be observed.
#[must_use]
pub fn read_manager_snapshot(
    source: &mut (impl AuthenticatedManagerSnapshotSource + ?Sized),
) -> ManagerSnapshot {
    let mut snapshot = ManagerSnapshot::default();
    let startup = source.observe_operation(STARTUP_OPERATION).ok();
    if let Some(observation) = &startup {
        accept_platform_identity(&mut snapshot, observation);
    }
    let mut observed_pages = 0_usize;
    let mut attempted = 0_usize;
    for (page, operation) in MANAGER_OPERATIONS {
        attempted += 1;
        let truth = match source.observe_operation(operation) {
            Ok(observation) => observe_page(&mut snapshot, page, &observation),
            Err(failure) => truth_from_failure(failure),
        };
        if truth == SectionTruth::Observed {
            observed_pages += 1;
        }
        snapshot.mark(page, truth);
    }
    if let Some(observation) = &startup {
        if platform_matches(&snapshot, observation) {
            snapshot.startup = parse_startup(&observation.data);
        }
    }
    if let Ok(observation) = source.observe_operation(REVISION_OPERATION) {
        if platform_matches(&snapshot, &observation) {
            snapshot.platform_revision = observation
                .data
                .get("revision")
                .and_then(Value::as_u64)
                .filter(|revision| *revision > 0);
        }
    }
    snapshot.freshness = if attempted > 0 && observed_pages == attempted {
        ObservationFreshness::Fresh
    } else {
        ObservationFreshness::Stale
    };
    snapshot
}

fn accept_platform_identity(
    snapshot: &mut ManagerSnapshot,
    observation: &AuthenticatedObservation,
) {
    if valid_identifier(&observation.platform_id)
        && observation.platform_generation > 0
        && snapshot.platform_id.is_none()
    {
        snapshot.platform_id = Some(observation.platform_id.clone());
        snapshot.platform_generation = Some(observation.platform_generation);
    }
}

fn observe_page(
    snapshot: &mut ManagerSnapshot,
    page: ManagerPage,
    observation: &AuthenticatedObservation,
) -> SectionTruth {
    if !valid_identifier(&observation.platform_id) || observation.platform_generation == 0 {
        return SectionTruth::Unknown;
    }
    if snapshot.platform_id.is_none() {
        snapshot.platform_id = Some(observation.platform_id.clone());
        snapshot.platform_generation = Some(observation.platform_generation);
    } else if !platform_matches(snapshot, observation) {
        return SectionTruth::Unknown;
    }
    let result = match page {
        ManagerPage::Cores => parse_cores(snapshot, &observation.data),
        ManagerPage::Modules => parse_modules(snapshot, &observation.data),
        ManagerPage::Fleet => parse_fleet(snapshot, &observation.data),
        ManagerPage::Security => parse_security(snapshot, &observation.data),
        ManagerPage::Updates => parse_updates(snapshot, &observation.data),
        ManagerPage::Diagnostics => parse_diagnostics(snapshot, &observation.data),
    };
    if result.is_ok() {
        SectionTruth::Observed
    } else {
        SectionTruth::Unknown
    }
}

fn platform_matches(snapshot: &ManagerSnapshot, observation: &AuthenticatedObservation) -> bool {
    snapshot.platform_id.as_deref() == Some(observation.platform_id.as_str())
        && snapshot.platform_generation == Some(observation.platform_generation)
}

fn truth_from_failure(failure: ReadFailure) -> SectionTruth {
    match failure {
        ReadFailure::Offline => SectionTruth::Offline,
        ReadFailure::Stale => SectionTruth::Stale,
        ReadFailure::Revoked => SectionTruth::Revoked,
        ReadFailure::Stopped => SectionTruth::Stop,
        ReadFailure::Denied => SectionTruth::Denied,
        ReadFailure::Connecting
        | ReadFailure::Unverified
        | ReadFailure::Restarting
        | ReadFailure::UnknownGeneration => SectionTruth::Unknown,
    }
}

fn object(value: &Value) -> Result<&Map<String, Value>, ()> {
    value.as_object().ok_or(())
}

fn array<'a>(data: &'a Map<String, Value>, key: &str) -> Result<&'a [Value], ()> {
    data.get(key)
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .ok_or(())
}

fn required_id(data: &Map<String, Value>, key: &str) -> Result<String, ()> {
    data.get(key)
        .and_then(Value::as_str)
        .filter(|value| valid_identifier(value))
        .map(str::to_owned)
        .ok_or(())
}

fn optional_id(data: &Map<String, Value>, key: &str) -> Result<Option<String>, ()> {
    match data.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(value)) if valid_identifier(value) => Ok(Some(value.clone())),
        _ => Err(()),
    }
}

fn required_u64(data: &Map<String, Value>, key: &str) -> Result<u64, ()> {
    data.get(key)
        .and_then(Value::as_u64)
        .filter(|value| *value <= 9_007_199_254_740_991)
        .ok_or(())
}

fn required_bool(data: &Map<String, Value>, key: &str) -> Result<bool, ()> {
    data.get(key).and_then(Value::as_bool).ok_or(())
}

fn optional_text(data: &Map<String, Value>, key: &str) -> Result<Option<String>, ()> {
    match data.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(value)) if !value.chars().any(char::is_control) => {
            Ok(Some(value.clone()))
        }
        _ => Err(()),
    }
}

fn required_timestamp(data: &Map<String, Value>, key: &str) -> Result<String, ()> {
    optional_text(data, key)?.ok_or(())
}

fn valid_identifier(value: &str) -> bool {
    let bytes = value.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= 160
        && bytes[0].is_ascii_alphanumeric()
        && bytes.iter().all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-' | b':' | b'@' | b'/')
        })
}

fn parse_cores(snapshot: &mut ManagerSnapshot, value: &Value) -> Result<(), ()> {
    let data = object(value)?;
    let cores = array(data, "cores")?;
    if cores.len() > 1024 {
        return Err(());
    }
    let mut parsed = Vec::with_capacity(cores.len());
    for core in cores {
        let core = core.as_object().ok_or(())?;
        parsed.push(parse_core(core)?);
    }
    snapshot.cores = parsed;
    Ok(())
}

fn parse_core(core: &Map<String, Value>) -> Result<CoreObservation, ()> {
    let core_id = required_id(core, "core_id")?;
    let legacy = core.contains_key("lifecycle") || core.contains_key("health");
    if legacy {
        if core.contains_key("installed") || core.contains_key("observed_state") {
            return Err(());
        }
        return Ok(CoreObservation {
            core_id,
            lifecycle: match core.get("lifecycle").and_then(Value::as_str).ok_or(())? {
                "INSTALLED" => CoreLifecycle::Installed,
                "ACTIVE" => CoreLifecycle::Active,
                "PAUSED" => CoreLifecycle::Paused,
                "DISABLED" => CoreLifecycle::Disabled,
                "UNAVAILABLE" => CoreLifecycle::Unavailable,
                _ => return Err(()),
            },
            health: match core.get("health").and_then(Value::as_str).ok_or(())? {
                "VERIFIED_HEALTHY" => ManagedHealth::VerifiedHealthy,
                "VERIFIED_UNHEALTHY" => ManagedHealth::VerifiedUnhealthy,
                "UNKNOWN" => ManagedHealth::Unknown,
                _ => return Err(()),
            },
            generation: required_u64(core, "generation")?,
            source_digest: Some(required_digest(core, "source_digest")?),
            installed: None,
            enabled: None,
            startup_mode: None,
            observed_state: None,
            last_error_code: None,
        });
    }
    if core.len() != 7 {
        return Err(());
    }
    let installed = required_bool(core, "installed")?;
    let enabled = required_bool(core, "enabled")?;
    let startup_mode = required_text(core, "startup_mode")?;
    if !matches!(
        startup_mode.as_str(),
        "on_platform_ready" | "manual" | "on_demand"
    ) {
        return Err(());
    }
    let observed_state = required_text(core, "observed_state")?;
    if !matches!(
        observed_state.as_str(),
        "RUNNING" | "STOPPED" | "STARTING" | "FAILED" | "UNKNOWN" | "NOT_OBSERVED"
    ) {
        return Err(());
    }
    let last_error_code = optional_text(core, "last_error_code")?;
    if last_error_code
        .as_deref()
        .is_some_and(|code| !valid_error_code(code))
    {
        return Err(());
    }
    let lifecycle = if !installed {
        CoreLifecycle::Unavailable
    } else if !enabled {
        CoreLifecycle::Disabled
    } else if observed_state == "RUNNING" {
        CoreLifecycle::Active
    } else {
        CoreLifecycle::Installed
    };
    Ok(CoreObservation {
        core_id,
        lifecycle,
        health: ManagedHealth::Unknown,
        generation: required_u64(core, "generation")?,
        source_digest: None,
        installed: Some(installed),
        enabled: Some(enabled),
        startup_mode: Some(startup_mode),
        observed_state: Some(observed_state),
        last_error_code,
    })
}

fn parse_startup(value: &Value) -> Option<StartupObservation> {
    let data = object(value).ok()?;
    if data.len() != 10
        || ![
            "platform_id",
            "generation",
            "operator_stop",
            "core_started",
            "core_count",
            "active_core_count",
            "startup_state",
            "autostart_enabled_count",
            "autostart_reconciled_at",
            "management_listening",
        ]
        .iter()
        .all(|key| data.contains_key(*key))
    {
        return None;
    }
    let core_count = required_count(data, "core_count").ok()?;
    let active_core_count = required_count(data, "active_core_count").ok()?;
    if active_core_count > core_count {
        return None;
    }
    let startup_state = match data.get("startup_state").and_then(Value::as_str)? {
        "ZERO_CORE_HEALTHY" if core_count == 0 => StartupState::ZeroCoreHealthy,
        "CORES_RUNNING" if active_core_count > 0 => StartupState::CoresRunning,
        "CORES_DISABLED" => StartupState::CoresDisabled,
        "DEGRADED" => StartupState::Degraded,
        "UNKNOWN" => StartupState::Unknown,
        _ => return None,
    };
    let core_started = required_bool(data, "core_started").ok()?;
    if core_count == 0 && (active_core_count != 0 || core_started) {
        return None;
    }
    Some(StartupObservation {
        core_started,
        core_count,
        active_core_count,
        startup_state,
        autostart_enabled_count: required_count(data, "autostart_enabled_count").ok()?,
        autostart_reconciled_at: optional_text(data, "autostart_reconciled_at").ok()?,
        management_listening: required_bool(data, "management_listening").ok()?,
    })
}

fn required_count(data: &Map<String, Value>, key: &str) -> Result<u64, ()> {
    required_u64(data, key).and_then(|value| if value <= 65_535 { Ok(value) } else { Err(()) })
}

fn required_text(data: &Map<String, Value>, key: &str) -> Result<String, ()> {
    optional_text(data, key)?.ok_or(())
}

fn valid_error_code(value: &str) -> bool {
    let bytes = value.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= 80
        && bytes[0].is_ascii_alphanumeric()
        && bytes
            .iter()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(*byte, b'_' | b'.' | b':' | b'-'))
}

fn parse_modules(snapshot: &mut ManagerSnapshot, value: &Value) -> Result<(), ()> {
    let data = object(value)?;
    let modules = array(data, "modules")?;
    if modules.len() > 1024 {
        return Err(());
    }
    let mut parsed = Vec::with_capacity(modules.len());
    for module in modules {
        let module = module.as_object().ok_or(())?;
        parsed.push(ModuleView {
            module_id: required_id(module, "module_id")?,
            lifecycle: match module.get("lifecycle").and_then(Value::as_str).ok_or(())? {
                "INSTALLED" => ModuleLifecycle::Installed,
                "DISABLED" => ModuleLifecycle::Disabled,
                "ACTIVATING" => ModuleLifecycle::Activating,
                "ACTIVE" => ModuleLifecycle::Active,
                "PAUSED" => ModuleLifecycle::Paused,
                "QUARANTINED" => ModuleLifecycle::Quarantined,
                "REMOVED" => ModuleLifecycle::Removed,
                _ => return Err(()),
            },
            health: match module.get("health").and_then(Value::as_str).ok_or(())? {
                "VERIFIED_HEALTHY" => ModuleHealth::VerifiedHealthy,
                "VERIFIED_UNHEALTHY" => ModuleHealth::VerifiedUnhealthy,
                "UNKNOWN" => ModuleHealth::Unknown,
                _ => return Err(()),
            },
            publisher: required_id(module, "publisher")?,
            generation: required_u64(module, "generation")?,
            settings_revision: required_u64(module, "settings_revision")?,
            blocked_reinstall: required_bool(module, "blocked_reinstall")?,
            removal_receipt_id: optional_id(module, "removal_receipt_id")?,
        });
    }
    snapshot.modules = parsed;
    Ok(())
}

fn parse_fleet(snapshot: &mut ManagerSnapshot, value: &Value) -> Result<(), ()> {
    let data = object(value)?;
    let peers = array(data, "peers")?;
    if peers.len() > 1024 {
        return Err(());
    }
    let mut parsed = Vec::with_capacity(peers.len());
    for peer in peers {
        let peer = peer.as_object().ok_or(())?;
        parsed.push(FleetPeer {
            peer_id: required_id(peer, "peer_id")?,
            callsign: optional_text(peer, "callsign")?.unwrap_or_else(|| "UNKNOWN".to_owned()),
            trust: match peer.get("trust").and_then(Value::as_str).ok_or(())? {
                "ENROLLED" => FleetTrust::Enrolled,
                "CANDIDATE" => FleetTrust::Candidate,
                "STALE" => FleetTrust::Stale,
                "UNREACHABLE" => FleetTrust::Unreachable,
                "QUARANTINED" => FleetTrust::Quarantined,
                _ => return Err(()),
            },
            last_observed: required_timestamp(peer, "last_observed")?,
            scope: optional_text(peer, "scope")?.unwrap_or_else(|| "UNKNOWN".to_owned()),
        });
    }
    snapshot.fleet = parsed;
    Ok(())
}

fn parse_security(snapshot: &mut ManagerSnapshot, value: &Value) -> Result<(), ()> {
    let data = object(value)?;
    let approvals = array(data, "approvals")?;
    if approvals.len() > 1024 {
        return Err(());
    }
    let mut parsed = Vec::with_capacity(approvals.len());
    for approval in approvals {
        let approval = approval.as_object().ok_or(())?;
        parsed.push(ApprovalView {
            approval_id: required_id(approval, "approval_id")?,
            operation: required_id(approval, "operation")?,
            state: match approval.get("state").and_then(Value::as_str).ok_or(())? {
                "PENDING" => ApprovalState::Pending,
                "APPROVED" => ApprovalState::Approved,
                "DENIED" => ApprovalState::Denied,
                "EXPIRED" => ApprovalState::Expired,
                "REVOKED" => ApprovalState::Revoked,
                _ => return Err(()),
            },
            expires_at: required_timestamp(approval, "expires_at")?,
        });
    }
    let grants = array(data, "grants")?;
    if grants.len() > 1024 {
        return Err(());
    }
    let mut parsed_grants = Vec::with_capacity(grants.len());
    for grant in grants {
        let grant = grant
            .as_str()
            .filter(|value| valid_identifier(value))
            .ok_or(())?;
        parsed_grants.push(grant.to_owned());
    }
    snapshot.security = Some(SecurityObservation {
        approvals: parsed,
        grants: parsed_grants,
        stop_active: required_bool(data, "stop_active")?,
        revoked: required_bool(data, "revoked")?,
    });
    Ok(())
}

fn parse_updates(snapshot: &mut ManagerSnapshot, value: &Value) -> Result<(), ()> {
    let data = object(value)?;
    snapshot.updates = Some(UpdatesObservation {
        current_release: optional_text(data, "current_release")?,
        available_release: optional_text(data, "available_release")?,
        rollback_eligible: required_bool(data, "rollback_eligible")?,
        staged_receipt: optional_id(data, "staged_receipt")?,
        last_outcome: optional_text(data, "last_outcome")?,
    });
    Ok(())
}

fn parse_diagnostics(snapshot: &mut ManagerSnapshot, value: &Value) -> Result<(), ()> {
    let data = object(value)?;
    let prerequisites = array(data, "missing_prerequisites")?;
    if prerequisites.len() > 1024 {
        return Err(());
    }
    let mut parsed = Vec::with_capacity(prerequisites.len());
    for prerequisite in prerequisites {
        let prerequisite = prerequisite
            .as_str()
            .filter(|value| valid_identifier(value))
            .ok_or(())?;
        parsed.push(prerequisite.to_owned());
    }
    snapshot.diagnostics = Some(DiagnosticsObservation {
        service_id: required_id(data, "service_id")?,
        process_observed: required_bool(data, "process_observed")?,
        release_digest: required_digest(data, "release_digest")?,
        missing_prerequisites: parsed,
        freshness: match data.get("freshness").and_then(Value::as_str).ok_or(())? {
            "FRESH" => ObservationFreshness::Fresh,
            "STALE" => ObservationFreshness::Stale,
            _ => return Err(()),
        },
    });
    Ok(())
}

fn required_digest(data: &Map<String, Value>, key: &str) -> Result<String, ()> {
    let value = data.get(key).and_then(Value::as_str).ok_or(())?;
    if value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        Ok(value.to_owned())
    } else {
        Err(())
    }
}

#[cfg(test)]
mod tests {
    use super::{
        read_manager_snapshot, AuthenticatedManagerSnapshotSource, AuthenticatedObservation,
        MANAGER_OPERATIONS,
    };
    use crate::control_center::{InstallationState, LinkState, PermissionState, SafeState};
    use crate::control_center_session::ReadFailure;
    use crate::manager_views::{
        manager_lines, CoreLifecycle, ManagedHealth, ManagerPage, SectionTruth, StartupState,
    };
    use crate::platform_status::ObservationFreshness;
    use serde_json::json;
    use std::collections::BTreeMap;

    #[derive(Default)]
    struct Fake {
        responses: BTreeMap<&'static str, Result<AuthenticatedObservation, ReadFailure>>,
        calls: Vec<String>,
    }

    impl Fake {
        fn observe(&mut self, operation: &'static str, data: serde_json::Value) -> &mut Self {
            self.responses.insert(
                operation,
                Ok(AuthenticatedObservation {
                    platform_id: "platform:alpha".into(),
                    platform_generation: 9,
                    data,
                }),
            );
            self
        }

        fn fail(&mut self, operation: &'static str, failure: ReadFailure) -> &mut Self {
            self.responses.insert(operation, Err(failure));
            self
        }
    }

    impl AuthenticatedManagerSnapshotSource for Fake {
        fn observe_operation(
            &mut self,
            operation: &str,
        ) -> Result<AuthenticatedObservation, ReadFailure> {
            self.calls.push(operation.to_owned());
            self.responses
                .get(operation)
                .cloned()
                .unwrap_or(Err(ReadFailure::Denied))
        }
    }

    fn full_data() -> Vec<(&'static str, serde_json::Value)> {
        vec![
            (
                "core.list",
                json!({"cores":[{"core_id":"core:primary","lifecycle":"ACTIVE","health":"VERIFIED_HEALTHY","generation":3,"source_digest":"a".repeat(64)}]}),
            ),
            (
                "module.list",
                json!({"modules":[{"module_id":"module:demo","lifecycle":"ACTIVE","health":"VERIFIED_HEALTHY","publisher":"publisher:demo","generation":2,"settings_revision":5,"blocked_reinstall":false,"removal_receipt_id":null}]}),
            ),
            (
                "fleet.list",
                json!({"peers":[{"peer_id":"peer:one","callsign":"One","trust":"CANDIDATE","last_observed":"2026-11-08T04:00:00Z","scope":"local"}]}),
            ),
            (
                "security.status",
                json!({"approvals":[],"grants":[],"stop_active":false,"revoked":false}),
            ),
            (
                "updates.status",
                json!({"current_release":"1.0.0","available_release":null,"rollback_eligible":false,"staged_receipt":null,"last_outcome":null}),
            ),
            (
                "diagnostics.summary",
                json!({"service_id":"service:aegis","process_observed":true,"release_digest":"b".repeat(64),"missing_prerequisites":[],"freshness":"FRESH"}),
            ),
            ("jobs.list", json!({"revision":6})),
        ]
    }

    #[test]
    fn full_authenticated_snapshot_is_fresh_and_carries_exact_target_revision() {
        let mut source = Fake::default();
        for (operation, data) in full_data() {
            source.observe(operation, data);
        }
        let snapshot = read_manager_snapshot(&mut source);
        assert_eq!(snapshot.freshness, ObservationFreshness::Fresh);
        assert_eq!(snapshot.platform_id.as_deref(), Some("platform:alpha"));
        assert_eq!(snapshot.platform_generation, Some(9));
        assert_eq!(snapshot.platform_revision, Some(6));
        for page in ManagerPage::ALL {
            assert_eq!(snapshot.section(page), SectionTruth::Observed, "{page:?}");
        }
        assert_eq!(snapshot.cores.len(), 1);
        assert_eq!(snapshot.modules.len(), 1);
        assert_eq!(snapshot.fleet.len(), 1);
    }

    #[test]
    fn platform_startup_and_core_inventory_are_not_legacy_health_claims() {
        let mut source = Fake::default();
        source.observe(
            "startup.status",
            json!({
                "platform_id": "platform:alpha",
                "generation": 9,
                "operator_stop": false,
                "core_started": false,
                "core_count": 1,
                "active_core_count": 0,
                "startup_state": "CORES_DISABLED",
                "autostart_enabled_count": 0,
                "autostart_reconciled_at": null,
                "management_listening": true
            }),
        );
        source.observe(
            "core.list",
            json!({
                "platform_id": "platform:alpha",
                "generation": 9,
                "operator_stop": false,
                "cores": [{
                    "core_id": "01234567-89ab-cdef-0123-456789abcdef",
                    "installed": true,
                    "enabled": false,
                    "startup_mode": "manual",
                    "observed_state": "STOPPED",
                    "generation": 0,
                    "last_error_code": "OPERATOR_STOP"
                }]
            }),
        );
        let snapshot = read_manager_snapshot(&mut source);
        assert_eq!(snapshot.section(ManagerPage::Cores), SectionTruth::Observed);
        let startup = snapshot
            .startup
            .as_ref()
            .expect("reviewed startup projection");
        assert_eq!(startup.startup_state, StartupState::CoresDisabled);
        assert!(!startup.core_started);
        assert_eq!(startup.active_core_count, 0);
        assert_eq!(snapshot.cores.len(), 1);
        assert_eq!(snapshot.cores[0].lifecycle, CoreLifecycle::Disabled);
        assert_eq!(snapshot.cores[0].health, ManagedHealth::Unknown);
        assert_eq!(snapshot.cores[0].installed, Some(true));
        assert_eq!(snapshot.cores[0].enabled, Some(false));
        assert_eq!(
            snapshot.cores[0].last_error_code.as_deref(),
            Some("OPERATOR_STOP")
        );
        assert!(snapshot.cores[0].source_digest.is_none());
        let mut view = crate::control_center::ControlCenterView::offline();
        view.link = LinkState::Observed;
        view.safe = SafeState::Clear;
        view.permission = PermissionState::MayRequest;
        view.installation = InstallationState::Installed;
        view.platform_generation = Some(9);
        let lines = manager_lines(ManagerPage::Cores, &view, Some(&snapshot)).join("\n");
        assert!(lines.contains("STARTUP: state=CORES_DISABLED"));
        assert!(lines.contains("lifecycle=DISABLED"));
        assert!(lines.contains("health=UNKNOWN"));
        assert!(!lines.contains("VERIFIED_HEALTHY"));
    }

    #[test]
    fn revoked_stop_stale_and_denied_are_retained_per_page_not_collapsed() {
        let mut source = Fake::default();
        source
            .fail("core.list", ReadFailure::Revoked)
            .fail("module.list", ReadFailure::Stopped)
            .fail("fleet.list", ReadFailure::Stale)
            .fail("security.status", ReadFailure::Denied)
            .fail("updates.status", ReadFailure::Offline)
            .fail("diagnostics.summary", ReadFailure::Unverified);
        let snapshot = read_manager_snapshot(&mut source);
        assert_eq!(snapshot.section(ManagerPage::Cores), SectionTruth::Revoked);
        assert_eq!(snapshot.section(ManagerPage::Modules), SectionTruth::Stop);
        assert_eq!(snapshot.section(ManagerPage::Fleet), SectionTruth::Stale);
        assert_eq!(
            snapshot.section(ManagerPage::Security),
            SectionTruth::Denied
        );
        assert_eq!(
            snapshot.section(ManagerPage::Updates),
            SectionTruth::Offline
        );
        assert_eq!(
            snapshot.section(ManagerPage::Diagnostics),
            SectionTruth::Unknown
        );
        assert_eq!(snapshot.freshness, ObservationFreshness::Stale);
        assert!(snapshot.cores.is_empty());
        assert!(snapshot.modules.is_empty());
    }

    #[test]
    fn unobserved_sections_are_not_rendered_as_empty_inventories_or_health() {
        let mut source = Fake::default();
        source.fail("core.list", ReadFailure::Revoked);
        source.fail("module.list", ReadFailure::Stopped);
        source.fail("fleet.list", ReadFailure::Offline);
        source.fail("security.status", ReadFailure::Denied);
        source.fail("updates.status", ReadFailure::Stale);
        source.fail("diagnostics.summary", ReadFailure::Unverified);
        let snapshot = read_manager_snapshot(&mut source);
        let view = crate::control_center::ControlCenterView {
            link: LinkState::Observed,
            safe: SafeState::Clear,
            permission: PermissionState::MayRequest,
            installation: InstallationState::Installed,
            platform_generation: Some(9),
            settings_revision: Some(4),
            effective_settings_revision: Some(4),
            removal_receipt_verified: false,
        };
        for (page, expected) in [
            (ManagerPage::Cores, "CORE MANAGER: REVOKED"),
            (ManagerPage::Modules, "MODULE MANAGER: STOP"),
            (ManagerPage::Fleet, "FLEET MANAGER: OFFLINE"),
            (ManagerPage::Security, "SECURITY AND APPROVALS: DENIED"),
            (ManagerPage::Updates, "UPDATES AND RECOVERY: STALE"),
        ] {
            let lines = manager_lines(page, &view, Some(&snapshot)).join("\n");
            assert!(lines.contains(expected), "{page:?}: {lines}");
            assert!(!lines.contains("NONE_INSTALLED"));
            assert!(!lines.contains("VERIFIED_HEALTHY"));
            assert!(!lines.contains('\x1b'));
        }
    }

    #[test]
    fn malformed_or_mismatched_observations_never_become_success() {
        let mut source = Fake::default();
        for (operation, data) in full_data() {
            source.observe(operation, data);
        }
        source.responses.insert(
            "module.list",
            Ok(AuthenticatedObservation {
                platform_id: "platform:other".into(),
                platform_generation: 9,
                data: json!({"modules":[]}),
            }),
        );
        let snapshot = read_manager_snapshot(&mut source);
        assert_eq!(
            snapshot.section(ManagerPage::Modules),
            SectionTruth::Unknown
        );
        assert_eq!(snapshot.freshness, ObservationFreshness::Stale);
        assert!(snapshot.modules.is_empty());

        let mut malformed = Fake::default();
        for (operation, data) in full_data() {
            malformed.observe(operation, data);
        }
        malformed.responses.insert(
            "core.list",
            Ok(AuthenticatedObservation {
                platform_id: "platform:alpha".into(),
                platform_generation: 9,
                data: json!({"cores":[{"core_id":"core:primary"}]}),
            }),
        );
        let snapshot = read_manager_snapshot(&mut malformed);
        assert_eq!(snapshot.section(ManagerPage::Cores), SectionTruth::Unknown);
        assert!(snapshot.cores.is_empty());
    }

    #[test]
    fn every_reviewed_manager_operation_is_attempted() {
        let mut source = Fake::default();
        for (operation, data) in full_data() {
            source.observe(operation, data);
        }
        let _ = read_manager_snapshot(&mut source);
        for (_, operation) in MANAGER_OPERATIONS {
            assert!(source.calls.iter().any(|call| call == operation));
        }
        assert!(source.calls.iter().any(|call| call == "jobs.list"));
    }
}
