use chrono::DateTime;
use serde::Deserialize;
use serde_json::{json, Map, Value};
use sofia_contracts::{
    canonical_sha256, decode_request, decode_response, parse_strict, ContractError, DispatchContext,
};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Deserialize)]
struct Manifest {
    cases: Vec<Case>,
}

#[derive(Deserialize)]
struct Case {
    name: String,
    file: String,
    kind: String,
    context: Option<Context>,
    payload: Option<Value>,
}

#[derive(Deserialize)]
struct Context {
    now: String,
    expected_destination_generation: u64,
    expected_audience_id: String,
}

fn validate(case: &Case, root: &Path) -> Result<(), ContractError> {
    let raw = fs::read(root.join(&case.file))
        .map_err(|error| ContractError::new("fixture_io", error.to_string()))?;
    match case.kind.as_str() {
        "request" => {
            let parsed = case
                .context
                .as_ref()
                .map(|context| {
                    let now = DateTime::parse_from_rfc3339(&context.now).map_err(|_| {
                        ContractError::new("invalid_fixture", "invalid context time")
                    })?;
                    Ok(DispatchContext {
                        now,
                        expected_destination_generation: context.expected_destination_generation,
                        expected_audience_id: &context.expected_audience_id,
                    })
                })
                .transpose()?;
            decode_request(&raw, parsed.as_ref(), case.payload.as_ref()).map(|_| ())
        }
        "response" => decode_response(&raw).map(|_| ()),
        "raw" => {
            let value = parse_strict(&raw)?;
            canonical_sha256(&value).map(|_| ())
        }
        _ => Err(ContractError::new(
            "invalid_fixture",
            "unknown fixture kind",
        )),
    }
}

fn corpus(path: &Path) -> Result<Value, String> {
    let raw = fs::read(path).map_err(|error| error.to_string())?;
    let manifest: Manifest = serde_json::from_slice(&raw).map_err(|error| error.to_string())?;
    let root = path
        .parent()
        .ok_or_else(|| "manifest has no parent".to_owned())?;
    let mut report = Map::new();
    for case in &manifest.cases {
        let result = match validate(case, root) {
            Ok(()) => {
                let raw = fs::read(root.join(&case.file)).map_err(|error| error.to_string())?;
                let document = parse_strict(&raw).map_err(|error| error.to_string())?;
                let digest = canonical_sha256(&document).map_err(|error| error.to_string())?;
                json!({"valid": true, "error": null, "canonical_digest": digest})
            }
            Err(error) => json!({"valid": false, "error": error.code}),
        };
        report.insert(case.name.clone(), result);
    }
    Ok(Value::Object(report))
}

fn main() {
    let arguments: Vec<String> = env::args().collect();
    let result = match arguments.as_slice() {
        [_, command, path] if command == "validate-corpus" => corpus(&PathBuf::from(path)),
        _ => Err("usage: sofia-contract-tool validate-corpus MANIFEST".to_owned()),
    };
    match result {
        Ok(report) => println!(
            "{}",
            serde_json::to_string(&report).expect("report is JSON")
        ),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    }
}
