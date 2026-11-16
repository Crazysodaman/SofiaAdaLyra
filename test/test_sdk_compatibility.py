from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from sofia.sdk.compatibility import (
    CompatibilityError,
    MINIMUM_CRITICAL_FIELDS,
    ProtocolRange,
    compatibility_manifest,
    negotiate_protocol,
)
from sofia.sdk.contracts import ProtocolVersion, SDK_PROTOCOL_VERSION


ROOT = Path(__file__).resolve().parents[1]
COMPATIBILITY_SOURCE = ROOT / "src" / "sofia" / "sdk" / "compatibility.py"
FIXTURE = ROOT / "contracts" / "sdk" / "compatibility-v1.json"


def _fields() -> set[str]:
    return set(MINIMUM_CRITICAL_FIELDS)


def test_wire_protocol_remains_exactly_1_0() -> None:
    assert SDK_PROTOCOL_VERSION == ProtocolVersion(1, 0)
    assert str(SDK_PROTOCOL_VERSION) == "1.0"
    assert compatibility_manifest()["wire_protocol"] == "1.0"


def test_exact_1_0_is_accepted() -> None:
    assert negotiate_protocol("1.0", _fields()) == ProtocolVersion(1, 0)
    assert negotiate_protocol((1, 0), _fields()) == ProtocolVersion(1, 0)
    assert negotiate_protocol(ProtocolVersion(1, 0), _fields()) == ProtocolVersion(1, 0)


def test_1_1_is_rejected_without_mutual_additive_support() -> None:
    with pytest.raises(CompatibilityError) as caught:
        negotiate_protocol("1.1", _fields())
    assert caught.value.code == "unsupported_minor"
    with pytest.raises(CompatibilityError) as caught:
        negotiate_protocol(
            "1.1", _fields(), peer_supports_additive_minor=True
        )
    assert caught.value.code == "unsupported_minor"


def test_1_1_is_accepted_only_when_both_peers_explicitly_support_it() -> None:
    local = ProtocolRange(ProtocolVersion(1, 0), ProtocolVersion(1, 0), additive_minor=True)
    assert negotiate_protocol(
        "1.1",
        _fields(),
        local_range=local,
        peer_supports_additive_minor=True,
    ) == ProtocolVersion(1, 1)
    with pytest.raises(CompatibilityError) as caught:
        negotiate_protocol("1.1", _fields(), local_range=local)
    assert caught.value.code == "unsupported_minor"
    assert negotiate_protocol(
        "1.1",
        _fields(),
        local_supports_additive_minor=True,
        peer_supports_additive_minor=True,
    ) == ProtocolVersion(1, 1)


def test_unknown_major_is_rejected() -> None:
    for version in ("2.0", "0.0", "65536.0"):
        with pytest.raises(CompatibilityError) as caught:
            negotiate_protocol(version, _fields())
        assert caught.value.code in {"malformed_protocol", "unsupported_major"}


@pytest.mark.parametrize(
    "value",
    [None, True, 1.0, "", "1", "1.0.0", "v1.0", "01.0", (1,), (1, 0, 2)],
)
def test_malformed_protocol_is_rejected(value: object) -> None:
    with pytest.raises(CompatibilityError) as caught:
        negotiate_protocol(value, _fields())
    assert caught.value.code == "malformed_protocol"


def test_missing_critical_fields_are_rejected() -> None:
    for missing in sorted(MINIMUM_CRITICAL_FIELDS):
        with pytest.raises(CompatibilityError) as caught:
            negotiate_protocol("1.0", _fields() - {missing})
        assert caught.value.code == "missing_critical_fields"
        assert missing in str(caught.value)


def test_malformed_required_fields_are_rejected() -> None:
    for value in ("protocol", None, [1, "protocol"]):
        with pytest.raises(CompatibilityError) as caught:
            negotiate_protocol("1.0", value)
        assert caught.value.code == "malformed_fields"


def test_mapping_required_fields_use_their_names() -> None:
    assert negotiate_protocol("1.0", {name: True for name in _fields()}) == (
        ProtocolVersion(1, 0)
    )


def test_compatibility_manifest_is_deterministic_and_matches_golden_fixture() -> None:
    first = compatibility_manifest()
    second = compatibility_manifest()
    assert first == second
    assert first == json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert first["minimum_critical_fields"] == sorted(MINIMUM_CRITICAL_FIELDS)
    assert first["compatibility_claim"] is False
    assert first["inventory_only"] is True


def test_compatibility_module_has_no_core_or_platform_dependency() -> None:
    tree = ast.parse(COMPATIBILITY_SOURCE.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add("." * node.level + (node.module or ""))
    assert ".contracts" in imports
    assert not any(
        name == "sofia.core"
        or name.startswith("sofia.core.")
        or name == "sofia.platform"
        or name.startswith("sofia.platform.")
        for name in imports
    )


def test_fresh_process_import_does_not_load_sofia_core() -> None:
    code = (
        "import sys; import sofia.sdk.compatibility as c; "
        "assert c.compatibility_manifest()['wire_protocol'] == '1.0'; "
        "assert not any(name == 'sofia.core' or name.startswith('sofia.core.') "
        "for name in sys.modules), sorted(sys.modules)"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_protocol_range_rejects_incompatible_major_span() -> None:
    with pytest.raises(ValueError):
        ProtocolRange(ProtocolVersion(1, 0), ProtocolVersion(2, 0))
    with pytest.raises(ValueError):
        ProtocolRange(ProtocolVersion(1, 2), ProtocolVersion(1, 1))
