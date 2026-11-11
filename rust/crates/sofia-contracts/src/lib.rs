//! Authority-free, strict wire contracts shared with the Python SDK.
#![forbid(unsafe_code)]

pub mod identity;
pub mod library;
pub mod management;
pub mod ui_theme;
pub use identity::{AegisIdentity, IdentityKind, IDENTITY_SCHEMA};

use chrono::{DateTime, FixedOffset};
use regex::Regex;
use serde::de::{self, Deserialize, Deserializer, MapAccess, SeqAccess, Visitor};
use serde::Deserialize as DeriveDeserialize;
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fmt;
use std::sync::OnceLock;
use thiserror::Error;

pub const MAX_MESSAGE_BYTES: usize = 64 * 1024;
pub const MAX_NESTING_DEPTH: usize = 64;
pub const SUPPORTED_PROTOCOL: &str = "1.0";

#[derive(Debug, Error)]
#[error("{code}: {message}")]
pub struct ContractError {
    pub code: &'static str,
    pub message: String,
}

impl ContractError {
    #[must_use]
    pub fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }
}

#[derive(Debug)]
struct StrictValue(Value);

impl<'de> Deserialize<'de> for StrictValue {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        struct StrictVisitor;
        impl<'de> Visitor<'de> for StrictVisitor {
            type Value = StrictValue;
            fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
                formatter.write_str("finite JSON without duplicate object keys")
            }
            fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::Bool(value)))
            }
            fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::Number(value.into())))
            }
            fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::Number(value.into())))
            }
            fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
            where
                E: de::Error,
            {
                serde_json::Number::from_f64(value)
                    .map(|n| StrictValue(Value::Number(n)))
                    .ok_or_else(|| E::custom("non-finite number"))
            }
            fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
            where
                E: de::Error,
            {
                Ok(StrictValue(Value::String(value.to_owned())))
            }
            fn visit_string<E>(self, value: String) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::String(value)))
            }
            fn visit_none<E>(self) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::Null))
            }
            fn visit_unit<E>(self) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::Null))
            }
            fn visit_some<D>(self, deserializer: D) -> Result<Self::Value, D::Error>
            where
                D: Deserializer<'de>,
            {
                StrictValue::deserialize(deserializer)
            }
            fn visit_seq<A>(self, mut sequence: A) -> Result<Self::Value, A::Error>
            where
                A: SeqAccess<'de>,
            {
                let mut values = Vec::new();
                while let Some(value) = sequence.next_element::<StrictValue>()? {
                    values.push(value.0);
                }
                Ok(StrictValue(Value::Array(values)))
            }
            fn visit_map<A>(self, mut object: A) -> Result<Self::Value, A::Error>
            where
                A: MapAccess<'de>,
            {
                let mut values = Map::new();
                while let Some((key, value)) = object.next_entry::<String, StrictValue>()? {
                    if values.insert(key.clone(), value.0).is_some() {
                        return Err(de::Error::custom(format!("duplicate JSON key: {key}")));
                    }
                }
                Ok(StrictValue(Value::Object(values)))
            }
        }
        deserializer.deserialize_any(StrictVisitor)
    }
}

fn check_depth(value: &Value, depth: usize) -> Result<(), ContractError> {
    if depth > MAX_NESTING_DEPTH {
        return Err(ContractError::new(
            "malformed_json",
            "contract nesting exceeds 64 levels",
        ));
    }
    match value {
        Value::Array(values) => values
            .iter()
            .try_for_each(|child| check_depth(child, depth + 1)),
        Value::Object(values) => values
            .values()
            .try_for_each(|child| check_depth(child, depth + 1)),
        _ => Ok(()),
    }
}

/// Parse one bounded JSON document while rejecting duplicate keys.
///
/// # Errors
/// Returns a stable wire error for oversized, non-UTF-8, duplicate, or malformed input.
pub fn parse_strict(raw: &[u8]) -> Result<Value, ContractError> {
    if raw.len() > MAX_MESSAGE_BYTES {
        return Err(ContractError::new(
            "oversized",
            "contract message exceeds 64 KiB",
        ));
    }
    let text = std::str::from_utf8(raw)
        .map_err(|_| ContractError::new("malformed_json", "contract message is not UTF-8"))?;
    let mut decoder = serde_json::Deserializer::from_str(text);
    let value = StrictValue::deserialize(&mut decoder).map_err(|error| {
        let code = if error.to_string().contains("duplicate JSON key") {
            "duplicate_key"
        } else {
            "malformed_json"
        };
        ContractError::new(code, error.to_string())
    })?;
    decoder
        .end()
        .map_err(|error| ContractError::new("malformed_json", error.to_string()))?;
    check_depth(&value.0, 0)?;
    Ok(value.0)
}

/// Encode finite JSON with sorted keys and no insignificant whitespace.
///
/// # Errors
/// Returns `malformed_json` if the supplied value cannot be encoded.
pub fn canonical_json(value: &Value) -> Result<Vec<u8>, ContractError> {
    fn validate(value: &Value) -> Result<(), ContractError> {
        match value {
            Value::Null | Value::Bool(_) | Value::String(_) => Ok(()),
            Value::Number(number) if number.is_i64() || number.is_u64() => Ok(()),
            Value::Number(_) => Err(ContractError::new(
                "malformed_json",
                "canonical v1 JSON permits bounded integers, not fractions",
            )),
            Value::Array(values) => values.iter().try_for_each(validate),
            Value::Object(values) => values.values().try_for_each(validate),
        }
    }
    validate(value)?;
    serde_json::to_vec(value)
        .map_err(|error| ContractError::new("malformed_json", error.to_string()))
}

/// Hash canonical JSON bytes as lowercase SHA-256 hexadecimal.
///
/// # Errors
/// Returns the canonical encoding error if the value cannot be encoded.
pub fn canonical_sha256(value: &Value) -> Result<String, ContractError> {
    let bytes = canonical_json(value)?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
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
fn payload_type_regex() -> &'static Regex {
    static VALUE: OnceLock<Regex> = OnceLock::new();
    VALUE.get_or_init(|| {
        Regex::new(r"^[a-z][a-z0-9_.-]{0,127}\.v[1-9][0-9]*$").expect("constant regex")
    })
}
fn valid_id(value: &str) -> bool {
    id_regex().is_match(value)
}
fn parse_time(value: &str) -> Result<DateTime<FixedOffset>, ContractError> {
    DateTime::parse_from_rfc3339(value)
        .map_err(|_| ContractError::new("invalid_contract", "timestamp must be RFC 3339"))
}

#[derive(Debug, DeriveDeserialize)]
#[serde(deny_unknown_fields, rename_all = "lowercase")]
pub enum ComponentKind {
    Platform,
    Core,
    Module,
    Inference,
}

#[derive(Debug, DeriveDeserialize)]
#[serde(deny_unknown_fields)]
pub struct ComponentEndpoint {
    pub component_id: String,
    pub kind: ComponentKind,
    pub release_digest: String,
    pub generation: u64,
    pub platform_instance_id: String,
    pub core_identity_id: Option<String>,
}

impl ComponentEndpoint {
    fn validate(&self) -> Result<(), ContractError> {
        if !valid_id(&self.component_id)
            || !valid_id(&self.platform_instance_id)
            || !digest_regex().is_match(&self.release_digest)
            || self.generation == 0
        {
            return Err(ContractError::new(
                "invalid_contract",
                "invalid component endpoint",
            ));
        }
        let core = matches!(self.kind, ComponentKind::Core);
        if core != self.core_identity_id.is_some()
            || self
                .core_identity_id
                .as_deref()
                .is_some_and(|id| !valid_id(id))
        {
            return Err(ContractError::new(
                "invalid_contract",
                "invalid Core identity binding",
            ));
        }
        Ok(())
    }
}

#[derive(Debug, DeriveDeserialize)]
#[serde(deny_unknown_fields)]
pub struct AuthorityProjection {
    pub principal_id: String,
    pub audience_id: String,
    pub audience_kind: String,
    pub authority_ref: String,
    pub scopes: Vec<String>,
    pub expires_at: String,
}

impl AuthorityProjection {
    fn validate(&self) -> Result<DateTime<FixedOffset>, ContractError> {
        if !valid_id(&self.principal_id)
            || !valid_id(&self.audience_id)
            || !valid_id(&self.authority_ref)
            || !matches!(
                self.audience_kind.as_str(),
                "private" | "shared" | "public" | "system"
            )
            || self.scopes.is_empty()
            || self.scopes.len() > 32
            || self.scopes.iter().any(|scope| !valid_id(scope))
            || self.scopes.iter().collect::<HashSet<_>>().len() != self.scopes.len()
        {
            return Err(ContractError::new(
                "invalid_contract",
                "invalid authority projection",
            ));
        }
        parse_time(&self.expires_at)
    }
}

#[derive(Debug, DeriveDeserialize)]
#[serde(deny_unknown_fields)]
pub struct ComponentRequest {
    pub protocol: String,
    pub request_id: String,
    pub correlation_id: String,
    pub idempotency_key: String,
    pub source: ComponentEndpoint,
    pub destination: ComponentEndpoint,
    pub authority: AuthorityProjection,
    pub payload_type: String,
    pub payload_digest: String,
    pub created_at: String,
    pub deadline: String,
}

pub struct DispatchContext<'a> {
    pub now: DateTime<FixedOffset>,
    pub expected_destination_generation: u64,
    pub expected_audience_id: &'a str,
}

impl ComponentRequest {
    fn validate(&self) -> Result<(), ContractError> {
        if self.protocol != SUPPORTED_PROTOCOL {
            return Err(ContractError::new(
                "unsupported_protocol",
                "unsupported SDK protocol",
            ));
        }
        if !payload_type_regex().is_match(&self.payload_type) {
            return Err(ContractError::new(
                "unsupported_schema",
                "unsupported payload schema",
            ));
        }
        if !valid_id(&self.request_id)
            || !valid_id(&self.correlation_id)
            || !valid_id(&self.idempotency_key)
            || !digest_regex().is_match(&self.payload_digest)
        {
            return Err(ContractError::new(
                "invalid_contract",
                "invalid component request",
            ));
        }
        self.source.validate()?;
        self.destination.validate()?;
        let expires = self.authority.validate()?;
        let created = parse_time(&self.created_at)?;
        let deadline = parse_time(&self.deadline)?;
        if deadline <= created || expires < deadline {
            return Err(ContractError::new(
                "invalid_contract",
                "invalid request deadline",
            ));
        }
        Ok(())
    }
    fn validate_context(&self, context: &DispatchContext<'_>) -> Result<(), ContractError> {
        if self.authority.audience_id != context.expected_audience_id {
            return Err(ContractError::new(
                "wrong_audience",
                "authority audience does not match dispatch",
            ));
        }
        if self.destination.generation != context.expected_destination_generation {
            return Err(ContractError::new(
                "wrong_generation",
                "destination generation is stale",
            ));
        }
        let expires = parse_time(&self.authority.expires_at)?;
        let deadline = parse_time(&self.deadline)?;
        if context.now >= expires || context.now >= deadline {
            return Err(ContractError::new("expired", "request is expired"));
        }
        Ok(())
    }
}

#[derive(Debug, DeriveDeserialize)]
#[serde(rename_all = "snake_case")]
pub enum ComponentOutcome {
    Denied,
    Unavailable,
    Failed,
    Cancelled,
    OutcomeUnknown,
    SucceededReportedUnverified,
    SucceededVerified,
}

#[derive(Debug, DeriveDeserialize)]
#[serde(deny_unknown_fields)]
pub struct ComponentResponse {
    pub protocol: String,
    pub request_id: String,
    pub correlation_id: String,
    pub responder: ComponentEndpoint,
    pub outcome: ComponentOutcome,
    pub payload_type: Option<String>,
    pub payload_digest: Option<String>,
    pub evidence_refs: Vec<String>,
    pub completed_at: String,
}

impl ComponentResponse {
    fn validate(&self) -> Result<(), ContractError> {
        if self.protocol != SUPPORTED_PROTOCOL {
            return Err(ContractError::new(
                "unsupported_protocol",
                "unsupported SDK protocol",
            ));
        }
        if !valid_id(&self.request_id) || !valid_id(&self.correlation_id) {
            return Err(ContractError::new(
                "invalid_contract",
                "invalid response identity",
            ));
        }
        self.responder.validate()?;
        if self.payload_type.is_some() != self.payload_digest.is_some()
            || self
                .payload_type
                .as_deref()
                .is_some_and(|v| !payload_type_regex().is_match(v))
            || self
                .payload_digest
                .as_deref()
                .is_some_and(|v| !digest_regex().is_match(v))
            || self.evidence_refs.len() > 32
            || self.evidence_refs.iter().any(|v| !valid_id(v))
            || matches!(self.outcome, ComponentOutcome::SucceededVerified)
                && self.evidence_refs.is_empty()
        {
            return Err(ContractError::new(
                "invalid_contract",
                "invalid component response",
            ));
        }
        parse_time(&self.completed_at)?;
        Ok(())
    }
}

fn deserialize_contract<T: for<'de> Deserialize<'de>>(value: Value) -> Result<T, ContractError> {
    serde_json::from_value(value)
        .map_err(|error| ContractError::new("invalid_contract", error.to_string()))
}

/// Strictly decode a request and optionally check payload and dispatch context.
///
/// # Errors
/// Returns a stable contract error when framing, shape, digest, audience,
/// generation, deadline, or protocol validation fails.
pub fn decode_request(
    raw: &[u8],
    context: Option<&DispatchContext<'_>>,
    payload: Option<&Value>,
) -> Result<ComponentRequest, ContractError> {
    let request: ComponentRequest = deserialize_contract(parse_strict(raw)?)?;
    request.validate()?;
    if let Some(value) = payload {
        if canonical_sha256(value)? != request.payload_digest {
            return Err(ContractError::new(
                "digest_mismatch",
                "payload digest mismatch",
            ));
        }
    }
    if let Some(value) = context {
        request.validate_context(value)?;
    }
    Ok(request)
}

/// Strictly decode a component response.
///
/// # Errors
/// Returns a stable contract error when framing, shape, outcome, or protocol
/// validation fails.
pub fn decode_response(raw: &[u8]) -> Result<ComponentResponse, ContractError> {
    let response: ComponentResponse = deserialize_contract(parse_strict(raw)?)?;
    response.validate()?;
    Ok(response)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn duplicate_keys_are_rejected() {
        let error = parse_strict(br#"{"a":1,"a":2}"#).expect_err("duplicate accepted");
        assert_eq!(error.code, "duplicate_key");
    }
    #[test]
    fn canonical_digest_is_order_independent() {
        let left = parse_strict(r#"{"z":1,"a":"é"}"#.as_bytes()).expect("valid");
        let right = parse_strict(r#"{"a":"é","z":1}"#.as_bytes()).expect("valid");
        assert_eq!(
            canonical_sha256(&left).expect("digest"),
            canonical_sha256(&right).expect("digest")
        );
    }

    #[test]
    fn deterministic_canonical_property_corpus_is_order_independent() {
        for index in 0..128_u64 {
            let left = format!(r#"{{"z":{index},"a":[true,null,"value"]}}"#);
            let right = format!(r#"{{"a":[true,null,"value"],"z":{index}}}"#);
            let left = parse_strict(left.as_bytes()).expect("valid generated JSON");
            let right = parse_strict(right.as_bytes()).expect("valid generated JSON");
            assert_eq!(
                canonical_sha256(&left).expect("left digest"),
                canonical_sha256(&right).expect("right digest")
            );
        }
    }
}
