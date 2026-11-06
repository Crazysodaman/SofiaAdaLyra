//! Lossless identity projections. Decoding never authenticates or allocates one.

use crate::ContractError;
use serde_json::{json, Value};

pub const IDENTITY_SCHEMA: &str = "aegis.identity.v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum IdentityKind {
    Platform,
    Core,
}

impl IdentityKind {
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Platform => "platform",
            Self::Core => "core",
        }
    }
}

/// An inert typed UUID, never evidence of enrollment, permission or ownership.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct AegisIdentity {
    kind: IdentityKind,
    uuid_bytes: [u8; 16],
}

impl AegisIdentity {
    /// Wrap existing UUID bytes without allocating or deriving another identity.
    #[must_use]
    pub const fn new(kind: IdentityKind, uuid_bytes: [u8; 16]) -> Self {
        Self { kind, uuid_bytes }
    }

    #[must_use]
    pub const fn kind(self) -> IdentityKind {
        self.kind
    }

    #[must_use]
    pub const fn uuid_bytes(self) -> [u8; 16] {
        self.uuid_bytes
    }

    #[must_use]
    pub fn canonical_uuid(self) -> String {
        let digits = format!("{:032x}", u128::from_be_bytes(self.uuid_bytes));
        format!(
            "{}-{}-{}-{}-{}",
            &digits[..8],
            &digits[8..12],
            &digits[12..16],
            &digits[16..20],
            &digits[20..]
        )
    }

    #[must_use]
    pub fn serial(self) -> String {
        let prefix = match self.kind {
            IdentityKind::Platform => 'P',
            IdentityKind::Core => 'C',
        };
        let digits = format!("{:032X}", u128::from_be_bytes(self.uuid_bytes));
        format!(
            "AEG-{prefix}-{}-{}-{}-{}",
            &digits[..8],
            &digits[8..16],
            &digits[16..24],
            &digits[24..]
        )
    }

    /// Parse only full hyphenated UUID text, normalizing ASCII hexadecimal case.
    ///
    /// # Errors
    /// Rejects shortened forms, whitespace, URNs and non-ASCII hexadecimal.
    pub fn from_uuid_text(kind: IdentityKind, value: &str) -> Result<Self, ContractError> {
        Ok(Self::new(
            kind,
            grouped_hex(value.as_bytes(), 36, &[8, 13, 18, 23])?,
        ))
    }

    /// Parse serial v1 without inferring trust from the prefix or digits.
    ///
    /// # Errors
    /// Rejects unknown prefixes, separators, lengths, whitespace and non-ASCII input.
    pub fn from_serial(value: &str) -> Result<Self, ContractError> {
        let bytes = value.as_bytes();
        if bytes.len() != 41 || !bytes[..4].eq_ignore_ascii_case(b"AEG-") || bytes[5] != b'-' {
            return Err(invalid_identity());
        }
        let kind = match bytes[4].to_ascii_uppercase() {
            b'P' => IdentityKind::Platform,
            b'C' => IdentityKind::Core,
            _ => return Err(invalid_identity()),
        };
        Ok(Self::new(kind, grouped_hex(&bytes[6..], 35, &[8, 17, 26])?))
    }

    #[must_use]
    pub fn to_payload(self) -> Value {
        json!({"schema": IDENTITY_SCHEMA, "kind": self.kind.as_str(), "uuid": self.canonical_uuid()})
    }

    /// Decode the exact versioned, authority-free projection shape.
    ///
    /// # Errors
    /// Rejects unknown schemas, additional fields and malformed kind/UUID values.
    pub fn from_payload(payload: &Value) -> Result<Self, ContractError> {
        let object = payload.as_object().ok_or_else(invalid_identity)?;
        if object.len() != 3
            || object.get("schema").and_then(Value::as_str) != Some(IDENTITY_SCHEMA)
        {
            return Err(invalid_identity());
        }
        let kind = match object.get("kind").and_then(Value::as_str) {
            Some("platform") => IdentityKind::Platform,
            Some("core") => IdentityKind::Core,
            _ => return Err(invalid_identity()),
        };
        let uuid = object
            .get("uuid")
            .and_then(Value::as_str)
            .ok_or_else(invalid_identity)?;
        Self::from_uuid_text(kind, uuid)
    }
}

fn invalid_identity() -> ContractError {
    ContractError::new(
        "invalid_identity",
        "unsupported or malformed Aegis identity",
    )
}

fn grouped_hex(
    bytes: &[u8],
    length: usize,
    separators: &[usize],
) -> Result<[u8; 16], ContractError> {
    if bytes.len() != length {
        return Err(invalid_identity());
    }
    let mut value = 0_u128;
    for (index, byte) in bytes.iter().enumerate() {
        if separators.contains(&index) {
            if *byte != b'-' {
                return Err(invalid_identity());
            }
        } else {
            let digit = match byte {
                b'0'..=b'9' => byte - b'0',
                b'a'..=b'f' => byte - b'a' + 10,
                b'A'..=b'F' => byte - b'A' + 10,
                _ => return Err(invalid_identity()),
            };
            value = (value << 4) | u128::from(digit);
        }
    }
    Ok(value.to_be_bytes())
}
