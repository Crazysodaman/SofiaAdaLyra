"""Test-only opt-in seam for genuine CORE-002 / CORE-003 application probes.

No production composition or runtime configuration change is allowed here.
Consumers MUST provide a disposable canonical state directory as a proof
of isolation. This fixture does not authenticate the host or create a writer.
"""
from pathlib import Path

from sofia.core.memory.eligibility_v1 import (
    ReviewedMemoryEligibilityV1, install_disposable_policy_v1,
)
from sofia.platform.application.bootstrap import SofiaApplication
from sofia.core.social.model import PrincipalContext


def attach_disposable_memory_policy_v1(
    application: SofiaApplication, *, disposable_root: Path,
    approved_by: PrincipalContext,
    expected_version: int | None = None,
) -> ReviewedMemoryEligibilityV1:
    """Bind V1 to the exact existing runtime MemorySystem before app.start().

    Team 2 should call this between SofiaApplication construction and start:
        app = SofiaApplication(disposable_config)
        attach_disposable_memory_policy_v1(
            app, disposable_root=tmp_path, approved_by=owner,
        )
        app.start()
    The existing provider and conversation pipeline are not replaced.
    """
    if not isinstance(application, SofiaApplication):
        raise TypeError("a real SofiaApplication is required")
    root = Path(disposable_root).resolve(strict=True)
    state = Path(application._configuration.state_path).resolve(strict=True)
    if state == root or root not in state.parents:
        raise PermissionError("V1 fixture must point inside explicit disposable root")
    runtime = application._runtime
    if getattr(runtime.state, "value", None) != "created":
        raise RuntimeError("test V1 must be attached before application startup")
    memory_system = runtime.memory_system
    if getattr(memory_system, "_eligibility_policy", None) is not None:
        raise RuntimeError("memory system already has an eligibility policy")
    install_disposable_policy_v1(
        state, approved_by=approved_by, expected_version=expected_version,
    )
    policy = ReviewedMemoryEligibilityV1(state)
    policy.assert_same_canonical_state(memory_system.candidate_store.database_path)
    memory_system._eligibility_policy = policy
    return policy


def create_disposable_core_application(disposable_root: Path) -> SofiaApplication:
    """Create a fully isolated synthetic Core home, never a repo identity writer.

    Constitution/hash/avatar fixtures are copied read-only from repository
    examples on FIRST disposable use. Identity is minted only under tmp_path;
    all subsequent application composition requires the same existing UUID.
    """
    from dataclasses import replace
    from shutil import copyfile
    from sofia.core.identity.model import IdentityBootstrapMode
    from sofia.core.identity.store import IdentityStore
    from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
    from test.test_application_restart_continuity import (
        CONSTITUTION_PATH, HASH_PATH, AVATAR_PATH,
        create_configuration, create_personality,
    )

    root = Path(disposable_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("disposable_root must be an existing directory")
    copies = (
        (CONSTITUTION_PATH, root / "constitution.md"),
        (HASH_PATH, root / "constitution.sha256"),
        (AVATAR_PATH, root / "avatar.json"),
    )
    for source, destination in copies:
        if not destination.exists():
            copyfile(source, destination)
    identity_path = root / "identity.json"
    if not identity_path.exists():
        IdentityStore(identity_path).load()  # new disposable UUID only
    personality_path = root / "personality.json"
    if not personality_path.exists():
        create_personality(root)
    state_path = bootstrap_canonical_sqlite(root / "sofia.db")
    original = create_configuration(personality_path, state_path)
    config = replace(
        original,
        constitution_path=root / "constitution.md",
        constitution_hash_path=root / "constitution.sha256",
        identity_path=identity_path,
        avatar_path=root / "avatar.json",
        identity_bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
        filesystem_root=root,
    )
    return SofiaApplication(config)
