from pathlib import Path

from sofia.composition.root import compose
from sofia.config.model import ProviderConfiguration,SofiaConfiguration


def configuration(tmp_path:Path)->SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=tmp_path/"constitution.md",
        constitution_hash_path=tmp_path/"constitution.sha256",
        identity_path=tmp_path/"identity.json",
        personality_path=tmp_path/"personality.json",
        avatar_path=tmp_path/"avatar.json",
        state_path=tmp_path/"sofia.db",
        provider=ProviderConfiguration(provider="test",model="test-model"),
        filesystem_root=tmp_path,
    )


def test_composition_registers_core_readonly_tools(tmp_path:Path):
    runtime=compose(configuration(tmp_path))
    for name in (
        "process.inspect",
        "system.inspect",
        "network.inspect",
        "service.inspect",
        "machine.inspect",
        "knowledge.source.read",
        "knowledge.search",
    ):
        assert runtime.capability_system.resolve(name).name==name


def test_runtime_default_authority_exposes_only_local_readonly_tools(tmp_path:Path):
    runtime=compose(configuration(tmp_path))
    authority=runtime._operation_authority()
    assert {
        "process.inspect",
        "system.inspect",
        "network.inspect",
        "service.inspect",
        "machine.inspect",
    }.issubset(set(authority.allowed_capabilities))
    assert "knowledge.source.read" not in authority.allowed_capabilities
    assert "knowledge.search" not in authority.allowed_capabilities
    assert not authority.can_inspect_filesystem
