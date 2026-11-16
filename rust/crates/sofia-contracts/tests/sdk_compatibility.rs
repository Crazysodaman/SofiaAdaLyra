use serde_json::Value;
use sofia_contracts::{
    MINIMUM_CRITICAL_FIELDS, PROTOCOL_ADDITIVE_MINOR_SUPPORTED, SUPPORTED_PROTOCOL,
};
use std::fs;
use std::path::PathBuf;

#[test]
fn compatibility_fixture_matches_rust_protocol_constants() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..");
    let raw = fs::read(root.join("contracts/sdk/compatibility-v1.json"))
        .expect("compatibility fixture is readable");
    let value: Value = serde_json::from_slice(&raw).expect("compatibility fixture is JSON");

    assert_eq!(value["schema"], "aegis.sdk.compatibility.v1");
    assert_eq!(value["wire_protocol"], SUPPORTED_PROTOCOL);
    assert_eq!(value["protocol_major"], 1);
    assert_eq!(value["protocol_minor"], 0);

    let fields: Vec<&str> = value["minimum_critical_fields"]
        .as_array()
        .expect("critical fields are an array")
        .iter()
        .map(|item| item.as_str().expect("critical field is a string"))
        .collect();
    assert_eq!(fields.as_slice(), MINIMUM_CRITICAL_FIELDS);
    assert_eq!(
        value["additive_minor"].as_bool(),
        Some(PROTOCOL_ADDITIVE_MINOR_SUPPORTED)
    );
    assert_eq!(value["compatibility_claim"].as_bool(), Some(false));
    assert_eq!(value["inventory_only"].as_bool(), Some(true));
}
