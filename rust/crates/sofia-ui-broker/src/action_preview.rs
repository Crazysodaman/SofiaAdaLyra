//! Bounded, authority-free operator action preview and submission guard.
//!
//! Flow: select a manager action -> display the exact target Platform,
//! generation, revision and operation -> require a caller-supplied approval ID
//! produced by the independent owner ceremony -> submit one already-approved
//! typed request -> display the typed receipt or denial.
//!
//! This module never mints, guesses or extends approvals, never treats a
//! display name as a target identity, never performs local authorization and
//! never retries blindly after an unknown outcome.

use crate::control_center::{ActionHint, ControlCenterView, ProposedAction};
use crate::management_mutation::{
    ManagementMutationReply, ManagementMutationRequest, MutationClient, MutationClientError,
    MutationOutcome, MutationTransport,
};
use crate::manager_views::{is_current_observation, ManagerPage, ManagerSnapshot, SectionTruth};
use chrono::{DateTime, FixedOffset};
use serde_json::{json, Value};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActionPreviewError {
    ReadOnly,
    Blocked(&'static str),
    NoCurrentObservation,
    SectionNotObserved,
    InvalidTargetIdentity,
    MissingTargetPlatform,
    MissingGeneration,
    MissingRevision,
    InvalidApprovalId,
}

impl ActionPreviewError {
    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            Self::ReadOnly => "READ_ONLY",
            Self::Blocked(reason) => reason,
            Self::NoCurrentObservation => "NO_CURRENT_AUTHENTICATED_OBSERVATION",
            Self::SectionNotObserved => "MANAGER_SECTION_NOT_OBSERVED",
            Self::InvalidTargetIdentity => "INVALID_EXACT_TARGET_IDENTITY",
            Self::MissingTargetPlatform => "TARGET_PLATFORM_NOT_OBSERVED",
            Self::MissingGeneration => "EXPECTED_GENERATION_NOT_OBSERVED",
            Self::MissingRevision => "EXPECTED_REVISION_NOT_OBSERVED",
            Self::InvalidApprovalId => "CALLER_SUPPLIED_APPROVAL_ID_REQUIRED",
        }
    }
}

/// Exact rendered action candidate. Construction performs NO approval or
/// authorization. A display name/callsign is not accepted as the exact target.
#[derive(Debug, Clone, PartialEq)]
pub struct ActionPreview {
    pub page: ManagerPage,
    pub operation: &'static str,
    pub operation_scope: &'static str,
    pub target_platform_id: String,
    pub target_identity: String,
    pub expected_generation: u64,
    pub expected_revision: u64,
    pub payload: Value,
}

impl ActionPreview {
    /// Build a preview only from a current authenticated observation.
    ///
    /// # Errors
    /// Stale, offline, revoked, STOP, denied and unobserved pages are rejected.
    /// The revision must have been observed separately; a settings revision is
    /// not silently substituted for the service mutation revision.
    pub fn prepare(
        page: ManagerPage,
        target_identity: &str,
        payload: Value,
        view: &ControlCenterView,
        snapshot: &ManagerSnapshot,
    ) -> Result<Self, ActionPreviewError> {
        let (operation, operation_scope) = match page {
            ManagerPage::Cores => ("core.restart", "platform"),
            ManagerPage::Modules => ("module.install", "platform"),
            ManagerPage::Security => ("security.approval.request", "owner"),
            ManagerPage::Updates => ("platform.update", "platform"),
            ManagerPage::Fleet | ManagerPage::Diagnostics => {
                return Err(ActionPreviewError::ReadOnly);
            }
        };
        if !is_current_observation(view) {
            return Err(ActionPreviewError::NoCurrentObservation);
        }
        if snapshot.section(page) != SectionTruth::Observed {
            return Err(ActionPreviewError::SectionNotObserved);
        }
        match view.action_hint(proposed_action(page)) {
            ActionHint::Blocked(reason) => return Err(ActionPreviewError::Blocked(reason)),
            ActionHint::ReadOnly => return Err(ActionPreviewError::ReadOnly),
            ActionHint::RecheckWithService => {}
        }
        if !valid_identity(target_identity) {
            return Err(ActionPreviewError::InvalidTargetIdentity);
        }
        let target_platform_id = snapshot
            .platform_id
            .clone()
            .ok_or(ActionPreviewError::MissingTargetPlatform)?;
        let expected_generation = view
            .platform_generation
            .filter(|generation| *generation > 0)
            .ok_or(ActionPreviewError::MissingGeneration)?;
        let expected_revision = snapshot
            .platform_revision
            .ok_or(ActionPreviewError::MissingRevision)?;
        Ok(Self {
            page,
            operation,
            operation_scope,
            target_platform_id,
            target_identity: target_identity.to_owned(),
            expected_generation,
            expected_revision,
            payload,
        })
    }

    /// Display the exact candidate before any approval is attached.
    #[must_use]
    pub fn lines(&self, approval: Option<&CallerApproval>) -> Vec<String> {
        let approval_line = approval.map_or_else(
            || "APPROVAL: NOT_SUPPLIED / CALLER_SUPPLIED_APPROVAL_ID_REQUIRED".to_owned(),
            |approval| {
                format!(
                    "APPROVAL: CALLER_SUPPLIED / ID: {} / NOT_VERIFIED_BY_UI",
                    approval.id()
                )
            },
        );
        vec![
            format!("ACTION PREVIEW: {}", self.operation),
            format!("ACTION SCOPE: {}", self.operation_scope),
            format!("TARGET PLATFORM: {}", self.target_platform_id),
            format!("EXACT TARGET IDENTITY: {}", self.target_identity),
            format!("EXPECTED GENERATION: {}", self.expected_generation),
            format!("EXPECTED REVISION: {}", self.expected_revision),
            approval_line,
            if approval.is_some() {
                "SUBMISSION: READY / SERVICE_RECHECK_REQUIRED / RECEIPT_REQUIRED".to_owned()
            } else {
                "SUBMISSION: BLOCKED / APPROVAL_ID_REQUIRED".to_owned()
            },
            "NO_LOCAL_AUTHORIZATION / NO_APPROVAL_MINTED / DISPLAY_NAME_IS_NOT_AUTHORITY"
                .to_owned(),
        ]
    }

    /// Attach an approval ID supplied by the caller's independent ceremony.
    ///
    /// # Errors
    /// Empty, control-bearing or malformed IDs are rejected. This never creates
    /// or upgrades an approval.
    #[must_use]
    pub fn approve(self, approval: CallerApproval) -> ApprovedAction {
        ApprovedAction {
            preview: self,
            approval,
        }
    }

    /// Build the exact mutation request from caller-supplied correlation IDs.
    ///
    /// # Errors
    /// Identity, scope, revision and deadline syntax remain fail-closed.
    pub fn request<I, C, K>(
        &self,
        request_id: I,
        correlation_id: C,
        idempotency_key: K,
        deadline: &str,
        approval: &CallerApproval,
    ) -> Result<ManagementMutationRequest, ActionPreviewError>
    where
        I: Into<String>,
        C: Into<String>,
        K: Into<String>,
    {
        ManagementMutationRequest::new_untrusted(
            request_id,
            correlation_id,
            idempotency_key,
            self.target_platform_id.clone(),
            self.operation,
            self.operation_scope,
            self.expected_generation,
            self.expected_revision,
            deadline,
            approval.id(),
            self.payload.clone(),
        )
        .map_err(|_| ActionPreviewError::InvalidTargetIdentity)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CallerApproval {
    id: String,
}

impl CallerApproval {
    /// Accept only a non-empty approval reference supplied by the caller.
    ///
    /// # Errors
    /// Blank or malformed approval references are rejected, never repaired.
    pub fn new(id: impl Into<String>) -> Result<Self, ActionPreviewError> {
        let id = id.into();
        if valid_identity(&id) {
            Ok(Self { id })
        } else {
            Err(ActionPreviewError::InvalidApprovalId)
        }
    }

    #[must_use]
    pub fn id(&self) -> &str {
        &self.id
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct ApprovedAction {
    preview: ActionPreview,
    approval: CallerApproval,
}

impl ApprovedAction {
    #[must_use]
    pub fn preview(&self) -> &ActionPreview {
        &self.preview
    }

    #[must_use]
    pub fn approval(&self) -> &CallerApproval {
        &self.approval
    }

    #[must_use]
    pub fn lines(&self) -> Vec<String> {
        self.preview.lines(Some(&self.approval))
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SubmissionOutcome {
    Succeeded {
        receipt_id: String,
        generation: u64,
        revision: u64,
    },
    Denied {
        error_code: String,
        detail: Option<String>,
    },
    Failed {
        error_code: String,
        detail: Option<String>,
    },
    OutcomeUnknown {
        detail: Option<String>,
    },
    NotSubmitted {
        reason: String,
    },
}

impl SubmissionOutcome {
    #[must_use]
    pub fn from_reply(reply: &ManagementMutationReply) -> Self {
        match reply.outcome {
            MutationOutcome::Succeeded => Self::Succeeded {
                receipt_id: reply
                    .receipt_id
                    .clone()
                    .unwrap_or_else(|| "UNVERIFIED".to_owned()),
                generation: reply.current_generation,
                revision: reply.current_revision,
            },
            MutationOutcome::Denied => Self::Denied {
                error_code: reply
                    .error_code
                    .clone()
                    .unwrap_or_else(|| "UNSPECIFIED".to_owned()),
                detail: reply.detail.clone(),
            },
            MutationOutcome::Failed => Self::Failed {
                error_code: reply
                    .error_code
                    .clone()
                    .unwrap_or_else(|| "UNSPECIFIED".to_owned()),
                detail: reply.detail.clone(),
            },
            MutationOutcome::OutcomeUnknown => Self::OutcomeUnknown {
                detail: reply.detail.clone(),
            },
        }
    }

    /// Distinct, ASCII-safe operator lines. Never collapse UNKNOWN to failure.
    #[must_use]
    pub fn lines(&self) -> Vec<String> {
        match self {
            Self::Succeeded {
                receipt_id,
                generation,
                revision,
            } => vec![
                "OUTCOME: SUCCEEDED".to_owned(),
                format!("RECEIPT: {receipt_id}"),
                format!("CURRENT GENERATION: {generation}"),
                format!("CURRENT REVISION: {revision}"),
            ],
            Self::Denied { error_code, detail } => vec![
                "OUTCOME: DENIED".to_owned(),
                format!("ERROR CODE: {error_code}"),
                format!("DETAIL: {}", detail.as_deref().unwrap_or("NONE")),
                "NO_EFFECT_ACKNOWLEDGED_BY_SERVICE / DO_NOT_RETRY_WITHOUT_A_NEW_APPROVAL"
                    .to_owned(),
            ],
            Self::Failed { error_code, detail } => vec![
                "OUTCOME: FAILED".to_owned(),
                format!("ERROR CODE: {error_code}"),
                format!("DETAIL: {}", detail.as_deref().unwrap_or("NONE")),
                "SERVICE_REPORTED_FAILURE / A NEW_APPROVAL_IS_REQUIRED_FOR_ANY_RETRY".to_owned(),
            ],
            Self::OutcomeUnknown { detail } => vec![
                "OUTCOME: UNKNOWN".to_owned(),
                format!("DETAIL: {}", detail.as_deref().unwrap_or("NONE")),
                "RECONCILIATION_REQUIRED / NO_BLIND_RETRY".to_owned(),
            ],
            Self::NotSubmitted { reason } => vec![
                "OUTCOME: NOT_SUBMITTED".to_owned(),
                format!("REASON: {reason}"),
            ],
        }
    }

    #[must_use]
    pub fn is_unknown(&self) -> bool {
        matches!(self, Self::OutcomeUnknown { .. })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SubmissionError {
    BlindRetryRefused,
    DuplicateSubmissionRefused,
    InvalidRequest,
    Transport(crate::management_mutation::MutationTransportError),
    InvalidReply,
}

impl SubmissionError {
    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            Self::BlindRetryRefused => "BLIND_RETRY_REFUSED / RECONCILIATION_REQUIRED",
            Self::DuplicateSubmissionRefused => "DUPLICATE_SUBMISSION_REFUSED",
            Self::InvalidRequest => "INVALID_REQUEST",
            Self::Transport(_) => "TRANSPORT_UNAVAILABLE / OUTCOME_TREATED_AS_UNKNOWN",
            Self::InvalidReply => "INVALID_REPLY / OUTCOME_TREATED_AS_UNKNOWN",
        }
    }
}

/// Per-idempotency submission guard. A transport failure, invalid reply or
/// canonical `OUTCOME_UNKNOWN` permanently (for this session) fences the same
/// idempotency key from an automatic/blind retry.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct MutationSubmission {
    unknown_idempotency_key: Option<String>,
    completed_idempotency_key: Option<String>,
    session_fenced: bool,
}

impl MutationSubmission {
    #[must_use]
    pub fn unknown_key(&self) -> Option<&str> {
        self.unknown_idempotency_key.as_deref()
    }

    #[must_use]
    pub fn completed_key(&self) -> Option<&str> {
        self.completed_idempotency_key.as_deref()
    }

    #[must_use]
    pub fn is_fenced(&self) -> bool {
        self.session_fenced
    }

    /// Clear the unknown-outcome fence only after independent reconciliation
    /// proves the effect state. This method cannot verify that evidence.
    pub fn clear_after_reconciliation(&mut self) {
        self.session_fenced = false;
        self.unknown_idempotency_key = None;
    }

    /// Submit exactly one request. The caller must supply an already-approved
    /// preview request with stable request/correlation/idempotency identifiers.
    ///
    /// # Errors
    /// Refuses blind retry after an unknown outcome and never marks an
    /// unverified transport/reply failure as success.
    pub fn submit<T: MutationTransport>(
        &mut self,
        client: &mut MutationClient<T>,
        request: &ManagementMutationRequest,
        now: DateTime<FixedOffset>,
    ) -> Result<SubmissionOutcome, SubmissionError> {
        self.submit_at(client, request, now, now)
    }

    /// Submit with a separately sampled reply clock. A real native transport
    /// MUST sample `reply_now` after the exchange.
    ///
    /// # Errors
    /// Refuses blind retry after an unknown outcome and never marks an
    /// unverified transport/reply failure as success.
    pub fn submit_at<T: MutationTransport>(
        &mut self,
        client: &mut MutationClient<T>,
        request: &ManagementMutationRequest,
        request_now: DateTime<FixedOffset>,
        reply_now: DateTime<FixedOffset>,
    ) -> Result<SubmissionOutcome, SubmissionError> {
        self.submit_with_clock(client, request, request_now, || reply_now)
    }

    /// Submit and sample the reply clock only after the exchange.
    ///
    /// # Errors
    /// Refuses blind retry after an unknown outcome and never marks an
    /// unverified transport/reply failure as success.
    pub fn submit_with_clock<T: MutationTransport, C>(
        &mut self,
        client: &mut MutationClient<T>,
        request: &ManagementMutationRequest,
        request_now: DateTime<FixedOffset>,
        reply_clock: C,
    ) -> Result<SubmissionOutcome, SubmissionError>
    where
        C: FnOnce() -> DateTime<FixedOffset>,
    {
        if self.session_fenced {
            return Err(SubmissionError::BlindRetryRefused);
        }
        if self.unknown_idempotency_key.as_deref() == Some(request.idempotency_key.as_str()) {
            return Err(SubmissionError::BlindRetryRefused);
        }
        if self.completed_idempotency_key.as_deref() == Some(request.idempotency_key.as_str()) {
            return Err(SubmissionError::DuplicateSubmissionRefused);
        }
        match client.submit_with_clock(request, request_now, reply_clock) {
            Ok(reply) => {
                let outcome = SubmissionOutcome::from_reply(&reply);
                if outcome.is_unknown() {
                    self.session_fenced = true;
                    self.unknown_idempotency_key = Some(request.idempotency_key.clone());
                } else {
                    self.completed_idempotency_key = Some(request.idempotency_key.clone());
                }
                Ok(outcome)
            }
            Err(MutationClientError::InvalidRequest) => Err(SubmissionError::InvalidRequest),
            Err(MutationClientError::Transport(error)) => {
                // The request may have reached the service before the channel
                // failed. Treat it as unknown, never as safely retryable.
                self.session_fenced = true;
                self.unknown_idempotency_key = Some(request.idempotency_key.clone());
                Err(SubmissionError::Transport(error))
            }
            Err(MutationClientError::InvalidReply) => {
                self.session_fenced = true;
                self.unknown_idempotency_key = Some(request.idempotency_key.clone());
                Err(SubmissionError::InvalidReply)
            }
        }
    }
}

fn proposed_action(page: ManagerPage) -> ProposedAction {
    match page {
        ManagerPage::Cores => ProposedAction::RestartCore,
        ManagerPage::Modules => ProposedAction::InstallModule,
        ManagerPage::Fleet | ManagerPage::Diagnostics => ProposedAction::Inspect,
        ManagerPage::Security => ProposedAction::RequestApproval,
        ManagerPage::Updates => ProposedAction::UpdatePlatform,
    }
}

fn valid_identity(value: &str) -> bool {
    let bytes = value.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= 160
        && bytes[0].is_ascii_alphanumeric()
        && bytes.iter().all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-' | b':' | b'@' | b'/')
        })
}

/// Preview context for a page without claiming an exact selectable target.
#[must_use]
pub fn context_lines(
    page: ManagerPage,
    view: &ControlCenterView,
    snapshot: &ManagerSnapshot,
) -> Vec<String> {
    let operation = match page {
        ManagerPage::Cores => "core.restart",
        ManagerPage::Modules => "module.install",
        ManagerPage::Fleet => "fleet.inspect",
        ManagerPage::Security => "security.approval.request",
        ManagerPage::Updates => "platform.update",
        ManagerPage::Diagnostics => "diagnostics.inspect",
    };
    vec![
        format!("ACTION PREVIEW CONTEXT: {operation}"),
        format!(
            "EXACT TARGET PLATFORM: {}",
            snapshot.platform_id.as_deref().unwrap_or("NOT_OBSERVED")
        ),
        format!(
            "EXPECTED GENERATION: {}",
            view.platform_generation
                .map_or_else(|| "NOT_OBSERVED".to_owned(), |value| value.to_string())
        ),
        format!(
            "EXPECTED REVISION: {}",
            snapshot
                .platform_revision
                .map_or_else(|| "NOT_OBSERVED".to_owned(), |value| value.to_string())
        ),
        format!(
            "TARGET IDENTITY: {}",
            if page == ManagerPage::Fleet || page == ManagerPage::Diagnostics {
                "READ_ONLY_NO_TARGET"
            } else {
                "SELECT_EXACT_TARGET_ID / DISPLAY_NAME_IS_NOT_AUTHORITY"
            }
        ),
        "APPROVAL: CALLER_SUPPLIED_APPROVAL_ID_REQUIRED / NOT_MINTED_BY_UI".to_owned(),
    ]
}

/// Sample payload builder for the bounded operator preview. It does not encode
/// any operation-specific authority and is never sent until approval exists.
#[must_use]
pub fn empty_payload() -> Value {
    json!({})
}

#[cfg(test)]
mod tests {
    use super::{
        empty_payload, ActionPreview, ActionPreviewError, CallerApproval, MutationSubmission,
        SubmissionError, SubmissionOutcome,
    };
    use crate::control_center::{
        ControlCenterView, InstallationState, LinkState, PermissionState, SafeState,
    };
    use crate::management_mutation::{
        ManagementMutationReply, ManagementMutationRequest, MutationClient, MutationOutcome,
        MutationTransport, MutationTransportError,
    };
    use crate::manager_views::{ManagerPage, ManagerSnapshot, SectionTruth};
    use crate::platform_status::ObservationFreshness;
    use chrono::{DateTime, FixedOffset};
    use serde_json::{json, Value};

    fn now() -> DateTime<FixedOffset> {
        DateTime::parse_from_rfc3339("2026-11-08T04:00:00Z").expect("clock")
    }

    fn view() -> ControlCenterView {
        ControlCenterView {
            link: LinkState::Observed,
            safe: SafeState::Clear,
            permission: PermissionState::MayRequest,
            installation: InstallationState::Absent,
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
            sections: ManagerPage::ALL
                .iter()
                .copied()
                .map(|page| (page, SectionTruth::Observed))
                .collect(),
            ..ManagerSnapshot::default()
        }
    }

    fn preview() -> ActionPreview {
        ActionPreview::prepare(
            ManagerPage::Modules,
            "module:demo",
            empty_payload(),
            &view(),
            &snapshot(),
        )
        .expect("preview")
    }

    fn request(preview: &ActionPreview, approval: &CallerApproval) -> ManagementMutationRequest {
        preview
            .request(
                "req:mutation:42",
                "corr:42",
                "idem:42",
                "2026-11-08T04:00:30Z",
                approval,
            )
            .expect("request")
    }

    fn reply(request: &ManagementMutationRequest, outcome: &str) -> Vec<u8> {
        json!({
            "schema": "aegis.platform.management_mutation-response.v1",
            "protocol_version": "1.0",
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            "idempotency_key": request.idempotency_key,
            "platform_id": request.target_platform_id,
            "operation": request.operation,
            "outcome": outcome,
            "receipt_id": if outcome == "SUCCEEDED" { json!("receipt:one") } else { Value::Null },
            "current_generation": 9,
            "current_revision": 7,
            "error_code": if outcome == "SUCCEEDED" { Value::Null } else { json!("HANDLER_FAILED") },
            "detail": null,
            "observed_at": "2026-11-08T04:00:00Z"
        })
        .to_string()
        .into_bytes()
    }

    #[test]
    fn preview_shows_exact_target_generation_revision_operation_and_requires_approval() {
        let modest = preview();
        let lines = modest.lines(None).join("\n");
        assert!(lines.contains("ACTION PREVIEW: module.install"));
        assert!(lines.contains("TARGET PLATFORM: platform:alpha"));
        assert!(lines.contains("EXACT TARGET IDENTITY: module:demo"));
        assert!(lines.contains("EXPECTED GENERATION: 9"));
        assert!(lines.contains("EXPECTED REVISION: 6"));
        assert!(lines.contains("APPROVAL: NOT_SUPPLIED"));
        assert!(lines.contains("SUBMISSION: BLOCKED / APPROVAL_ID_REQUIRED"));
        assert!(lines.contains("NO_LOCAL_AUTHORIZATION"));
        assert!(lines.contains("DISPLAY_NAME_IS_NOT_AUTHORITY"));
        assert!(!lines.contains('\x1b'));

        let approval = CallerApproval::new("approval:owner:1").expect("caller approval");
        let approved = modest.approve(approval);
        let lines = approved.lines().join("\n");
        assert!(lines.contains("APPROVAL: CALLER_SUPPLIED"));
        assert!(lines.contains("SUBMISSION: READY"));
    }

    #[test]
    fn preview_rejects_stale_unobserved_and_unknown_revision_states() {
        assert_eq!(
            ActionPreview::prepare(
                ManagerPage::Modules,
                "module:demo",
                empty_payload(),
                &ControlCenterView::offline(),
                &snapshot()
            ),
            Err(ActionPreviewError::NoCurrentObservation)
        );
        let mut stale = snapshot();
        stale.freshness = ObservationFreshness::Stale;
        stale.mark(ManagerPage::Modules, SectionTruth::Stale);
        assert_eq!(
            ActionPreview::prepare(
                ManagerPage::Modules,
                "module:demo",
                empty_payload(),
                &view(),
                &stale
            ),
            Err(ActionPreviewError::SectionNotObserved)
        );
        let mut no_revision = snapshot();
        no_revision.platform_revision = None;
        assert_eq!(
            ActionPreview::prepare(
                ManagerPage::Modules,
                "module:demo",
                empty_payload(),
                &view(),
                &no_revision
            ),
            Err(ActionPreviewError::MissingRevision)
        );
        assert_eq!(
            ActionPreview::prepare(
                ManagerPage::Modules,
                "Friendly Display Name",
                empty_payload(),
                &view(),
                &snapshot()
            ),
            Err(ActionPreviewError::InvalidTargetIdentity)
        );
        for page in [ManagerPage::Fleet, ManagerPage::Diagnostics] {
            assert_eq!(
                ActionPreview::prepare(page, "peer:one", empty_payload(), &view(), &snapshot()),
                Err(ActionPreviewError::ReadOnly)
            );
        }
    }

    #[test]
    fn approval_id_must_be_caller_supplied_and_valid() {
        for blank in ["", " ", "\n", "display name"] {
            assert_eq!(
                CallerApproval::new(blank),
                Err(ActionPreviewError::InvalidApprovalId)
            );
        }
        let approval = CallerApproval::new("approval:owner:1").expect("approval");
        let request = request(&preview(), &approval);
        assert_eq!(request.approval_id, "approval:owner:1");
        assert_eq!(request.request_id, "req:mutation:42");
        assert_eq!(request.correlation_id, "corr:42");
        assert_eq!(request.idempotency_key, "idem:42");
        assert_eq!(request.expected_generation, 9);
        assert_eq!(request.expected_revision, 6);
    }

    #[derive(Clone)]
    struct FixedTransport {
        reply: Result<Vec<u8>, MutationTransportError>,
        calls: std::rc::Rc<std::cell::Cell<u32>>,
    }

    impl MutationTransport for FixedTransport {
        fn exchange(&mut self, _request_wire: &[u8]) -> Result<Vec<u8>, MutationTransportError> {
            self.calls.set(self.calls.get() + 1);
            self.reply.clone()
        }
    }

    #[test]
    fn successful_reply_is_distinct_and_reports_receipt() {
        let approval = CallerApproval::new("approval:owner:1").expect("approval");
        let request = request(&preview(), &approval);
        let calls = std::rc::Rc::new(std::cell::Cell::new(0));
        let mut client = MutationClient::new(FixedTransport {
            reply: Ok(reply(&request, "SUCCEEDED")),
            calls: calls.clone(),
        });
        let mut submission = MutationSubmission::default();
        let outcome = submission
            .submit(&mut client, &request, now())
            .expect("outcome");
        assert!(
            matches!(outcome, SubmissionOutcome::Succeeded { ref receipt_id, .. } if receipt_id == "receipt:one")
        );
        assert_eq!(calls.get(), 1);
        assert_eq!(submission.completed_key(), Some("idem:42"));
        assert!(outcome.lines().join("\n").contains("OUTCOME: SUCCEEDED"));
        assert_eq!(
            submission.submit(&mut client, &request, now()),
            Err(SubmissionError::DuplicateSubmissionRefused)
        );
        assert_eq!(calls.get(), 1);
    }

    #[test]
    fn denied_failed_and_unknown_are_surfaced_distinctly() {
        for (wire, marker) in [
            ("DENIED", "OUTCOME: DENIED"),
            ("FAILED", "OUTCOME: FAILED"),
            ("OUTCOME_UNKNOWN", "OUTCOME: UNKNOWN"),
        ] {
            let approval = CallerApproval::new("approval:owner:1").expect("approval");
            let request = request(&preview(), &approval);
            let mut client = MutationClient::new(FixedTransport {
                reply: Ok(reply(&request, wire)),
                calls: std::rc::Rc::new(std::cell::Cell::new(0)),
            });
            let mut submission = MutationSubmission::default();
            let outcome = submission
                .submit(&mut client, &request, now())
                .expect("outcome");
            assert!(outcome.lines().join("\n").contains(marker), "{wire}");
        }
    }

    #[test]
    fn unknown_outcome_and_transport_failure_never_allow_blind_retry() {
        let approval = CallerApproval::new("approval:owner:1").expect("approval");
        let request = request(&preview(), &approval);

        let calls = std::rc::Rc::new(std::cell::Cell::new(0));
        let mut client = MutationClient::new(FixedTransport {
            reply: Ok(reply(&request, "OUTCOME_UNKNOWN")),
            calls: calls.clone(),
        });
        let mut submission = MutationSubmission::default();
        assert_eq!(
            submission.submit(&mut client, &request, now()),
            Ok(SubmissionOutcome::OutcomeUnknown { detail: None })
        );
        assert_eq!(submission.unknown_key(), Some("idem:42"));
        assert!(submission.is_fenced());
        assert_eq!(
            submission.submit(&mut client, &request, now()),
            Err(SubmissionError::BlindRetryRefused)
        );
        let different_key = preview()
            .request(
                "req:mutation:other",
                "corr:other",
                "idem:other",
                "2026-11-08T04:00:30Z",
                &approval,
            )
            .expect("different request");
        assert_eq!(
            submission.submit(&mut client, &different_key, now()),
            Err(SubmissionError::BlindRetryRefused)
        );
        assert_eq!(calls.get(), 1);
        submission.clear_after_reconciliation();
        assert!(!submission.is_fenced());

        let transport_calls = std::rc::Rc::new(std::cell::Cell::new(0));
        let mut failed = MutationClient::new(FixedTransport {
            reply: Err(MutationTransportError::Offline),
            calls: transport_calls.clone(),
        });
        let mut submission = MutationSubmission::default();
        assert_eq!(
            submission.submit(&mut failed, &request, now()),
            Err(SubmissionError::Transport(MutationTransportError::Offline))
        );
        assert_eq!(submission.unknown_key(), Some("idem:42"));
        assert_eq!(
            submission.submit(&mut failed, &request, now()),
            Err(SubmissionError::BlindRetryRefused)
        );
        assert_eq!(transport_calls.get(), 1);
    }

    #[test]
    fn no_local_approval_or_authority_is_minted() {
        let lines = preview().lines(None).join("\n");
        assert!(!lines.contains("AUTHORIZED"));
        assert!(lines.contains("NO_APPROVAL_MINTED") || lines.contains("NOT_MINTED_BY_UI"));
        assert_eq!(
            CallerApproval::new(""),
            Err(ActionPreviewError::InvalidApprovalId)
        );
    }

    #[test]
    fn reply_outcomes_are_never_collapsed() {
        let approval = CallerApproval::new("approval:owner:1").expect("approval");
        let request = request(&preview(), &approval);
        for (wire, expected) in [
            ("SUCCEEDED", MutationOutcome::Succeeded),
            ("DENIED", MutationOutcome::Denied),
            ("FAILED", MutationOutcome::Failed),
            ("OUTCOME_UNKNOWN", MutationOutcome::OutcomeUnknown),
        ] {
            let raw = reply(&request, wire);
            let parsed = ManagementMutationReply::parse(&raw, &request, now()).expect("reply");
            assert_eq!(parsed.outcome, expected);
        }
    }
}
