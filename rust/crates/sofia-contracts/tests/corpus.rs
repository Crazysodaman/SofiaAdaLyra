use std::path::PathBuf;
use std::process::Command;

#[test]
fn golden_corpus_matches_declared_acceptance() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..");
    let manifest = root.join("contracts/fixtures/manifest.v1.json");
    let output = Command::new(env!("CARGO_BIN_EXE_sofia-contract-tool"))
        .args(["validate-corpus", manifest.to_str().expect("UTF-8 path")])
        .output()
        .expect("contract tool runs");
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let actual: serde_json::Value = serde_json::from_slice(&output.stdout).expect("JSON report");
    let source: serde_json::Value =
        serde_json::from_slice(&std::fs::read(manifest).expect("manifest")).expect("manifest JSON");
    let expected: serde_json::Map<String, serde_json::Value> = source["cases"].as_array().expect("cases").iter().map(|case| {
        let name = case["name"].as_str().expect("name").to_owned();
        let value = serde_json::json!({"valid": case["valid"], "error": case.get("error").unwrap_or(&serde_json::Value::Null)});
        let value = if case["valid"].as_bool() == Some(true) {
            serde_json::json!({"valid": true, "error": null, "canonical_digest": case["canonical_digest"]})
        } else {
            value
        };
        (name, value)
    }).collect();
    assert_eq!(actual, serde_json::Value::Object(expected));
}
