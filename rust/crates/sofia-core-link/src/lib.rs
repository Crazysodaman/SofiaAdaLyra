//! Read-only Core Link client. Authority comes exclusively from the enrolled
//! client certificate; wire JSON contains routing data, never grants.

use chrono::{DateTime, Duration, Utc};
use regex::Regex;
use rustls::pki_types::{CertificateDer, ServerName};
use rustls::version::{TLS12, TLS13};
use rustls::RootCertStore;
use serde::de::{self, Deserializer, MapAccess, SeqAccess, Visitor};
use serde_json::{Map, Value};
use std::collections::BTreeSet;
use std::fmt;
use std::io::{Cursor, Read, Write};
use std::net::{SocketAddr, TcpStream, ToSocketAddrs};
use std::time::{Duration as StdDuration, Instant};
use thiserror::Error;
use url::{Host, Url};

pub const PROTOCOL: &str = "1.0";
pub const MAX_PAYLOAD_BYTES: usize = 64 * 1024;
pub const MAX_WIRE_BYTES: usize = 72 * 1024;
const REQUEST_SCHEMA: &str = "companion.platform.core_link_request.v1";
const RESPONSE_SCHEMA: &str = "companion.platform.core_link_response.v1";
const TLS_VERSIONS: [&'static rustls::SupportedProtocolVersion; 2] = [&TLS12, &TLS13];

mod der;

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
    Connection(#[source] Box<dyn std::error::Error + Send + Sync>),
    #[error("Core Link host returned HTTP {0}")]
    Http(u16),
    #[error("Core Link response exceeds 72 KiB")]
    Oversized,
    #[error("Core Link response is malformed")]
    Malformed,
}

fn map_io(error: std::io::Error) -> Error {
    Error::Connection(Box::new(error))
}

fn map_rustls(error: rustls::Error) -> Error {
    Error::Connection(Box::new(error))
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
    /// Lowercase SHA-256 of the enrolled host certificate subjectPublicKeyInfo.
    pub trust_anchor_sha256: String,
}

#[derive(Clone)]
pub struct TlsCredentials {
    /// PEM trust anchor and combined PEM client certificate/private key.
    /// Callers must resolve these from the Platform secret owner at use time.
    pub ca_pem: Vec<u8>,
    pub client_identity_pem: Vec<u8>,
}

impl fmt::Debug for TlsCredentials {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("TlsCredentials { ca_pem: <redacted>, client_identity_pem: <redacted> }")
    }
}

/// Exact structured history cursor used by the Python gateway:
/// `{created_at, message_id}` with RFC 3339 timestamps.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HistoryCursor {
    pub created_at: DateTime<Utc>,
    pub message_id: String,
}

impl HistoryCursor {
    /// Builds one bounded cursor element.
    ///
    /// # Errors
    /// Returns an error when the message identifier is invalid.
    pub fn new(created_at: DateTime<Utc>, message_id: impl Into<String>) -> Result<Self, Error> {
        let message_id = message_id.into();
        if !valid_id(&message_id) {
            return Err(Error::Contract("invalid history cursor"));
        }
        Ok(Self {
            created_at,
            message_id,
        })
    }

    /// The exact wire form: `{"created_at": "...", "message_id": "..."}`.
    #[must_use]
    pub fn to_value(&self) -> Value {
        serde_json::json!({
            "created_at": self.created_at.to_rfc3339(),
            "message_id": self.message_id,
        })
    }

    /// Parses a structured cursor issued by the host.
    ///
    /// # Errors
    /// Returns an error for unexpected keys, invalid identifiers, or timestamps.
    pub fn from_value(value: &Value) -> Result<Self, Error> {
        let object = value.as_object().ok_or(Error::Contract("invalid history cursor"))?;
        if object.len() != 2 {
            return Err(Error::Contract("invalid history cursor"));
        }
        let created_at = object
            .get("created_at")
            .and_then(Value::as_str)
            .ok_or(Error::Contract("invalid history cursor"))?
            .parse::<DateTime<Utc>>()
            .map_err(|_| Error::Contract("invalid history cursor"))?;
        let message_id = object
            .get("message_id")
            .and_then(Value::as_str)
            .filter(|value| valid_id(value))
            .ok_or(Error::Contract("invalid history cursor"))?;
        Ok(Self {
            created_at,
            message_id: message_id.to_owned(),
        })
    }
}

#[derive(Clone)]
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

impl fmt::Debug for Request {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("Request")
            .field("request_id", &self.request_id)
            .field("idempotency_key", &self.idempotency_key)
            .field("local_platform_id", &self.local_platform_id)
            .field("remote_platform_id", &self.remote_platform_id)
            .field(
                "remote_core_identity_id",
                &self.remote_core_identity_id,
            )
            .field("remote_core_generation", &self.remote_core_generation)
            .field("operation", &self.operation)
            .field("payload", &"<redacted>")
            .field("created_at", &self.created_at.to_rfc3339())
            .field("deadline", &self.deadline.to_rfc3339())
            .finish()
    }
}

#[derive(Clone, PartialEq)]
pub struct Response {
    pub request_id: String,
    pub status: String,
    pub payload: Value,
    pub server_at: DateTime<Utc>,
}

impl fmt::Debug for Response {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("Response")
            .field("request_id", &self.request_id)
            .field("status", &self.status)
            .field("payload", &"<redacted>")
            .field("server_at", &self.server_at.to_rfc3339())
            .finish()
    }
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
    /// Returns an error for an invalid session, cursor, or limit.
    pub fn history(
        binding: &EnrolledBinding,
        request_id: &str,
        session_id: &str,
        after: Option<&HistoryCursor>,
        limit: u16,
        now: DateTime<Utc>,
    ) -> Result<Self, Error> {
        if !valid_id(session_id) || !(1..=200).contains(&limit) {
            return Err(Error::Contract("invalid history query"));
        }
        let payload = if let Some(cursor) = after {
            if cursor.message_id.is_empty() || !valid_id(&cursor.message_id) {
                return Err(Error::Contract("invalid history query"));
            }
            serde_json::json!({"session_id": session_id, "after": cursor.to_value(), "limit": limit})
        } else {
            serde_json::json!({"session_id": session_id, "after": None::<Value>, "limit": limit})
        };
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

pub struct CoreLinkClient {
    binding: EnrolledBinding,
    tls: std::sync::Arc<rustls::ClientConfig>,
    server_name: ServerName<'static>,
    timeout: StdDuration,
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
        let host = binding
            .endpoint
            .host_str()
            .ok_or(Error::Contract("endpoint must be the exact Core Link HTTPS path"))?;
        if binding.endpoint.scheme() != "https"
            || binding.endpoint.path() != "/v1/core-link"
            || binding.endpoint.username() != ""
            || binding.endpoint.password().is_some()
            || binding.endpoint.query().is_some()
            || binding.endpoint.fragment().is_some()
            || binding
                .endpoint
                .port()
                .is_some_and(|port| port == 0)
        {
            return Err(Error::Contract(
                "endpoint must be the exact Core Link HTTPS path",
            ));
        }
        let server_name =
            ServerName::try_from(host.to_owned()).map_err(|_| Error::Contract(
                "endpoint must be the exact Core Link HTTPS path",
            ))?;
        let mut roots = RootCertStore::empty();
        for result in rustls_pemfile::certs(&mut Cursor::new(&credentials.ca_pem)) {
            let certificate = result.map_err(map_io)?;
            roots
                .add(certificate)
                .map_err(|_| Error::Contract("trust anchor is not a valid certificate"))?;
        }
        if roots.is_empty() {
            return Err(Error::Connection(Box::new(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "Core Link trust anchor is required",
            ))));
        }
        let chain: Vec<CertificateDer<'static>> =
            rustls_pemfile::certs(&mut Cursor::new(&credentials.client_identity_pem))
                .collect::<Result<Vec<_>, _>>()
                .map_err(map_io)?;
        let private_key = rustls_pemfile::private_key(&mut Cursor::new(
            &credentials.client_identity_pem,
        ))
        .map_err(map_io)?
        .ok_or(Error::Contract("client identity is not a certificate and key"))?;
        if chain.is_empty() {
            return Err(Error::Contract("client identity is not a certificate and key"));
        }
        let provider = std::sync::Arc::new(rustls::crypto::ring::default_provider());
        let builder = rustls::ClientConfig::builder_with_provider(provider)
            .with_protocol_versions(&TLS_VERSIONS)
            .map_err(map_rustls)?
            .with_root_certificates(roots)
            .with_client_auth_cert(chain, private_key)
            .map_err(map_rustls)?;
        Ok(Self {
            binding,
            tls: std::sync::Arc::new(builder),
            server_name,
            timeout,
        })
    }

    fn host_header(&self, endpoint: &Url) -> Result<String, Error> {
        let server_host = match endpoint.host() {
            Some(Host::Domain(domain)) => domain.to_owned(),
            Some(Host::Ipv4(ipv4)) => ipv4.to_string(),
            Some(Host::Ipv6(ipv6)) => format!("[{ipv6}]"),
            None => return Err(Error::Contract("endpoint host is missing")),
        };
        Ok(match endpoint.port() {
            Some(port) => format!("{server_host}:{port}"),
            None => server_host,
        })
    }

    fn resolve_host(&self, host: &str, port: u16) -> Result<Vec<SocketAddr>, Error> {
        let addresses: Vec<SocketAddr> =
            (host, port).to_socket_addrs().map_err(map_io)?.collect();
        Ok(addresses)
    }

    fn establish(&self, started: Instant) -> Result<rustls::StreamOwned<rustls::ClientConnection, TcpStream>, Error> {
        let endpoint = self.binding.endpoint.clone();
        let host = endpoint.host_str().ok_or(Error::Contract("endpoint host is missing"))?;
        let port = endpoint.port_or_known_default().unwrap_or(443);
        let address = self
            .resolve_host(host, port)?
            .into_iter()
            .next()
            .ok_or(Error::Contract("endpoint host cannot be resolved"))?;
        let mut socket = TcpStream::connect_timeout(&address, self.timeout).map_err(map_io)?;
        socket
            .set_nodelay(true)
            .map_err(map_io)?;
        self.apply_remaining_timeouts(&mut socket, started)?;
        let mut connection = rustls::ClientConnection::new(self.tls.clone(), self.server_name.clone())
            .map_err(map_rustls)?;
        while connection.is_handshaking() {
            connection
                .complete_io(&mut socket)
                .map_err(map_io)?;
            if started.elapsed() >= self.timeout {
                return Err(Error::Deadline);
            }
        }
        let peers = connection.peer_certificates().map_or_else(
            || Err(Error::Contract("host certificate unavailable")),
            |certificates| {
                certificates
                    .first()
                    .cloned()
                    .ok_or(Error::Contract("host certificate unavailable"))
            },
        )?;
        let observed = digest_hex(spki_digest(peers.as_ref())?);
        if observed != self.binding.trust_anchor_sha256 {
            return Err(Error::BindingMismatch);
        }
        self.apply_remaining_timeouts(&mut socket, started)?;
        Ok(rustls::StreamOwned::new(connection, socket))
    }

    fn apply_remaining_timeouts(&self, socket: &TcpStream, started: Instant) -> Result<(), Error> {
        let remaining = self.timeout.checked_sub(started.elapsed()).ok_or(Error::Deadline)?;
        socket.set_read_timeout(Some(remaining)).map_err(map_io)?;
        socket.set_write_timeout(Some(remaining)).map_err(map_io)?;
        Ok(())
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
        let started = Instant::now();
        let mut stream = self.establish(started)?;
        let endpoint = self.binding.endpoint.clone();
        let head = format!(
            "POST {} HTTP/1.1\r\nhost: {}\r\ncontent-type: application/json\r\naccept: application/json\r\ncontent-length: {}\r\nconnection: close\r\n\r\n",
            endpoint.path(),
            self.host_header(&endpoint)?,
            body.len(),
        );
        stream.write_all(head.as_bytes()).map_err(map_io)?;
        stream.write_all(&body).map_err(map_io)?;
        stream.flush().map_err(map_io)?;
        let raw = self.read_response(&mut stream, started)?;
        let response = parse_response(&raw)?;
        if response.request_id != request.request_id {
            return Err(Error::BindingMismatch);
        }
        Ok(response)
    }

    fn read_response(
        &self,
        stream: &mut impl Read,
        started: Instant,
    ) -> Result<Vec<u8>, Error> {
        let mut header = Vec::new();
        let mut byte = [0_u8; 1];
        loop {
            stream.read_exact(&mut byte).map_err(map_io)?;
            header.push(byte[0]);
            if header.ends_with(b"\r\n\r\n") {
                break;
            }
            if header.len() > 16 * 1024 {
                return Err(Error::Malformed);
            }
            if started.elapsed() >= self.timeout {
                return Err(Error::Deadline);
            }
        }
        let head = String::from_utf8_lossy(&header);
        let status_line = head.lines().next().ok_or(Error::Malformed)?;
        let parts = status_line.split(' ').collect::<Vec<_>>();
        if parts.len() < 3 || !parts[0].starts_with("HTTP/") {
            return Err(Error::Malformed);
        }
        let status = parts[1]
            .parse::<u16>()
            .map_err(|_| Error::Malformed)?;
        if !matches!(status, 200..=599) {
            return Err(Error::Malformed);
        }
        let content_length = head.lines().skip(1).find_map(|line| {
            let (name, value) = line.split_once(':')?;
            let name = name.trim().to_ascii_lowercase();
            if name == "content-length" {
                value.trim().parse::<usize>().ok()
            } else {
                None
            }
        });
        let length = content_length.ok_or(Error::Malformed)?;
        if length == 0 || length > MAX_WIRE_BYTES {
            return Err(Error::Oversized);
        }
        let mut body = vec![0_u8; length];
        stream.read_exact(&mut body).map_err(map_io)?;
        Ok(body)
    }
}

fn digest_hex(digest: [u8; 32]) -> String {
    digest
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect::<String>()
}

fn spki_digest(certificate: &[u8]) -> Result<[u8; 32], Error> {
    crate::der::spki_sha256(certificate).ok_or(Error::Contract("host certificate invalid"))
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

    fn binding() -> EnrolledBinding {
        EnrolledBinding {
            active: true,
            local_platform_id: "p:local".into(),
            remote_platform_id: "p:remote".into(),
            remote_core_identity_id: "c:one".into(),
            remote_core_generation: 1,
            endpoint: Url::parse("https://localhost/v1/core-link").unwrap(),
            protocol: PROTOCOL.into(),
            trust_anchor_sha256: "0".repeat(64),
        }
    }

    #[test]
    fn rejects_mutation_and_malformed_response() {
        let now = Utc::now();
        let mut request =
            Request::status(&binding(), "req:1", now);
        request.operation = "conversation.send".into();
        assert!(request.to_value().is_err());
        assert!(parse_response(br#"{"schema":"wrong"}"#).is_err());
    }

    #[test]
    fn history_accepts_structured_cursor_and_writes_none() {
        let now = Utc::now();
        let cursor = HistoryCursor {
            created_at: now,
            message_id: "m:1".into(),
        };
        let value = Request::history(
            &binding(),
            "req:2",
            "session:1",
            Some(&cursor),
            100,
            now,
        )
        .unwrap()
        .to_value()
        .unwrap();
        assert_eq!(value["operation"], "conversation.history");
        assert_eq!(value["payload"]["after"]["message_id"], "m:1");
        assert!(value["payload"]["after"].get("created_at").is_some());
        for forbidden in ["principal", "audience", "credential", "grant"] {
            assert!(value.get(forbidden).is_none());
        }
        let none = Request::history(&binding(), "req:3", "session:1", None, 100, now)
            .unwrap()
            .to_value()
            .unwrap();
        assert!(none["payload"]["after"].is_null());
    }

    #[test]
    fn history_rejects_invalid_cursor_and_debug_redacts() {
        let now = Utc::now();
        let cursor = HistoryCursor {
            created_at: now,
            message_id: String::new(),
        };
        assert!(Request::history(&binding(), "req:4", "s:1", Some(&cursor), 10, now).is_err());
        let valid = HistoryCursor::new(now, "m:1").unwrap();
        assert_eq!(
            valid,
            HistoryCursor {
                created_at: now,
                message_id: "m:1".to_owned(),
            }
        );
    }
}
