//! Read-only Core Link probe used by the R2 compatibility CI. It prints the
//! status payload and a redacted history summary; conversation message
//! contents are never written to stdout or stderr.

use chrono::{DateTime, Utc};
use sofia_core_link::{
    CoreLinkClient, EnrolledBinding, HistoryCursor, PROTOCOL, Request, TlsCredentials,
};
use serde_json::Value;
use std::time::Duration;
use url::Url;

const PROBE_TIMEOUT_SECONDS: u64 = 10;
const USAGE: &str = "usage: r2_core_link_probe <endpoint> <host_public_key_sha256> <ca_pem> <client_cert_pem> <client_key_pem> <local_platform_id> <remote_platform_id> <core_identity_id> <core_generation> [session_id [created_at message_id]]";

fn main() {
    match run() {
        Ok(()) => {}
        Err(message) => {
            eprintln!("{message}");
            std::process::exit(1);
        }
    }
}

fn load_pem(path: &str) -> Result<Vec<u8>, String> {
    std::fs::read(path).map_err(|error| format!("could not read {path}: {error}"))
}

/// Builds the pinned read-only client from probe arguments.
///
/// # Errors
/// Returns an error for usage, TLS material, or binding errors.
fn build_client(arguments: &[String]) -> Result<(CoreLinkClient, EnrolledBinding), String> {
    let binding = EnrolledBinding {
        active: true,
        local_platform_id: arguments[5].clone(),
        remote_platform_id: arguments[6].clone(),
        remote_core_identity_id: arguments[7].clone(),
        remote_core_generation: arguments[8]
            .parse::<u64>()
            .map_err(|_| "core generation must be a positive integer".to_owned())?,
        endpoint: Url::parse(&arguments[0])
            .map_err(|_| "endpoint must be the exact Core Link HTTPS path".to_owned())?,
        protocol: PROTOCOL.to_owned(),
        trust_anchor_sha256: arguments[1].clone(),
    };
    let mut client_identity_pem = load_pem(&arguments[3])?;
    client_identity_pem.extend(load_pem(&arguments[4])?);
    let credentials = TlsCredentials {
        ca_pem: load_pem(&arguments[2])?,
        client_identity_pem,
    };
    Ok((
        CoreLinkClient::new(
            binding.clone(),
            &credentials,
            Duration::from_secs(PROBE_TIMEOUT_SECONDS),
        )
        .map_err(|error| error.to_string())?,
        binding,
    ))
}

/// Prints the status payload of the selected Core Link binding.
///
/// # Errors
/// Returns an error when the request or response validation fails.
fn execute_status(client: &CoreLinkClient, binding: &EnrolledBinding) -> Result<(), String> {
    let now = Utc::now();
    let response = client
        .execute(&Request::status(binding, "probe:status:1", now), now)
        .map_err(|error| error.to_string())?;
    println!("{}", response.payload);
    Ok(())
}

/// Prints a redacted history summary; message contents are dropped.
///
/// # Errors
/// Returns an error when the payload is not an object or execution fails.
fn execute_history(
    client: &CoreLinkClient,
    binding: &EnrolledBinding,
    session_id: &str,
    cursor: Option<HistoryCursor>,
) -> Result<(), String> {
    let now = Utc::now();
    let response = client
        .execute(
            &Request::history(
                binding,
                "probe:history:1",
                session_id,
                cursor.as_ref(),
                50,
                now,
            )
            .map_err(|error| error.to_string())?,
            now,
        )
        .map_err(|error| error.to_string())?;
    let output = redact_history_payload(&response.payload)?;
    println!("{output}");
    Ok(())
}

fn redact_history_payload(payload: &Value) -> Result<Value, String> {
    let mut output = payload
        .as_object()
        .ok_or_else(|| "history payload is not an object".to_owned())?
        .clone();
    if let Some(messages) = output.get_mut("messages").and_then(Value::as_array_mut) {
        *messages = messages
            .iter()
            .map(|message| {
                serde_json::json!({
                    "message_id": message.get("message_id"),
                    "created_at": message.get("created_at"),
                })
            })
            .collect();
    }
    Ok(Value::Object(output))
}

fn parse_cursor(arguments: &[String]) -> Result<HistoryCursor, String> {
    let created_at = DateTime::parse_from_rfc3339(&arguments[11])
        .map_err(|_| "history cursor created_at must be RFC 3339".to_owned())?
        .with_timezone(&Utc);
    HistoryCursor::new(created_at, arguments[12].as_str()).map_err(|error| error.to_string())
}

fn run() -> Result<(), String> {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    if arguments.len() != 10 && arguments.len() != 11 && arguments.len() != 13 {
        return Err(USAGE.to_owned());
    }
    let (client, binding) = build_client(&arguments)?;
    execute_status(&client, &binding)?;
    if arguments.len() >= 11 {
        let cursor = if arguments.len() == 13 {
            Some(parse_cursor(&arguments)?)
        } else {
            None
        };
        execute_history(&client, &binding, arguments[10].as_str(), cursor)?;
    }
    Ok(())
}
