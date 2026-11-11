//! Authority-free AG-D028 Library v1 request/response contract.
//! Source JSON, Hub claims and catalog pointers NEVER authenticate a peer,
//! sign publisher bytes, authorize installation or activate a Core.

use crate::{parse_strict, ContractError};
use chrono::{DateTime, Duration, FixedOffset};
use regex::Regex;
use serde_json::{Map, Value};
use std::collections::BTreeSet;
use std::sync::OnceLock;

pub const LIBRARY_REQUEST_SCHEMA: &str = "aegis.platform.library.request.v1";
pub const LIBRARY_RESPONSE_SCHEMA: &str = "aegis.platform.library.response.v1";
pub const LIBRARY_PROTOCOL: &str = "1.0";
pub const MAX_LIBRARY_CONTROL_BYTES: usize = 32 * 1024;
const MAX_SAFE_INTEGER: u64 = 9_007_199_254_740_991;
const REQUEST_KEYS: [&str; 12] = [
    "schema",
    "protocol",
    "request_id",
    "correlation_id",
    "operation",
    "target_platform_id",
    "expected_generation",
    "expected_revision",
    "idempotency_key",
    "created_at",
    "deadline",
    "parameters",
];
const RESPONSE_KEYS: [&str; 12] = [
    "schema",
    "protocol",
    "request_id",
    "correlation_id",
    "operation",
    "platform_id",
    "platform_generation",
    "state_revision",
    "observed_at",
    "outcome",
    "data",
    "denial",
];
const CATALOG_KEYS: [&str; 7] = [
    "catalog_revision",
    "catalog_generation",
    "catalog_fresh_until",
    "target_platform_id",
    "source",
    "page",
    "items",
];
const CATALOG_ITEM_KEYS: [&str; 17] = [
    "artifact_id",
    "kind",
    "version",
    "revision",
    "manifest_digest",
    "content_digest",
    "size_bytes",
    "publisher",
    "signer_key_id",
    "signature_scheme",
    "signature_receipt_ref",
    "target_os_arch",
    "sdk_range",
    "abi_range",
    "license_distribution",
    "data_class",
    "distribution_allowed",
];
pub const OWNER_SOURCES_STATUS_SCHEMA: &str = "aegis.library.owner-sources.v1";
const SOURCES_STATUS_KEYS: [&str; 8] = [
    "schema",
    "owner_mode",
    "source_platform_id",
    "publisher_state",
    "catalog_state",
    "hub_state",
    "served_chunks",
    "served_bytes",
];

const TRANSFER_KEYS: [&str; 13] = [
    "job_id",
    "artifact_content_digest",
    "target_platform_id",
    "source_platform_id",
    "source_kind",
    "received_bytes",
    "verified_bytes",
    "total_bytes",
    "state",
    "failure",
    "last_observed_at",
    "restart_cursor",
    "receipt_ref",
];
const KINDS: [&str; 8] = [
    "platform_release",
    "sdk",
    "core_runtime",
    "core_definition",
    "module",
    "model",
    "asset",
    "rollback",
];
const SOURCES: [&str; 5] = [
    "LOCAL_VERIFIED_CACHE",
    "OFFLINE_MEDIA",
    "OWNER_SELECTED_HUB",
    "AUTHORIZED_PEER",
    "OFFICIAL_REMOTE",
];
const DENIALS: [&str; 6] = [
    "NOT_PERMITTED",
    "REVOKED",
    "STOPPED",
    "STALE_GENERATION",
    "EXPIRED",
    "UNAVAILABLE",
];

fn invalid(reason: &'static str) -> ContractError {
    ContractError::new("invalid_library_contract", reason)
}

fn fields<'a>(v: &'a Value, required: &[&str]) -> Result<&'a Map<String, Value>, ContractError> {
    let obj = v
        .as_object()
        .ok_or_else(|| invalid("Library object required"))?;
    if obj.len() != required.len() || required.iter().any(|key| !obj.contains_key(*key)) {
        return Err(invalid("missing or unreviewed Library fields"));
    }
    Ok(obj)
}

fn str_field<'a>(obj: &'a Map<String, Value>, key: &str) -> Result<&'a str, ContractError> {
    obj.get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| invalid("Library string field invalid"))
}

fn exact_int(value: &Value, minimum: u64) -> Result<u64, ContractError> {
    let number = value
        .as_u64()
        .ok_or_else(|| invalid("nonportable Library integer"))?;
    if number < minimum || number > MAX_SAFE_INTEGER {
        return Err(invalid("nonportable Library integer"));
    }
    Ok(number)
}

fn id(value: &str) -> Result<(), ContractError> {
    let bytes = value.as_bytes();
    if bytes.is_empty()
        || bytes.len() > 160
        || !bytes[0].is_ascii_alphanumeric()
        || bytes.iter().any(|b| {
            !b.is_ascii_alphanumeric() && !matches!(b, b'.' | b'_' | b':' | b'@' | b'/' | b'-')
        })
        || value.contains("://")
        || value.contains("..")
    {
        return Err(invalid("Library opaque identifier invalid"));
    }
    Ok(())
}

fn digest(value: &str) -> Result<(), ContractError> {
    if value.len() != 64
        || value
            .bytes()
            .any(|b| !b.is_ascii_digit() && !(b'a'..=b'f').contains(&b))
    {
        return Err(invalid("invalid Library digest syntax"));
    }
    Ok(())
}

fn utc(value: &str) -> Result<DateTime<FixedOffset>, ContractError> {
    static RFC3339: OnceLock<Regex> = OnceLock::new();
    let pattern = RFC3339.get_or_init(|| {
        Regex::new(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$")
            .expect("valid library RFC3339 format")
    });
    if !pattern.is_match(value) {
        return Err(invalid("Library timestamp must be bounded RFC3339"));
    }
    DateTime::parse_from_rfc3339(value).map_err(|_| invalid("invalid Library timestamp"))
}

fn safe(value: &Value, depth: usize) -> Result<(), ContractError> {
    if depth > 8 {
        return Err(invalid("Library projection nested too deeply"));
    }
    match value {
        Value::Object(fields) => {
            if fields.len() > 256 {
                return Err(invalid("Library projection has excessive keys"));
            }
            for (key, member) in fields {
                let lower = key.to_ascii_lowercase();
                if key.is_empty()
                    || key.len() > 160
                    || !key.is_ascii()
                    || key.chars().any(char::is_control)
                    || ["__proto__", "constructor", "prototype"].contains(&lower.as_str())
                    || [
                        "secret",
                        "password",
                        "credential",
                        "authorization",
                        "owner_proof",
                        "private_key",
                        "access_token",
                        "refresh_token",
                        "api_key",
                        "sofia.db",
                        "peer_sid",
                        "peer_uid",
                    ]
                    .iter()
                    .any(|part| lower.contains(*part))
                {
                    return Err(invalid("unsafe Library projection key"));
                }
                safe(member, depth + 1)?;
            }
        }
        Value::Array(items) => {
            if items.len() > 128 {
                return Err(invalid("Library array exceeds control bounds"));
            }
            for member in items {
                safe(member, depth + 1)?;
            }
        }
        Value::String(text) => {
            if text.chars().count() > 4096 || text.chars().any(char::is_control) {
                return Err(invalid("unsafe Library string"));
            }
        }
        Value::Number(number) => {
            let n = number
                .as_f64()
                .ok_or_else(|| invalid("unportable Library number"))?;
            if !n.is_finite() || n.abs() > 9_007_199_254_740_991.0 {
                return Err(invalid("unportable Library number"));
            }
        }
        Value::Null | Value::Bool(_) => {}
    }
    Ok(())
}

fn decode(raw: &[u8]) -> Result<Value, ContractError> {
    if raw.is_empty() || raw.len() > MAX_LIBRARY_CONTROL_BYTES {
        return Err(invalid("Library control bytes exceed bound"));
    }
    let doc = parse_strict(raw)?;
    safe(&doc, 0)?;
    Ok(doc)
}

fn read_operation(operation: &str) -> bool {
    matches!(
        operation,
        "library.catalog.snapshot.v1"
            | "library.inventory.snapshot.v1"
            | "library.sources.snapshot.v1"
            | "library.transfer.status.v1"
            | "library.history.snapshot.v1"
            | "library.plan.acquire.v1"
    )
}

#[derive(Debug, Clone)]
pub struct UntrustedLibraryRequest {
    pub request_id: String,
    pub correlation_id: String,
    pub operation: String,
    pub target_platform_id: String,
    pub expected_generation: u64,
    pub expected_revision: u64,
    pub created_at: String,
    pub deadline: String,
}

impl UntrustedLibraryRequest {
    /// Syntax only; NEVER a grant, principal or installer authority.
    ///
    /// # Errors
    /// Fails on unreviewed operation/version/schema, ID or time boundaries.
    pub fn parse(raw: &[u8], now: DateTime<FixedOffset>) -> Result<Self, ContractError> {
        let doc = decode(raw)?;
        let obj = fields(&doc, &REQUEST_KEYS)?;
        if str_field(obj, "schema")? != LIBRARY_REQUEST_SCHEMA
            || str_field(obj, "protocol")? != LIBRARY_PROTOCOL
        {
            return Err(invalid("unsupported Library protocol version"));
        }
        let request_id = str_field(obj, "request_id")?;
        let correlation_id = str_field(obj, "correlation_id")?;
        let target_platform_id = str_field(obj, "target_platform_id")?;
        for value in [request_id, correlation_id, target_platform_id] {
            id(value)?;
        }
        let generation = exact_int(&obj["expected_generation"], 1)?;
        let revision = exact_int(&obj["expected_revision"], 0)?;
        let operation = str_field(obj, "operation")?;
        if !read_operation(operation) {
            return Err(invalid(
                "effectful Library operation cannot use read preview",
            ));
        }
        if !obj["idempotency_key"].is_null() {
            return Err(invalid(
                "read Library operation cannot claim effect idempotency",
            ));
        }
        let created_at = str_field(obj, "created_at")?;
        let deadline = str_field(obj, "deadline")?;
        let created = utc(created_at)?;
        let end = utc(deadline)?;
        if created > now
            || created < now - Duration::seconds(60)
            || end <= now
            || end <= created
            || end > created + Duration::seconds(60)
        {
            return Err(invalid("stale or future Library request"));
        }
        let params = &obj["parameters"];
        if operation == "library.catalog.snapshot.v1" {
            let options = fields(params, &["limit", "cursor", "kinds"])?;
            if exact_int(&options["limit"], 1)? > 128 {
                return Err(invalid("catalog limit exceeds bound"));
            }
            if !options["cursor"].is_null() {
                id(options["cursor"]
                    .as_str()
                    .ok_or_else(|| invalid("invalid cursor"))?)?;
            }
            let kinds = options["kinds"]
                .as_array()
                .ok_or_else(|| invalid("catalog kinds must be array"))?;
            if kinds.len() > 8 {
                return Err(invalid("catalog kinds exceed bound"));
            }
            let mut unique = BTreeSet::new();
            for kind in kinds {
                let value = kind
                    .as_str()
                    .ok_or_else(|| invalid("invalid artifact kind"))?;
                if !KINDS.contains(&value) || !unique.insert(value) {
                    return Err(invalid("unsupported catalog filter"));
                }
            }
        } else if operation == "library.transfer.status.v1" {
            let options = fields(params, &["job_id"])?;
            id(str_field(options, "job_id")?)?;
        } else if params.as_object().is_none_or(|value| !value.is_empty()) {
            return Err(invalid("Library projection parameters not yet reviewed"));
        }
        Ok(Self {
            request_id: request_id.to_owned(),
            correlation_id: correlation_id.to_owned(),
            operation: operation.to_owned(),
            target_platform_id: target_platform_id.to_owned(),
            expected_generation: generation,
            expected_revision: revision,
            created_at: created_at.to_owned(),
            deadline: deadline.to_owned(),
        })
    }
}

fn owner_sources(data: &Value, expected: &UntrustedLibraryRequest) -> Result<(), ContractError> {
    let obj = fields(data, &SOURCES_STATUS_KEYS)?;
    if str_field(obj, "schema")? != OWNER_SOURCES_STATUS_SCHEMA
        || str_field(obj, "owner_mode")? != "SINGLE_OWNER_PRIVATE"
        || expected.expected_revision != 0
    {
        return Err(invalid("unsupported owner-only Library status"));
    }
    let source = &obj["source_platform_id"];
    if !source.is_null() {
        id(source
            .as_str()
            .ok_or_else(|| invalid("bad publisher source"))?)?;
    }
    let publisher = str_field(obj, "publisher_state")?;
    let catalog_state = str_field(obj, "catalog_state")?;
    let hub_state = str_field(obj, "hub_state")?;
    if !["UNENROLLED", "CURRENT", "REVOKED", "UNKNOWN"].contains(&publisher)
        || !["UNAVAILABLE", "CURRENT", "UNVERIFIED"].contains(&catalog_state)
        || !["CLOSED", "OPEN_IDLE", "SERVING", "UNKNOWN"].contains(&hub_state)
    {
        return Err(invalid("unreviewed owner Library source state"));
    }
    if publisher == "UNENROLLED" && !source.is_null() {
        return Err(invalid("unenrolled publisher cannot assert source"));
    }
    if publisher == "CURRENT" && source.is_null() {
        return Err(invalid("current publisher needs enrolled source"));
    }
    if catalog_state == "CURRENT" && publisher != "CURRENT" {
        return Err(invalid("signed catalog requires owner publisher"));
    }
    exact_int(&obj["served_chunks"], 0)?;
    exact_int(&obj["served_bytes"], 0)?;
    Ok(())
}

fn catalog(
    data: &Value,
    expected: &UntrustedLibraryRequest,
    now: DateTime<FixedOffset>,
) -> Result<(), ContractError> {
    let obj = fields(data, &CATALOG_KEYS)?;
    exact_int(&obj["catalog_revision"], 0)?;
    exact_int(&obj["catalog_generation"], 1)?;
    let fresh_until = utc(str_field(obj, "catalog_fresh_until")?)?;
    if str_field(obj, "target_platform_id")? != expected.target_platform_id {
        return Err(invalid("catalog target differs from request"));
    }
    let source = fields(
        &obj["source"],
        &["kind", "source_id", "last_observed_at", "status"],
    )?;
    if !SOURCES.contains(&str_field(source, "kind")?)
        || !["CURRENT", "STALE", "UNAVAILABLE"].contains(&str_field(source, "status")?)
    {
        return Err(invalid("unsupported Library source projection"));
    }
    id(str_field(source, "source_id")?)?;
    let last = utc(str_field(source, "last_observed_at")?)?;
    if last > now || (str_field(source, "status")? == "CURRENT" && fresh_until <= now) {
        return Err(invalid("Library source claimed fresh after expiry"));
    }
    let page = fields(&obj["page"], &["limit", "next_cursor", "cursor_state"])?;
    let limit = exact_int(&page["limit"], 1)?;
    if limit > 128 || !["CURRENT", "STALE", "LOST"].contains(&str_field(page, "cursor_state")?) {
        return Err(invalid("invalid Library catalog page"));
    }
    if !page["next_cursor"].is_null() {
        id(page["next_cursor"]
            .as_str()
            .ok_or_else(|| invalid("invalid catalog cursor"))?)?;
    }
    let items = obj["items"]
        .as_array()
        .ok_or_else(|| invalid("catalog items must be list"))?;
    if items.len() as u64 > limit {
        return Err(invalid("unbounded Library catalog page"));
    }
    for item in items {
        let entry = fields(item, &CATALOG_ITEM_KEYS)?;
        if !KINDS.contains(&str_field(entry, "kind")?) {
            return Err(invalid("unsupported artifact type"));
        }
        for name in [
            "artifact_id",
            "version",
            "publisher",
            "signer_key_id",
            "signature_receipt_ref",
            "target_os_arch",
            "sdk_range",
            "abi_range",
        ] {
            id(str_field(entry, name)?)?;
        }
        for name in ["manifest_digest", "content_digest"] {
            digest(str_field(entry, name)?)?;
        }
        exact_int(&entry["revision"], 1)?;
        exact_int(&entry["size_bytes"], 1)?;
        if !["ed25519", "ecdsa-p256"].contains(&str_field(entry, "signature_scheme")?)
            || !["permitted", "restricted", "non_redistributable", "unknown"]
                .contains(&str_field(entry, "license_distribution")?)
            || !["public", "protected", "private"].contains(&str_field(entry, "data_class")?)
        {
            return Err(invalid(
                "invalid artifact provenance or distribution metadata",
            ));
        }
        let allowed = entry["distribution_allowed"]
            .as_bool()
            .ok_or_else(|| invalid("distribution flag must be boolean"))?;
        if allowed
            && (str_field(entry, "license_distribution")? != "permitted"
                || str_field(entry, "data_class")? != "public")
        {
            return Err(invalid("restricted Library bytes offered as distributable"));
        }
    }
    Ok(())
}

fn transfer(
    data: &Value,
    expected: &UntrustedLibraryRequest,
    now: DateTime<FixedOffset>,
) -> Result<(), ContractError> {
    let obj = fields(data, &TRANSFER_KEYS)?;
    for name in [
        "job_id",
        "target_platform_id",
        "source_platform_id",
        "receipt_ref",
    ] {
        id(str_field(obj, name)?)?;
    }
    if str_field(obj, "target_platform_id")? != expected.target_platform_id {
        return Err(invalid("transfer status target differs from request"));
    }
    if !SOURCES.contains(&str_field(obj, "source_kind")?) {
        return Err(invalid("unknown transfer source"));
    }
    digest(str_field(obj, "artifact_content_digest")?)?;
    let total = exact_int(&obj["total_bytes"], 1)?;
    let received = exact_int(&obj["received_bytes"], 0)?;
    let verified = exact_int(&obj["verified_bytes"], 0)?;
    if received > total || verified > received {
        return Err(invalid("inconsistent transfer progress"));
    }
    let state = str_field(obj, "state")?;
    if ![
        "QUEUED",
        "DOWNLOADING",
        "PAUSED",
        "VERIFYING",
        "COMPLETE",
        "FAILED",
        "CANCELLED",
        "OUTCOME_UNKNOWN",
    ]
    .contains(&state)
    {
        return Err(invalid("unsupported transfer state"));
    }
    if state == "COMPLETE" && verified != total {
        return Err(invalid(
            "transfer completion is not independent verification",
        ));
    }
    if !obj["failure"].is_null()
        && ![
            "CONFLICT",
            "QUOTA_EXCEEDED",
            "REJECTED",
            "UNAVAILABLE",
            "INTERRUPTED",
        ]
        .contains(&str_field(obj, "failure")?)
    {
        return Err(invalid("unreviewed transfer failure"));
    }
    if utc(str_field(obj, "last_observed_at")?)? > now {
        return Err(invalid("transfer observation from future"));
    }
    if !obj["restart_cursor"].is_null() {
        id(obj["restart_cursor"]
            .as_str()
            .ok_or_else(|| invalid("invalid resume cursor"))?)?;
    }
    Ok(())
}

#[derive(Debug, Clone)]
pub struct UntrustedLibraryResponse {
    pub request_id: String,
    pub correlation_id: String,
    pub operation: String,
    pub platform_id: String,
    pub platform_generation: u64,
    pub state_revision: u64,
    pub observed_at: String,
    pub outcome: String,
    pub data: Option<Value>,
    pub denial_code: Option<String>,
}

impl UntrustedLibraryResponse {
    /// Syntax and request-correlation only. Never proves a Hub's publisher
    /// signature, installed-host identity, permissions, Core or worker state.
    ///
    /// # Errors
    /// Rejects untrusted authority, stale data, wrong generation/revision and
    /// claims that downloaded bytes are installed or independently verified.
    pub fn parse(
        raw: &[u8],
        expected: &UntrustedLibraryRequest,
        now: DateTime<FixedOffset>,
    ) -> Result<Self, ContractError> {
        let doc = decode(raw)?;
        let obj = fields(&doc, &RESPONSE_KEYS)?;
        if str_field(obj, "schema")? != LIBRARY_RESPONSE_SCHEMA
            || str_field(obj, "protocol")? != LIBRARY_PROTOCOL
            || str_field(obj, "request_id")? != expected.request_id
            || str_field(obj, "correlation_id")? != expected.correlation_id
            || str_field(obj, "operation")? != expected.operation
            || str_field(obj, "platform_id")? != expected.target_platform_id
            || exact_int(&obj["platform_generation"], 1)? != expected.expected_generation
            || exact_int(&obj["state_revision"], 0)? != expected.expected_revision
        {
            return Err(invalid(
                "Library correlation, revision or generation mismatch",
            ));
        }
        let observed_at = str_field(obj, "observed_at")?;
        let observed = utc(observed_at)?;
        let created = utc(&expected.created_at)?;
        let deadline = utc(&expected.deadline)?;
        if observed < created
            || observed > now
            || observed >= deadline
            || now >= deadline
            || now - observed > Duration::seconds(5)
        {
            return Err(invalid("Library response stale, future or replayed"));
        }
        let outcome = str_field(obj, "outcome")?;
        let (data, denial_code) = match outcome {
            "DENIED" => {
                if !obj["data"].is_null() {
                    return Err(invalid("denial cannot contain data"));
                }
                let denial = fields(&obj["denial"], &["code"])?;
                let code = str_field(denial, "code")?;
                if !DENIALS.contains(&code) {
                    return Err(invalid("unsupported Library denial"));
                }
                (None, Some(code.to_owned()))
            }
            "OK" => {
                if !obj["denial"].is_null() || !obj["data"].is_object() {
                    return Err(invalid("Library success must have typed data only"));
                }
                if expected.operation == "library.catalog.snapshot.v1" {
                    catalog(&obj["data"], expected, now)?;
                } else if expected.operation == "library.sources.snapshot.v1" {
                    owner_sources(&obj["data"], expected)?;
                } else if expected.operation == "library.transfer.status.v1" {
                    transfer(&obj["data"], expected, now)?;
                } else {
                    return Err(invalid("Library successful projection not yet frozen"));
                }
                (Some(obj["data"].clone()), None)
            }
            _ => return Err(invalid("unsupported Library response outcome")),
        };
        Ok(Self {
            request_id: expected.request_id.clone(),
            correlation_id: expected.correlation_id.clone(),
            operation: expected.operation.clone(),
            platform_id: expected.target_platform_id.clone(),
            platform_generation: expected.expected_generation,
            state_revision: expected.expected_revision,
            observed_at: observed_at.to_owned(),
            outcome: outcome.to_owned(),
            data,
            denial_code,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::{UntrustedLibraryRequest, UntrustedLibraryResponse};
    use chrono::{DateTime, FixedOffset};
    use serde_json::{json, Value};

    fn clock() -> DateTime<FixedOffset> {
        DateTime::parse_from_rfc3339("2026-11-08T04:00:02Z").expect("clock")
    }

    #[test]
    fn python_shared_library_catalog_and_denial_fixtures_are_syntax_only() {
        let request = UntrustedLibraryRequest::parse(
            include_str!("../../../../contracts/platform/library-request-catalog-preview-v1.json")
                .as_bytes(),
            clock(),
        )
        .expect("catalog request");
        let reply = UntrustedLibraryResponse::parse(
            include_str!("../../../../contracts/platform/library-response-catalog-preview-v1.json")
                .as_bytes(),
            &request,
            clock(),
        )
        .expect("catalog reply");
        assert_eq!(reply.outcome, "OK");
        assert_eq!(reply.state_revision, 12);
        let denied = UntrustedLibraryResponse::parse(
            include_str!("../../../../contracts/platform/library-response-stop-preview-v1.json")
                .as_bytes(),
            &request,
            clock(),
        )
        .expect("scoped STOP denial");
        assert_eq!(denied.denial_code.as_deref(), Some("STOPPED"));
        assert!(denied.data.is_none());
    }

    #[test]
    fn transfer_bytes_received_never_imply_verified_or_installed() {
        let request = UntrustedLibraryRequest::parse(
            include_str!("../../../../contracts/platform/library-request-transfer-preview-v1.json")
                .as_bytes(),
            clock(),
        )
        .expect("transfer request");
        let body = include_str!(
            "../../../../contracts/platform/library-response-transfer-preview-v1.json"
        );
        let reply = UntrustedLibraryResponse::parse(body.as_bytes(), &request, clock())
            .expect("valid verification pending");
        let data = reply.data.expect("transfer observation");
        assert_eq!(data["received_bytes"], 4096);
        assert_eq!(data["verified_bytes"], 0);
        assert!(data.get("installed").is_none());
        let mut complete: Value = serde_json::from_str(body).expect("fixture");
        complete["data"]["state"] = json!("COMPLETE");
        assert!(UntrustedLibraryResponse::parse(
            complete.to_string().as_bytes(),
            &request,
            clock()
        )
        .is_err());
    }

    #[test]
    fn shared_python_owner_sources_are_correlated_without_grant_claims() {
        let request = UntrustedLibraryRequest::parse(
            include_str!("../../../../contracts/platform/library-request-personal-sources-v1.json")
                .as_bytes(),
            clock(),
        )
        .expect("typed personal-only source request");
        assert_eq!(request.operation, "library.sources.snapshot.v1");
        let reply = UntrustedLibraryResponse::parse(
            include_str!(
                "../../../../contracts/platform/library-response-personal-sources-v1.json"
            )
            .as_bytes(),
            &request,
            clock(),
        )
        .expect("strict source projection");
        assert_eq!(reply.state_revision, 0);
        let data = reply.data.expect("owner-only data");
        assert_eq!(data["owner_mode"], "SINGLE_OWNER_PRIVATE");
        assert_eq!(data["publisher_state"], "CURRENT");
        assert_eq!(data["hub_state"], "SERVING");
        assert_eq!(data["served_bytes"], 3145728);
        assert!(data.get("installed").is_none());
        assert!(data.get("private_key").is_none());
    }

    #[test]
    fn personal_sources_refuse_fake_ready_and_leaked_authority() {
        let req_bytes =
            include_str!("../../../../contracts/platform/library-request-personal-sources-v1.json");
        let request = UntrustedLibraryRequest::parse(req_bytes.as_bytes(), clock())
            .expect("expected source read");
        let fixture = include_str!(
            "../../../../contracts/platform/library-response-personal-sources-v1.json"
        );
        let original: Value = serde_json::from_str(fixture).expect("source fixture");
        let mut invalid = original.clone();
        invalid["data"]["publisher_state"] = json!("UNENROLLED");
        assert!(
            UntrustedLibraryResponse::parse(invalid.to_string().as_bytes(), &request, clock(),)
                .is_err()
        );
        invalid = original.clone();
        invalid["data"]["owner_proof"] = json!("forged");
        assert!(
            UntrustedLibraryResponse::parse(invalid.to_string().as_bytes(), &request, clock(),)
                .is_err()
        );
        invalid = original.clone();
        invalid["data"]["hub_state"] = json!("READY");
        assert!(
            UntrustedLibraryResponse::parse(invalid.to_string().as_bytes(), &request, clock(),)
                .is_err()
        );
        invalid = original.clone();
        invalid["data"]["served_bytes"] = json!(-1);
        assert!(
            UntrustedLibraryResponse::parse(invalid.to_string().as_bytes(), &request, clock(),)
                .is_err()
        );
        invalid = original.clone();
        invalid["state_revision"] = json!(1);
        assert!(
            UntrustedLibraryResponse::parse(invalid.to_string().as_bytes(), &request, clock(),)
                .is_err()
        );
    }

    #[test]
    fn hostile_library_authority_fields_and_versions_fail_closed() {
        let request_fixture =
            include_str!("../../../../contracts/platform/library-request-catalog-preview-v1.json");
        let response_fixture =
            include_str!("../../../../contracts/platform/library-response-catalog-preview-v1.json");
        let mut payload: Value = serde_json::from_str(request_fixture).expect("fixture");
        payload["protocol"] = json!("1.1");
        assert!(UntrustedLibraryRequest::parse(payload.to_string().as_bytes(), clock()).is_err());
        payload["protocol"] = json!("1.0");
        payload["operation"] = json!("library.install.execute.v1");
        assert!(UntrustedLibraryRequest::parse(payload.to_string().as_bytes(), clock()).is_err());
        payload["operation"] = json!("library.catalog.snapshot.v1");
        payload["caller_principal"] = json!("owner:forged");
        assert!(UntrustedLibraryRequest::parse(payload.to_string().as_bytes(), clock()).is_err());
        let request = UntrustedLibraryRequest::parse(request_fixture.as_bytes(), clock())
            .expect("valid request");
        let mut reply: Value = serde_json::from_str(response_fixture).expect("fixture");
        reply["data"]["items"][0]["installed"] = json!(true);
        assert!(
            UntrustedLibraryResponse::parse(reply.to_string().as_bytes(), &request, clock())
                .is_err()
        );
        reply["data"]["items"][0]
            .as_object_mut()
            .expect("item")
            .remove("installed");
        reply["data"]["items"][0]["license_distribution"] = json!("non_redistributable");
        assert!(
            UntrustedLibraryResponse::parse(reply.to_string().as_bytes(), &request, clock())
                .is_err()
        );
        let mut absent: Value = serde_json::from_str(response_fixture).expect("fixture");
        absent.as_object_mut().expect("reply").remove("denial");
        assert!(
            UntrustedLibraryResponse::parse(absent.to_string().as_bytes(), &request, clock())
                .is_err()
        );
    }
}
