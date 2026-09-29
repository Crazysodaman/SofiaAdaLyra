from sofia.ops import (
    AgentPackage,
    BootstrapCandidate,
    BootstrapDisposition,
    FleetBootstrapExecutor,
    FleetBootstrapPlanner,
    InstallAuthority,
    InstallReceipt,
)


PACKAGE = AgentPackage(
    "sofia-fleet-agent",
    "1.2.3",
    "a" * 64,
    "signed-project-release",
)


def candidate(**overrides):
    values = {
        "host_id": "terra",
        "platform": "linux",
        "architecture": "x86_64",
        "discovery_source": "approved-lan",
        "inside_approved_scope": True,
        "trusted_bootstrap_available": True,
        "installed_agent_version": None,
    }
    values.update(overrides)
    return BootstrapCandidate(**values)


def test_matching_agent_is_ready_without_reinstall():
    plan = FleetBootstrapPlanner().plan(
        candidate(
            installed_agent_version=PACKAGE.version,
            installed_agent_sha256=PACKAGE.sha256,
            installed_protocol_version=PACKAGE.protocol_version,
        ),
        PACKAGE,
        authority=InstallAuthority.NONE,
    )
    assert plan.disposition is BootstrapDisposition.READY_FOR_ENROLLMENT


def test_standing_policy_allows_typed_auto_install_only_with_trusted_bootstrap():
    plan = FleetBootstrapPlanner().plan(
        candidate(),
        PACKAGE,
        authority=InstallAuthority.STANDING_POLICY,
    )
    assert plan.disposition is BootstrapDisposition.AUTO_INSTALL


def test_missing_bootstrap_authority_asks_sparks_instead_of_guessing_credentials():
    plan = FleetBootstrapPlanner().plan(
        candidate(trusted_bootstrap_available=False),
        PACKAGE,
        authority=InstallAuthority.NONE,
    )
    assert plan.disposition is BootstrapDisposition.ASK_OPERATOR
    assert "Install/authorize" in plan.operator_message
    assert "terra" in plan.operator_message


def test_out_of_scope_candidate_is_rejected():
    plan = FleetBootstrapPlanner().plan(
        candidate(inside_approved_scope=False),
        PACKAGE,
        authority=InstallAuthority.STANDING_POLICY,
    )
    assert plan.disposition is BootstrapDisposition.REJECTED


def test_executor_verifies_exact_installed_package():
    plan = FleetBootstrapPlanner().plan(
        candidate(),
        PACKAGE,
        authority=InstallAuthority.OPERATOR_APPROVED,
    )

    class Installer:
        def install(self, host, package):
            return InstallReceipt(
                host.host_id,
                package.package_id,
                package.version,
                package.sha256,
                True,
            )

    receipt = FleetBootstrapExecutor().execute(plan, Installer())
    assert receipt.verified is True


def test_executor_rejects_unverified_or_wrong_install_receipt():
    plan = FleetBootstrapPlanner().plan(
        candidate(),
        PACKAGE,
        authority=InstallAuthority.STANDING_POLICY,
    )

    class BadInstaller:
        def install(self, host, package):
            return InstallReceipt(
                host.host_id,
                package.package_id,
                "different",
                package.sha256,
                True,
            )

    import pytest

    with pytest.raises(RuntimeError, match="did not verify"):
        FleetBootstrapExecutor().execute(plan, BadInstaller())


def test_compatible_present_agent_is_ready_without_package_hash_evidence():
    plan = FleetBootstrapPlanner().plan(
        candidate(
            installed_protocol_version=PACKAGE.protocol_version,
            agent_present=True,
        ),
        PACKAGE,
        authority=InstallAuthority.NONE,
    )

    assert plan.disposition is BootstrapDisposition.READY_FOR_ENROLLMENT
    assert "already present" in plan.reason
