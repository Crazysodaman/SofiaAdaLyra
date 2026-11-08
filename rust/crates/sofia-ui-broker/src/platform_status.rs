//! Display-only module observation model shared by native GUI and TUI.
//! No socket, DB, owner authentication, approval or module execution lives here.
//! The upstream Platform client MUST authenticate the service and freshness
//! before it calls `observe`; a snapshot is never an authorization grant.

use std::collections::BTreeMap;
use std::time::{Duration, Instant};

const MAX_ROWS: usize = 1024;
const MAX_IDENT_BYTES: usize = 160;

fn valid_identifier(raw: &str) -> bool {
    let bytes = raw.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= MAX_IDENT_BYTES
        && bytes[0].is_ascii_alphanumeric()
        && raw.bytes().all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-' | b':' | b'@' | b'/')
        })
}

fn valid_digest(raw: &str) -> bool {
    raw.len() == 64
        && raw
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

/// Installed lifecycle and runtime health must never be collapsed to one flag.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ModuleLifecycle {
    Installed,
    Disabled,
    Activating,
    Active,
    Paused,
    Quarantined,
    Removed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ModuleHealth {
    VerifiedHealthy,
    VerifiedUnhealthy,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ObservationFreshness {
    Fresh,
    Stale,
}

/// Projections come from an authenticated Platform service observer only.
/// Caller-provided strings are display data, not trusted execution authority.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ModuleObservation {
    pub host_id: String,
    pub module_id: String,
    pub platform_generation: u64,
    pub module_generation: u64,
    pub sequence: u64,
    pub package_digest: String,
    pub settings_revision: u64,
    pub lifecycle: ModuleLifecycle,
    pub health: ModuleHealth,
    pub removal_receipt_id: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ModelError {
    UnauthenticatedSource,
    InvalidIdentity,
    MalformedObservation,
    StaleGeneration,
    StaleSequence,
    UnprovenRemoval,
    CapacityExceeded,
}

/// An editor is bound to the exact observed installed module incarnation.
/// This is not a write permission, and a UI can only re-submit after review.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EditSnapshot {
    pub platform_generation: u64,
    pub module_generation: u64,
    pub package_digest: String,
    pub settings_revision: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ModuleRow {
    pub observation: ModuleObservation,
    pub freshness: ObservationFreshness,
    pub last_received_at: Instant,
    pub editing_snapshot: Option<EditSnapshot>,
}

impl ModuleRow {
    /// A stale row is not evidence that a module is connected.
    #[must_use]
    pub fn current_health(&self) -> ModuleHealth {
        if self.freshness == ObservationFreshness::Stale {
            ModuleHealth::Unknown
        } else {
            self.observation.health
        }
    }

    /// Drafts are never silently applied to a changed or unavailable module.
    #[must_use]
    pub fn needs_edit_review(&self) -> bool {
        self.editing_snapshot.as_ref().is_some_and(|original| {
            original.settings_revision != self.observation.settings_revision
                || original.platform_generation != self.observation.platform_generation
                || original.module_generation != self.observation.module_generation
                || original.package_digest != self.observation.package_digest
                || self.freshness != ObservationFreshness::Fresh
                || self.observation.lifecycle != ModuleLifecycle::Active
                || self.current_health() != ModuleHealth::VerifiedHealthy
        })
    }

    /// Pure read-only draft marker. The service still decides edit authority.
    pub fn begin_edit(&mut self) {
        self.editing_snapshot = Some(EditSnapshot {
            platform_generation: self.observation.platform_generation,
            module_generation: self.observation.module_generation,
            package_digest: self.observation.package_digest.clone(),
            settings_revision: self.observation.settings_revision,
        });
    }
}

/// Authority-free, bounded mirror. No database and no service ownership.
/// Both GUI and TUI consume the same monotonic host-specific event stream.
#[derive(Debug, Default)]
pub struct ModuleStatusModel {
    rows: BTreeMap<(String, String), ModuleRow>,
    host_clocks: BTreeMap<String, (u64, u64)>,
}

impl ModuleStatusModel {
    /// # Errors
    /// Fails closed for untrusted source, forged health, unproven removal,
    /// reused generations, non-monotonic streams, and unbounded row counts.
    pub fn observe(
        &mut self,
        incoming: ModuleObservation,
        from_authenticated_service: bool,
    ) -> Result<(), ModelError> {
        if !from_authenticated_service {
            return Err(ModelError::UnauthenticatedSource);
        }
        if !valid_identifier(&incoming.host_id)
            || !valid_identifier(&incoming.module_id)
            || !valid_digest(&incoming.package_digest)
            || incoming.platform_generation == 0
            || incoming.module_generation == 0
            || incoming.sequence == 0
        {
            return Err(ModelError::InvalidIdentity);
        }
        if incoming.health == ModuleHealth::VerifiedHealthy
            && incoming.lifecycle != ModuleLifecycle::Active
        {
            return Err(ModelError::MalformedObservation);
        }
        if incoming.lifecycle == ModuleLifecycle::Removed {
            if incoming
                .removal_receipt_id
                .as_deref()
                .is_none_or(|id| !valid_identifier(id))
            {
                return Err(ModelError::UnprovenRemoval);
            }
        } else if incoming.removal_receipt_id.is_some() {
            return Err(ModelError::MalformedObservation);
        }

        if let Some((generation, sequence)) = self.host_clocks.get(&incoming.host_id) {
            if incoming.platform_generation < *generation {
                return Err(ModelError::StaleGeneration);
            }
            if incoming.platform_generation == *generation && incoming.sequence <= *sequence {
                return Err(ModelError::StaleSequence);
            }
        }
        let key = (incoming.host_id.clone(), incoming.module_id.clone());
        if let Some(existing) = self.rows.get(&key) {
            if incoming.module_generation < existing.observation.module_generation {
                return Err(ModelError::StaleGeneration);
            }
            if existing.observation.lifecycle == ModuleLifecycle::Removed
                && incoming.lifecycle != ModuleLifecycle::Removed
                && incoming.module_generation <= existing.observation.module_generation
            {
                return Err(ModelError::StaleGeneration);
            }
        } else if self.rows.len() >= MAX_ROWS {
            return Err(ModelError::CapacityExceeded);
        }

        // An authenticated host restart invalidates *all* prior live
        // observations for that host. Missing modules become STALE, not REMOVED.
        if let Some((generation, _)) = self.host_clocks.get(&incoming.host_id) {
            if incoming.platform_generation > *generation {
                self.note_disconnect(&incoming.host_id);
            }
        }

        let prior_edit = self
            .rows
            .get(&key)
            .and_then(|row| row.editing_snapshot.clone());
        self.host_clocks.insert(
            incoming.host_id.clone(),
            (incoming.platform_generation, incoming.sequence),
        );
        self.rows.insert(
            key,
            ModuleRow {
                observation: incoming,
                freshness: ObservationFreshness::Fresh,
                last_received_at: Instant::now(),
                editing_snapshot: prior_edit,
            },
        );
        Ok(())
    }

    /// On transport loss, keep installed information but never claim live
    /// health or treat missing heartbeat as a module uninstallation.
    pub fn note_disconnect(&mut self, host_id: &str) {
        for row in self.rows.values_mut() {
            if row.observation.host_id == host_id {
                row.freshness = ObservationFreshness::Stale;
            }
        }
    }

    /// Called by the UI's local monotonic refresh loop. A silent link loss
    /// must not leave old healthy observations looking connected indefinitely.
    /// Backward or uncertain clocks also stale the row rather than extending
    /// its verified health. This never changes installed lifecycle.
    pub fn expire_at(&mut self, now: Instant, max_age: Duration) {
        for row in self.rows.values_mut() {
            if now
                .checked_duration_since(row.last_received_at)
                .is_none_or(|age| age > max_age)
            {
                row.freshness = ObservationFreshness::Stale;
            }
        }
    }

    #[must_use]
    pub fn row(&self, host_id: &str, module_id: &str) -> Option<&ModuleRow> {
        self.rows.get(&(host_id.to_owned(), module_id.to_owned()))
    }

    /// Read-only editable metadata for a current selected module.
    pub fn row_mut(&mut self, host_id: &str, module_id: &str) -> Option<&mut ModuleRow> {
        self.rows
            .get_mut(&(host_id.to_owned(), module_id.to_owned()))
    }

    #[must_use]
    pub fn count(&self) -> usize {
        self.rows.len()
    }
}

#[cfg(test)]
mod tests {
    use super::{
        ModelError, ModuleHealth, ModuleLifecycle, ModuleObservation, ModuleStatusModel,
        ObservationFreshness,
    };

    fn event(module: &str, sequence: u64) -> ModuleObservation {
        ModuleObservation {
            host_id: "host:local".to_owned(),
            module_id: module.to_owned(),
            platform_generation: 1,
            module_generation: 1,
            sequence,
            package_digest: "a".repeat(64),
            settings_revision: 1,
            lifecycle: ModuleLifecycle::Active,
            health: ModuleHealth::VerifiedHealthy,
            removal_receipt_id: None,
        }
    }

    #[test]
    fn connect_disconnect_and_reconnect_preserve_installed_state() {
        let mut model = ModuleStatusModel::default();
        model
            .observe(event("module:one", 1), true)
            .expect("authenticated observation");
        model.note_disconnect("host:local");
        let row = model.row("host:local", "module:one").expect("retained");
        assert_eq!(row.freshness, ObservationFreshness::Stale);
        assert_eq!(row.current_health(), ModuleHealth::Unknown);
        assert_eq!(row.observation.lifecycle, ModuleLifecycle::Active);
        model
            .observe(event("module:one", 2), true)
            .expect("new observation");
        assert_eq!(
            model
                .row("host:local", "module:one")
                .expect("reconnected")
                .current_health(),
            ModuleHealth::VerifiedHealthy,
        );
    }

    #[test]
    fn reject_unauthenticated_or_out_of_order_updates() {
        let mut model = ModuleStatusModel::default();
        assert_eq!(
            model.observe(event("module:one", 1), false),
            Err(ModelError::UnauthenticatedSource),
        );
        model.observe(event("module:one", 3), true).expect("first");
        assert_eq!(
            model.observe(event("module:one", 2), true),
            Err(ModelError::StaleSequence)
        );
        assert_eq!(
            model.observe(event("module:one", 3), true),
            Err(ModelError::StaleSequence)
        );
    }

    #[test]
    fn only_proven_removal_creates_a_tombstone() {
        let mut model = ModuleStatusModel::default();
        model.observe(event("module:one", 1), true).expect("first");
        let mut removed = event("module:one", 2);
        removed.lifecycle = ModuleLifecycle::Removed;
        removed.health = ModuleHealth::Unknown;
        assert_eq!(
            model.observe(removed.clone(), true),
            Err(ModelError::UnprovenRemoval)
        );
        removed.removal_receipt_id = Some("receipt:remove:1".to_owned());
        model.observe(removed, true).expect("verified receipt");
        let prior = event("module:one", 3);
        assert_eq!(model.observe(prior, true), Err(ModelError::StaleGeneration));
        let mut reinstall = event("module:one", 4);
        reinstall.module_generation = 2;
        model.observe(reinstall, true).expect("new generation");
    }

    #[test]
    fn settings_revision_changes_and_disconnect_invalidate_open_editor() {
        let mut model = ModuleStatusModel::default();
        model.observe(event("module:one", 1), true).expect("first");
        model
            .row_mut("host:local", "module:one")
            .expect("selected")
            .begin_edit();
        assert!(!model
            .row("host:local", "module:one")
            .expect("row")
            .needs_edit_review());
        let mut edited = event("module:one", 2);
        edited.settings_revision = 2;
        model.observe(edited, true).expect("new revision");
        assert!(model
            .row("host:local", "module:one")
            .expect("row")
            .needs_edit_review());
        model.note_disconnect("host:local");
        assert!(model
            .row("host:local", "module:one")
            .expect("row")
            .needs_edit_review());
    }

    #[test]
    fn editor_needs_review_after_reinstall_even_when_revision_reused() {
        let mut model = ModuleStatusModel::default();
        model
            .observe(event("module:one", 1), true)
            .expect("initial module");
        model
            .row_mut("host:local", "module:one")
            .expect("editor")
            .begin_edit();

        let mut removed = event("module:one", 2);
        removed.lifecycle = ModuleLifecycle::Removed;
        removed.health = ModuleHealth::Unknown;
        removed.removal_receipt_id = Some("receipt:old".to_owned());
        model
            .observe(removed, true)
            .expect("verified removal event");
        let mut replacement = event("module:one", 3);
        replacement.module_generation = 2;
        // Same settings revision is not authority to reuse a stale draft.
        model.observe(replacement, true).expect("new incarnation");
        assert!(model
            .row("host:local", "module:one")
            .expect("replacement")
            .needs_edit_review());
    }

    #[test]
    fn editor_needs_review_after_signed_package_replacement_or_host_restart() {
        let mut model = ModuleStatusModel::default();
        model
            .observe(event("module:one", 1), true)
            .expect("initial module");
        model
            .row_mut("host:local", "module:one")
            .expect("editor")
            .begin_edit();
        let mut replacement = event("module:one", 2);
        replacement.package_digest = "b".repeat(64);
        model
            .observe(replacement, true)
            .expect("signed package changed");
        assert!(model
            .row("host:local", "module:one")
            .expect("package replacement")
            .needs_edit_review());

        model
            .row_mut("host:local", "module:one")
            .expect("new editor")
            .begin_edit();
        let mut restarted = event("module:one", 1);
        restarted.package_digest = "b".repeat(64);
        restarted.platform_generation = 2;
        model.observe(restarted, true).expect("new host process");
        assert!(model
            .row("host:local", "module:one")
            .expect("restarted")
            .needs_edit_review());
    }

    #[test]
    fn host_restart_stales_other_modules_and_fences_late_generations() {
        let mut model = ModuleStatusModel::default();
        model.observe(event("module:one", 1), true).expect("first");
        model.observe(event("module:two", 2), true).expect("second");
        let mut restart = event("module:one", 1);
        restart.platform_generation = 2;
        model.observe(restart, true).expect("new host generation");
        assert_eq!(
            model
                .row("host:local", "module:two")
                .expect("unchanged module")
                .freshness,
            ObservationFreshness::Stale,
        );
        assert_eq!(
            model.observe(event("module:two", 4), true),
            Err(ModelError::StaleGeneration)
        );
    }

    #[test]
    fn silent_network_loss_expires_live_health_without_uninstalling() {
        use std::time::Duration;
        let mut model = ModuleStatusModel::default();
        model
            .observe(event("module:one", 1), true)
            .expect("initial authenticated status");
        let received = model
            .row("host:local", "module:one")
            .expect("row")
            .last_received_at;
        model.expire_at(received + Duration::from_secs(31), Duration::from_secs(30));
        let row = model
            .row("host:local", "module:one")
            .expect("still installed");
        assert_eq!(row.current_health(), ModuleHealth::Unknown);
        assert_eq!(row.observation.lifecycle, ModuleLifecycle::Active);
        assert_eq!(row.freshness, ObservationFreshness::Stale);

        model
            .observe(event("module:one", 2), true)
            .expect("fresh observed reconnect");
        assert_eq!(
            model
                .row("host:local", "module:one")
                .expect("reconnected")
                .current_health(),
            ModuleHealth::VerifiedHealthy
        );
    }

    #[test]
    fn backward_observer_clock_never_extends_health() {
        use std::time::Duration;
        let mut model = ModuleStatusModel::default();
        model
            .observe(event("module:one", 1), true)
            .expect("initial status");
        let received = model
            .row("host:local", "module:one")
            .expect("row")
            .last_received_at;
        model.expire_at(received - Duration::from_secs(1), Duration::from_secs(30));
        assert_eq!(
            model
                .row("host:local", "module:one")
                .expect("row")
                .current_health(),
            ModuleHealth::Unknown
        );
    }

    #[test]
    fn disabled_module_cannot_claim_verified_running_health() {
        let mut model = ModuleStatusModel::default();
        let mut event = event("module:one", 1);
        event.lifecycle = ModuleLifecycle::Disabled;
        assert_eq!(
            model.observe(event, true),
            Err(ModelError::MalformedObservation)
        );
    }
}
