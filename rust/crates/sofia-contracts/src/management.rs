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
            || request.expected_generation > 9_007_199_254_740_991
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
        // Python datetime preserves microseconds, so refuse nanosecond
        // precision rather than silently permitting cross-language rounding.
        if request
            .created_at
            .split_once('.')
            .is_some_and(|(_, suffix)| suffix.bytes().take_while(u8::is_ascii_digit).count() > 6)
            || request
                .deadline
                .split_once('.')
                .is_some_and(|(_, suffix)| suffix.bytes().take_while(u8::is_ascii_digit).count() > 6)
        {
            return Err(ContractError::new(
                "invalid_management_read",
                "request timestamp precision exceeds six fractional digits",
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

pub const MANAGEMENT_RESPONSE_SCHEMA: &str = "aegis.platform.management.read-response.v1";
pub const MAX_MANAGEMENT_RESPONSE_BYTES: usize = 32 * 1024;

/// Parsed syntax and correlation only; it NEVER proves an authenticated sender.
#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UntrustedManagementResponse {
    pub schema: String,
    pub protocol: String,
    pub request_id: String,
    pub platform_id: String,
    pub platform_generation: u64,
    pub operation: String,
    pub source: String,
    pub observed_at: String,
    pub outcome: String,
    pub data: Option<serde_json::Value>,
    pub denial: Option<ManagementDenial>,
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ManagementDenial {
    pub code: String,
}

fn safe_management_projection(
    value: &serde_json::Value,
    depth: usize,
) -> Result<(), ContractError> {
    if depth > 8 {
        return Err(ContractError::new(
            "invalid_management_response",
            "management result nesting exceeds bound",
        ));
    }
    match value {
        serde_json::Value::Object(values) => {
            if values.len() > 256 {
                return Err(ContractError::new(
                    "invalid_management_response",
                    "management result has too many keys",
                ));
            }
            for (key, member) in values {
                let lower = key.to_ascii_lowercase();
                if key.is_empty()
                    || key.len() > 160
                    || !key.is_ascii()
                    || key.chars().any(char::is_control)
                    || ["__proto__", "prototype", "constructor"].contains(&lower.as_str())
                    || [
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
                {
                    return Err(ContractError::new(
                        "invalid_management_response",
                        "management result contains unsafe key",
                    ));
                }
                safe_management_projection(member, depth + 1)?;
            }
        }
        serde_json::Value::Array(values) => {
            if values.len() > 1024 {
                return Err(ContractError::new(
                    "invalid_management_response",
                    "management result array exceeds bound",
                ));
            }
            for member in values {
                safe_management_projection(member, depth + 1)?;
            }
        }
        serde_json::Value::Number(number) => {
            const MAX_EXACT_JSON_INTEGER: f64 = 9_007_199_254_740_991.0;
            // If a huge integer token became f64 during serde parsing,
            // reject it too. Never advertise cross-language exactness that
            // Python, Rust and a GUI client cannot preserve identically.
            let Some(value) = number.as_f64() else {
                return Err(ContractError::new(
                    "invalid_management_response",
                    "unrepresentable management numeric value",
                ));
            };
            if !value.is_finite() || value.abs() > MAX_EXACT_JSON_INTEGER {
                return Err(ContractError::new(
                    "invalid_management_response",
                    "management numeric value exceeds portable JSON range",
                ));
            }
        }
        serde_json::Value::String(value) => {
            if value.chars().any(char::is_control) {
                return Err(ContractError::new(
                    "invalid_management_response",
                    "management result contains control characters",
                ));
            }
        }
        _ => {}
    }
    Ok(())
}

impl UntrustedManagementResponse {
    /// Parse only bounded, correlated, fresh syntax; transport trust is independent.
    ///
    /// # Errors
    /// Reject duplicate keys, stale/future responses, secret payload and forged denial.
    pub fn parse(
        raw: &[u8],
        expected: &UntrustedManagementRead,
        now: DateTime<FixedOffset>,
    ) -> Result<Self, ContractError> {
        if raw.is_empty() || raw.len() > MAX_MANAGEMENT_RESPONSE_BYTES {
            return Err(ContractError::new(
                "invalid_management_response",
                "response byte size exceeds bound",
            ));
        }
        let value = parse_strict(raw)?;
        // Serde's Option<T> permits *missing* fields by default; Python's
        // canonical v1 parser requires all eleven envelope keys, including
        // explicit null for the unused data or denial side. Fence that here.
        let keys = value.as_object().ok_or_else(|| {
            ContractError::new("invalid_management_response", "response must be an object")
        })?;
        const REQUIRED: [&str; 11] = [
            "schema", "protocol", "request_id", "platform_id",
            "platform_generation", "operation", "source", "observed_at",
            "outcome", "data", "denial",
        ];
        if keys.len() != REQUIRED.len() || REQUIRED.iter().any(|key| !keys.contains_key(*key)) {
            return Err(ContractError::new(
                "invalid_management_response",
                "response envelope must include every versioned field",
            ));
        }
        let reply: Self = serde_json::from_value(value).map_err(|_| {
            ContractError::new("invalid_management_response", "response fields invalid")
        })?;
        if reply.schema != MANAGEMENT_RESPONSE_SCHEMA
            || reply.protocol != MANAGEMENT_READ_PROTOCOL
            || reply.source != "PLATFORM_SESSION"
            || reply.request_id != expected.request_id
            || reply.platform_id != expected.target_platform_id
            || reply.platform_generation != expected.expected_generation
            || reply.operation != expected.operation
        {
            return Err(ContractError::new(
                "uncorrelated_management_response",
                "management response identity, generation or operation mismatch",
            ));
        }
        // Python datetime stores microseconds, while chrono accepts nanos.
        // Freeze 0..6 digits so freshness comparisons cannot disagree at
        // a nanosecond boundary across GUI/TUI and service clients.
        if reply
            .observed_at
            .split_once('.')
            .is_some_and(|(_, suffix)| {
                suffix.bytes().take_while(u8::is_ascii_digit).count() > 6
            })
        {
            return Err(ContractError::new(
                "invalid_management_response",
                "observation precision exceeds six fractional digits",
            ));
        }
        let observed = DateTime::parse_from_rfc3339(&reply.observed_at).map_err(|_| {
            ContractError::new("invalid_management_response", "invalid observation time")
        })?;
        let created = DateTime::parse_from_rfc3339(&expected.created_at).map_err(|_| {
            ContractError::new(
                "invalid_management_response",
                "invalid request creation time",
            )
        })?;
        let deadline = DateTime::parse_from_rfc3339(&expected.deadline).map_err(|_| {
            ContractError::new("invalid_management_response", "invalid request deadline")
        })?;
        if observed < created
            || observed > now
            || observed >= deadline
            || now >= deadline
            || now - observed > Duration::seconds(5)
        {
            return Err(ContractError::new(
                "stale_management_response",
                "management observation outside fresh request window",
            ));
        }
        match reply.outcome.as_str() {
            "OK" => {
                if reply.denial.is_some() {
                    return Err(ContractError::new(
                        "invalid_management_response",
                        "successful observation may not contain a denial",
                    ));
                }
                let Some(serde_json::Value::Object(data)) = reply.data.as_ref() else {
                    return Err(ContractError::new(
                        "invalid_management_response",
                        "successful observation requires an object",
                    ));
                };
                safe_management_projection(&serde_json::Value::Object(data.clone()), 0)?;
                if reply.operation == "platform.status"
                    && (data.len() != 4
                        || data.get("platform_id").and_then(serde_json::Value::as_str)
                            != Some(expected.target_platform_id.as_str())
                        || data.get("generation").and_then(serde_json::Value::as_u64)
                            != Some(expected.expected_generation)
                        || data
                            .get("core_started")
                            .and_then(serde_json::Value::as_bool)
                            != Some(false)
                        || data
                            .get("operator_stop")
                            .and_then(serde_json::Value::as_bool)
                            != Some(false))
                {
                    return Err(ContractError::new(
                        "invalid_management_response",
                        "Platform status projection differs from trusted request",
                    ));
                }
            }
            "DENIED" => {
                let Some(denial) = reply.denial.as_ref() else {
                    return Err(ContractError::new(
                        "invalid_management_response",
                        "typed denial code required",
                    ));
                };
                if reply.data.is_some()
                    || !matches!(
                        denial.code.as_str(),
                        "NOT_PERMITTED"
                            | "REVOKED"
                            | "STOPPED"
                            | "STALE_GENERATION"
                            | "EXPIRED"
                            | "UNAVAILABLE"
                    )
                {
                    return Err(ContractError::new(
                        "invalid_management_response",
                        "management denial malformed",
                    ));
                }
            }
            _ => {
                return Err(ContractError::new(
                    "invalid_management_response",
                    "management outcome unsupported",
                ));
            }
        }
        Ok(reply)
    }
}

#[cfg(test)]
mod tests {
    use super::{
        UntrustedManagementRead, UntrustedManagementResponse, MANAGEMENT_READ_PROTOCOL,
        MANAGEMENT_READ_SCHEMA,
    };
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
    #[test]
    fn management_reply_shared_fixture_and_denial_are_strict() {
        let request_json =
            include_str!("../../../../contracts/platform/management-read-valid-v1.json");
        let response_json =
            include_str!("../../../../contracts/platform/management-read-response-valid-v1.json");
        let start =
            chrono::DateTime::parse_from_rfc3339("2026-11-08T04:00:00Z").expect("known start");
        let now = chrono::DateTime::parse_from_rfc3339("2026-11-08T04:00:01Z")
            .expect("known receiver time");
        let request =
            UntrustedManagementRead::parse(request_json.as_bytes(), start).expect("shared request");
        let response = UntrustedManagementResponse::parse(response_json.as_bytes(), &request, now)
            .expect("correlated read observation");
        assert_eq!(response.outcome, "OK");
        assert_eq!(response.platform_generation, 3);

        let mut value: Value = serde_json::from_str(response_json).expect("response");
        value["outcome"] = json!("DENIED");
        value["data"] = Value::Null;
        value["denial"] = json!({"code":"NOT_PERMITTED"});
        assert!(
            UntrustedManagementResponse::parse(value.to_string().as_bytes(), &request, now).is_ok()
        );
        value["denial"] = json!({"code":"UNREVIEWED"});
        assert!(
            UntrustedManagementResponse::parse(value.to_string().as_bytes(), &request, now)
                .is_err()
        );
        value["denial"] = json!({"code":"NOT_PERMITTED"});
        value["data"] = json!({});
        assert!(
            UntrustedManagementResponse::parse(value.to_string().as_bytes(), &request, now)
                .is_err()
        );

        // Absent Option<T> is NOT equivalent to explicit null in v1.
        let mut omitted: Value = serde_json::from_str(response_json).expect("response");
        omitted.as_object_mut().expect("object").remove("denial");
        assert!(UntrustedManagementResponse::parse(
            omitted.to_string().as_bytes(), &request, now
        ).is_err());
        let mut omitted_data: Value = serde_json::from_str(response_json).expect("response");
        omitted_data.as_object_mut().expect("object").remove("data");
        assert!(UntrustedManagementResponse::parse(
            omitted_data.to_string().as_bytes(), &request, now
        ).is_err());
        let mut forged: Value = serde_json::from_str(response_json).expect("response");
        forged["platform_generation"] = json!(4);
        assert!(
            UntrustedManagementResponse::parse(forged.to_string().as_bytes(), &request, now)
                .is_err()
        );
        forged["platform_generation"] = json!(3);
        forged["data"]["owner_secret"] = json!("leak");
        assert!(
            UntrustedManagementResponse::parse(forged.to_string().as_bytes(), &request, now)
                .is_err()
        );
        let duplicate = response_json.replacen('{', r#"{"schema":"forged","#, 1);
        assert!(UntrustedManagementResponse::parse(duplicate.as_bytes(), &request, now).is_err());
        let late =
            chrono::DateTime::parse_from_rfc3339("2026-11-08T04:00:06Z").expect("known late time");
        assert!(
            UntrustedManagementResponse::parse(response_json.as_bytes(), &request, late).is_err()
        );
    }

    #[test]
    fn shared_denial_and_unicode_c1_parity_corpus() {
        let request_json =
            include_str!("../../../../contracts/platform/management-read-valid-v1.json");
        let denied_json =
            include_str!("../../../../contracts/platform/management-read-response-denied-v1.json");
        let settings_json =
            include_str!("../../../../contracts/platform/management-read-settings-valid-v1.json");
        let c1_json =
            include_str!("../../../../contracts/platform/management-read-response-invalid-c1-v1.json");
        let start = chrono::DateTime::parse_from_rfc3339("2026-11-08T04:00:00Z")
            .expect("known start");
        let now = chrono::DateTime::parse_from_rfc3339("2026-11-08T04:00:01Z")
            .expect("known receiver");
        let request = UntrustedManagementRead::parse(request_json.as_bytes(), start)
            .expect("valid status request");
        let denied = UntrustedManagementResponse::parse(
            denied_json.as_bytes(), &request, now,
        ).expect("correlated typed denial");
        assert_eq!(denied.outcome, "DENIED");
        assert_eq!(denied.denial.expect("denial").code, "STOPPED");
        let settings = UntrustedManagementRead::parse(settings_json.as_bytes(), start)
            .expect("valid read syntax");
        assert!(UntrustedManagementResponse::parse(
            c1_json.as_bytes(), &settings, now,
        ).is_err());
        let mut allowed: Value = serde_json::from_str(c1_json).expect("strict fixture");
        allowed["data"] = json!({"message":"\u{2028}"});
        assert!(UntrustedManagementResponse::parse(
            allowed.to_string().as_bytes(), &settings, now,
        ).is_ok());
        allowed["data"] = json!({"nönascii":"safe"});
        assert!(UntrustedManagementResponse::parse(
            allowed.to_string().as_bytes(), &settings, now,
        ).is_err());
    }

    #[test]
    fn reject_request_nanoseconds_before_authorization() {
        let raw = include_str!("../../../../contracts/platform/management-read-valid-v1.json");
        let now = chrono::DateTime::parse_from_rfc3339("2026-11-08T04:00:00Z")
            .expect("known time");
        let mut request: Value = serde_json::from_str(raw).expect("fixture");
        request["created_at"] = json!("2026-11-08T03:59:59.123456789Z");
        assert!(UntrustedManagementRead::parse(request.to_string().as_bytes(), now).is_err());
        request["created_at"] = json!("2026-11-08T03:59:59.123456Z");
        request["deadline"] = json!("2026-11-08T04:00:05.123456789Z");
        assert!(UntrustedManagementRead::parse(request.to_string().as_bytes(), now).is_err());
        request["deadline"] = json!("2026-11-08T04:00:05.123456Z");
        assert!(UntrustedManagementRead::parse(request.to_string().as_bytes(), now).is_ok());
    }

}
