from sofia.platform.modules import (
    DependencyRequirement,
    ModulePlatformTarget,
    OperationProfileKind,
    evaluate_module_compatibility,
)
from test.test_module_package_v1 import manifest


def target(**changes):
    values = dict(
        os_arch="linux-x86_64", platform_api_version="1.5.0",
        available_devices=(),
        resource_capacity=(("cpu_millis", 200), ("ram_mib", 256)),
        allowed_isolation_profiles=("subprocess-restricted",),
    )
    values.update(changes)
    return ModulePlatformTarget(**values)


def test_compatible_package_admission_is_advisory_not_authority():
    value = manifest((("module.py", "0" * 64),))
    report = evaluate_module_compatibility(
        value, profile=OperationProfileKind.OBSERVE, target=target(),
    )
    assert report.compatible is True
    assert report.authoritative is False
    assert report.reasons == ()


def test_os_api_isolation_resources_and_devices_fail_closed():
    value = manifest((("module.py", "0" * 64),))
    report = evaluate_module_compatibility(
        value, profile=OperationProfileKind.OBSERVE,
        target=target(
            os_arch="darwin-arm64", platform_api_version="2.0.0",
            resource_capacity=(("ram_mib", 64),),
            allowed_isolation_profiles=("none",),
        ),
    )
    assert report.compatible is False
    assert "target OS/architecture is unsupported" in report.reasons
    assert "Platform API version is outside the signed range" in report.reasons
    assert "required isolation profile is unavailable" in report.reasons
    assert "module resource unavailable: ram_mib" in report.reasons
    assert "profile resource unavailable: cpu_millis" in report.reasons


def test_dependency_requirement_uses_dependency_declared_range():
    dependency = manifest(
        (("dep.py", "0" * 64),), module_id="org.sofia.library",
        version="1.4.0", capabilities=("library.read",),
    )
    value = manifest(
        (("module.py", "0" * 64),), dependencies=(
            DependencyRequirement("org.sofia.library", "1.0.0", "2.0.0"),
        ),
    )
    accepted = evaluate_module_compatibility(
        value, profile=OperationProfileKind.OBSERVE, target=target(),
        installed_dependencies=(dependency,),
    )
    assert accepted.compatible is True
    rejected = evaluate_module_compatibility(
        value, profile=OperationProfileKind.OBSERVE, target=target(),
        installed_dependencies=(),
    )
    assert rejected.reasons == ("dependency missing: org.sofia.library",)
