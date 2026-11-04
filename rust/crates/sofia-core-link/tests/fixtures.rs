use sofia_core_link::parse_response;

#[test]
fn accepts_reviewed_response_fixtures() {
    for raw in [
        include_bytes!("../../../../contracts/core-link/valid-status-response.json").as_slice(),
        include_bytes!("../../../../contracts/core-link/valid-history-response.json").as_slice(),
    ] {
        parse_response(raw).expect("reviewed response fixture");
    }
}

#[test]
fn rejects_duplicate_and_oversized_responses() {
    let duplicate = br#"{"schema":"companion.platform.core_link_response.v1","protocol":"1.0","request_id":"r:1","request_id":"r:2","status":"completed","payload":{},"server_at":"2026-01-01T00:00:00Z"}"#;
    assert!(parse_response(duplicate).is_err());
    let trailing = br#"{"schema":"companion.platform.core_link_response.v1","protocol":"1.0","request_id":"r:1","status":"completed","payload":{},"server_at":"2026-01-01T00:00:00Z"} {}"#;
    assert!(parse_response(trailing).is_err());
    assert!(parse_response(&vec![b' '; sofia_core_link::MAX_WIRE_BYTES + 1]).is_err());
}
