//! Disposable oracle for the production status adapter; never a launcher.
use chrono::Utc;
use reqwest::Url;
use sofia_core_link::{
    platform_authority::{PlatformStatusClient, PlatformStatusConfiguration},
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
    if !matches!(args.len(), 10 | 11) || (args.len() == 11 && args[10] != "revocation-cycle") {
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
    let client = PlatformStatusClient::new(config, |reference| {
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
    })?;
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
