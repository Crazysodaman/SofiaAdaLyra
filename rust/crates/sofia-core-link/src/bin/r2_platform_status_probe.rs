//! Disposable oracle for the production status adapter; never a launcher.
use chrono::Utc;
use reqwest::Url;
use sofia_core_link::{
    platform_authority::{
        PlatformConversationClient, PlatformStatusClient, PlatformStatusConfiguration,
    },
    Error, TlsCredentials,
};
use std::{
    env, fs,
    io::{Read, Write},
    path::PathBuf,
    process,
    time::Duration,
};

fn run() -> Result<(), Error> {
    let args: Vec<String> = env::args().collect();
    if !matches!(args.len(), 10 | 11 | 12 | 14)
        || (args.len() == 11 && args[10] != "revocation-cycle")
        || (args.len() == 12 && args[10] != "conversation-history")
        || (args.len() == 14 && args[10] != "conversation-cycle")
    {
        return Err(Error::Contract("invalid status probe arguments"));
    }
    let config = PlatformStatusConfiguration {
        python: PathBuf::from(&args[1]),
        binding_store: PathBuf::from(&args[2]),
        minimum_store_revision: args[3].parse().map_err(|_| Error::Malformed)?,
        endpoint_id: args[4].clone(),
        credential_ref: args[5].clone(),
        endpoint: Url::parse(&args[6]).map_err(|_| Error::Malformed)?,
        timeout: Duration::from_secs(3),
    };
    let resolve = |reference: &str| {
        if reference != args[5] {
            return Err(Error::BindingMismatch);
        }
        let mut identity =
            fs::read(&args[8]).map_err(|_| Error::Contract("fixture certificate unavailable"))?;
        identity.extend_from_slice(
            &fs::read(&args[9]).map_err(|_| Error::Contract("fixture key unavailable"))?,
        );
        Ok(TlsCredentials {
            ca_pem: fs::read(&args[7]).map_err(|_| Error::Contract("fixture CA unavailable"))?,
            client_identity_pem: identity,
        })
    };
    if matches!(args.len(), 12 | 14) {
        let client = PlatformConversationClient::new(config, resolve)?;
        if args.len() == 12 {
            let history = client.history(&args[11], None, 100, Utc::now())?;
            let messages = history
                .payload
                .get("messages")
                .and_then(serde_json::Value::as_array)
                .ok_or(Error::Malformed)?;
            println!(
                "{}",
                serde_json::json!({
                    "operation":"conversation-history",
                    "history_status":history.status,
                    "messages":messages.len(),
                })
            );
            return Ok(());
        }
        let created = client.create(&args[11], Utc::now())?;
        let session_id = created
            .payload
            .get("session_id")
            .and_then(serde_json::Value::as_str)
            .ok_or(Error::Malformed)?;
        let sent = client.send(&args[12], session_id, &args[13], None, Utc::now())?;
        let history = client.history(session_id, None, 100, Utc::now())?;
        let messages = history
            .payload
            .get("messages")
            .and_then(serde_json::Value::as_array)
            .ok_or(Error::Malformed)?;
        println!(
            "{}",
            serde_json::json!({
                "operation":"conversation-cycle",
                "create_status":created.status,
                "send_status":sent.status,
                "history_status":history.status,
                "messages":messages.len(),
                "session_id":session_id,
            })
        );
        return Ok(());
    }
    let client = PlatformStatusClient::new(config, resolve)?;
    let result = client.status(Utc::now())?;
    println!(
        "{}",
        serde_json::json!({"operation":"status", "status":result.status})
    );
    if args.len() == 11 {
        std::io::stdout().flush().map_err(|_| Error::Malformed)?;
        for phase in ["denied", "rollback-denied"] {
            std::io::stdin()
                .read_exact(&mut [0u8])
                .map_err(|_| Error::Malformed)?;
            if client.status(Utc::now()).is_ok() {
                return Err(Error::Contract("revoked or rolled-back selection admitted"));
            }
            println!("{}", serde_json::json!({"phase": phase}));
            std::io::stdout().flush().map_err(|_| Error::Malformed)?;
        }
    }
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("status unavailable: {error}");
        process::exit(2);
    }
}
