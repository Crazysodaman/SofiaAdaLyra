//! Typed, authority-free client adapter for the canonical management mutation
//! wire contract.
//!
//! This module frames and validates request syntax and parses correlated
//! replies. It NEVER mints an approval, owner identity, idempotency key,
//! authority, receipt, or success outcome. A caller must supply an approval
//! reference produced by the independently authenticated owner ceremony.
//! Unknown fields, schemas, outcomes and portable-value violations fail closed.
//! Transport composition remains replaceable by the integration owner.

use chrono::{DateTime, Duration, FixedOffset};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sofia_contracts::{parse_strict, ContractError};

pub const MANAGEMENT_MUTATION_SCHEMA: &str = "aegis.platform.management_mutation.v1";
pub const MANAGEMENT_MUTATION_RESPONSE_SCHEMA: &str =
    "aegis.platform.management_mutation-response.v1";
pub const MANAGEMENT_MUTATION_PROTOCOL: &str = "1.0";
pub const MAX_MUTATION_REQUEST_BYTES: usize = 64 * 1024;
pub const MAX_MUTATION_RESPONSE_BYTES: usize = 64 * 1024;
pub const MAX_MUTATION_WINDOW_SECONDS: i64 = 120;
pub const MAX_MUTATION_REPLY_AGE_SECONDS: i64 = 30;
const MAX_EXACT_JSON_INTEGER: u64 = 9_007_199_254_740_991;
const MAX_EXACT_JSON_INTEGER_F64: f64 = 9_007_199_254_740_991.0;
const MAX_PAYLOAD_DEPTH: usize = 8;
const MAX_PAYLOAD_KEYS: usize = 256;
const MAX_PAYLOAD_ARRAY: usize = 1024;

const REQUEST_KEYS: [&str; 13] = [
    "schema",
    "protocol_version",
    "request_id",
    "correlation_id",
    "idempotency_key",
    "target_platform_id",
    "operation",
    "operation_scope",
    "expected_generation",
    "expected_revision",
    "deadline",
    "approval_id",
    "payload",
];

const RESPONSE_KEYS: [&str; 14] = [
    "schema",
    "protocol_version",
    "request_id",
    "correlation_id",
    "idempotency_key",
    "platform_id",
    "operation",
    "outcome",
    "receipt_id",
    "current_generation",
    "current_revision",
    "error_code",
    "detail",
    "observed_at",
];

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum MutationOutcome {
    Succeeded,
    Denied,
    Failed,
    OutcomeUnknown,
}

/// Wire request. Constructing this type does not authenticate the operator,
/// approve an operation, or authorize a service to execute it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ManagementMutationRequest {
    pub schema: String,
    pub protocol_version: String,
    pub request_id: String,
    pub correlation_id: String,
    pub idempotency_key: String,
    pub target_platform_id: String,
    pub operation: String,
    pub operation_scope: String,
    pub expected_generation: u64,
    pub expected_revision: u64,
    pub deadline: String,
    pub approval_id: String,
    pub payload: Value,
}

#[allow(clippy::too_many_arguments)]
impl ManagementMutationRequest {
    /// Frame untrusted request syntax. `approval_id` must already exist.
    ///
    /// # Errors
    /// Rejects invalid IDs, operations, windows and payload projections.
    pub fn new_untrusted(
        request_id: impl Into<String>,
        correlation_id: impl Into<String>,
        idempotency_key: impl Into<String>,
        target_platform_id: impl Into<String>,
        operation: impl Into<String>,
        operation_scope: impl Into<String>,
        expected_generation: u64,
        expected_revision: u64,
        deadline: impl Into<String>,
        approval_id: impl Into<String>,
        payload: Value,
    ) -> Result<Self, ContractError> {
        let request = Self {
            schema: MANAGEMENT_MUTATION_SCHEMA.to_owned(),
            protocol_version: MANAGEMENT_MUTATION_PROTOCOL.to_owned(),
            request_id: request_id.into(),
            correlation_id: correlation_id.into(),
            idempotency_key: idempotency_key.into(),
            target_platform_id: target_platform_id.into(),
            operation: operation.into(),
            operation_scope: operation_scope.into(),
            expected_generation,
            expected_revision,
            deadline: deadline.into(),
            approval_id: approval_id.into(),
            payload,
        };
        request.validate_syntax()?;
        Ok(request)
    }

    /// Parse one bounded wire request, including the current deadline window.
    ///
    /// # Errors
    /// Rejects duplicate/unknown keys, wrong schema/protocol, malformed IDs,
    /// stale or distant deadlines, and unsafe payload projections.
    pub fn parse(raw: &[u8], now: DateTime<FixedOffset>) -> Result<Self, ContractError> {
        if raw.is_empty() || raw.len() > MAX_MUTATION_REQUEST_BYTES {
            return Err(ContractError::new(
                "invalid_management_mutation",
                "request byte size exceeds bound",
            ));
        }
        let value = parse_strict(raw)?;
        require_exact_keys(&value, &REQUEST_KEYS, "request")?;
        let request: Self = serde_json::from_value(value).map_err(|error| {
            ContractError::new("invalid_management_mutation", error.to_string())
        })?;
        request.validate_syntax()?;
        request.validate_deadline(now)?;
        Ok(request)
    }

    /// Encode this request after revalidating its current deadline window.
    ///
    /// # Errors
    /// Rejects invalid syntax or a deadline outside the bounded window.
    pub fn encode(&self, now: DateTime<FixedOffset>) -> Result<Vec<u8>, ContractError> {
        self.validate_syntax()?;
        self.validate_deadline(now)?;
        let raw = serde_json::to_vec(self).map_err(|error| {
            ContractError::new("invalid_management_mutation", error.to_string())
        })?;
        if raw.len() > MAX_MUTATION_REQUEST_BYTES {
            return Err(ContractError::new(
                "invalid_management_mutation",
                "encoded request byte size exceeds bound",
            ));
        }
        Ok(raw)
    }

    fn validate_syntax(&self) -> Result<(), ContractError> {
        if self.schema != MANAGEMENT_MUTATION_SCHEMA
            || self.protocol_version != MANAGEMENT_MUTATION_PROTOCOL
        {
            return Err(ContractError::new(
                "unsupported_management_mutation_schema",
                "mutation protocol version is unsupported",
            ));
        }
        for value in [
            &self.request_id,
            &self.correlation_id,
            &self.idempotency_key,
            &self.target_platform_id,
            &self.operation,
            &self.operation_scope,
            &self.approval_id,
        ] {
            if !valid_id(value) {
                return Err(ContractError::new(
                    "invalid_management_mutation",
                    "mutation request identity is invalid",
                ));
            }
        }
        if self.expected_generation == 0
            || self.expected_generation > MAX_EXACT_JSON_INTEGER
            || self.expected_revision > MAX_EXACT_JSON_INTEGER
        {
            return Err(ContractError::new(
                "invalid_management_mutation",
                "expected generation or revision is outside portable range",
            ));
        }
        if !valid_timestamp_text(&self.deadline) {
            return Err(ContractError::new(
                "invalid_management_mutation",
                "deadline must use canonical RFC3339",
            ));
        }
        safe_payload(&self.payload, 0)
    }

    fn validate_deadline(&self, now: DateTime<FixedOffset>) -> Result<(), ContractError> {
        let deadline = mutation_time(&self.deadline)?;
        if deadline <= now || deadline > now + Duration::seconds(MAX_MUTATION_WINDOW_SECONDS) {
            return Err(ContractError::new(
                "expired_management_mutation",
                "mutation deadline is outside the bounded execution window",
            ));
        }
        Ok(())
    }
}

/// Parsed, correlated reply syntax. Transport authentication is separate and
/// remains the responsibility of the reviewed native client.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ManagementMutationReply {
    pub schema: String,
    pub protocol_version: String,
    pub request_id: String,
    pub correlation_id: String,
    pub idempotency_key: String,
    pub platform_id: String,
    pub operation: String,
    pub outcome: MutationOutcome,
    pub receipt_id: Option<String>,
    pub current_generation: u64,
    pub current_revision: u64,
    pub error_code: Option<String>,
    pub detail: Option<String>,
    pub observed_at: String,
}

impl ManagementMutationReply {
    /// Parse a strict, correlated reply. A valid reply is not an owner grant.
    ///
    /// # Errors
    /// Rejects unknown fields/outcomes, identity or correlation mismatch,
    /// forged success without a receipt, and stale/future observations.
    pub fn parse(
        raw: &[u8],
        expected: &ManagementMutationRequest,
        now: DateTime<FixedOffset>,
    ) -> Result<Self, ContractError> {
        if raw.is_empty() || raw.len() > MAX_MUTATION_RESPONSE_BYTES {
            return Err(ContractError::new(
                "invalid_management_mutation_response",
                "response byte size exceeds bound",
            ));
        }
        let value = parse_strict(raw)?;
        require_exact_keys(&value, &RESPONSE_KEYS, "response")?;
        let reply: Self = serde_json::from_value(value).map_err(|error| {
            ContractError::new("invalid_management_mutation_response", error.to_string())
        })?;
        if reply.schema != MANAGEMENT_MUTATION_RESPONSE_SCHEMA
            || reply.protocol_version != MANAGEMENT_MUTATION_PROTOCOL
            || reply.request_id != expected.request_id
            || reply.correlation_id != expected.correlation_id
            || reply.idempotency_key != expected.idempotency_key
            || reply.platform_id != expected.target_platform_id
            || reply.operation != expected.operation
        {
            return Err(ContractError::new(
                "uncorrelated_management_mutation_response",
                "response identity, correlation or operation mismatch",
            ));
        }
        if reply.current_generation == 0 || reply.current_generation > MAX_EXACT_JSON_INTEGER {
            return Err(ContractError::new(
                "invalid_management_mutation_response",
                "current generation is outside portable range",
            ));
        }
        if reply.current_revision > MAX_EXACT_JSON_INTEGER {
            return Err(ContractError::new(
                "invalid_management_mutation_response",
                "current revision is outside portable range",
            ));
        }
        if reply
            .receipt_id
            .as_deref()
            .is_some_and(|value| !valid_id(value))
            || reply
                .error_code
                .as_deref()
                .is_some_and(|value| !valid_id(value))
        {
            return Err(ContractError::new(
                "invalid_management_mutation_response",
                "receipt or error identity is invalid",
            ));
        }
        if reply
            .detail
            .as_deref()
            .is_some_and(|value| !valid_detail(value))
        {
            return Err(ContractError::new(
                "invalid_management_mutation_response",
                "mutation detail is invalid or unbounded",
            ));
        }
        match reply.outcome {
            MutationOutcome::Succeeded => {
                if reply.receipt_id.is_none() || reply.error_code.is_some() {
                    return Err(ContractError::new(
                        "invalid_management_mutation_response",
                        "SUCCEEDED requires a receipt and no error code",
                    ));
                }
            }
            MutationOutcome::Denied | MutationOutcome::Failed => {
                if reply.error_code.is_none() {
                    return Err(ContractError::new(
                        "invalid_management_mutation_response",
                        "DENIED or FAILED requires a typed error code",
                    ));
                }
            }
            MutationOutcome::OutcomeUnknown => {}
        }
        if !valid_timestamp_text(&reply.observed_at) {
            return Err(ContractError::new(
                "invalid_management_mutation_response",
                "observation must use canonical RFC3339",
            ));
        }
        let observed = mutation_time(&reply.observed_at)?;
        if observed > now || observed < now - Duration::seconds(MAX_MUTATION_REPLY_AGE_SECONDS) {
            return Err(ContractError::new(
                "stale_management_mutation_response",
                "mutation observation is outside the fresh reply window",
            ));
        }
        Ok(reply)
    }
}

/// Replaceable integration seam. This trait performs NO authentication and has
/// no approval, enrollment, discovery or owner-secret methods.
pub trait MutationTransport {
    /// Exchange one framed request for one bounded reply.
    ///
    /// # Errors
    /// Unavailable, offline or rejected native delivery must fail closed.
    fn exchange(&mut self, request_wire: &[u8]) -> Result<Vec<u8>, MutationTransportError>;
}

impl<T: MutationTransport + ?Sized> MutationTransport for &mut T {
    fn exchange(&mut self, request_wire: &[u8]) -> Result<Vec<u8>, MutationTransportError> {
        (**self).exchange(request_wire)
    }
}

impl<T: MutationTransport + ?Sized> MutationTransport for Box<T> {
    fn exchange(&mut self, request_wire: &[u8]) -> Result<Vec<u8>, MutationTransportError> {
        (**self).exchange(request_wire)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MutationTransportError {
    Unavailable,
    Offline,
    Rejected,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MutationClientError {
    InvalidRequest,
    Transport(MutationTransportError),
    InvalidReply,
}

/// Client adapter around a separately composed native transport. It cannot
/// invent a success outcome when the transport fails.
pub struct MutationClient<T: MutationTransport> {
    transport: T,
}

impl<T: MutationTransport> MutationClient<T> {
    #[must_use]
    pub fn new(transport: T) -> Self {
        Self { transport }
    }

    /// Submit one already-approved request and parse only a correlated reply.
    ///
    /// # Errors
    /// Returns no reply on invalid framing, transport failure or invalid reply.
    pub fn submit(
        &mut self,
        request: &ManagementMutationRequest,
        now: DateTime<FixedOffset>,
    ) -> Result<ManagementMutationReply, MutationClientError> {
        self.submit_at(request, now, now)
    }

    /// Submit with a separately sampled reply clock.
    ///
    /// The request deadline is validated against `request_now`, while the
    /// correlated reply freshness is validated against `reply_now` sampled
    /// after the transport exchange. Real transports MUST use this method so a
    /// service observation produced after dispatch is not misclassified as a
    /// future reply.
    ///
    /// # Errors
    /// Returns no reply on invalid framing, transport failure or invalid reply.
    pub fn submit_at(
        &mut self,
        request: &ManagementMutationRequest,
        request_now: DateTime<FixedOffset>,
        reply_now: DateTime<FixedOffset>,
    ) -> Result<ManagementMutationReply, MutationClientError> {
        self.submit_with_clock(request, request_now, || reply_now)
    }

    /// Submit and sample the reply-freshness clock only after the exchange.
    ///
    /// This is the preferred real-transport API: the clock is evaluated after
    /// the bounded reply has been received, so a service observation produced
    /// during dispatch is not misclassified as a future reply.
    ///
    /// # Errors
    /// Returns no reply on invalid framing, transport failure or invalid reply.
    pub fn submit_with_clock<C>(
        &mut self,
        request: &ManagementMutationRequest,
        request_now: DateTime<FixedOffset>,
        reply_clock: C,
    ) -> Result<ManagementMutationReply, MutationClientError>
    where
        C: FnOnce() -> DateTime<FixedOffset>,
    {
        let wire = request
            .encode(request_now)
            .map_err(|_| MutationClientError::InvalidRequest)?;
        let raw = self
            .transport
            .exchange(&wire)
            .map_err(MutationClientError::Transport)?;
        ManagementMutationReply::parse(&raw, request, reply_clock())
            .map_err(|_| MutationClientError::InvalidReply)
    }
}

fn require_exact_keys(value: &Value, expected: &[&str], label: &str) -> Result<(), ContractError> {
    let object = value.as_object().ok_or_else(|| {
        ContractError::new(
            "invalid_management_mutation",
            format!("{label} must be a JSON object"),
        )
    })?;
    if object.len() != expected.len() || expected.iter().any(|key| !object.contains_key(*key)) {
        return Err(ContractError::new(
            "invalid_management_mutation",
            format!("{label} must include exactly the reviewed fields"),
        ));
    }
    Ok(())
}

fn valid_id(value: &str) -> bool {
    let bytes = value.as_bytes();
    if bytes.is_empty() || bytes.len() > 160 {
        return false;
    }
    bytes[0].is_ascii_alphanumeric()
        && bytes.iter().all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-' | b':' | b'@' | b'/')
        })
}

fn valid_detail(value: &str) -> bool {
    value.len() <= 512
        && !value
            .chars()
            .any(|character| character.is_control() || character == '\u{FFFD}')
}

fn valid_timestamp_text(value: &str) -> bool {
    let bytes = value.as_bytes();
    if bytes.len() < 20 || bytes.len() > 32 {
        return false;
    }
    if bytes[4] != b'-'
        || bytes[7] != b'-'
        || bytes[10] != b'T'
        || bytes[13] != b':'
        || bytes[16] != b':'
    {
        return false;
    }
    for index in [0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18] {
        if !bytes[index].is_ascii_digit() {
            return false;
        }
    }
    let mut index = 19;
    if bytes.get(index) == Some(&b'.') {
        index += 1;
        let start = index;
        while bytes.get(index).is_some_and(u8::is_ascii_digit) {
            index += 1;
        }
        let digits = index - start;
        if !(1..=6).contains(&digits) {
            return false;
        }
    }
    match bytes.get(index) {
        Some(b'Z') => index + 1 == bytes.len(),
        Some(b'+' | b'-') => {
            index + 6 == bytes.len()
                && bytes[index + 3] == b':'
                && bytes[index + 1].is_ascii_digit()
                && bytes[index + 2].is_ascii_digit()
                && bytes[index + 4].is_ascii_digit()
                && bytes[index + 5].is_ascii_digit()
        }
        _ => false,
    }
}

fn mutation_time(value: &str) -> Result<DateTime<FixedOffset>, ContractError> {
    if !valid_timestamp_text(value) {
        return Err(ContractError::new(
            "invalid_management_mutation",
            "timestamp must use canonical RFC3339",
        ));
    }
    DateTime::parse_from_rfc3339(value)
        .map_err(|_| ContractError::new("invalid_management_mutation", "invalid timestamp"))
}

fn safe_payload(value: &Value, depth: usize) -> Result<(), ContractError> {
    if depth > MAX_PAYLOAD_DEPTH {
        return Err(ContractError::new(
            "invalid_management_mutation",
            "payload nesting exceeds bound",
        ));
    }
    match value {
        Value::Object(values) => {
            if values.len() > MAX_PAYLOAD_KEYS {
                return Err(ContractError::new(
                    "invalid_management_mutation",
                    "payload has too many keys",
                ));
            }
            for (key, member) in values {
                if !safe_key(key) {
                    return Err(ContractError::new(
                        "invalid_management_mutation",
                        "payload contains unsafe key",
                    ));
                }
                safe_payload(member, depth + 1)?;
            }
        }
        Value::Array(values) => {
            if values.len() > MAX_PAYLOAD_ARRAY {
                return Err(ContractError::new(
                    "invalid_management_mutation",
                    "payload array exceeds bound",
                ));
            }
            for member in values {
                safe_payload(member, depth + 1)?;
            }
        }
        Value::Number(number) => {
            let Some(value) = number.as_f64() else {
                return Err(ContractError::new(
                    "invalid_management_mutation",
                    "unrepresentable payload number",
                ));
            };
            if !value.is_finite() || value.abs() > MAX_EXACT_JSON_INTEGER_F64 {
                return Err(ContractError::new(
                    "invalid_management_mutation",
                    "payload number exceeds portable JSON range",
                ));
            }
        }
        Value::String(value) => {
            if value.chars().any(char::is_control) {
                return Err(ContractError::new(
                    "invalid_management_mutation",
                    "payload string contains control characters",
                ));
            }
        }
        Value::Null | Value::Bool(_) => {}
    }
    Ok(())
}

fn safe_key(key: &str) -> bool {
    let lower = key.to_ascii_lowercase();
    !key.is_empty()
        && key.len() <= 160
        && key.is_ascii()
        && !key.chars().any(char::is_control)
        && !["__proto__", "prototype", "constructor"].contains(&lower.as_str())
        && ![
            "secret",
            "password",
            "credential",
            "access_token",
            "refresh_token",
            "private_key",
            "api_key",
            "owner_proof",
            "authorization",
        ]
        .iter()
        .any(|name| lower.contains(*name))
}

#[cfg(test)]
mod tests {
    use super::{
        ManagementMutationReply, ManagementMutationRequest, MutationClient, MutationClientError,
        MutationOutcome, MutationTransport, MutationTransportError, MANAGEMENT_MUTATION_SCHEMA,
    };
    use serde_json::{json, Value};

    fn now() -> chrono::DateTime<chrono::FixedOffset> {
        chrono::DateTime::parse_from_rfc3339("2026-11-08T04:00:00Z").expect("known test clock")
    }

    fn valid_request() -> ManagementMutationRequest {
        ManagementMutationRequest::new_untrusted(
            "req:mutation:1",
            "corr:1",
            "idem:1",
            "platform:alpha",
            "module.install",
            "host:alpha/module:demo",
            3,
            7,
            "2026-11-08T04:00:30Z",
            "approval:owner:1",
            json!({"package_sha256": "a".repeat(64)}),
        )
        .expect("valid request")
    }

    fn valid_reply_value(request: &ManagementMutationRequest) -> Value {
        json!({
            "schema": "aegis.platform.management_mutation-response.v1",
            "protocol_version": "1.0",
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            "idempotency_key": request.idempotency_key,
            "platform_id": request.target_platform_id,
            "operation": request.operation,
            "outcome": "SUCCEEDED",
            "receipt_id": "receipt:install:1",
            "current_generation": 3,
            "current_revision": 8,
            "error_code": null,
            "detail": null,
            "observed_at": "2026-11-08T03:59:59Z"
        })
    }

    #[test]
    fn valid_request_round_trips_with_strict_syntax() {
        let request = valid_request();
        assert_eq!(request.schema, MANAGEMENT_MUTATION_SCHEMA);
        let raw = request.encode(now()).expect("encode");
        let parsed = ManagementMutationRequest::parse(&raw, now()).expect("parse");
        assert_eq!(parsed, request);
        assert_eq!(parsed.approval_id, "approval:owner:1");
    }

    #[test]
    fn current_protocol_is_accepted_and_unknown_major_or_minor_is_refused() {
        let request = valid_request();
        let raw = request.encode(now()).expect("current protocol encodes");
        assert!(ManagementMutationRequest::parse(&raw, now()).is_ok());

        for protocol in ["1", "1.0.0", "1.1", "2.0", "0.9", "", " 1.0"] {
            let mut value = serde_json::to_value(&request).expect("request value");
            value["protocol_version"] = serde_json::json!(protocol);
            assert!(
                ManagementMutationRequest::parse(value.to_string().as_bytes(), now()).is_err(),
                "protocol {protocol} must be refused"
            );
        }
    }

    #[test]
    fn reply_protocol_is_exact_and_unknown_versions_are_refused() {
        let request = valid_request();
        for protocol in ["1", "1.0.0", "1.1", "2.0"] {
            let mut value = valid_reply_value(&request);
            value["protocol_version"] = serde_json::json!(protocol);
            assert!(
                ManagementMutationReply::parse(value.to_string().as_bytes(), &request, now())
                    .is_err(),
                "reply protocol {protocol} must be refused"
            );
        }
        let value = valid_reply_value(&request);
        assert!(
            ManagementMutationReply::parse(value.to_string().as_bytes(), &request, now()).is_ok()
        );
    }

    #[test]
    fn unknown_duplicate_and_authority_fields_are_denied() {
        let request = valid_request();
        let mut value = serde_json::to_value(&request).expect("request value");
        value["grant"] = json!("self-authorized");
        assert!(ManagementMutationRequest::parse(value.to_string().as_bytes(), now()).is_err());

        let mut value = serde_json::to_value(&request).expect("request value");
        value.as_object_mut().expect("object").remove("approval_id");
        assert!(ManagementMutationRequest::parse(value.to_string().as_bytes(), now()).is_err());

        let duplicate = format!(
            "{{\"schema\":\"{MANAGEMENT_MUTATION_SCHEMA}\",\"schema\":\"{MANAGEMENT_MUTATION_SCHEMA}\"}}"
        );
        assert!(ManagementMutationRequest::parse(duplicate.as_bytes(), now()).is_err());
    }

    #[test]
    fn approval_is_required_and_never_minted() {
        let empty = ManagementMutationRequest::new_untrusted(
            "req:mutation:1",
            "corr:1",
            "idem:1",
            "platform:alpha",
            "core.restart",
            "platform",
            3,
            7,
            "2026-11-08T04:00:30Z",
            "",
            json!({}),
        );
        assert!(empty.is_err());
        let request = valid_request();
        assert!(!request.approval_id.is_empty());
    }

    #[test]
    fn stale_and_distant_deadlines_are_denied() {
        let mut request = valid_request();
        request.deadline = "2026-11-08T03:59:59Z".into();
        assert!(request.encode(now()).is_err());
        request.deadline = "2026-11-08T04:10:00Z".into();
        assert!(request.encode(now()).is_err());
        request.deadline = "2026-11-08T04:00:30.1234567Z".into();
        assert!(request.encode(now()).is_err());
    }

    #[test]
    fn unsafe_payload_projection_is_denied() {
        let base = valid_request();
        for payload in [
            json!({"password": "leak"}),
            json!({"nested": {"owner_secret": "x"}}),
            json!({"value": 9_007_199_254_740_992_u64}),
            json!({"value": "line\nbreak"}),
        ] {
            let mut value = serde_json::to_value(&base).expect("request");
            value["payload"] = payload;
            assert!(ManagementMutationRequest::parse(value.to_string().as_bytes(), now()).is_err());
        }
    }

    #[test]
    fn succeeded_reply_requires_receipt_and_exact_correlation() {
        let request = valid_request();
        let raw = valid_reply_value(&request).to_string();
        let reply = ManagementMutationReply::parse(raw.as_bytes(), &request, now()).expect("reply");
        assert_eq!(reply.outcome, MutationOutcome::Succeeded);
        assert_eq!(reply.current_generation, 3);

        let mut forged = valid_reply_value(&request);
        forged["receipt_id"] = Value::Null;
        assert!(
            ManagementMutationReply::parse(forged.to_string().as_bytes(), &request, now()).is_err()
        );

        let mut forged = valid_reply_value(&request);
        forged["correlation_id"] = json!("corr:other");
        assert!(
            ManagementMutationReply::parse(forged.to_string().as_bytes(), &request, now()).is_err()
        );
    }

    #[test]
    fn unknown_outcomes_fields_and_missing_error_code_are_denied() {
        let request = valid_request();
        for outcome in ["SUCCESS", "OK", "UNKNOWN", "succeeded"] {
            let mut value = valid_reply_value(&request);
            value["outcome"] = json!(outcome);
            assert!(
                ManagementMutationReply::parse(value.to_string().as_bytes(), &request, now())
                    .is_err()
            );
        }
        let mut value = valid_reply_value(&request);
        value["authority"] = json!("owner");
        assert!(
            ManagementMutationReply::parse(value.to_string().as_bytes(), &request, now()).is_err()
        );
        let mut value = valid_reply_value(&request);
        value["outcome"] = json!("DENIED");
        value["receipt_id"] = Value::Null;
        value["error_code"] = Value::Null;
        assert!(
            ManagementMutationReply::parse(value.to_string().as_bytes(), &request, now()).is_err()
        );
    }

    #[test]
    fn denied_failed_and_unknown_outcomes_are_preserved_not_collapsed() {
        let request = valid_request();
        for (outcome, error, receipt) in [
            ("DENIED", Some("NOT_PERMITTED"), None::<&str>),
            ("FAILED", Some("INTERNAL"), None::<&str>),
            ("OUTCOME_UNKNOWN", None::<&str>, None::<&str>),
        ] {
            let mut value = valid_reply_value(&request);
            value["outcome"] = json!(outcome);
            value["error_code"] = json!(error);
            value["receipt_id"] = json!(receipt);
            let reply =
                ManagementMutationReply::parse(value.to_string().as_bytes(), &request, now())
                    .expect("typed reply");
            assert_eq!(reply.error_code.as_deref(), error);
        }
    }

    struct FixedTransport(Result<Vec<u8>, MutationTransportError>);

    impl MutationTransport for FixedTransport {
        fn exchange(&mut self, _request_wire: &[u8]) -> Result<Vec<u8>, MutationTransportError> {
            self.0.clone()
        }
    }

    #[test]
    fn transport_failure_never_fabricates_success() {
        let request = valid_request();
        for failure in [
            MutationTransportError::Unavailable,
            MutationTransportError::Offline,
            MutationTransportError::Rejected,
        ] {
            let mut client = MutationClient::new(FixedTransport(Err(failure)));
            assert_eq!(
                client.submit(&request, now()),
                Err(MutationClientError::Transport(failure))
            );
        }
        let mut client = MutationClient::new(FixedTransport(Ok(Vec::new())));
        assert_eq!(
            client.submit(&request, now()),
            Err(MutationClientError::InvalidReply)
        );
    }

    #[test]
    fn valid_transport_reply_is_parsed_without_granting_authority() {
        let request = valid_request();
        let raw = valid_reply_value(&request).to_string().into_bytes();
        let mut client = MutationClient::new(FixedTransport(Ok(raw)));
        let reply = client.submit(&request, now()).expect("correlated reply");
        assert_eq!(reply.outcome, MutationOutcome::Succeeded);
        assert_eq!(reply.receipt_id.as_deref(), Some("receipt:install:1"));
    }

    #[test]
    fn timestamp_grammar_is_strict() {
        for allowed in [
            "2026-11-08T04:00:00Z",
            "2026-11-08T04:00:00.123456Z",
            "2026-11-08T04:00:00+00:00",
        ] {
            assert!(super::valid_timestamp_text(allowed), "{allowed}");
        }
        for denied in [
            "2026-11-08t04:00:00z",
            "2026-11-08T04:00:00.1234567Z",
            "2026-11-08T04:00:00",
            "2026-11-08T04:00:00+0000",
        ] {
            assert!(!super::valid_timestamp_text(denied), "{denied}");
        }
    }
}
