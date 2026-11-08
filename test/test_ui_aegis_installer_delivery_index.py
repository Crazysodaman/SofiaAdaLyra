"""B-007 stock Bash bounded ZIP member integrity, never publisher approval.

Only the outer Ed25519 verification and independently provisioned publisher
root can authenticate delivery. This helper cannot install or grant SAFE.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import zipfile

import pytest

pytestmark = [
    pytest.mark.pkg_ui,
    pytest.mark.skipif(os.name == "nt", reason="stock Debian Bash/unzip"),
]
SCRIPT = Path(__file__).resolve().parents[1] / "packaging/installers/inspect-aegis-capsule-members.sh"


def produce(path: Path, *, defect: str = "") -> str:
    entries = {
        "aegis/release-manifest.json": b"synthetic untrusted manifest",
        "aegis/release-signature.json": b"synthetic untrusted signature",
    }
    if defect == "changed-member":
        index_content = dict(entries)
        entries["aegis/release-manifest.json"] += b"post-index-change"
    else:
        index_content = dict(entries)
    names = sorted(index_content)
    if defect == "unsorted":
        names = list(reversed(names))
    rows = ["aegis.delivery-index.v1"]
    for name in names:
        value = index_content[name]
        digest = sha256(value).hexdigest()
        size = len(value)
        if defect == "wrong-hash" and name.endswith("manifest.json"):
            digest = "f" * 64
        if defect == "wrong-size" and name.endswith("manifest.json"):
            size += 1
        if defect == "traversal" and name.endswith("manifest.json"):
            name = "aegis/../release-manifest.json"
        rows.append(f"{digest}\t{size}\t{name}")
    if defect == "invalid-header":
        rows[0] = "other.index.v1"
    index = ("\n".join(rows) + "\n").encode("ascii")
    if defect == "missing-listed-member":
        del entries["aegis/release-manifest.json"]
    if defect == "extra-unlisted-member":
        entries["aegis/private.json"] = b"not reviewed"
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name, value in sorted({**entries, "aegis/delivery-index.v1": index}.items()):
            archive.writestr(name, value)
        if defect == "duplicate-member":
            archive.writestr("aegis/release-signature.json", entries["aegis/release-signature.json"])
    return sha256(path.read_bytes()).hexdigest()


def invoke(path: Path, digest: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), "--capsule", str(path), "--expected-sha256", digest, *extra],
        capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )


def test_exact_stock_bash_delivery_integrity_is_not_install_or_trust(tmp_path):
    syntax = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert syntax.returncode == 0, syntax.stderr
    path = tmp_path / "test-only.zip"
    digest = produce(path)
    result = invoke(path, digest)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["result"] == "MEMBERS_HASHED_NOT_INSTALLABLE"
    assert receipt["member_count"] == 2
    assert receipt["capsule_sha256"] == digest
    assert len(receipt["delivery_index_sha256"]) == 64
    for field in ("publisher_signature_verified", "release_manifest_verified",
                  "owner_approved", "service_mutated", "core_activated"):
        assert receipt[field] is False


@pytest.mark.parametrize("defect", (
    "changed-member", "wrong-hash", "wrong-size", "traversal", "invalid-header",
    "missing-listed-member", "extra-unlisted-member", "duplicate-member", "unsorted",
))
def test_bounded_index_refuses_signed_but_hostile_member_set(tmp_path, defect):
    media = tmp_path / "malformed-test-only.zip"
    digest = produce(media, defect=defect)
    outcome = invoke(media, digest)
    assert outcome.returncode == 3, (defect, outcome.stdout, outcome.stderr)
    assert "MEMBERS_HASHED_NOT_INSTALLABLE" not in outcome.stdout


@pytest.mark.parametrize("defect", ("wrong-archive-sha", "tampered-after-hash", "force", "bad-pin"))
def test_pin_and_protected_cli_refusals(tmp_path, defect):
    media = tmp_path / "test-only.zip"
    digest = produce(media)
    extra = ()
    if defect == "wrong-archive-sha":
        digest = "f" * 64
    elif defect == "tampered-after-hash":
        with media.open("ab") as stream:
            stream.write(b"tampered")
    elif defect == "force":
        extra = ("--install",)
    else:
        digest = "not-a-sha"
    outcome = invoke(media, digest, *extra)
    assert outcome.returncode in (2, 3), (defect, outcome.stdout, outcome.stderr)
    assert "MEMBERS_HASHED_NOT_INSTALLABLE" not in outcome.stdout
