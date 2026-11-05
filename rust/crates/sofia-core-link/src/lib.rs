//! Read-only Core Link client. Authority comes exclusively from the enrolled
//! client certificate; wire JSON contains routing data, never grants.

use chrono::{DateTime, Duration, Utc};
use regex::Regex;
use reqwest::blocking::Client;
use reqwest::{StatusCode, Url};
use rustls::client::danger::{HandshakeSignatureValid, ServerCertVerified, ServerCertVerifier};
use rustls::client::WebPkiServerVerifier;
use rustls::pki_types::{pem::PemObject, CertificateDer, PrivateKeyDer, ServerName, UnixTime};
use rustls::{DigitallySignedStruct, RootCertStore, SignatureScheme};
use serde::de::{self, Deserializer, MapAccess, SeqAccess, Visitor};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::fmt;
use std::io::Read;
use std::sync::Arc;
use std::time::Duration as StdDuration;
use thiserror::Error;
use x509_parser::parse_x509_certificate;

pub const PROTOCOL: &str = "1.0";
pub const MAX_PAYLOAD_BYTES: usize = 64 * 1024;
pub const MAX_WIRE_BYTES: usize = 72 * 1024;
const REQUEST_SCHEMA: &str = "companion.platform.core_link_request.v1";
const RESPONSE_SCHEMA: &str = "companion.platform.core_link_response.v1";

#[derive(Debug, Error)]
pub enum Error {
    #[error("invalid Core Link contract: {0}")]
    Contract(&'static str),
    #[error("selected Core Link binding is not active")]
    RevokedBinding,
    #[error("Core Link request does not match enrolled binding")]
    BindingMismatch,
    #[error("Core Link deadline expired")]
    Deadline,
    #[error("Core Link authentication or connection failed")]
    Connection(#[source] reqwest::Error),
    #[error("Core Link host returned HTTP {0}")]
    Http(StatusCode),
    #[error("Core Link response exceeds 72 KiB")]
    Oversized,
    #[error("Core Link response is malformed")]
    Malformed,
}

#[derive(Clone, Debug)]
pub struct EnrolledBinding {
    pub active: bool,
    pub local_platform_id: String,
    pub remote_platform_id: String,
    pub remote_core_identity_id: String,
    pub remote_core_generation: u64,
    pub endpoint: Url,
    pub protocol: String,
    /// Lowercase SHA-256 of the enrolled host certificate public-key bits.
    pub trust_anchor_sha256: String,
}

#[derive(Clone)]
pub struct TlsCredentials {
    /// PEM trust anchor and combined PEM client certificate/private key.
    /// Callers must resolve these from the Platform secret owner at use time.
    pub ca_pem: Vec<u8>,
    pub client_identity_pem: Vec<u8>,
}

// Never derive Debug for a structure containing PEM private-key bytes.
impl fmt::Debug for TlsCredentials {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("TlsCredentials")
            .field("ca_pem", &"[REDACTED]")
            .field("client_identity_pem", &"[REDACTED]")
            .finish()
    }
}

/// Exact non-null Core Link history cursor used by the Python gateway.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HistoryCursor {
    pub created_at: DateTime<Utc>,
    pub message_id: String,
}

#[derive(Clone, Debug)]
pub struct Request {
    pub request_id: String,
    pub idempotency_key: String,
    pub local_platform_id: String,
    pub remote_platform_id: String,
    pub remote_core_identity_id: String,
    pub remote_core_generation: u64,
    pub operation: String,
    pub payload: Value,
    pub created_at: DateTime<Utc>,
    pub deadline: DateTime<Utc>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Response {
    pub request_id: String,
    pub status: String,
    pub payload: Value,
    pub server_at: DateTime<Utc>,
}

fn valid_id(value: &str) -> bool {
    Regex::new(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
        .expect("constant regex")
        .is_match(value)
}

fn canonical_size(value: &Value) -> Result<usize, Error> {
    serde_json::to_vec(value)
        .map(|bytes| bytes.len())
        .map_err(|_| Error::Contract("payload must be finite JSON"))
}

impl Request {
    #[must_use]
    pub fn status(binding: &EnrolledBinding, request_id: &str, now: DateTime<Utc>) -> Self {
        Self::new(
            binding,
            request_id,
            request_id,
            "status",
            Value::Object(Map::new()),
            now,
        )
    }

    /// Builds a bounded query for an existing authorized session.
    ///
    /// # Errors
    /// Returns an error for an invalid session/cursor or limit.
    pub fn history(
        binding: &EnrolledBinding,
        request_id: &str,
        session_id: &str,
        after: Option<&HistoryCursor>,
        limit: u16,
        now: DateTime<Utc>,
    ) -> Result<Self, Error> {
        if !valid_id(session_id)
            || after.is_some_and(|cursor| !valid_id(&cursor.message_id))
            || !(1..=200).contains(&limit)
        {
            return Err(Error::Contract("invalid history query"));
        }
        let after = after.map(|cursor| {
            serde_json::json!({
                "created_at": cursor.created_at.to_rfc3339(),
                "message_id": cursor.message_id,
            })
        });
        let payload = serde_json::json!({"session_id": session_id, "after": after, "limit": limit});
        Ok(Self::new(
            binding,
            request_id,
            request_id,
            "conversation.history",
            payload,
            now,
        ))
    }

    fn new(
        binding: &EnrolledBinding,
        request_id: &str,
        idempotency_key: &str,
        operation: &str,
        payload: Value,
        now: DateTime<Utc>,
    ) -> Self {
        Self {
            request_id: request_id.to_owned(),
            idempotency_key: idempotency_key.to_owned(),
            local_platform_id: binding.local_platform_id.clone(),
            remote_platform_id: binding.remote_platform_id.clone(),
            remote_core_identity_id: binding.remote_core_identity_id.clone(),
            remote_core_generation: binding.remote_core_generation,
            operation: operation.to_owned(),
            payload,
            created_at: now,
            deadline: now + Duration::seconds(30),
        }
    }

    /// Produces the exact authority-free Core Link wire object.
    ///
    /// # Errors
    /// Returns an error when an identifier, operation, payload, generation, or deadline is invalid.
    pub fn to_value(&self) -> Result<Value, Error> {
        for value in [
            &self.request_id,
            &self.idempotency_key,
            &self.local_platform_id,
            &self.remote_platform_id,
            &self.remote_core_identity_id,
        ] {
            if !valid_id(value) {
                return Err(Error::Contract("identifier is invalid"));
            }
        }
        if self.remote_core_generation == 0 {
            return Err(Error::Contract("generation must be positive"));
        }
        if !matches!(self.operation.as_str(), "status" | "conversation.history") {
            return Err(Error::Contract("operation is not read-only"));
        }
        if !self.payload.is_object() || canonical_size(&self.payload)? > MAX_PAYLOAD_BYTES {
            return Err(Error::Contract(
                "payload exceeds 64 KiB or is not an object",
            ));
        }
        let lifetime = self.deadline - self.created_at;
        if lifetime <= Duration::zero() || lifetime > Duration::minutes(5) {
            return Err(Error::Contract("invalid deadline"));
        }
        Ok(serde_json::json!({
            "schema": REQUEST_SCHEMA, "protocol": PROTOCOL,
            "request_id": self.request_id, "idempotency_key": self.idempotency_key,
            "local_platform_id": self.local_platform_id,
            "remote_platform_id": self.remote_platform_id,
            "remote_core_identity_id": self.remote_core_identity_id,
            "remote_core_generation": self.remote_core_generation,
            "operation": self.operation, "payload": self.payload,
            "created_at": self.created_at.to_rfc3339(), "deadline": self.deadline.to_rfc3339()
        }))
    }
}

/// Enforce the existing Python Core Link SPKI pin *during* TLS certificate
/// validation, before reqwest can transmit an HTTP request on that connection.
/// The standard verifier must still validate hostname, CA chain and validity.
#[derive(Debug)]
struct PinnedServerVerifier {
    standard: Arc<dyn ServerCertVerifier>,
    sha256: String,
}

impl ServerCertVerifier for PinnedServerVerifier {
    fn verify_server_cert(
        &self,
        end_entity: &CertificateDer<'_>,
        intermediates: &[CertificateDer<'_>],
        server_name: &ServerName<'_>,
        ocsp_response: &[u8],
        now: UnixTime,
    ) -> Result<ServerCertVerified, rustls::Error> {
        let verified = self.standard.verify_server_cert(
            end_entity,
            intermediates,
            server_name,
            ocsp_response,
            now,
        )?;
        let (_, certificate) = parse_x509_certificate(end_entity.as_ref())
            .map_err(|_| rustls::Error::General("invalid Core Link host certificate".into()))?;
        // Python's certificate pin hashes DER SubjectPublicKeyInfo, not the leaf.
        let observed = format!("{:x}", Sha256::digest(certificate.public_key().raw));
        if observed != self.sha256 {
            return Err(rustls::Error::General(
                "Core Link host public-key pin mismatch".into(),
            ));
        }
        Ok(verified)
    }

    fn verify_tls12_signature(
        &self,
        message: &[u8],
        cert: &CertificateDer<'_>,
        dss: &DigitallySignedStruct,
    ) -> Result<HandshakeSignatureValid, rustls::Error> {
        self.standard.verify_tls12_signature(message, cert, dss)
    }

    fn verify_tls13_signature(
        &self,
        message: &[u8],
        cert: &CertificateDer<'_>,
        dss: &DigitallySignedStruct,
    ) -> Result<HandshakeSignatureValid, rustls::Error> {
        self.standard.verify_tls13_signature(message, cert, dss)
    }

    fn supported_verify_schemes(&self) -> Vec<SignatureScheme> {
        self.standard.supported_verify_schemes()
    }
}

pub struct CoreLinkClient {
    binding: EnrolledBinding,
    client: Client,
}

impl CoreLinkClient {
    /// Constructs an HTTPS-only client from an active enrolled binding.
    ///
    /// # Errors
    /// Returns an error for an invalid binding, certificate, key, trust anchor, or TLS configuration.
    pub fn new(
        binding: EnrolledBinding,
        credentials: &TlsCredentials,
        timeout: StdDuration,
    ) -> Result<Self, Error> {
        if !binding.active {
            return Err(Error::RevokedBinding);
        }
        if binding.protocol != PROTOCOL {
            return Err(Error::Contract("unsupported protocol"));
        }
        if binding.trust_anchor_sha256.len() != 64
            || !binding
                .trust_anchor_sha256
                .bytes()
                .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
        {
            return Err(Error::Contract("invalid host public-key pin"));
        }
        if binding.endpoint.scheme() != "https"
            || binding.endpoint.path() != "/v1/core-link"
            || binding.endpoint.query().is_some()
            || binding.endpoint.fragment().is_some()
            || !binding.endpoint.username().is_empty()
            || binding.endpoint.password().is_some()
        {
            return Err(Error::Contract(
                "endpoint must be the exact Core Link HTTPS path without credentials, query or fragment",
            ));
        }
        let ca_certificates = CertificateDer::pem_slice_iter(&credentials.ca_pem)
            .collect::<Result<Vec<_>, _>>()
            .map_err(|_| Error::Contract("invalid Core Link CA certificate PEM"))?;
        if ca_certificates.is_empty() {
            return Err(Error::Contract("Core Link CA certificate required"));
        }
        let mut roots = RootCertStore::empty();
        for ca in ca_certificates {
            roots
                .add(ca)
                .map_err(|_| Error::Contract("invalid Core Link CA certificate"))?;
        }
        let identity_certificates =
            CertificateDer::pem_slice_iter(&credentials.client_identity_pem)
                .collect::<Result<Vec<_>, _>>()
                .map_err(|_| Error::Contract("invalid Core Link client certificate PEM"))?;
        if identity_certificates.is_empty() {
            return Err(Error::Contract("Core Link client certificate required"));
        }
        let identity_key = PrivateKeyDer::from_pem_slice(&credentials.client_identity_pem)
            .map_err(|_| Error::Contract("invalid Core Link client private key PEM"))?;
        let standard = WebPkiServerVerifier::builder(Arc::new(roots))
            .build()
            .map_err(|_| Error::Contract("invalid Core Link trust anchor"))?;
        let pinned = Arc::new(PinnedServerVerifier {
            standard,
            sha256: binding.trust_anchor_sha256.clone(),
        });
        let tls = rustls::ClientConfig::builder()
            .dangerous()
            .with_custom_certificate_verifier(pinned)
            .with_client_auth_cert(identity_certificates, identity_key)
            .map_err(|_| Error::Contract("invalid Core Link client identity"))?;
        // A preconfigured rustls verifier is invoked on each actual TLS
        // connection, never on a disconnected preflight socket.
        let client = Client::builder()
            .use_preconfigured_tls(tls)
            .tls_info(true)
            .https_only(true)
            .no_proxy()
            .redirect(reqwest::redirect::Policy::none())
            .min_tls_version(reqwest::tls::Version::TLS_1_2)
            .timeout(timeout)
            .build()
            .map_err(Error::Connection)?;
        Ok(Self { binding, client })
    }

    /// Executes exactly one read-only request without automatic retry.
    ///
    /// # Errors
    /// Fails closed on binding, deadline, TLS, pin, HTTP, size, or response validation errors.
    pub fn execute(&self, request: &Request, now: DateTime<Utc>) -> Result<Response, Error> {
        if !self.binding.active {
            return Err(Error::RevokedBinding);
        }
        if request.local_platform_id != self.binding.local_platform_id
            || request.remote_platform_id != self.binding.remote_platform_id
            || request.remote_core_identity_id != self.binding.remote_core_identity_id
            || request.remote_core_generation != self.binding.remote_core_generation
        {
            return Err(Error::BindingMismatch);
        }
        if now < request.created_at || now >= request.deadline {
            return Err(Error::Deadline);
        }
        let value = request.to_value()?;
        let body = serde_json::to_vec(&value).map_err(|_| Error::Malformed)?;
        if body.len() > MAX_WIRE_BYTES {
            return Err(Error::Oversized);
        }
        let http = self
            .client
            .post(self.binding.endpoint.clone())
            .header("content-type", "application/json")
            .header("accept", "application/json")
            .body(body)
            .send()
            .map_err(Error::Connection)?;
        let peer = http
            .extensions()
            .get::<reqwest::tls::TlsInfo>()
            .and_then(reqwest::tls::TlsInfo::peer_certificate)
            .ok_or(Error::Contract("host certificate unavailable"))?;
        let (_, certificate) = parse_x509_certificate(peer)
            .map_err(|_| Error::Contract("host certificate invalid"))?;
        let observed = format!("{:x}", Sha256::digest(certificate.public_key().raw));
        if observed != self.binding.trust_anchor_sha256 {
            return Err(Error::BindingMismatch);
        }
        if !http.status().is_success() {
            return Err(Error::Http(http.status()));
        }
        let mut raw = Vec::new();
        http.take((MAX_WIRE_BYTES + 1) as u64)
            .read_to_end(&mut raw)
            .map_err(|_| Error::Malformed)?;
        if raw.len() > MAX_WIRE_BYTES {
            return Err(Error::Oversized);
        }
        let response = parse_response(&raw)?;
        if response.request_id != request.request_id {
            return Err(Error::BindingMismatch);
        }
        Ok(response)
    }
}

/// Identity of a binding selected by the canonical Platform owner.
/// A revisioned, selected binding is required before production read requests.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EnrollmentIdentity {
    pub binding_id: String,
    pub binding_revision: u64,
    pub store_revision: u64,
}

/// Fresh owner-issued state, loaded for each dispatch, not a cached GUI flag.
#[derive(Clone, Debug)]
pub struct CurrentEnrollment {
    pub identity: EnrollmentIdentity,
    pub selected: bool,
    pub binding: EnrolledBinding,
}

/// Implement only through the canonical Platform binding store. Failure to
/// read the store must return an error, never substitute an earlier snapshot.
pub trait BindingAuthority {
    /// Read the selected binding and revisions directly from the owner.
    ///
    /// # Errors
    /// Fail closed if the authoritative store is unavailable or inconsistent.
    fn selected_binding(&self) -> Result<CurrentEnrollment, Error>;
}

/// Production-facing read-only client. The legacy `CoreLinkClient` is retained
/// for disposable compatibility probes but cannot establish fresh enrollment.
pub struct AuthorizedCoreLinkClient {
    transport: CoreLinkClient,
    enrollment: EnrollmentIdentity,
}

impl AuthorizedCoreLinkClient {
    /// Captures the exact enrolled binding identity for later fresh checks.
    ///
    /// # Errors
    /// Rejects invalid binding IDs, zero revisions or invalid mTLS identity.
    pub fn new(
        binding: EnrolledBinding,
        enrollment: EnrollmentIdentity,
        credentials: &TlsCredentials,
        timeout: StdDuration,
    ) -> Result<Self, Error> {
        if !valid_id(&enrollment.binding_id)
            || enrollment.binding_revision == 0
            || enrollment.store_revision == 0
        {
            return Err(Error::Contract(
                "valid enrolled binding and revisions required",
            ));
        }
        let transport = CoreLinkClient::new(binding, credentials, timeout)?;
        Ok(Self {
            transport,
            enrollment,
        })
    }

    fn assert_current(&self, authority: &impl BindingAuthority) -> Result<(), Error> {
        let current = authority.selected_binding()?;
        if !current.selected || !current.binding.active {
            return Err(Error::RevokedBinding);
        }
        if current.identity.binding_id != self.enrollment.binding_id
            || current.identity.binding_revision != self.enrollment.binding_revision
            || current.identity.store_revision < self.enrollment.store_revision
        {
            return Err(Error::BindingMismatch);
        }
        let previous = &self.transport.binding;
        let binding = &current.binding;
        if binding.local_platform_id != previous.local_platform_id
            || binding.remote_platform_id != previous.remote_platform_id
            || binding.remote_core_identity_id != previous.remote_core_identity_id
            || binding.remote_core_generation != previous.remote_core_generation
            || binding.endpoint != previous.endpoint
            || binding.protocol != previous.protocol
            || binding.trust_anchor_sha256 != previous.trust_anchor_sha256
        {
            return Err(Error::BindingMismatch);
        }
        Ok(())
    }

    /// Re-reads canonical enrollment immediately before each read-only HTTP
    /// request. The owner must enforce revocation and selection atomically;
    /// no credential, grant or permission is ever accepted from wire JSON.
    ///
    /// # Errors
    /// Fails closed on removed/changed selection, generation, pin, endpoint
    /// or authority-store errors, in addition to Core Link transport errors.
    pub fn execute(
        &self,
        request: &Request,
        now: DateTime<Utc>,
        authority: &impl BindingAuthority,
    ) -> Result<Response, Error> {
        self.assert_current(authority)?;
        self.transport.execute(request, now)
    }
}

/// Parses one bounded response using the strict Python-compatible field set.
///
/// # Errors
/// Returns an error for malformed, duplicate-key, oversized, or incompatible responses.
pub fn parse_response(raw: &[u8]) -> Result<Response, Error> {
    if raw.is_empty() || raw.len() > MAX_WIRE_BYTES {
        return Err(Error::Oversized);
    }
    let mut deserializer = serde_json::Deserializer::from_slice(raw);
    let value = (&mut deserializer)
        .deserialize_any(StrictValueVisitor)
        .map_err(|_| Error::Malformed)?;
    deserializer.end().map_err(|_| Error::Malformed)?;
    let object = value.as_object().ok_or(Error::Malformed)?;
    let expected = [
        "schema",
        "protocol",
        "request_id",
        "status",
        "payload",
        "server_at",
    ];
    if object.len() != expected.len()
        || expected.iter().any(|key| !object.contains_key(*key))
        || object.get("schema").and_then(Value::as_str) != Some(RESPONSE_SCHEMA)
        || object.get("protocol").and_then(Value::as_str) != Some(PROTOCOL)
    {
        return Err(Error::Malformed);
    }
    let request_id = object["request_id"]
        .as_str()
        .filter(|v| valid_id(v))
        .ok_or(Error::Malformed)?;
    let status = object["status"]
        .as_str()
        .filter(|v| {
            matches!(
                *v,
                "completed"
                    | "pending"
                    | "cancelled"
                    | "denied"
                    | "conflict"
                    | "outcome_unknown"
                    | "unavailable"
                    | "failed"
            )
        })
        .ok_or(Error::Malformed)?;
    let payload = object["payload"].clone();
    if !payload.is_object() || canonical_size(&payload)? > MAX_PAYLOAD_BYTES {
        return Err(Error::Malformed);
    }
    let server_at = object["server_at"]
        .as_str()
        .ok_or(Error::Malformed)?
        .parse()
        .map_err(|_| Error::Malformed)?;
    Ok(Response {
        request_id: request_id.to_owned(),
        status: status.to_owned(),
        payload,
        server_at,
    })
}

struct StrictValueVisitor;

impl<'de> Visitor<'de> for StrictValueVisitor {
    type Value = Value;
    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("unique-key JSON")
    }
    fn visit_bool<E: de::Error>(self, value: bool) -> Result<Value, E> {
        Ok(Value::Bool(value))
    }
    fn visit_i64<E: de::Error>(self, value: i64) -> Result<Value, E> {
        Ok(Value::Number(value.into()))
    }
    fn visit_u64<E: de::Error>(self, value: u64) -> Result<Value, E> {
        Ok(Value::Number(value.into()))
    }
    fn visit_f64<E: de::Error>(self, value: f64) -> Result<Value, E> {
        serde_json::Number::from_f64(value)
            .map(Value::Number)
            .ok_or_else(|| E::custom("non-finite number"))
    }
    fn visit_str<E: de::Error>(self, value: &str) -> Result<Value, E> {
        Ok(Value::String(value.to_owned()))
    }
    fn visit_string<E: de::Error>(self, value: String) -> Result<Value, E> {
        Ok(Value::String(value))
    }
    fn visit_none<E: de::Error>(self) -> Result<Value, E> {
        Ok(Value::Null)
    }
    fn visit_unit<E: de::Error>(self) -> Result<Value, E> {
        Ok(Value::Null)
    }
    fn visit_seq<A: SeqAccess<'de>>(self, mut sequence: A) -> Result<Value, A::Error> {
        let mut values = Vec::new();
        while let Some(value) = sequence.next_element_seed(StrictSeed)? {
            values.push(value);
        }
        Ok(Value::Array(values))
    }
    fn visit_map<A: MapAccess<'de>>(self, mut mapping: A) -> Result<Value, A::Error> {
        let mut keys = BTreeSet::new();
        let mut values = Map::new();
        while let Some(key) = mapping.next_key::<String>()? {
            if !keys.insert(key.clone()) {
                return Err(de::Error::custom("duplicate key"));
            }
            values.insert(key, mapping.next_value_seed(StrictSeed)?);
        }
        Ok(Value::Object(values))
    }
}

struct StrictSeed;
impl<'de> de::DeserializeSeed<'de> for StrictSeed {
    type Value = Value;
    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<Value, D::Error> {
        deserializer.deserialize_any(StrictValueVisitor)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_mutation_and_malformed_response() {
        let now = Utc::now();
        let binding = EnrolledBinding {
            active: true,
            local_platform_id: "p:local".into(),
            remote_platform_id: "p:remote".into(),
            remote_core_identity_id: "c:one".into(),
            remote_core_generation: 1,
            endpoint: Url::parse("https://localhost/v1/core-link").unwrap(),
            protocol: PROTOCOL.into(),
            trust_anchor_sha256: "0".repeat(64),
        };
        let mut request = Request::status(&binding, "req:1", now);
        request.operation = "conversation.send".into();
        assert!(request.to_value().is_err());
        assert!(parse_response(br#"{"schema":"wrong"}"#).is_err());
    }
    #[test]
    fn history_is_exact_and_authority_free() {
        let now = Utc::now();
        let binding = EnrolledBinding {
            active: true,
            local_platform_id: "p:local".into(),
            remote_platform_id: "p:remote".into(),
            remote_core_identity_id: "c:one".into(),
            remote_core_generation: 2,
            endpoint: Url::parse("https://localhost/v1/core-link").unwrap(),
            protocol: PROTOCOL.into(),
            trust_anchor_sha256: "0".repeat(64),
        };
        let value = Request::history(&binding, "req:2", "session:1", None, 100, now)
            .unwrap()
            .to_value()
            .unwrap();
        assert_eq!(value["operation"], "conversation.history");
        for forbidden in ["principal", "audience", "credential", "grant"] {
            assert!(value.get(forbidden).is_none());
        }
    }
    #[test]
    fn nonnull_history_cursor_matches_python_gateway_fixture() {
        let now = DateTime::parse_from_rfc3339("2026-01-01T00:00:00+00:00")
            .unwrap()
            .with_timezone(&Utc);
        let cursor = HistoryCursor {
            created_at: DateTime::parse_from_rfc3339("2025-12-31T23:59:59+00:00")
                .unwrap()
                .with_timezone(&Utc),
            message_id: "message:1".into(),
        };
        let binding = EnrolledBinding {
            active: true,
            local_platform_id: "platform:windows".into(),
            remote_platform_id: "platform:canonical".into(),
            remote_core_identity_id: "core:sofia".into(),
            remote_core_generation: 7,
            endpoint: Url::parse("https://localhost/v1/core-link").unwrap(),
            protocol: PROTOCOL.into(),
            trust_anchor_sha256: "0".repeat(64),
        };
        let request = Request::history(
            &binding,
            "request:history:1",
            "session:existing",
            Some(&cursor),
            100,
            now,
        )
        .unwrap();
        let actual = request.to_value().unwrap();
        let expected: Value = serde_json::from_str(include_str!(
            "../../../../contracts/core-link/valid-history-page-2-request.json"
        ))
        .unwrap();
        assert_eq!(actual, expected);
        assert_eq!(actual["payload"]["after"]["message_id"], "message:1");
        assert!(Request::history(
            &binding,
            "request:history:1",
            "session:existing",
            Some(&HistoryCursor {
                created_at: cursor.created_at,
                message_id: "invalid cursor with whitespace".into(),
            }),
            100,
            now,
        )
        .is_err());
    }

    #[test]
    fn tls_credentials_debug_redacts_private_bytes() {
        let credentials = TlsCredentials {
            ca_pem: b"TEST_CA_MATERIAL".to_vec(),
            client_identity_pem: b"TEST_PRIVATE_KEY_MATERIAL".to_vec(),
        };
        let output = format!("{credentials:?}");
        assert!(output.contains("[REDACTED]"));
        assert!(!output.contains("TEST_CA_MATERIAL"));
        assert!(!output.contains("TEST_PRIVATE_KEY_MATERIAL"));
    }
    #[test]
    fn rejects_endpoint_userinfo_query_and_fragment_before_network() {
        for address in [
            "https://user:password@localhost/v1/core-link",
            "https://localhost/v1/core-link?debug=1",
            "https://localhost/v1/core-link#fragment",
            "http://localhost/v1/core-link",
            "https://localhost/wrong-path",
        ] {
            let binding = EnrolledBinding {
                active: true,
                local_platform_id: "platform:local".into(),
                remote_platform_id: "platform:host".into(),
                remote_core_identity_id: "core:one".into(),
                remote_core_generation: 1,
                endpoint: Url::parse(address).unwrap(),
                protocol: PROTOCOL.into(),
                trust_anchor_sha256: "a".repeat(64),
            };
            let credentials = TlsCredentials {
                ca_pem: b"not-a-ca".to_vec(),
                client_identity_pem: b"not-a-key".to_vec(),
            };
            assert!(matches!(
                CoreLinkClient::new(binding, &credentials, StdDuration::from_secs(1)),
                Err(Error::Contract(_))
            ));
        }
    }
    #[test]
    fn authorized_client_rejects_revoked_changed_and_missing_enrollments_before_io() {
        #[derive(Clone)]
        struct FakeAuthority(Option<CurrentEnrollment>);
        impl BindingAuthority for FakeAuthority {
            fn selected_binding(&self) -> Result<CurrentEnrollment, Error> {
                self.0.clone().ok_or(Error::RevokedBinding)
            }
        }
        let binding = EnrolledBinding {
            active: true,
            local_platform_id: "platform:venus".into(),
            remote_platform_id: "platform:artemis".into(),
            remote_core_identity_id: "core:sofia".into(),
            remote_core_generation: 7,
            endpoint: Url::parse("https://localhost/v1/core-link").unwrap(),
            protocol: PROTOCOL.into(),
            trust_anchor_sha256: "a".repeat(64),
        };
        let identity = EnrollmentIdentity {
            binding_id: "binding:sofia".into(),
            binding_revision: 3,
            store_revision: 8,
        };
        // Direct unit construction isolates pre-send checks from TLS/network.
        let client = AuthorizedCoreLinkClient {
            transport: CoreLinkClient {
                binding: binding.clone(),
                client: Client::new(),
            },
            enrollment: identity.clone(),
        };
        let valid = CurrentEnrollment {
            identity: identity.clone(),
            selected: true,
            binding: binding.clone(),
        };
        assert!(client
            .assert_current(&FakeAuthority(Some(valid.clone())))
            .is_ok());
        assert!(matches!(
            client.assert_current(&FakeAuthority(None)),
            Err(Error::RevokedBinding)
        ));
        let mut revoked = valid.clone();
        revoked.binding.active = false;
        assert!(matches!(
            client.assert_current(&FakeAuthority(Some(revoked))),
            Err(Error::RevokedBinding)
        ));
        let mut unselected = valid.clone();
        unselected.selected = false;
        assert!(matches!(
            client.assert_current(&FakeAuthority(Some(unselected))),
            Err(Error::RevokedBinding)
        ));
        let mut changed = valid.clone();
        changed.identity.binding_revision += 1;
        assert!(matches!(
            client.assert_current(&FakeAuthority(Some(changed))),
            Err(Error::BindingMismatch)
        ));
        let mut replaced = valid.clone();
        replaced.binding.remote_core_generation += 1;
        assert!(matches!(
            client.assert_current(&FakeAuthority(Some(replaced))),
            Err(Error::BindingMismatch)
        ));
        let mut pin_changed = valid.clone();
        pin_changed.binding.trust_anchor_sha256 = "b".repeat(64);
        assert!(matches!(
            client.assert_current(&FakeAuthority(Some(pin_changed))),
            Err(Error::BindingMismatch)
        ));
        let mut rollback = valid;
        rollback.identity.store_revision -= 1;
        assert!(matches!(
            client.assert_current(&FakeAuthority(Some(rollback))),
            Err(Error::BindingMismatch)
        ));
    }
}
