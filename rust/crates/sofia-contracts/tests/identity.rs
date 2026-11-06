use serde_json::Value;
use sofia_contracts::{AegisIdentity, ContractError, IdentityKind};

fn decode(case: &Value) -> Result<AegisIdentity, ContractError> {
    match case["form"].as_str().expect("fixture form") {
        "serial" => case["input"]
            .as_str()
            .ok_or_else(|| ContractError::new("invalid_identity", "serial is not text"))
            .and_then(AegisIdentity::from_serial),
        "uuid" => {
            let kind = match case["kind"].as_str() {
                Some("platform") => IdentityKind::Platform,
                Some("core") => IdentityKind::Core,
                _ => panic!("fixture UUID kind"),
            };
            case["input"]
                .as_str()
                .ok_or_else(|| ContractError::new("invalid_identity", "UUID is not text"))
                .and_then(|value| AegisIdentity::from_uuid_text(kind, value))
        }
        "payload" => AegisIdentity::from_payload(&case["input"]),
        _ => panic!("unknown fixture form"),
    }
}

#[test]
fn shared_identity_fixtures_match_python_contract() {
    let manifest: Value = serde_json::from_str(include_str!(
        "../../../../contracts/identity/fixtures.v1.json"
    ))
    .expect("identity fixtures");
    assert_eq!(manifest["schema"], "aegis.identity.fixtures.v1");
    for case in manifest["cases"].as_array().expect("fixture cases") {
        let identity = decode(case);
        if case["valid"] == true {
            let identity = identity.unwrap_or_else(|error| panic!("{}: {error}", case["name"]));
            assert_eq!(identity.to_payload(), case["expected"], "{}", case["name"]);
            assert_eq!(identity.serial(), case["serial"], "{}", case["name"]);
        } else {
            assert!(identity.is_err(), "{}", case["name"]);
        }
    }
}

#[test]
fn every_uuid_bit_and_extreme_value_round_trips() {
    for kind in [IdentityKind::Platform, IdentityKind::Core] {
        for number in [0, u128::MAX]
            .into_iter()
            .chain((0..128).map(|bit| 1_u128 << bit))
        {
            let identity = AegisIdentity::new(kind, number.to_be_bytes());
            assert_eq!(identity.uuid_bytes(), number.to_be_bytes());
            assert_eq!(identity.kind(), kind);
            assert_eq!(
                AegisIdentity::from_serial(&identity.serial()).unwrap(),
                identity
            );
            assert_eq!(
                AegisIdentity::from_uuid_text(kind, &identity.canonical_uuid()).unwrap(),
                identity
            );
            assert_eq!(
                AegisIdentity::from_payload(&identity.to_payload()).unwrap(),
                identity
            );
        }
    }
}

#[test]
fn different_kind_or_uuid_never_collapses_in_sample() {
    let mut serials = std::collections::HashSet::new();
    for kind in [IdentityKind::Platform, IdentityKind::Core] {
        for number in 0_u128..256 {
            assert!(serials.insert(AegisIdentity::new(kind, number.to_be_bytes()).serial()));
        }
    }
    assert_eq!(serials.len(), 512);
}
