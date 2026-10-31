"""Bind immutable RC archives to GitHub's cryptographically verified provenance.

This stdlib-only entry point runs in the isolated OIDC job without installing
candidate code/dependencies. It never creates keys or grants deployment rights.
Cryptographic verification belongs to `gh attestation verify`, not JSON parsing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile

REPOSITORY = "Crazysodaman/SofiaAdaLyra"
WORKFLOWS = frozenset({
    ".github/workflows/release-candidate.yml",
    ".github/workflows/debian-release-candidate.yml",
})
REFS = frozenset({"refs/heads/main", "refs/heads/chatgpt/go-live-release-env-version"})


def _sha(value: str, length: int) -> str:
    if not isinstance(value, str) or not re.fullmatch(rf"[0-9a-f]{{{length}}}", value):
        raise ValueError("invalid exact source/artifact digest")
    return value


def _digest(path: Path) -> str:
    for item in (path, *path.parents):
        if item.is_symlink() or (getattr(item, "is_junction", lambda: False)()):
            raise ValueError("redirected attestation subject")
    if not path.is_file():
        raise ValueError("attestation subject must be an existing regular file")
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate evidence JSON field")
        result[key] = value
    return result


def inspect_subject(path: Path, expected_digest: str, revision: str) -> dict:
    """Check upload digest and the accepted exact-SHA gate inside the archive."""
    _sha(revision, 40)
    if _digest(path) != _sha(expected_digest, 64):
        raise ValueError("immutable uploaded artifact digest mismatch")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [item.filename for item in entries]
        if len(names) != len(set(names)) or len(names) > 1024:
            raise ValueError("duplicate or excessive release archive entries")
        if sum(item.file_size for item in entries) > 1024 ** 3:
            raise ValueError("release archive exceeds inspection bound")
        for item in entries:
            name = PurePosixPath(item.filename)
            if (name.is_absolute() or ".." in name.parts or "\\" in item.filename
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError("unsafe release archive entry")
        manifests = [name for name in names if PurePosixPath(name).name == "release-manifest.json"]
        if len(manifests) != 1:
            raise ValueError("archive must contain exactly one release manifest")
        manifest_path = PurePosixPath(manifests[0])
        manifest = json.loads(archive.read(manifests[0]), object_pairs_hook=_unique_object)
        evidence_path = str(manifest_path.parent / "verification-evidence.json")
        evidence_bytes = archive.read(evidence_path)
        evidence = json.loads(evidence_bytes, object_pairs_hook=_unique_object)
        if manifest.get("git_revision") != revision or evidence.get("git_revision") != revision:
            raise ValueError("release evidence source revision mismatch")
        if (evidence.get("accepted") is not True
                or evidence.get("tracked_tree_clean") is not True
                or evidence.get("phase") != "full"
                or manifest.get("verification_phase") != "full"):
            raise ValueError("release requires accepted clean full verification")
        commands = evidence.get("commands")
        if not isinstance(commands, list) or not commands or any(
            not isinstance(item, dict) or type(item.get("returncode")) is not int
            or item["returncode"] != 0 for item in commands
        ):
            raise ValueError("release verification contains missing or failed gates")
        if hashlib.sha256(evidence_bytes).hexdigest() != manifest.get("verification_evidence_sha256"):
            raise ValueError("verification evidence manifest digest mismatch")
        prefix = str(manifest_path.parent / "artifact") + "/"
        wheels = [name for name in names if name.startswith(prefix) and name.endswith(".whl")]
        # A root-level manifest has no './' prefix in a ZIP entry.
        if str(manifest_path.parent) == ".":
            wheels = [name for name in names if name.startswith("artifact/") and name.endswith(".whl")]
        components = manifest.get("components") or []
        if len(wheels) != (3 if components else 1):
            raise ValueError("release archive wheel set is incomplete")
    return {
        "path": str(path.absolute()), "sha256": expected_digest,
        "git_revision": revision, "format": "components" if components else "integrated",
    }


def prepare_subjects(inputs: list[tuple[Path, str]], revision: str, output: Path) -> None:
    if len(inputs) != 2:
        raise ValueError("both integrated and separated release archives are required")
    rows = []
    for directory, digest in inputs:
        # The artifact client's raw download fallback is named 'artifact',
        # without an extension. ZIP structure and digest, not filename suffix,
        # establish the subject's identity.
        archives = [item for item in directory.iterdir() if item.is_file() or item.is_symlink()]
        if len(archives) != 1:
            raise ValueError("each immutable artifact must download as one ZIP archive")
        rows.append(inspect_subject(archives[0], digest, revision))
    if len({row["sha256"] for row in rows}) != 2:
        raise ValueError("release subjects must be distinct")
    if [row["format"] for row in rows] != ["integrated", "components"]:
        raise ValueError("integrated and separated artifact formats must match their inputs")
    if any("\n" in row["path"] or "\r" in row["path"] for row in rows):
        raise ValueError("invalid checksum subject path")
    output.mkdir(parents=True, exist_ok=True)
    (output / "subjects.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (output / "subjects.sha256").write_text(
        "".join(f'{row["sha256"]}  {row["path"]}\n' for row in rows), encoding="utf-8",
    )


def verify_subjects(
    index: Path, *, repository: str, workflow: str, source_ref: str,
    revision: str, receipt: Path, run=subprocess.run,
) -> None:
    # Remove stale acceptance before any attempt, including malformed context.
    receipt.unlink(missing_ok=True)
    _sha(revision, 40)
    if repository != REPOSITORY or workflow not in WORKFLOWS or source_ref not in REFS:
        raise ValueError("unapproved candidate provenance context")
    rows = json.loads(index.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError("both release subjects are required")
    if (len({row["sha256"] for row in rows}) != 2
            or [row["format"] for row in rows] != ["integrated", "components"]):
        raise ValueError("distinct integrated and separated subjects are required")
    results = []
    for row in rows:
        path = Path(row["path"])
        if row.get("git_revision") != revision:
            raise ValueError("subject index revision mismatch")
        if inspect_subject(path, row["sha256"], revision) != row:
            raise ValueError("subject index does not match inspected artifact")
        command = [
            "gh", "attestation", "verify", str(path),
            "--repo", repository,
            "--signer-workflow", f"{repository}/{workflow}",
            "--signer-digest", revision,
            "--source-digest", revision,
            "--source-ref", source_ref,
            "--cert-oidc-issuer", "https://token.actions.githubusercontent.com",
            "--predicate-type", "https://slsa.dev/provenance/v1",
            "--deny-self-hosted-runners", "--format", "json",
        ]
        completed = run(command, check=True, capture_output=True, text=True, timeout=180)
        verified = json.loads(completed.stdout)
        if not isinstance(verified, list) or not verified:
            raise ValueError("gh returned no cryptographically verified attestation")
        results.append({"subject": row, "verification": verified})
    # Do not publish a success receipt if either subject changed during checks.
    for row in rows:
        if _digest(Path(row["path"])) != row["sha256"]:
            raise ValueError("subject changed during attestation verification")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({
        "schema": "sofia.release.keyless-verification.v1",
        "repository": repository, "workflow": workflow, "source_ref": source_ref,
        "git_revision": revision, "results": results,
        "production_authorized": False,
    }, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    for kind in ("integrated", "components"):
        prepare.add_argument(f"--{kind}-dir", type=Path, required=True)
        prepare.add_argument(f"--{kind}-digest", required=True)
    prepare.add_argument("--revision", required=True)
    prepare.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--index", type=Path, required=True)
    verify.add_argument("--repository", required=True)
    verify.add_argument("--workflow", required=True)
    verify.add_argument("--source-ref", required=True)
    verify.add_argument("--revision", required=True)
    verify.add_argument("--receipt", type=Path, required=True)
    args = vars(parser.parse_args())
    if args.pop("command") == "prepare":
        prepare_subjects([
            (args.pop("integrated_dir"), args.pop("integrated_digest")),
            (args.pop("components_dir"), args.pop("components_digest")),
        ], **args)
    else:
        verify_subjects(**args)


if __name__ == "__main__":
    main()
