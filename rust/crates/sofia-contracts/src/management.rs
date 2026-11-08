//! Untrusted, read-only v1 management wire syntax shared by CLI, TUI and GUI.
//!
//! Not an IPC listener, credential validator or execution authority. Platform
//! must authenticate the OS peer/session and enforce current SAFE/STOP before
//! returning any observation or dispatching any consequential operation.

use crate::{parse_strict, ContractError};
use chrono::{DateTime, Duration, FixedOffset};
use serde::Deserialize;

pub const MANAGEMENT_READ_SCHEMA: &str = "aegis.platform.management.read.v1";
pub const MANAGEMENT_READ_PROTOCOL: &str = "1.0";

#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UntrustedManagementRead {
    pub schema: String,
    pub protocol: String,
    pub request_id: String,
    pub target_platform_id: String,
    pub expected_generation: u64,
    pub operation: String,
    pub created_at: String,
    pub deadline: String,
}

fn valid_id(value: &str) -> bool {
    let bytes = value.as_bytes();
    if bytes.is_empty() || bytes.len() > 160 {
        return false;
    }
    bytes[0].is_ascii_alphanumeric()
        && bytes.iter().all(|b| {
            b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b'-' | b':' | b'@' | b'/')
        })
}

impl UntrustedManagementRead {
    /// Parse untrusted read-only request syntax without granting access.
    ///
    /// # Errors
    /// Reject duplicate/unreviewed keys, mutations, malformed IDs, wrong
    /// protocol and requests outside a short, bounded observation window.
    pub fn parse(raw: &[u8], now: DateTime<FixedOffset>) -> Result<Self, ContractError> {
        let value = parse_strict(raw)?;
        let request: Self = serde_json::from_value(value)
            .map_err(|error| ContractError::new("invalid_management_read", error.to_string()))?;
        if request.schema != MANAGEMENT_READ_SCHEMA || request.protocol != MANAGEMENT_READ_PROTOCOL
        {
            return Err(ContractError::new(
                "unsupported_management_schema",
                "read-only management protocol version is unsupported",
            ));
        }
        if !valid_id(&request.request_id)
            || !valid_id(&request.target_platform_id)
            || request.expected_generation == 0
        {
            return Err(ContractError::new(
                "invalid_management_read",
                "request identity or expected generation is invalid",
            ));
        }
        if !matches!(
            request.operation.as_str(),
            "platform.status"
                | "core.list"
                | "module.list"
                | "fleet.list"
                | "settings.inspect"
                | "security.status"
                | "updates.status"
                | "diagnostics.summary"
                | "jobs.list"
        ) {
            return Err(ContractError::new(
                "operation_denied",
                "only reviewed read-only management queries are permitted",
            ));
        }
        let created = DateTime::parse_from_rfc3339(&request.created_at)
            .map_err(|_| ContractError::new("invalid_management_read", "invalid creation time"))?;
        let deadline = DateTime::parse_from_rfc3339(&request.deadline)
            .map_err(|_| ContractError::new("invalid_management_read", "invalid deadline"))?;
        if created > now
            || created < now - Duration::seconds(60)
            || deadline <= now
            || deadline <= created
            || deadline > created + Duration::seconds(60)
        {
            return Err(ContractError::new(
                "expired_management_read",
                "request deadline or creation time is outside the bounded observation window",
            ));
        }
        Ok(request)
    }
}


/// A read-only reply that has passed schema and request-correlation checks.
/// This is *not* evidence that the reply came from an authenticated service.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UntrustedManagementStatus {
    pub schema: String,
    pub protocol: String,
    pub request_id: String,
    pub platform_id: String,
    pub platform_generation: u64,
    pub operation: String,
    pub source: String,
    pub data: ManagementStatusData,
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ManagementStatusData {
    pub platform_id: String,
    pub generation: u64,
    pub operator_stop: bool,
    pub core_started: bool,
}

impl UntrustedManagementStatus {
    /// Strict parsing does not authenticate an IPC sender.
    ///
    /// # Errors
    /// Reject oversized, duplicated, uncorrelated or forged-status fields.
    pub fn parse(raw: &[u8], expected: &UntrustedManagementRead) -> Result<Self, ContractError> {
        if raw.is_empty() || raw.len() > 65536 || expected.operation != "platform.status" {
            return Err(ContractError::new(
                "invalid_management_status",
                "bounded status response requires matching status operation",
            ));
        }
        let value = parse_strict(raw)?;
        let response: Self = serde_json::from_value(value).map_err(|error| {
            ContractError::new("invalid_management_status", error.to_string())
        })?;
        if response.schema != "aegis.platform.management.read-response.v1"
            || response.protocol != MANAGEMENT_READ_PROTOCOL
            || response.operation != "platform.status"
            || response.source != "PLATFORM_SESSION"
            || response.request_id != expected.request_id
            || response.platform_id != expected.target_platform_id
            || response.platform_generation != expected.expected_generation
            || response.data.platform_id != expected.target_platform_id
            || response.data.generation != expected.expected_generation
            || response.data.core_started
            || response.data.operator_stop
        {
            return Err(ContractError::new(
                "uncorrelated_management_status",
                "current Platform identity, generation or operation mismatch",
            ));
        }
        Ok(response)
    }
}

#[cfg(test)]
mod tests {
    use super::{UntrustedManagementRead, UntrustedManagementStatus, MANAGEMENT_READ_PROTOCOL, MANAGEMENT_READ_SCHEMA};
    use serde_json::{json, Value};

    fn valid() -> (Value, chrono::DateTime<chrono::FixedOffset>) {
        let now = chrono::DateTime::parse_from_rfc3339("2026-11-08T04:00:00Z")
            .expect("known test timestamp");
        (
            json!({
                "schema": MANAGEMENT_READ_SCHEMA,
                "protocol": MANAGEMENT_READ_PROTOCOL,
                "request_id": "req:1",
                "target_platform_id": "platform:alpha",
                "expected_generation": 1,
                "operation": "platform.status",
                "created_at": "2026-11-08T03:59:59Z",
                "deadline": "2026-11-08T04:00:05Z"
            }),
            now,
        )
    }

    #[test]
    fn shared_python_sdk_fixture_is_accepted_as_untrusted() {
        let raw = include_str!("../../../../contracts/platform/management-read-valid-v1.json");
        let now = chrono::DateTime::parse_from_rfc3339("2026-11-08T04:00:00Z")
            .expect("known fixture clock");
        let request = UntrustedManagementRead::parse(raw.as_bytes(), now)
            .expect("shared fixture obeys strict read contract");
        assert_eq!(request.operation, "platform.status");
        assert_eq!(request.expected_generation, 3);
    }

    #[test]
    fn shared_python_sdk_status_fixture_is_correlated_but_not_authentication() {
        let request_json = include_str!("../../../../contracts/platform/management-read-valid-v1.json");
        let status_json = include_str!("../../../../contracts/platform/management-status-valid-v1.json");
        let now = chrono::DateTime::parse_from_rfc3339("2026-11-08T04:00:00Z")
            .expect("known fixture clock");
        let request = UntrustedManagementRead::parse(request_json.as_bytes(), now)
            .expect("shared request fixture");
        let status = UntrustedManagementStatus::parse(status_json.as_bytes(), &request)
            .expect("shared status fixture");
        assert_eq!(status.platform_generation, request.expected_generation);
        assert_eq!(status.request_id, request.request_id);
        assert!(!status.data.operator_stop);
        assert!(!status.data.core_started);
    }

    #[test]
    fn stale_status_forged_trust_and_duplicate_response_are_denied() {
        let request_json = include_str!("../../../../contracts/platform/management-read-valid-v1.json");
        let status_json = include_str!("../../../../contracts/platform/management-status-valid-v1.json");
        let now = chrono::DateTime::parse_from_rfc3339("2026-11-08T04:00:00Z")
            .expect("known fixture clock");
        let request = UntrustedManagementRead::parse(request_json.as_bytes(), now)
            .expect("shared request fixture");
        let valid: Value = serde_json::from_str(status_json).expect("fixture JSON");
        for (key, replacement) in [
            ("platform_generation", json!(4)),
            ("request_id", json!("req:other")),
            ("source", json!("I-am-authenticated")),
            ("operation", json!("core.start")),
        ] {
            let mut forged = valid.clone();
            forged[key] = replacement;
            assert!(UntrustedManagementStatus::parse(
                forged.to_string().as_bytes(),
                &request,
            )
            .is_err());
        }
        let mut data_forged = valid.clone();
        data_forged["data"]["operator_stop"] = json!(true);
        assert!(UntrustedManagementStatus::parse(
            data_forged.to_string().as_bytes(),
            &request,
        )
        .is_err());
        let mut extra = valid;
        extra["owner_approved"] = json!(true);
        assert!(UntrustedManagementStatus::parse(extra.to_string().as_bytes(), &request).is_err());
        let dup = status_json.replacen("{", r#"{"source":"PLATFORM_SESSION","#, 1);
        assert!(UntrustedManagementStatus::parse(dup.as_bytes(), &request).is_err());
    }

    #[test]
    fn accepts_bounded_read_only_query_as_untrusted() {
        let (value, now) = valid();
        let request = UntrustedManagementRead::parse(value.to_string().as_bytes(), now)
            .expect("reviewed syntax");
        assert_eq!(request.operation, "platform.status");
        assert_eq!(request.expected_generation, 1);
    }

    #[test]
    fn rejects_mutation_and_unknown_operations() {
        let (mut value, now) = valid();
        for operation in [
            "module.remove",
            "core.start",
            "platform.install",
            "safe.approve",
        ] {
            value["operation"] = json!(operation);
            assert!(UntrustedManagementRead::parse(value.to_string().as_bytes(), now).is_err());
        }
    }

    #[test]
    fn rejects_duplicate_and_extra_authority_fields() {
        let (mut value, now) = valid();
        value["grant"] = json!("self-authorized");
        assert!(UntrustedManagementRead::parse(value.to_string().as_bytes(), now).is_err());
        let dup = r#"{"schema":"aegis.platform.management.read.v1","schema":"aegis.platform.management.read.v1"}"#;
        assert!(UntrustedManagementRead::parse(dup.as_bytes(), now).is_err());
    }

    #[test]
    fn rejects_stale_wrong_generation_and_invalid_identity() {
        let (mut value, now) = valid();
        value["expected_generation"] = json!(0);
        assert!(UntrustedManagementRead::parse(value.to_string().as_bytes(), now).is_err());
        value["expected_generation"] = json!(1);
        value["target_platform_id"] = json!("../bad");
        assert!(UntrustedManagementRead::parse(value.to_string().as_bytes(), now).is_err());
        value["target_platform_id"] = json!("platform:alpha");
        value["deadline"] = json!("2026-11-08T03:59:59Z");
        assert!(UntrustedManagementRead::parse(value.to_string().as_bytes(), now).is_err());
        value["deadline"] = json!("2026-11-08T04:00:05Z");
        value["created_at"] = json!("2026-11-08T03:50:00Z");
        assert!(UntrustedManagementRead::parse(value.to_string().as_bytes(), now).is_err());
    }
}
