"""Independent host-owned effect attestation ledger for GOALS reconciliation.

A Core-authored receipt can never prove a real external effect. When a GOALS
dispatch reserves an effectful action, the overseeing Platform host observes
the outcome from outside the cognitive process, ``attest_effect`` seals that
observation with a host-only HMAC key, and ``verify_dispatch_outcome``
independently re-attests the exact dispatch before canonical reconciliation
may run. The ledger is platform-local operational storage, never another
canonical Sofía state writer, and follows the approved local-vs-canonical
ownership boundary: host stores hold scope-limited operational evidence only.
"""

from datetime import datetime
import hashlib
import hmac
import json
import secrets
from pathlib import Path

from sofia.platform.state.private_file import (
    assert_no_redirected_components,
    atomic_write_private_text,
    ensure_owner_private_directory,
)

_ALLOWED_OUTCOMES = frozenset({"performed", "absent"})
_MAX_ROWS = 200_000
_KEY_BYTES = 32
_GENESIS_DIGEST = "genesis"
_REQUIRED_PAYLOAD_FIELDS = {
    "row_no", "dispatch_id", "goal_id", "capability",
    "outcome", "attested_by", "observed_at", "prev_digest",
}


class HostEffectAttestationError(RuntimeError):
    """Host attestation integrity failure; verification must fail closed."""


def _canonical(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _aware(value: datetime, *, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


class HostEffectAttestationLedger:
    """Sealed append-only host observation journal bound to a host-only key.

    Any unsealable or reordered row invalidates the entire journal, so a
    tampered or forged history can never authorize canonical reconciliation.
    """

    def __init__(self, root: Path) -> None:
        if not isinstance(root, Path):
            raise TypeError("host attestation root must be a Path")
        self._root = Path(root) / "platform-host-effects"
        ensure_owner_private_directory(self._root)
        self._key_path = self._root / "host-effect-key.hex"
        self._store_file: Path | None = None

    @property
    def store_path(self) -> Path:
        return self._store_file or self._root / "host-effect-attestations.jsonl"

    @property
    def tip_path(self) -> Path:
        return self._store_file or self._root / "host-effect-journal.tip"

    def _key(self) -> bytes:
        if self._key_path.exists():
            material = self._key_path.read_text(encoding="utf-8-sig").strip()
            try:
                key = bytes.fromhex(material)
            except ValueError as error:
                raise HostEffectAttestationError(
                    "host attestation key is invalid"
                ) from error
            if len(key) != _KEY_BYTES:
                raise HostEffectAttestationError("host attestation key is invalid")
            return key
        assert_no_redirected_components(self._key_path, include_leaf=True)
        atomic_write_private_text(self._key_path, secrets.token_hex(_KEY_BYTES))
        return self._key()

    # -- public host-side API ------------------------------------------------

    def attest_effect(
        self, *, dispatch_id: str, goal_id: str, capability: str,
        outcome: str, attested_by: str, now: datetime,
    ) -> str:
        """Seal one host observation for the exact dispatch; returns row digest."""
        if not isinstance(dispatch_id, str) or not dispatch_id.strip():
            raise ValueError("exact dispatch id required")
        if not isinstance(goal_id, str) or not goal_id.strip():
            raise ValueError("exact goal id required")
        if not isinstance(capability, str) or not capability.strip():
            raise ValueError("exact capability required")
        if outcome not in _ALLOWED_OUTCOMES:
            raise ValueError("host outcome must be performed or absent")
        if not isinstance(attested_by, str) or not attested_by.strip():
            raise ValueError("attesting host identity required")
        now = _aware(now, label="observation time")
        rows, last_digest = self._journal(self.store_path)
        if any(row["dispatch_id"] == dispatch_id for row in rows):
            raise ValueError(
                "dispatch already independently attested; one-seal per dispatch"
            )
        entry = {
            "row_no": len(rows),
            "dispatch_id": dispatch_id,
            "goal_id": goal_id,
            "capability": capability,
            "outcome": outcome,
            "attested_by": attested_by,
            "observed_at": now.isoformat(),
            "prev_digest": last_digest if rows else _GENESIS_DIGEST,
        }
        payload_digest = hashlib.sha256(_canonical(entry)).hexdigest()
        tag = hmac.new(self._key(), _canonical(entry), hashlib.sha256).hexdigest()
        line = json.dumps(
            {"payload": entry, "entry_digest": payload_digest, "tag": tag},
            separators=(",", ":"), ensure_ascii=False,
        )
        assert_no_redirected_components(self.store_path, include_leaf=False)
        with self.store_path.open("a", encoding="utf-8-sig") as sink:
            sink.write(f"{line}\n")
        self._seal_tip(len(rows) + 1, payload_digest)
        return payload_digest

    def _seal_tip(self, row_count: int, tip_digest: str) -> None:
        payload = {"row_no": row_count, "tip_digest": tip_digest}
        tag = hmac.new(self._key(), _canonical(payload), hashlib.sha256).hexdigest()
        sealed = json.dumps(
            {"payload": payload, "tag": tag},
            separators=(",", ":"), ensure_ascii=False,
        )
        assert_no_redirected_components(self.tip_path, include_leaf=True)
        atomic_write_private_text(self.tip_path, f"{sealed}\n")

    # -- production verification callback ------------------------------------

    def verify_dispatch_outcome(self, dispatch_id: str, evidence) -> bool:
        """GOALS ``independent_outcome_verifier`` implementation.

        Returns True only when an unforgeable host attestation matches the
        exact dispatch, goal, capability and outcome mapping of the claimed
        core receipt. Structural failures raise; they must surface loudly.
        """
        if not isinstance(dispatch_id, str) or not dispatch_id.strip():
            return False
        rows, _digest = self._journal(self.store_path)
        successful = getattr(evidence, "successful", None)
        observed_at = getattr(evidence, "observed_at", None)
        for row in rows:
            if row["dispatch_id"] != dispatch_id:
                continue
            if row["goal_id"] != getattr(evidence, "goal_id", None):
                continue
            if row["capability"] != getattr(evidence, "assertion", None):
                continue
            expected_outcome = "performed" if successful is True else (
                "absent" if successful is False else None
            )
            if row["outcome"] != expected_outcome:
                continue
            if observed_at is None:
                return False
            if not self._observation_precedes(row, observed_at):
                continue
            return True
        return False

    @staticmethod
    def _observation_precedes(row: dict, observed_at: datetime) -> bool:
        if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
            return False
        try:
            stamped = datetime.fromisoformat(row["observed_at"])
        except ValueError as error:
            raise HostEffectAttestationError(
                "host attestation row timestamp is corrupt"
            ) from error
        if stamped.tzinfo is None:
            raise HostEffectAttestationError("host attestation time lost timezone")
        # Host observation must be no later than the claimed core receipt.
        return stamped <= observed_at

    # -- journal integrity ---------------------------------------------------

    def _journal(self, path: Path) -> tuple[list[dict], str]:
        """Walk the sealed journal; returns payloads and the anchored tip."""
        if not path.exists():
            return [], _GENESIS_DIGEST
        assert_no_redirected_components(path, include_leaf=False)
        rows: list[dict] = []
        key = self._key()
        expected_prev = _GENESIS_DIGEST
        with path.open("r", encoding="utf-8-sig") as source:
            for number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                if number > _MAX_ROWS:
                    raise HostEffectAttestationError(
                        "host attestation journal exceeded integrity bound"
                    )
                try:
                    sealed = json.loads(line)
                except json.JSONDecodeError as error:
                    raise HostEffectAttestationError(
                        f"host attestation row {number} is corrupt"
                    ) from error
                if not isinstance(sealed, dict) or set(sealed) != {
                    "payload", "entry_digest", "tag",
                }:
                    raise HostEffectAttestationError("attestation row is malformed")
                payload = sealed["payload"]
                if not isinstance(payload, dict) or set(payload) != (
                    _REQUIRED_PAYLOAD_FIELDS
                ):
                    raise HostEffectAttestationError("attestation payload is malformed")
                canonical = _canonical(payload)
                entry_digest_ok = hmac.compare_digest(
                    hashlib.sha256(canonical).hexdigest(), sealed["entry_digest"]
                )
                tag_ok = hmac.compare_digest(
                    hmac.new(key, canonical, hashlib.sha256).hexdigest(),
                    sealed["tag"],
                )
                if (
                    not entry_digest_ok or not tag_ok
                    or payload["prev_digest"] != expected_prev
                    or payload["row_no"] != len(rows)
                ):
                    raise HostEffectAttestationError(
                        "host attestation chain is tampered or forged"
                    )
                if payload.get("outcome") not in _ALLOWED_OUTCOMES:
                    raise HostEffectAttestationError("attestation outcome is invalid")
                expected_prev = sealed["entry_digest"]
                rows.append(payload)
        self._verify_tip(len(rows), expected_prev, key)
        return rows, expected_prev

    def _verify_tip(self, row_count: int, tip_digest: str, key: bytes) -> None:
        """The sealed tip anchor prevents silent truncation of the journal."""
        if not self.tip_path.exists():
            raise HostEffectAttestationError(
                "host attestation journal tip anchor is missing"
            )
        text = self.tip_path.read_text(encoding="utf-8-sig").strip()
        try:
            sealed = json.loads(text)
        except json.JSONDecodeError as error:
            raise HostEffectAttestationError(
                "host attestation tip anchor is corrupt"
            ) from error
        if not isinstance(sealed, dict) or set(sealed) != {"payload", "tag"}:
            raise HostEffectAttestationError("host attestation tip is malformed")
        payload = sealed["payload"]
        if not isinstance(payload, dict) or set(payload) != {
            "row_no", "tip_digest",
        }:
            raise HostEffectAttestationError("host attestation tip is malformed")
        tag_ok = hmac.compare_digest(
            hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest(),
            sealed["tag"],
        )
        rows_ok = payload["row_no"] == row_count
        digest_ok = hmac.compare_digest(payload["tip_digest"], tip_digest)
        if not tag_ok or not rows_ok or not digest_ok:
            raise HostEffectAttestationError(
                "host attestation journal diverges from its sealed tip"
            )
