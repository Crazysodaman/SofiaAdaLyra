//! Explicit operator-visible connection distinctions.
//!
//! This model is presentation only. It never authenticates a peer, grants
//! owner permission, starts a service, or makes cached values current.
//! Reconnecting reuses the same client/session and never restarts the process.

use crate::control_center::{ControlCenterView, LinkState};
use crate::control_center_session::ReadFailure;

/// Distinct states an operator must be able to tell apart.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConnectionState {
    Connected,
    Offline,
    Stale,
    Revoked,
    Stop,
    Unknown,
    Unavailable,
}

impl ConnectionState {
    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            Self::Connected => "CONNECTED",
            Self::Offline => "OFFLINE",
            Self::Stale => "STALE",
            Self::Revoked => "REVOKED",
            Self::Stop => "STOP",
            Self::Unknown => "UNKNOWN",
            Self::Unavailable => "UNAVAILABLE",
        }
    }

    #[must_use]
    pub fn is_current(self) -> bool {
        self == Self::Connected
    }

    /// Content-free projection used by stateless CLI/status paths.
    /// OFFLINE is intentionally not inferred without prior contact history;
    /// the stateful model below makes that distinction.
    #[must_use]
    pub fn from_view(view: &ControlCenterView) -> Self {
        match view.link {
            LinkState::Observed => Self::Connected,
            LinkState::Stale => Self::Stale,
            LinkState::Revoked => Self::Revoked,
            LinkState::Stopped => Self::Stop,
            LinkState::Offline => Self::Unavailable,
            LinkState::Connecting
            | LinkState::Unverified
            | LinkState::Restarting
            | LinkState::AccessDenied
            | LinkState::UnknownGeneration => Self::Unknown,
        }
    }
}

/// Stateful connection tracker with explicit reconnect support.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ConnectionStateModel {
    state: ConnectionState,
    ever_connected: bool,
    reconnect_attempts: u64,
}

impl Default for ConnectionStateModel {
    fn default() -> Self {
        Self {
            state: ConnectionState::Unavailable,
            ever_connected: false,
            reconnect_attempts: 0,
        }
    }
}

impl ConnectionStateModel {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    #[must_use]
    pub fn state(&self) -> ConnectionState {
        self.state
    }

    #[must_use]
    pub fn ever_connected(&self) -> bool {
        self.ever_connected
    }

    #[must_use]
    pub fn reconnect_attempts(&self) -> u64 {
        self.reconnect_attempts
    }

    /// Apply an already-validated display link. Cached values are not made
    /// current by this call; only `Connected` means current observation.
    pub fn observe_link(&mut self, link: LinkState) {
        self.state = match link {
            LinkState::Observed => {
                self.ever_connected = true;
                ConnectionState::Connected
            }
            LinkState::Stale => ConnectionState::Stale,
            LinkState::Revoked => ConnectionState::Revoked,
            LinkState::Stopped => ConnectionState::Stop,
            LinkState::Offline if self.ever_connected => ConnectionState::Offline,
            LinkState::Offline => ConnectionState::Unavailable,
            LinkState::Connecting
            | LinkState::Unverified
            | LinkState::Restarting
            | LinkState::AccessDenied
            | LinkState::UnknownGeneration => ConnectionState::Unknown,
        };
    }

    /// Apply a service/display failure without changing the pinned platform
    /// identity or cached lifecycle data.
    pub fn note_failure(&mut self, failure: ReadFailure) {
        self.state = match failure {
            ReadFailure::Stale => ConnectionState::Stale,
            ReadFailure::Revoked => ConnectionState::Revoked,
            ReadFailure::Stopped => ConnectionState::Stop,
            ReadFailure::Offline if self.ever_connected => ConnectionState::Offline,
            ReadFailure::Offline => ConnectionState::Unavailable,
            ReadFailure::Connecting
            | ReadFailure::Unverified
            | ReadFailure::Restarting
            | ReadFailure::Denied
            | ReadFailure::UnknownGeneration => ConnectionState::Unknown,
        };
    }

    /// Begin a fresh read attempt on the same client. This never restarts the
    /// process, clears stored installed state, or upgrades cached values.
    pub fn begin_reconnect(&mut self) {
        self.reconnect_attempts = self.reconnect_attempts.saturating_add(1);
        self.state = if self.ever_connected {
            ConnectionState::Offline
        } else {
            ConnectionState::Unavailable
        };
    }
}

#[cfg(test)]
mod tests {
    use super::{ConnectionState, ConnectionStateModel};
    use crate::control_center::{ControlCenterView, LinkState};
    use crate::control_center_session::ReadFailure;

    #[test]
    fn initial_state_is_unavailable_not_connected_or_offline() {
        let model = ConnectionStateModel::default();
        assert_eq!(model.state(), ConnectionState::Unavailable);
        assert!(!model.state().is_current());
        assert!(!model.ever_connected());
    }

    #[test]
    fn all_explicit_states_are_distinguishable() {
        let labels = [
            ConnectionState::Connected,
            ConnectionState::Offline,
            ConnectionState::Stale,
            ConnectionState::Revoked,
            ConnectionState::Stop,
            ConnectionState::Unknown,
            ConnectionState::Unavailable,
        ]
        .map(ConnectionState::label);
        assert_eq!(
            labels,
            [
                "CONNECTED",
                "OFFLINE",
                "STALE",
                "REVOKED",
                "STOP",
                "UNKNOWN",
                "UNAVAILABLE"
            ]
        );
        assert!(ConnectionState::Connected.is_current());
        for state in [
            ConnectionState::Offline,
            ConnectionState::Stale,
            ConnectionState::Revoked,
            ConnectionState::Stop,
            ConnectionState::Unknown,
            ConnectionState::Unavailable,
        ] {
            assert!(!state.is_current());
        }
    }

    #[test]
    fn observed_connect_and_loss_switch_to_offline_not_unavailable() {
        let mut model = ConnectionStateModel::default();
        model.observe_link(LinkState::Observed);
        assert_eq!(model.state(), ConnectionState::Connected);
        assert!(model.ever_connected());
        model.observe_link(LinkState::Offline);
        assert_eq!(model.state(), ConnectionState::Offline);
        model.note_failure(ReadFailure::Stale);
        assert_eq!(model.state(), ConnectionState::Stale);
        model.observe_link(LinkState::Observed);
        assert_eq!(model.state(), ConnectionState::Connected);
    }

    #[test]
    fn denied_stop_revoked_and_unknown_are_not_collapsed() {
        let mut model = ConnectionStateModel::default();
        model.note_failure(ReadFailure::Revoked);
        assert_eq!(model.state(), ConnectionState::Revoked);
        model.note_failure(ReadFailure::Stopped);
        assert_eq!(model.state(), ConnectionState::Stop);
        model.note_failure(ReadFailure::Denied);
        assert_eq!(model.state(), ConnectionState::Unknown);
        model.note_failure(ReadFailure::UnknownGeneration);
        assert_eq!(model.state(), ConnectionState::Unknown);
        model.observe_link(LinkState::Stale);
        assert_eq!(model.state(), ConnectionState::Stale);
    }

    #[test]
    fn reconnect_reuses_client_without_claiming_current_values() {
        let mut model = ConnectionStateModel::default();
        model.observe_link(LinkState::Observed);
        model.observe_link(LinkState::Stale);
        model.begin_reconnect();
        assert_eq!(model.state(), ConnectionState::Offline);
        assert_eq!(model.reconnect_attempts(), 1);
        assert!(model.ever_connected());
        model.observe_link(LinkState::Observed);
        assert_eq!(model.state(), ConnectionState::Connected);
        assert_eq!(model.reconnect_attempts(), 1);
    }

    #[test]
    fn stateless_projection_never_infers_offline_without_history() {
        let mut view = ControlCenterView::offline();
        assert_eq!(
            ConnectionState::from_view(&view),
            ConnectionState::Unavailable
        );
        view.link = LinkState::Observed;
        assert_eq!(
            ConnectionState::from_view(&view),
            ConnectionState::Connected
        );
        view.link = LinkState::Stopped;
        assert_eq!(ConnectionState::from_view(&view), ConnectionState::Stop);
        view.link = LinkState::Revoked;
        assert_eq!(ConnectionState::from_view(&view), ConnectionState::Revoked);
        view.link = LinkState::Stale;
        assert_eq!(ConnectionState::from_view(&view), ConnectionState::Stale);
        view.link = LinkState::AccessDenied;
        assert_eq!(ConnectionState::from_view(&view), ConnectionState::Unknown);
    }
}
