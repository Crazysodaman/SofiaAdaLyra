//! Current status admission from the installed canonical Python Platform owner.
//! The executable/store/route configuration is trusted operator configuration,
//! never renderer or model input. No binding or credential store is created.
use super::{
    AuthorizedCoreLinkClient, BindingAuthority, CurrentEnrollment, EnrolledBinding,
    EnrollmentIdentity, Error, Request, Response, StrictValueVisitor, TlsCredentials, PROTOCOL,
};
use chrono::{DateTime, Utc};
use reqwest::Url;
use serde::de::Deserializer;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::io::Read;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{
    atomic::{AtomicU64, Ordering},
    mpsc,
};
use std::time::{Duration, Instant};

const SCHEMA: &str = "aegis.platform.core-link-status-authority.v1";
const MAX_REPLY: u64 = 16 * 1024;
static NEXT_REQUEST: AtomicU64 = AtomicU64::new(0);

/// Operator-owned references, not enrollment evidence or an owner secret.
#[derive(Clone, Debug)]
pub struct PlatformStatusConfiguration {
    pub python: PathBuf,
    pub binding_store: PathBuf,
    pub minimum_store_revision: u64,
    pub endpoint_id: String,
    pub credential_ref: String,
    pub endpoint: Url,
    pub timeout: Duration,
}

struct ChildGuard(Child);
impl Drop for ChildGuard {
    fn drop(&mut self) {
        if !matches!(self.0.try_wait(), Ok(Some(_))) {
            let _ = self.0.kill();
        }
        let _ = self.0.wait();
    }
}

fn nonce() -> Result<String, Error> {
    let number = NEXT_REQUEST
        .fetch_update(Ordering::SeqCst, Ordering::SeqCst, |value| {
            value.checked_add(1)
        })
        .map_err(|_| Error::Contract("authority correlation exhausted"))?;
    Ok(format!(
        "{:x}",
        Sha256::digest(format!("{}:{number}:{}", std::process::id(), Utc::now()).as_bytes())
    ))
}

fn query(
    config: &PlatformStatusConfiguration,
    expected: Option<&EnrollmentIdentity>,
    minimum: u64,
    request_id: &str,
) -> Result<Vec<u8>, Error> {
    let mut command = Command::new(&config.python);
    command
        .args([
            "-I",
            "-m",
            "sofia.platform.core_link.rust_authority",
            "--store",
        ])
        .arg(&config.binding_store)
        .arg("--request-id")
        .arg(request_id)
        .arg("--minimum-store-revision")
        .arg(minimum.to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    if let Some(identity) = expected {
        command
            .arg("--binding-id")
            .arg(&identity.binding_id)
            .arg("--binding-revision")
            .arg(identity.binding_revision.to_string());
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    let mut child = ChildGuard(
        command
            .spawn()
            .map_err(|_| Error::Contract("Platform authority unavailable"))?,
    );
    let stdout = child
        .0
        .stdout
        .take()
        .ok_or(Error::Contract("authority pipe unavailable"))?;
    let (sender, receiver) = mpsc::sync_channel(1);
    std::thread::spawn(move || {
        let mut bytes = Vec::new();
        let result = stdout
            .take(MAX_REPLY + 1)
            .read_to_end(&mut bytes)
            .map(|_| bytes);
        let _ = sender.send(result);
    });
    let start = Instant::now();
    let mut output = None;
    loop {
        if start.elapsed() >= config.timeout {
            return Err(Error::Contract("Platform authority deadline exceeded"));
        }
        if output.is_none() {
            match receiver.try_recv() {
                Ok(Ok(bytes)) if bytes.len() as u64 <= MAX_REPLY => output = Some(bytes),
                Ok(Ok(_)) => return Err(Error::Oversized),
                Ok(Err(_)) | Err(mpsc::TryRecvError::Disconnected) => return Err(Error::Malformed),
                Err(mpsc::TryRecvError::Empty) => {}
            }
        }
        if let Some(status) = child
            .0
            .try_wait()
            .map_err(|_| Error::Contract("authority exit unknown"))?
        {
            if !status.success() {
                return Err(Error::Contract("Platform authority denied or unavailable"));
            }
            if let Some(bytes) = output {
                return Ok(bytes);
            }
        }
        std::thread::sleep(Duration::from_millis(2));
    }
}

fn text<'a>(value: &'a Value, key: &str) -> Result<&'a str, Error> {
    value
        .get(key)
        .and_then(Value::as_str)
        .ok_or(Error::Malformed)
}
fn number(value: &Value, key: &str) -> Result<u64, Error> {
    value
        .get(key)
        .and_then(Value::as_u64)
        .ok_or(Error::Malformed)
}
fn fields(value: &Value, expected: &[&str]) -> Result<(), Error> {
    let map = value.as_object().ok_or(Error::Malformed)?;
    if map.len() != expected.len() || expected.iter().any(|key| !map.contains_key(*key)) {
        return Err(Error::Malformed);
    }
    Ok(())
}

fn reply_value(bytes: &[u8], request_id: &str) -> Result<Value, Error> {
    let mut decoder = serde_json::Deserializer::from_slice(bytes);
    let value = (&mut decoder)
        .deserialize_any(StrictValueVisitor)
        .map_err(|_| Error::Malformed)?;
    decoder.end().map_err(|_| Error::Malformed)?;
    fields(
        &value,
        &[
            "schema",
            "request_id",
            "store_revision",
            "admission",
            "binding",
        ],
    )?;
    if text(&value, "schema")? != SCHEMA || text(&value, "request_id")? != request_id {
        return Err(Error::Malformed);
    }
    Ok(value)
}

struct StatusAuthority {
    config: PlatformStatusConfiguration,
    expected: Option<EnrollmentIdentity>,
    highest: AtomicU64,
}
impl StatusAuthority {
    fn read(&self) -> Result<(CurrentEnrollment, String), Error> {
        let request_id = nonce()?;
        let bytes = query(
            &self.config,
            self.expected.as_ref(),
            self.highest.load(Ordering::SeqCst),
            &request_id,
        )?;
        let value = reply_value(&bytes, &request_id)?;
        let revision = number(&value, "store_revision")?;
        let previous = self.highest.fetch_max(revision, Ordering::SeqCst);
        if revision < previous || revision < self.config.minimum_store_revision {
            return Err(Error::BindingMismatch);
        }
        match text(&value, "admission")? {
            "denied" if value["binding"].is_null() => return Err(Error::RevokedBinding),
            "allowed" => {}
            _ => return Err(Error::Malformed),
        }
        let row = &value["binding"];
        fields(
            row,
            &[
                "schema",
                "binding_id",
                "local_platform_id",
                "remote_platform_id",
                "remote_core_identity_id",
                "remote_core_generation",
                "endpoint_id",
                "credential_ref",
                "trust_anchor_ref",
                "audience_id",
                "granted_scopes",
                "protocol_version",
                "state",
                "revision",
                "created_at",
                "updated_at",
                "last_verified_contact_at",
            ],
        )?;
        if text(row, "schema")? != "companion.platform.core_link.v1"
            || text(row, "state")? != "active"
            || text(row, "protocol_version")? != "1.0"
            || text(row, "endpoint_id")? != self.config.endpoint_id
            || text(row, "credential_ref")? != self.config.credential_ref
            || !row["granted_scopes"]
                .as_array()
                .ok_or(Error::Malformed)?
                .iter()
                .any(|v| v.as_str() == Some("status.read"))
        {
            return Err(Error::BindingMismatch);
        }
        for key in [
            "binding_id",
            "local_platform_id",
            "remote_platform_id",
            "remote_core_identity_id",
            "audience_id",
        ] {
            if !super::valid_id(text(row, key)?) {
                return Err(Error::Malformed);
            }
        }
        let binding_revision = number(row, "revision")?;
        let generation = number(row, "remote_core_generation")?;
        if binding_revision == 0 || generation == 0 {
            return Err(Error::Malformed);
        }
        let pin = text(row, "trust_anchor_ref")?
            .strip_prefix("sha256:")
            .ok_or(Error::Malformed)?;
        let enrollment = CurrentEnrollment {
            identity: EnrollmentIdentity {
                binding_id: text(row, "binding_id")?.into(),
                binding_revision,
                store_revision: revision,
            },
            selected: true,
            binding: EnrolledBinding {
                active: true,
                local_platform_id: text(row, "local_platform_id")?.into(),
                remote_platform_id: text(row, "remote_platform_id")?.into(),
                remote_core_identity_id: text(row, "remote_core_identity_id")?.into(),
                remote_core_generation: generation,
                endpoint: self.config.endpoint.clone(),
                protocol: PROTOCOL.into(),
                trust_anchor_sha256: pin.into(),
            },
        };
        Ok((enrollment, text(row, "credential_ref")?.into()))
    }
}
impl BindingAuthority for StatusAuthority {
    fn selected_binding(&self) -> Result<CurrentEnrollment, Error> {
        self.read().map(|(binding, _)| binding)
    }
}

/// Status-only production adapter. Fresh canonical owner checks fence both
/// dispatch and response release. It never enrolls, selects or starts a Core.
pub struct PlatformStatusClient {
    authority: StatusAuthority,
    client: AuthorizedCoreLinkClient,
    binding: EnrolledBinding,
}
impl PlatformStatusClient {
    /// Resolve TLS material only after canonical status admission succeeds.
    /// The resolver must be the existing Platform secret owner, not UI input.
    ///
    /// # Errors
    /// Reject invalid configuration, stale/revoked selection or credential/route mismatch.
    pub fn new(
        config: PlatformStatusConfiguration,
        resolve_credentials: impl FnOnce(&str) -> Result<TlsCredentials, Error>,
    ) -> Result<Self, Error> {
        if !config.python.is_absolute()
            || !config.python.is_file()
            || !config.binding_store.is_absolute()
            || config.minimum_store_revision == 0
            || config.timeout < Duration::from_millis(50)
            || config.timeout > Duration::from_secs(10)
            || !super::valid_id(&config.endpoint_id)
        {
            return Err(Error::Contract(
                "trusted absolute Platform authority configuration required",
            ));
        }
        let mut authority = StatusAuthority {
            highest: AtomicU64::new(config.minimum_store_revision),
            config,
            expected: None,
        };
        let (current, credential_ref) = authority.read()?;
        let credentials = resolve_credentials(&credential_ref)?;
        let client = AuthorizedCoreLinkClient::new(
            current.binding.clone(),
            current.identity.clone(),
            &credentials,
            authority.config.timeout,
        )?;
        authority.expected = Some(current.identity);
        Ok(Self {
            binding: current.binding,
            authority,
            client,
        })
    }

    /// Read current status; no history, conversation mutation or cached fallback.
    ///
    /// # Errors
    /// Fail closed on changed binding, timeout, revocation or transport errors.
    pub fn status(&self, now: DateTime<Utc>) -> Result<Response, Error> {
        let id = format!("platform-status:{}", &nonce()?[..24]);
        let request = Request::status(&self.binding, &id, now);
        let response = self.client.execute(&request, now, &self.authority)?;
        if response.status != "completed" {
            return Err(Error::RevokedBinding);
        }
        Ok(response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn authority_reply_requires_exact_correlation_schema_and_unique_fields() {
        let id = "a".repeat(64);
        let valid = serde_json::json!({"schema":SCHEMA,"request_id":id,"store_revision":4,
            "admission":"denied","binding":null});
        let raw = serde_json::to_vec(&valid).unwrap();
        assert!(reply_value(&raw, &id).is_ok());
        assert!(reply_value(&raw, &"b".repeat(64)).is_err());
        let mut extra = valid.clone();
        extra["owner_verified"] = Value::Bool(true);
        assert!(reply_value(&serde_json::to_vec(&extra).unwrap(), &id).is_err());
        let duplicated = format!(
            "{{\"store_revision\":1,{}",
            &String::from_utf8(raw).unwrap()[1..]
        );
        assert!(reply_value(duplicated.as_bytes(), &id).is_err());
    }

    #[test]
    fn unavailable_authority_cannot_resolve_credentials() {
        let config = PlatformStatusConfiguration {
            python: std::env::current_exe().unwrap(),
            binding_store: std::env::temp_dir().join("no-binding.json"),
            minimum_store_revision: 1,
            endpoint_id: "endpoint:test".into(),
            credential_ref: "os-keystore:test".into(),
            endpoint: Url::parse("https://localhost:8443/v1/core-link").unwrap(),
            timeout: Duration::from_secs(1),
        };
        // The Rust test executable rejects the isolated Python module options.
        // No credential material may be requested after that authority failure.
        let called = std::cell::Cell::new(false);
        assert!(PlatformStatusClient::new(config, |_| {
            called.set(true);
            Err(Error::Contract("credentials must not be resolved"))
        })
        .is_err());
        assert!(!called.get());
    }
}
