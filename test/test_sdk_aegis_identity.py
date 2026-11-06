"""Public Aegis serials preserve UUID bits without granting authority."""
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID

import pytest

from sofia.sdk.identity import AegisIdentity, IDENTITY_SCHEMA, IdentityKind


@pytest.mark.parametrize("kind,prefix", [(IdentityKind.PLATFORM, "P"), (IdentityKind.CORE, "C")])
def test_full_uuid_serial_contract_known_vector(kind, prefix):
    identity = AegisIdentity(kind, UUID("01234567-89ab-cdef-fedc-ba9876543210"))
    assert identity.serial == f"AEG-{prefix}-01234567-89ABCDEF-FEDCBA98-76543210"
    assert identity.canonical_uuid == "01234567-89ab-cdef-fedc-ba9876543210"
    assert AegisIdentity.from_serial(identity.serial) == identity
    assert AegisIdentity.from_serial(identity.serial.lower()) == identity
    assert AegisIdentity.from_uuid_text(kind, identity.canonical_uuid.upper()) == identity


@pytest.mark.parametrize("value", [0, (1 << 128) - 1, *(1 << bit for bit in range(128))])
def test_codec_preserves_every_uuid_bit(value):
    for kind in IdentityKind:
        identity = AegisIdentity(kind, UUID(int=value))
        assert AegisIdentity.from_serial(identity.serial).identity_id.int == value


def test_distinct_kinds_and_uuid_values_do_not_collapse():
    identities = [AegisIdentity(kind, UUID(int=value)) for kind in IdentityKind for value in range(256)]
    assert len({identity.serial for identity in identities}) == len(identities)
    assert len({AegisIdentity.from_serial(identity.serial) for identity in identities}) == len(identities)


@pytest.mark.parametrize("value", [
    "AEG-P-0123456789ABCDEFFEDCBA9876543210", "AEG-X-01234567-89ABCDEF-FEDCBA98-76543210",
    "AEG-P-01234567-89ABCDEF-FEDCBA98-7654321", "AEG-P-01234567-89ABCDEF-FEDCBA98-765432100",
    "AEG-P-01234567-89ABCDEF-FEDCBA98-7654321G", "AEG-P-01234567-89ABCDEF-FEDCBA98-76543210\n",
    " AEG-P-01234567-89ABCDEF-FEDCBA98-76543210", "AEG-Ρ-01234567-89ABCDEF-FEDCBA98-76543210",
    "AEG-P-v2-01234567-89ABCDEF-FEDCBA98-76543210", "", None, 123,
])
def test_serial_rejects_truncation_unknown_formats_whitespace_and_lookalikes(value):
    with pytest.raises(ValueError):
        AegisIdentity.from_serial(value)


@pytest.mark.parametrize("value", [
    "0123456789abcdeffedcba9876543210", "{01234567-89ab-cdef-fedc-ba9876543210}",
    "urn:uuid:01234567-89ab-cdef-fedc-ba9876543210", "01234567-89ab-cdef-fedc-ba9876543210\n",
    "01234567-89ab-cdef-fedc-ba9876543210 ", None, 5,
])
def test_uuid_text_requires_one_unambiguous_full_form(value):
    with pytest.raises(ValueError):
        AegisIdentity.from_uuid_text(IdentityKind.PLATFORM, value)


def test_identity_projection_is_immutable_and_carries_no_authority():
    identity = AegisIdentity(IdentityKind.PLATFORM, UUID(int=42))
    with pytest.raises(FrozenInstanceError):
        identity.identity_id = UUID(int=43)
    assert identity.to_payload() == {"schema": IDENTITY_SCHEMA, "kind": "platform", "uuid": str(UUID(int=42))}
    assert AegisIdentity.from_payload(json.loads(json.dumps(identity.to_payload()))) == identity
    for extra in ("authenticated", "owner", "grant", "display_name", "serial"):
        with pytest.raises(ValueError):
            AegisIdentity.from_payload({**identity.to_payload(), extra: True})


@pytest.mark.parametrize("patch", [{"schema": "aegis.identity.v2"}, {"kind": "module"}, {"uuid": None}])
def test_payload_rejects_unknown_versions_kinds_and_invalid_uuid(patch):
    identity = AegisIdentity(IdentityKind.CORE, UUID(int=42))
    with pytest.raises(ValueError):
        AegisIdentity.from_payload({**identity.to_payload(), **patch})


def test_constructor_does_not_coerce_labels_or_allocate_an_identity():
    with pytest.raises(TypeError):
        AegisIdentity("platform", UUID(int=42))
    with pytest.raises(TypeError):
        AegisIdentity(IdentityKind.PLATFORM, "Sofía")


def test_three_synthetic_cores_use_identical_neutral_codec_without_identity_copying():
    cores = dict(zip(("Sofía", "Roland", "John"), (UUID(int=n) for n in (11, 22, 33))))
    platform = AegisIdentity(IdentityKind.PLATFORM, UUID(int=44))
    projections = [AegisIdentity(IdentityKind.CORE, uuid) for uuid in cores.values()]
    assert len({item.canonical_uuid for item in [platform, *projections]}) == 4
    for projection in projections:
        assert AegisIdentity.from_payload(projection.to_payload()) == projection
        assert AegisIdentity.from_serial(projection.serial) == projection
        assert all(name not in json.dumps(projection.to_payload()) for name in cores)


def test_identity_codec_loads_with_platform_and_core_implementations_blocked():
    root = Path(__file__).resolve().parents[1]
    code = '''
import importlib.abc, sys
class BlockImplementations(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(("sofia.core", "sofia.platform", "sofia.modules")):
            raise ImportError(fullname)
sys.meta_path.insert(0, BlockImplementations())
from sofia.sdk import AegisIdentity, IdentityKind
from uuid import UUID
assert AegisIdentity(IdentityKind.CORE, UUID(int=1)).serial.startswith("AEG-C-")
'''
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "src")
    result = subprocess.run([sys.executable, "-c", code], cwd=root, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
