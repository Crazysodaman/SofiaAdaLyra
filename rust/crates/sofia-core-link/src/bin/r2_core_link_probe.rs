//! Test-only compatibility probe. It is not installed or called by production launchers.
use chrono::Utc;
use reqwest::Url;
use sofia_core_link::{CoreLinkClient, EnrolledBinding, Request, TlsCredentials, PROTOCOL};
use std::{env, fs, process, time::Duration};

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    if !matches!(args.len(), 10 | 11) {
        return Err("expected endpoint, pin, CA, client certificate, client key, local Platform, remote Platform, Core identity, generation".into());
    }
    let mut identity = fs::read(&args[4]).map_err(|_| "client certificate unavailable")?;
    identity.extend_from_slice(&fs::read(&args[5]).map_err(|_| "client key unavailable")?);
    let binding = EnrolledBinding {
        active: true,
        endpoint: Url::parse(&args[1]).map_err(|_| "endpoint invalid")?,
        trust_anchor_sha256: args[2].clone(),
        local_platform_id: args[6].clone(),
        remote_platform_id: args[7].clone(),
        remote_core_identity_id: args[8].clone(),
        remote_core_generation: args[9].parse().map_err(|_| "generation invalid")?,
        protocol: PROTOCOL.into(),
    };
    let credentials = TlsCredentials {
        ca_pem: fs::read(&args[3]).map_err(|_| "CA unavailable")?,
        client_identity_pem: identity,
    };
    let client = CoreLinkClient::new(binding.clone(), &credentials, Duration::from_secs(3))
        .map_err(|error| error.to_string())?;
    let now = Utc::now();
    let request = if args.len() == 11 {
        Request::history(&binding, "r2:probe", &args[10], None, 100, now)
            .map_err(|error| error.to_string())?
    } else {
        Request::status(&binding, "r2:probe", now)
    };
    let response = client
        .execute(&request, now)
        .map_err(|error| error.to_string())?;
    // Diagnostic output intentionally excludes private message content and Core state.
    // The probe reports only the requested operation, outcome and message count.
    if response.status != "completed" {
        return Err("Core Link read did not complete".into());
    }
    let summary = if args.len() == 11 {
        let count = response.payload["messages"]
            .as_array()
            .ok_or("history response is missing messages")?
            .len();
        serde_json::json!({
            "operation": "conversation.history",
            "status": response.status,
            "message_count": count,
        })
    } else {
        serde_json::json!({
            "operation": "status",
            "status": response.status,
        })
    };
    println!("{summary}");
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        process::exit(2);
    }
}
