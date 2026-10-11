from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile

from sofia.identity.model import IdentityBootstrapMode


@dataclass(frozen=True, slots=True)
class RuntimeStorageLayout:
    mode: str
    source_root: Path
    state_root: Path
    protected_root: Path
    state_path: Path
    constitution_path: Path
    constitution_hash_path: Path
    identity_path: Path
    personality_path: Path
    avatar_path: Path
    identity_bootstrap_mode: IdentityBootstrapMode

    @classmethod
    def from_environment(
        cls,
        repository_root: Path,
        *,
        mode_override: str | None = None,
    ) -> "RuntimeStorageLayout":
        if not isinstance(repository_root, Path):
            raise TypeError("repository_root must be a Path")
        if not isinstance(mode_override, (str, type(None))):
            raise TypeError("mode_override must be text or None")
        mode = (
            os.environ.get(
                "SOFIA_RUNTIME_MODE",
                "development",
            ).strip().lower()
            if mode_override is None
            else mode_override.strip().lower()
        )
        if mode not in {"development", "production"}:
            raise ValueError(
                "SOFIA_RUNTIME_MODE must be development or production"
            )

        explicit_state = os.environ.get(
            "SOFIA_STATE_ROOT",
            "",
        ).strip()
        pointer_file = os.environ.get("SOFIA_STATE_HOME_POINTER", "").strip()
        pointer_key = os.environ.get("SOFIA_STATE_HOME_POINTER_KEY", "").strip()
        writer_host_id = os.environ.get("SOFIA_WRITER_HOST_ID", "").strip()
        epoch_floor = os.environ.get("SOFIA_MIN_WRITER_EPOCH", "").strip()
        if pointer_file and explicit_state:
            raise ValueError("SOFIA_STATE_ROOT conflicts with signed home pointer")
        if pointer_file:
            if (
                mode != "production" or not pointer_key
                or not writer_host_id or not epoch_floor
            ):
                raise ValueError(
                    "signed state-home pointer requires production mode, key, "
                    "writer host and a trusted minimum epoch"
                )
            try:
                required_epoch = int(epoch_floor)
            except ValueError as exc:
                raise ValueError("invalid SOFIA_MIN_WRITER_EPOCH") from exc
            from sofia.config.state_home_pointer import read_verified_state_home
            approved = read_verified_state_home(
                pointer_path=Path(pointer_file), key_path=Path(pointer_key),
                expected_writer_host_id=writer_host_id,
                minimum_writer_epoch=required_epoch,
            )
            state_root = approved.root
        elif pointer_key or epoch_floor:
            raise ValueError("state-home key or epoch floor requires a signed pointer")
        elif explicit_state:
            state_root = Path(explicit_state)
        elif mode == "production":
            if os.name == "nt":
                program_data = os.environ.get(
                    "PROGRAMDATA",
                    r"C:\ProgramData",
                )
                state_root = Path(program_data) / "SofiaAdaLyra"
            else:
                state_root = Path("/var/lib/sofia-ada-lyra")
        else:
            state_root = repository_root / "state"

        explicit_protected = os.environ.get(
            "SOFIA_PROTECTED_ROOT",
            "",
        ).strip()
        protected_root = (
            Path(explicit_protected)
            if explicit_protected
            else state_root / "protected"
        )

        bootstrap_raw = os.environ.get(
            "SOFIA_IDENTITY_BOOTSTRAP_MODE",
            "",
        ).strip().lower()
        if bootstrap_raw:
            try:
                bootstrap_mode = IdentityBootstrapMode(bootstrap_raw)
            except ValueError as exc:
                raise ValueError(
                    "SOFIA_IDENTITY_BOOTSTRAP_MODE must be "
                    "first_bootstrap or require_existing"
                ) from exc
        else:
            bootstrap_mode = (
                IdentityBootstrapMode.REQUIRE_EXISTING
                if mode == "production"
                else IdentityBootstrapMode.FIRST_BOOTSTRAP
            )

        source_root = repository_root / "src" / "sofia"
        return cls(
            mode=mode,
            source_root=source_root,
            state_root=state_root,
            protected_root=protected_root,
            state_path=state_root / "sofia.db",
            constitution_path=protected_root / "constitution.md",
            constitution_hash_path=protected_root / "constitution.sha256",
            identity_path=protected_root / "identity.json",
            personality_path=state_root / "personality.json",
            avatar_path=state_root / "avatar.json",
            identity_bootstrap_mode=bootstrap_mode,
        )

    def provision_from_source(self) -> None:
        """
        Seed missing runtime authority/state from immutable source material.

        Existing runtime files are never overwritten here. Production startup
        therefore cannot silently replace an established identity, Constitution,
        personality, or avatar with a newer release's seed copy.
        """
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.protected_root.mkdir(parents=True, exist_ok=True)

        seeds = (
            (
                self.source_root / "constitution" / "constitution.md",
                self.constitution_path,
                True,
            ),
            (
                self.source_root / "constitution" / "constitution.sha256",
                self.constitution_hash_path,
                True,
            ),
            (
                self.source_root / "identity" / "identity.json",
                self.identity_path,
                True,
            ),
            (
                self.source_root / "personality" / "personality.json",
                self.personality_path,
                False,
            ),
            (
                self.source_root / "embodiment" / "avatar.json",
                self.avatar_path,
                False,
            ),
        )
        for source, target, protected in seeds:
            self._seed_file(
                source,
                target,
                protected=protected,
            )

    @staticmethod
    def _seed_file(
        source: Path,
        target: Path,
        *,
        protected: bool,
    ) -> None:
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_file():
                raise RuntimeError(
                    f"runtime path exists but is not a regular file: {target}"
                )
            return
        if not source.is_file():
            raise FileNotFoundError(
                f"runtime seed source does not exist: {source}"
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )
        os.close(fd)
        temporary = Path(temp_name)
        try:
            shutil.copyfile(source, temporary)
            if os.name != "nt":
                temporary.chmod(0o600 if protected else 0o640)
            # Publish only a fully copied, flushed file. os.replace() used
            # here would destroy an identity written by a competing startup
            # between the initial existence check and this point.
            with temporary.open("rb") as persisted:
                os.fsync(persisted.fileno())
            try:
                # Same-directory hard link atomically creates only if absent.
                # Unsupported filesystems fail closed rather than exposing a
                # partially copied identity or overwriting an existing one.
                os.link(temporary, target)
            except FileExistsError:
                if target.is_symlink() or not target.is_file():
                    raise RuntimeError(
                        f"runtime path raced with an unsafe file: {target}"
                    )
                # The competing writer won; never overwrite or use the
                # staging copy as the new authority.
                return
        finally:
            temporary.unlink(missing_ok=True)

        if protected and os.name != "nt":
            try:
                target.parent.chmod(0o700)
            except OSError:
                pass
