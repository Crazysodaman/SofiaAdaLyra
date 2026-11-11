//! Untrusted Fleet admission wire syntax shared by native Platform clients.
//!
//! This module does not authenticate a candidate, verify a signature, or grant
//! trust. The Platform service must independently verify installation
//! provenance, the owner-established autonomy policy and current revocation
//! before any Fleet mutation.

use crate::{parse_strict, ContractError};
use chrono::{DateTime, Duration, FixedOffset};
use regex::Regex;
use serde::Deserialize;
use std::sync::OnceLock;

pub const FLEET_ADMISSION_SCHEMA: &str = "aegis.platform.fleet.admission.v1";
pub const FLEET_ADMISSION_PROTOCOL: &str = "1.0";
pub const FLEET_ADMISSION_MAX_INITIAL_PERMISSION: u8 = 3;

#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UntrustedFleetAdmissionRequest {
    pub schema: String,
    pub protocol: String,
    pub request_id: String,
    pub target_platform_id: String,
    pub expected_generation: u64,
    pub operation: String,
    pub candidate_host_id: String,
    pub candidate_node_id: String,
    pub candidate_public_key_sha256: String,
    pub installation_identity_id: String,
    pub signer_key_id: String,
    pub policy_id: String,
    pub policy_revision: u64,
    pub requested_role: String,
    pub initial_permission_level: u8,
    pub created_at: String,
    pub deadline: String,
}

fn id_regex() -> &'static Regex {
    static VALUE: OnceLock<Regex> = OnceLock::new();
    VALUE.get_or_init(|| {
        Regex::new(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$").expect("constant regex")
    })
}

fn digest_regex() -> &'static Regex {
    static VALUE: OnceLock<Regex> = OnceLock::new();
    VALUE.get_or_init(|| Regex::new(r"^[0-9a-f]{64}$").expect("constant regex"))
}

fn uuid_regex() -> &'static Regex {
    static VALUE: OnceLock<Regex> = OnceLock::new();
    VALUE.get_or_init(|| {
        Regex::new(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
            .expect("constant regex")
    })
}

fn time_regex() -> &'static Regex {
    static VALUE: OnceLock<Regex> = OnceLock::new();
    VALUE.get_or_init(|| {
        Regex::new(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$")
            .expect("constant regex")
    })
}

fn management_time(value: &str) -> Result<DateTime<FixedOffset>, ContractError> {
    if !time_regex().is_match(value) {
        return Err(ContractError::new(
            "invalid_fleet_admission",
            "timestamp must use canonical RFC3339 with <= 6 digits",
        ));
    }
    DateTime::parse_from_rfc3339(value)
        .map_err(|_| ContractError::new("invalid_fleet_admission", "invalid timestamp"))
}

impl UntrustedFleetAdmissionRequest {
    /// Parse untrusted admission syntax without granting Fleet trust.
    ///
    /// # Errors
    /// Reject duplicate/unreviewed keys, unsupported operations, removal
    /// requests, invalid identities, protected initial authority and requests
    /// outside a short bounded window.
    pub fn parse(raw: &[u8], now: DateTime<FixedOffset>) -> Result<Self, ContractError> {
        let value = parse_strict(raw)?;
        let request: Self = serde_json::from_value(value)
            .map_err(|error| ContractError::new("invalid_fleet_admission", error.to_string()))?;
        if request.schema != FLEET_ADMISSION_SCHEMA || request.protocol != FLEET_ADMISSION_PROTOCOL
        {
            return Err(ContractError::new(
                "unsupported_fleet_admission_schema",
                "Fleet admission protocol version is unsupported",
            ));
        }
        if !matches!(
            request.operation.as_str(),
            "fleet.admission.evaluate" | "fleet.admission.enroll"
        ) {
            return Err(ContractError::new(
                "operation_denied",
                "only reviewed automatic admission operations are permitted",
            ));
        }
        if !matches!(
            request.requested_role.as_str(),
            "core_host" | "core_link" | "module_host" | "standby"
        ) {
            return Err(ContractError::new(
                "invalid_fleet_admission",
                "requested role is not eligible for automatic admission",
            ));
        }
        if !id_regex().is_match(&request.request_id)
            || !id_regex().is_match(&request.target_platform_id)
            || !id_regex().is_match(&request.candidate_host_id)
            || !id_regex().is_match(&request.installation_identity_id)
            || !id_regex().is_match(&request.signer_key_id)
            || !id_regex().is_match(&request.policy_id)
            || !uuid_regex().is_match(&request.candidate_node_id)
            || !digest_regex().is_match(&request.candidate_public_key_sha256)
        {
            return Err(ContractError::new(
                "invalid_fleet_admission",
                "Fleet admission identity evidence is malformed",
            ));
        }
        if request.expected_generation == 0
            || request.expected_generation > 9_007_199_254_740_991
            || request.policy_revision == 0
            || request.policy_revision > 9_007_199_254_740_991
        {
            return Err(ContractError::new(
                "invalid_fleet_admission",
                "Fleet admission generation or policy revision is out of range",
            ));
        }
        if request.initial_permission_level == 0
            || request.initial_permission_level > FLEET_ADMISSION_MAX_INITIAL_PERMISSION
        {
            return Err(ContractError::new(
                "invalid_fleet_admission",
                "automatic admission cannot assign protected authority",
            ));
        }
        if request
            .created_at
            .split_once('.')
            .is_some_and(|(_, suffix)| suffix.bytes().take_while(u8::is_ascii_digit).count() > 6)
            || request.deadline.split_once('.').is_some_and(|(_, suffix)| {
                suffix.bytes().take_while(u8::is_ascii_digit).count() > 6
            })
        {
            return Err(ContractError::new(
                "invalid_fleet_admission",
                "timestamp precision exceeds six fractional digits",
            ));
        }
        let created = management_time(&request.created_at)?;
        let deadline = management_time(&request.deadline)?;
        if created > now
            || created < now - Duration::seconds(60)
            || deadline <= now
            || deadline <= created
            || deadline > created + Duration::seconds(60)
        {
            return Err(ContractError::new(
                "expired_fleet_admission",
                "request deadline or creation time is outside the bounded window",
            ));
        }
        Ok(request)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_request() -> serde_json::Value {
        serde_json::json!({
            "schema": FLEET_ADMISSION_SCHEMA,
            "protocol": FLEET_ADMISSION_PROTOCOL,
            "request_id": "admission-1",
            "target_platform_id": "platform:artemis",
            "expected_generation": 7,
            "operation": "fleet.admission.evaluate",
            "candidate_host_id": "worker",
            "candidate_node_id": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
            "candidate_public_key_sha256": "a".repeat(64),
            "installation_identity_id": "installation:worker",
            "signer_key_id": "publisher:sparks",
            "policy_id": "autonomy:main",
            "policy_revision": 1,
            "requested_role": "core_host",
            "initial_permission_level": 2,
            "created_at": "2026-11-11T12:00:00Z",
            "deadline": "2026-11-11T12:00:30Z"
        })
    }

    fn now() -> DateTime<FixedOffset> {
        DateTime::parse_from_rfc3339("2026-11-11T12:00:20Z").expect("now")
    }

    #[test]
    fn accepts_bounded_evaluation_and_enrollment() {
        let raw = serde_json::to_vec(&valid_request()).expect("json");
        let parsed = UntrustedFleetAdmissionRequest::parse(&raw, now()).expect("valid");
        assert_eq!(parsed.operation, "fleet.admission.evaluate");
        assert_eq!(parsed.initial_permission_level, 2);
    }

    #[test]
    fn shared_python_fixture_parses_identically() {
        let root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../../contracts/platform/fleet-admission-valid-v1.json");
        let raw = std::fs::read(root).expect("shared fixture");
        let parsed = UntrustedFleetAdmissionRequest::parse(&raw, now()).expect("fixture is valid");
        assert_eq!(parsed.candidate_host_id, "worker");
        assert_eq!(
            parsed.candidate_node_id,
            "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
        );
        assert_eq!(parsed.policy_revision, 1);
    }

    #[test]
    fn rejects_removal_and_protected_initial_authority() {
        for (field, value) in [
            ("operation", serde_json::json!("fleet.decommission")),
            ("initial_permission_level", serde_json::json!(4)),
            ("requested_role", serde_json::json!("system")),
        ] {
            let mut request = valid_request();
            request[field] = value;
            let raw = serde_json::to_vec(&request).expect("json");
            assert!(UntrustedFleetAdmissionRequest::parse(&raw, now()).is_err());
        }
    }

    #[test]
    fn rejects_unknown_fields_and_owner_secret_material() {
        let mut request = valid_request();
        request["owner_secret"] = serde_json::json!("ab".repeat(32));
        let raw = serde_json::to_vec(&request).expect("json");
        assert!(UntrustedFleetAdmissionRequest::parse(&raw, now()).is_err());
    }

    #[test]
    fn rejects_stale_and_future_windows() {
        let raw = serde_json::to_vec(&valid_request()).expect("json");
        let stale = DateTime::parse_from_rfc3339("2026-11-11T12:05:00Z").expect("now");
        let future = DateTime::parse_from_rfc3339("2026-11-11T11:59:00Z").expect("now");
        assert!(UntrustedFleetAdmissionRequest::parse(&raw, stale).is_err());
        assert!(UntrustedFleetAdmissionRequest::parse(&raw, future).is_err());
    }
}
