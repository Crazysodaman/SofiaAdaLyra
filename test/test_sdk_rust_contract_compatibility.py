from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess

import pytest

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
