//! Authority-free R3-R5 desktop broker policy foundation.
//! No OS windows, approval grants, secret access, or canonical state ownership.

use std::collections::BTreeMap;

pub mod journal;

pub const DAILY_AUTONOMOUS_LIMIT: usize = 5;
const MAX_APPEARANCE_ID_BYTES: usize = 256;

/// An IPC-provided identity must never be unbounded, blank, or include
/// control/whitespace characters. These fields are routing identifiers,
/// never OS credentials or owner permission grants.
fn valid_appearance_id(value: &str) -> bool {
    let bytes = value.as_bytes();
    if bytes.is_empty() || bytes.len() > MAX_APPEARANCE_ID_BYTES {
        return false;
    }
    let mut iter = value.bytes();
    iter.next().is_some_and(|byte| byte.is_ascii_alphanumeric())
        && iter.all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-' | b':' | b'@' | b'/')
        })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SlotState {
    Reserved,
    Visible,
    Uncertain,
    Released,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Appearance {
    pub request_id: String,
    pub local_day: String,
    pub host_id: String,
    pub session_id: String,
    pub broker_generation: u64,
    pub state: SlotState,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct OsSignals {
    pub session_locked: bool,
    pub do_not_disturb: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Suppression {
    LockedSession,
    DoNotDisturb,
    HiddenByOwner,
    DailyLimit,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Admission {
    Reserved,
    Duplicate(SlotState),
    Suppressed(Suppression),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BrokerError {
    InvalidIdentity,
    StaleGeneration,
    ClockRollback,
    RequestCollision,
    MissingReservation,
    ReceiptMismatch,
    AlreadyVisible,
}

#[derive(Debug, Clone)]
pub struct BrokerState {
    generation: u64,
    last_accepted_day: String,
    owner_hidden: bool,
    reservations: BTreeMap<String, Appearance>,
}

impl BrokerState {
    /// Construct an isolated broker state; production must restore the durable
    /// reservation ledger before autonomous admission is enabled.
    ///
    /// # Errors
    /// Reject invalid broker generation or malformed calendar day.
    pub fn new(generation: u64, last_accepted_day: String) -> Result<Self, BrokerError> {
        if generation == 0 || !valid_day(&last_accepted_day) {
            return Err(BrokerError::InvalidIdentity);
        }
        Ok(Self {
            generation,
            last_accepted_day,
            owner_hidden: false,
            reservations: BTreeMap::new(),
        })
    }

    /// Recover a complete ledger previously read by a trusted Platform
    /// storage adapter. This function neither loads bytes nor authenticates
    /// the storage source; callers must fail closed if that durable source is
    /// missing, corrupt, or incomplete.
    ///
    /// Any reserved/visible appearance from before restart remains uncertain
    /// and keeps its quota slot. A previous generation can never be used to
    /// claim a new visible receipt, and the watermark cannot move backwards.
    ///
    /// # Errors
    /// Refuses invalid identity/day, impossible future generation, duplicate
    /// request IDs, or a ledger that already exceeds the daily hard limit.
    pub fn restore(
        generation: u64,
        last_accepted_day: String,
        owner_hidden: bool,
        records: Vec<Appearance>,
    ) -> Result<Self, BrokerError> {
        let mut broker = Self::new(generation, last_accepted_day)?;
        broker.owner_hidden = owner_hidden;
        for mut item in records {
            if !valid_appearance_id(&item.request_id)
                || !valid_appearance_id(&item.host_id)
                || !valid_appearance_id(&item.session_id)
                || !valid_day(&item.local_day)
                || item.broker_generation == 0
                || item.broker_generation > generation
            {
                return Err(BrokerError::InvalidIdentity);
            }
            if matches!(item.state, SlotState::Reserved | SlotState::Visible) {
                item.state = SlotState::Uncertain;
            }
            if item.local_day > broker.last_accepted_day {
                broker.last_accepted_day.clone_from(&item.local_day);
            }
            if broker
                .reservations
                .insert(item.request_id.clone(), item)
                .is_some()
            {
                return Err(BrokerError::RequestCollision);
            }
        }
        let mut counts: BTreeMap<&str, usize> = BTreeMap::new();
        for item in broker.reservations.values() {
            if item.state != SlotState::Released {
                let count = counts.entry(item.local_day.as_str()).or_default();
                *count += 1;
                if *count > DAILY_AUTONOMOUS_LIMIT {
                    return Err(BrokerError::InvalidIdentity);
                }
            }
        }
        Ok(broker)
    }

    /// Immutable restored reservation projection for the trusted journal
    /// adapter to persist. This is not authorization to release a slot.
    #[must_use]
    pub fn reservations(&self) -> Vec<Appearance> {
        self.reservations.values().cloned().collect()
    }

    #[must_use]
    pub fn last_accepted_day(&self) -> &str {
        &self.last_accepted_day
    }

    #[must_use]
    pub fn owner_hidden(&self) -> bool {
        self.owner_hidden
    }

    #[must_use]
    pub fn reserved_or_uncertain_count(&self, day: &str) -> usize {
        self.reservations
            .values()
            .filter(|item| {
                item.local_day == day
                    && matches!(
                        item.state,
                        SlotState::Reserved | SlotState::Visible | SlotState::Uncertain
                    )
            })
            .count()
    }

    /// Called only after Platform OS lock/DND observation and admission checks.
    /// Quiet hours intentionally do not suppress this Companion appearance policy.
    ///
    /// # Errors
    /// Reject malformed, collided, stale-generation or rollback-day requests.
    pub fn reserve_autonomous(
        &mut self,
        request: Appearance,
        os: OsSignals,
    ) -> Result<Admission, BrokerError> {
        if !valid_appearance_id(&request.request_id)
            || !valid_appearance_id(&request.host_id)
            || !valid_appearance_id(&request.session_id)
            || !valid_day(&request.local_day)
        {
            return Err(BrokerError::InvalidIdentity);
        }
        if request.broker_generation != self.generation {
            return Err(BrokerError::StaleGeneration);
        }
        if request.local_day < self.last_accepted_day {
            return Err(BrokerError::ClockRollback);
        }
        if let Some(existing) = self.reservations.get(&request.request_id) {
            if existing.host_id != request.host_id
                || existing.session_id != request.session_id
                || existing.local_day != request.local_day
                || existing.broker_generation != request.broker_generation
            {
                return Err(BrokerError::RequestCollision);
            }
            return Ok(Admission::Duplicate(existing.state));
        }
        if os.session_locked {
            return Ok(Admission::Suppressed(Suppression::LockedSession));
        }
        if os.do_not_disturb {
            return Ok(Admission::Suppressed(Suppression::DoNotDisturb));
        }
        if self.owner_hidden {
            return Ok(Admission::Suppressed(Suppression::HiddenByOwner));
        }
        if self.reserved_or_uncertain_count(&request.local_day) >= DAILY_AUTONOMOUS_LIMIT {
            return Ok(Admission::Suppressed(Suppression::DailyLimit));
        }
        self.last_accepted_day.clone_from(&request.local_day);
        self.reservations.insert(
            request.request_id.clone(),
            Appearance {
                state: SlotState::Reserved,
                ..request
            },
        );
        Ok(Admission::Reserved)
    }

    /// The owner-authenticated Platform settings adapter may change this
    /// latch. UI client messages alone must never call this boundary.
    pub fn set_manual_hide(&mut self, hidden: bool) {
        self.owner_hidden = hidden;
    }

    /// Reserve-free manual opening; caller must independently authenticate
    /// the user and enforce OS window lifecycle rules.
    #[must_use]
    pub fn manual_open_allowed(&self, authenticated_user: bool) -> bool {
        authenticated_user
    }

    /// Workbench proposals from Core require a fresh explicit permission.
    /// Opening permission does not authorize any operation within Workbench.
    #[must_use]
    pub fn workbench_open_allowed(origin: WorkbenchOrigin) -> bool {
        matches!(
            origin,
            WorkbenchOrigin::AuthenticatedUser
                | WorkbenchOrigin::CoreProposal {
                    explicit_open_permission: true
                }
        )
    }

    /// Only the Platform observer adapter can produce trusted visible receipts.
    /// This crate does not expose this transition to renderer/IPC clients.
    #[cfg(test)]
    fn mark_visible(
        &mut self,
        request_id: &str,
        host: &str,
        session: &str,
        generation: u64,
    ) -> Result<(), BrokerError> {
        let item = self
            .reservations
            .get_mut(request_id)
            .ok_or(BrokerError::MissingReservation)?;
        if item.host_id != host
            || item.session_id != session
            || item.broker_generation != generation
        {
            return Err(BrokerError::ReceiptMismatch);
        }
        if item.state != SlotState::Reserved {
            return Err(BrokerError::AlreadyVisible);
        }
        item.state = SlotState::Visible;
        Ok(())
    }

    /// A restart cannot silently free an ambiguous attempted appearance.
    ///
    /// # Errors
    /// Reject unknown reservation identifiers.
    pub fn reconcile_uncertain(&mut self, request_id: &str) -> Result<(), BrokerError> {
        let item = self
            .reservations
            .get_mut(request_id)
            .ok_or(BrokerError::MissingReservation)?;
        if matches!(item.state, SlotState::Reserved | SlotState::Visible) {
            item.state = SlotState::Uncertain;
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WorkbenchOrigin {
    AuthenticatedUser,
    CoreProposal { explicit_open_permission: bool },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TrayProjection {
    pub core_connected: bool,
    pub broker_generation: u64,
    pub stop_active: bool,
}

fn valid_day(value: &str) -> bool {
    let b = value.as_bytes();
    if b.len() != 10
        || b[4] != b'-'
        || b[7] != b'-'
        || !b
            .iter()
            .enumerate()
            .all(|(i, byte)| i == 4 || i == 7 || byte.is_ascii_digit())
    {
        return false;
    }
    // Lexicographic rollback protection is sound only for real ISO dates.
    // A bogus future day must not permanently poison the appearance quota.
    let (Ok(year), Ok(month), Ok(day)) = (
        value[..4].parse::<u16>(),
        value[5..7].parse::<u8>(),
        value[8..].parse::<u8>(),
    ) else {
        return false;
    };
    if year == 0 {
        return false;
    }
    let leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    let max_day = match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if leap => 29,
        2 => 28,
        _ => return false,
    };
    (1..=max_day).contains(&day)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn appearance(id: &str, day: &str) -> Appearance {
        Appearance {
            request_id: id.to_owned(),
            local_day: day.to_owned(),
            host_id: "host:venus".into(),
            session_id: "session:owner".into(),
            broker_generation: 7,
            state: SlotState::Reserved,
        }
    }

    const IDLE: OsSignals = OsSignals {
        session_locked: false,
        do_not_disturb: false,
    };

    #[test]
    fn enforces_five_autonomous_appearances_and_idempotency() {
        let mut broker = BrokerState::new(7, "2026-11-04".into()).unwrap();
        for i in 0..DAILY_AUTONOMOUS_LIMIT {
            let item = appearance(&format!("request:{i}"), "2026-11-04");
            assert_eq!(
                broker.reserve_autonomous(item.clone(), IDLE),
                Ok(Admission::Reserved)
            );
            assert_eq!(
                broker.reserve_autonomous(item, IDLE),
                Ok(Admission::Duplicate(SlotState::Reserved))
            );
        }
        assert_eq!(broker.reserved_or_uncertain_count("2026-11-04"), 5);
        assert_eq!(
            broker.reserve_autonomous(appearance("request:extra", "2026-11-04"), IDLE),
            Ok(Admission::Suppressed(Suppression::DailyLimit))
        );
        broker.reconcile_uncertain("request:0").unwrap();
        assert_eq!(broker.reserved_or_uncertain_count("2026-11-04"), 5);
    }

    #[test]
    fn lock_dnd_hide_and_clock_rollback_fail_closed_without_quota_consumption() {
        let mut broker = BrokerState::new(7, "2026-11-04".into()).unwrap();
        assert_eq!(
            broker.reserve_autonomous(
                appearance("request:lock", "2026-11-04"),
                OsSignals {
                    session_locked: true,
                    do_not_disturb: false,
                }
            ),
            Ok(Admission::Suppressed(Suppression::LockedSession))
        );
        assert_eq!(
            broker.reserve_autonomous(
                appearance("request:dnd", "2026-11-04"),
                OsSignals {
                    session_locked: false,
                    do_not_disturb: true,
                }
            ),
            Ok(Admission::Suppressed(Suppression::DoNotDisturb))
        );
        broker.set_manual_hide(true);
        assert_eq!(
            broker.reserve_autonomous(appearance("request:hidden", "2026-11-04"), IDLE),
            Ok(Admission::Suppressed(Suppression::HiddenByOwner))
        );
        assert_eq!(broker.reserved_or_uncertain_count("2026-11-04"), 0);
        broker.set_manual_hide(false);
        assert_eq!(
            broker.reserve_autonomous(appearance("request:backward", "2026-11-03"), IDLE),
            Err(BrokerError::ClockRollback)
        );
    }

    #[test]
    fn observer_receipt_requires_exact_host_session_and_generation() {
        let mut broker = BrokerState::new(7, "2026-11-04".into()).unwrap();
        broker
            .reserve_autonomous(appearance("request:one", "2026-11-04"), IDLE)
            .unwrap();
        assert_eq!(
            broker.mark_visible("request:one", "host:other", "session:owner", 7),
            Err(BrokerError::ReceiptMismatch)
        );
        broker
            .mark_visible("request:one", "host:venus", "session:owner", 7)
            .unwrap();
        assert_eq!(
            broker.mark_visible("request:one", "host:venus", "session:owner", 7),
            Err(BrokerError::AlreadyVisible)
        );
    }

    #[test]
    fn workbench_never_infers_permission_from_a_core_proposal() {
        assert!(BrokerState::workbench_open_allowed(
            WorkbenchOrigin::AuthenticatedUser
        ));
        assert!(!BrokerState::workbench_open_allowed(
            WorkbenchOrigin::CoreProposal {
                explicit_open_permission: false,
            }
        ));
        assert!(BrokerState::workbench_open_allowed(
            WorkbenchOrigin::CoreProposal {
                explicit_open_permission: true,
            }
        ));
        assert!(!BrokerState::new(7, "2026-11-04".into())
            .unwrap()
            .manual_open_allowed(false));
    }

    #[test]
    fn rejects_nonexistent_calendar_days_before_mutating_quota() {
        assert!(valid_day("2028-02-29"));
        assert!(valid_day("2000-02-29"));
        for invalid in [
            "2026-02-29",
            "2100-02-29",
            "2026-04-31",
            "2026-00-10",
            "2026-13-01",
            "2026-11-00",
            "2026-11-32",
            "0000-01-01",
            "2026-1-05",
            "2026-11-0x",
        ] {
            assert!(!valid_day(invalid), "{invalid} must be refused");
        }
        assert_eq!(
            BrokerState::new(7, "9999-99-99".into()).unwrap_err(),
            BrokerError::InvalidIdentity
        );
        let mut broker = BrokerState::new(7, "2026-11-04".into()).unwrap();
        assert_eq!(
            broker.reserve_autonomous(appearance("request:bad", "2026-02-29"), IDLE),
            Err(BrokerError::InvalidIdentity)
        );
        assert_eq!(broker.reserved_or_uncertain_count("2026-11-04"), 0);
        assert_eq!(
            broker.reserve_autonomous(appearance("request:good", "2026-11-04"), IDLE),
            Ok(Admission::Reserved)
        );
    }

    #[test]
    fn malformed_and_unbounded_appearance_ids_never_reserve_quota() {
        let invalid = [
            "",
            " ",
            "host with space",
            "request:\nline",
            "session:\tcontrol",
            "bad?token",
            "é",
        ];
        let mut broker = BrokerState::new(7, "2026-11-04".into()).unwrap();
        for value in invalid {
            for field in 0..3 {
                let mut request = appearance("request:good", "2026-11-04");
                match field {
                    0 => request.request_id = value.into(),
                    1 => request.host_id = value.into(),
                    _ => request.session_id = value.into(),
                }
                assert_eq!(
                    broker.reserve_autonomous(request, IDLE),
                    Err(BrokerError::InvalidIdentity)
                );
            }
        }
        for field in 0..3 {
            let mut request = appearance("request:good", "2026-11-04");
            match field {
                0 => request.request_id = "a".repeat(257),
                1 => request.host_id = "a".repeat(257),
                _ => request.session_id = "a".repeat(257),
            }
            assert_eq!(
                broker.reserve_autonomous(request, IDLE),
                Err(BrokerError::InvalidIdentity)
            );
        }
        assert_eq!(broker.reserved_or_uncertain_count("2026-11-04"), 0);
        assert_eq!(
            broker.reserve_autonomous(appearance("request:good", "2026-11-04"), IDLE),
            Ok(Admission::Reserved)
        );
        assert_eq!(broker.reserved_or_uncertain_count("2026-11-04"), 1);
    }

    #[test]
    fn restored_ledger_preserves_uncertain_quota_and_owner_hide() {
        let mut broker = BrokerState::new(7, "2026-11-04".into()).unwrap();
        for i in 0..DAILY_AUTONOMOUS_LIMIT {
            broker
                .reserve_autonomous(appearance(&format!("request:{i}"), "2026-11-04"), IDLE)
                .unwrap();
        }
        broker
            .mark_visible("request:0", "host:venus", "session:owner", 7)
            .unwrap();
        broker.set_manual_hide(true);
        let persisted = broker.reservations();
        let mut restarted =
            BrokerState::restore(8, "2026-11-03".into(), broker.owner_hidden(), persisted).unwrap();
        assert_eq!(restarted.last_accepted_day(), "2026-11-04");
        assert!(restarted.owner_hidden());
        assert_eq!(restarted.reserved_or_uncertain_count("2026-11-04"), 5);
        assert!(restarted
            .reservations()
            .iter()
            .all(|row| row.state == SlotState::Uncertain));
        assert_eq!(
            restarted.reserve_autonomous(appearance("request:rollback", "2026-11-03"), IDLE),
            Err(BrokerError::StaleGeneration)
        );
        restarted.set_manual_hide(false);
        let mut extra = appearance("request:extra", "2026-11-04");
        extra.broker_generation = 8;
        assert_eq!(
            restarted.reserve_autonomous(extra, IDLE),
            Ok(Admission::Suppressed(Suppression::DailyLimit))
        );
        assert_eq!(restarted.reserved_or_uncertain_count("2026-11-04"), 5);
    }

    #[test]
    fn corrupted_restore_cannot_reset_or_exceed_quota() {
        let item = appearance("request:one", "2026-11-04");
        assert_eq!(
            BrokerState::restore(
                7,
                "2026-11-04".into(),
                false,
                vec![item.clone(), item.clone()],
            )
            .unwrap_err(),
            BrokerError::RequestCollision
        );
        let mut wrong_generation = item.clone();
        wrong_generation.broker_generation = 8;
        assert_eq!(
            BrokerState::restore(7, "2026-11-04".into(), false, vec![wrong_generation])
                .unwrap_err(),
            BrokerError::InvalidIdentity
        );
        let mut malformed = item;
        malformed.host_id = "bad\nidentity".into();
        assert_eq!(
            BrokerState::restore(7, "2026-11-04".into(), false, vec![malformed]).unwrap_err(),
            BrokerError::InvalidIdentity
        );
        let over_limit: Vec<Appearance> = (0..6)
            .map(|i| appearance(&format!("request:{i}"), "2026-11-04"))
            .collect();
        assert_eq!(
            BrokerState::restore(7, "2026-11-04".into(), false, over_limit).unwrap_err(),
            BrokerError::InvalidIdentity
        );
        let mut prior = appearance("request:prior", "2026-11-04");
        prior.broker_generation = 6;
        prior.state = SlotState::Released;
        assert_eq!(
            BrokerState::restore(7, "2026-11-04".into(), false, vec![prior])
                .unwrap()
                .reserved_or_uncertain_count("2026-11-04"),
            0
        );
    }

    #[test]
    fn request_collision_and_wrong_generation_are_rejected() {
        let mut broker = BrokerState::new(7, "2026-11-04".into()).unwrap();
        broker
            .reserve_autonomous(appearance("request:one", "2026-11-04"), IDLE)
            .unwrap();
        let mut collision = appearance("request:one", "2026-11-04");
        collision.session_id = "session:other".into();
        assert_eq!(
            broker.reserve_autonomous(collision, IDLE),
            Err(BrokerError::RequestCollision)
        );
        let mut stale = appearance("request:two", "2026-11-04");
        stale.broker_generation = 6;
        assert_eq!(
            broker.reserve_autonomous(stale, IDLE),
            Err(BrokerError::StaleGeneration)
        );
    }
}
