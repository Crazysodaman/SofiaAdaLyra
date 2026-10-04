from sofia.distributed.authorization import remote_operation_is_read_only
from sofia.safe.permissions import PermissionLevel, capability_permission_policy


def test_remote_release_current_is_level_one_read():
    assert remote_operation_is_read_only("release.inspect", "current") is True
    assert (
        capability_permission_policy("remote.release.current").level
        is PermissionLevel.OBSERVE_READ
    )


def test_release_rollout_and_host_mutations_are_protected():
    for capability in (
        "release.rollout.execute",
        "remote.release.stage",
        "remote.release.activate",
        "remote.release.rollback",
    ):
        assert (
            capability_permission_policy(capability).level
            is PermissionLevel.PROTECTED
        )
