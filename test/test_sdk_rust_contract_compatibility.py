from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from sofia.sdk.contract_wire import (
    ContractWireError,
    DispatchContext,
    canonical_sha256,
    decode_request,
    decode_response,
    loads_strict,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "contracts" / "fixtures" / "manifest.v1.json"
SCHEMAS = ROOT / "contracts" / "schemas"
CORRECTED_RULE_CASES = {
    "core_endpoint_with_identity": (True, True),
    "noncore_endpoint_without_identity": (True, True),
    "core_endpoint_missing_identity": (False, False),
    "noncore_endpoint_with_identity": (False, False),
    "response_payload_pair_present": (True, True),
    "response_payload_pair_null": (True, True),
    "response_payload_type_only": (False, False),
    "response_payload_digest_only": (False, False),
    "verified_response_with_evidence": (True, True),
    "verified_response_without_evidence": (False, False),
}


def _python_report() -> dict[str, dict[str, object]]:
    manifest = json.loads(CORPUS.read_text(encoding="utf-8"))
    report = {}
    for case in manifest["cases"]:
        raw = (CORPUS.parent / case["file"]).read_bytes()
        try:
            context = None
            if "context" in case:
                item = case["context"]
                context = DispatchContext(
                    now=datetime.fromisoformat(item["now"]),
                    expected_destination_generation=item["expected_destination_generation"],
                    expected_audience_id=item["expected_audience_id"],
                )
            payload = case.get("payload")
            if case["kind"] == "request":
                decode_request(raw, context=context, payload=payload)
            elif case["kind"] == "response":
                decode_response(raw)
            else:
                loads_strict(raw)
            result = {
                "valid": True,
                "error": None,
                "canonical_digest": canonical_sha256(loads_strict(raw)),
            }
        except ContractWireError as exc:
            result = {"valid": False, "error": exc.code}
        report[case["name"]] = result
    return report


def test_python_corpus_matches_manifest_expectations():
    report = _python_report()
    manifest = json.loads(CORPUS.read_text(encoding="utf-8"))
    expected = {
        case["name"]: {
            "valid": case["valid"],
            "error": case.get("error"),
            **(
                {"canonical_digest": case["canonical_digest"]}
                if case["valid"] else {}
            ),
        }
        for case in manifest["cases"]
    }
    assert report == expected


def test_typed_fixtures_match_versioned_json_schemas():
    documents = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in SCHEMAS.glob("*.json")
    }
    for document in documents.values():
        Draft202012Validator.check_schema(document)
    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document))
        for document in documents.values()
    )
    validators = {
        "request": Draft202012Validator(
            documents["component-request.v1.schema.json"],
            registry=registry,
            format_checker=FormatChecker(),
        ),
        "response": Draft202012Validator(
            documents["component-response.v1.schema.json"],
            registry=registry,
            format_checker=FormatChecker(),
        ),
    }
    manifest = json.loads(CORPUS.read_text(encoding="utf-8"))
    for case in manifest["cases"]:
        if case["kind"] not in validators:
            continue
        document = loads_strict((CORPUS.parent / case["file"]).read_bytes())
        errors = list(validators[case["kind"]].iter_errors(document))
        assert (not errors) is case["schema_valid"], (
            case["name"], [error.message for error in errors]
        )


def test_corrected_rules_have_explicit_positive_and_negative_conformance_cases():
    manifest = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases = {case["name"]: case for case in manifest["cases"]}
    report = _python_report()
    for name, (schema_valid, runtime_valid) in CORRECTED_RULE_CASES.items():
        assert cases[name]["schema_valid"] is schema_valid
        assert report[name]["valid"] is runtime_valid


def test_python_and_rust_accept_and_reject_identically():
    executable = os.environ.get("SOFIA_RUST_CONTRACT_TOOL")
    if executable:
        command = [executable, "validate-corpus", str(CORPUS)]
    else:
        cargo = os.environ.get("CARGO", "cargo")
        command = [
            cargo, "run", "--quiet", "--locked", "-p", "sofia-contracts",
            "--bin", "sofia-contract-tool", "--", "validate-corpus", str(CORPUS),
        ]
    completed = subprocess.run(
        command, cwd=ROOT, check=True, capture_output=True, text=True,
    )
    assert json.loads(completed.stdout) == _python_report()


def test_canonical_digest_is_order_independent_and_utf8_stable():
    assert canonical_sha256({"é": [1, True], "a": "value"}) == canonical_sha256(
        {"a": "value", "é": [1, True]}
    )


def test_duplicate_key_is_rejected_before_typed_decode():
    with pytest.raises(ContractWireError, match="duplicate") as caught:
        loads_strict(b'{"protocol":"1.0","protocol":"1.0"}')
    assert caught.value.code == "duplicate_key"


def test_deterministic_canonical_property_corpus_is_order_independent():
    for index in range(128):
        left = {"z": index, "a": [True, None, "value"]}
        right = {"a": [True, None, "value"], "z": index}
        assert canonical_sha256(left) == canonical_sha256(right)
