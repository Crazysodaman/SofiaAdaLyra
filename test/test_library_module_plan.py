"""D028-02 selective signed module closure, no installer or trust authority.

Fixtures use fresh throwaway Ed25519 signers and the existing module verifier.
These are source conformance tests, NOT LIB-06 installed-host acceptance.
"""
from dataclasses import replace

import pytest

from sofia.platform.modules import DependencyRequirement, OperationProfileKind
from sofia.platform.modules.library_plan import (
    ModuleLibraryPreviewRejected, plan_module_library_preview,
)
from test.test_module_compatibility_v1 import target
from test.test_module_lifecycle_v1 import verified_custom


def package(tmp_path, label, *, module_id=None, version="9.0.0", dependencies=()):
    return verified_custom(
        tmp_path, directory=label,
        module_id=module_id or ("org.sofia." + label),
        version=version, dependencies=dependencies,
        capabilities=("research.search",),
        content="MODULE = '" + label + "'\n",
    )


def preview(selected, candidates, *, installed=(), target_host=None):
    return plan_module_library_preview(
        selected=tuple((item.manifest.module_id, item.package_digest) for item in selected),
        candidates=tuple(candidates), installed=tuple(installed),
        target=target_host or target(),
    )


def test_select_only_one_signed_module_without_fetching_unselected(tmp_path):
    first = package(tmp_path, "alpha")
    unrelated = package(tmp_path, "third")
    before = {str(p): p.stat().st_size for p in tmp_path.rglob("*") if p.is_file()}
    plan = preview((first,), (first, unrelated))
    after = {str(p): p.stat().st_size for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
    assert [item.module_id for item in plan.items] == ["org.sofia.alpha"]
    assert plan.items[0].stage_required is True
    assert plan.items[0].package_digest == first.package_digest
    assert plan.items[0].peer_distribution_approved is False
    assert plan.executable is False
    assert plan.requires_independent_publisher_reverification
    assert plan.requires_separate_host_install_approval
    assert plan.requires_separate_activation_approval


def test_dependency_first_group_and_missing_third_module(tmp_path):
    a = package(tmp_path, "alpha")
    b = package(
        tmp_path, "beta",
        dependencies=(DependencyRequirement("org.sofia.alpha", "9.0.0", "10.0.0"),),
    )
    unused = package(tmp_path, "third")
    group = preview((b,), (unused, b, a))
    assert [(i.module_id, i.package_digest, i.stage_required) for i in group.items] == [
        ("org.sofia.alpha", a.package_digest, True),
        ("org.sofia.beta", b.package_digest, True),
    ]
    assert group.selected == (("org.sofia.beta", b.package_digest),)
    assert not any(i.module_id == "org.sofia.third" for i in group.items)


def test_existing_exact_dependency_not_reacquired_or_autoactivated(tmp_path):
    a = package(tmp_path, "alpha")
    b = package(
        tmp_path, "beta",
        dependencies=(DependencyRequirement("org.sofia.alpha", "9.0.0", "10.0.0"),),
    )
    result = preview((b,), (b,), installed=(a,))
    assert result.items[0].existing_same_digest is True
    assert result.items[0].stage_required is False
    assert result.items[1].stage_required is True
    assert result.executable is False


def test_installed_mismatch_requires_explicit_signed_replacement(tmp_path):
    old = package(tmp_path, "old", module_id="org.sofia.alpha")
    new = package(tmp_path, "new", module_id="org.sofia.alpha", version="9.1.0")
    b = package(
        tmp_path, "beta",
        dependencies=(DependencyRequirement("org.sofia.alpha", "9.1.0", "10.0.0"),),
    )
    with pytest.raises(ModuleLibraryPreviewRejected, match="explicitly selected update"):
        preview((b,), (new, b), installed=(old,))
    plan = preview((new, b), (new, b), installed=(old,))
    assert plan.items[0].replaces_existing_version is True
    assert plan.items[0].stage_required is True
    assert plan.items[1].stage_required is True
    assert plan.executable is False


def test_ambiguous_dependency_versions_require_pinned_explicit_selection(tmp_path):
    a = package(tmp_path, "alpha", version="9.0.0")
    a2 = package(tmp_path, "alpha2", module_id="org.sofia.alpha", version="9.1.0")
    b = package(
        tmp_path, "beta",
        dependencies=(DependencyRequirement("org.sofia.alpha", "9.0.0", "10.0.0"),),
    )
    with pytest.raises(ModuleLibraryPreviewRejected, match="ambiguous dependency"):
        preview((b,), (a, a2, b))
    chosen = preview((a2, b), (a, a2, b))
    assert chosen.items[0].package_digest == a2.package_digest


def test_missing_dependency_is_not_silent_network_fallback(tmp_path):
    b = package(
        tmp_path, "beta",
        dependencies=(DependencyRequirement("org.sofia.alpha", "9.0.0", "10.0.0"),),
    )
    with pytest.raises(ModuleLibraryPreviewRejected, match="missing signed dependency"):
        preview((b,), (b,))


def test_signed_dependency_cycle_is_denied(tmp_path):
    a = package(
        tmp_path, "alpha",
        dependencies=(DependencyRequirement("org.sofia.beta", "9.0.0", "10.0.0"),),
    )
    b = package(
        tmp_path, "beta",
        dependencies=(DependencyRequirement("org.sofia.alpha", "9.0.0", "10.0.0"),),
    )
    with pytest.raises(ModuleLibraryPreviewRejected, match="cycle"):
        preview((b,), (a, b))


def test_conflicting_selected_dependency_range_cannot_install_silently(tmp_path):
    a = package(tmp_path, "alpha", version="9.0.0")
    b = package(
        tmp_path, "beta",
        dependencies=(DependencyRequirement("org.sofia.alpha", "9.0.0", "9.1.0"),),
    )
    c = package(
        tmp_path, "charlie",
        dependencies=(DependencyRequirement("org.sofia.alpha", "9.1.0", "10.0.0"),),
    )
    with pytest.raises(ModuleLibraryPreviewRejected, match="conflicting dependency ranges"):
        preview((b, c), (a, b, c))


def test_wrong_host_or_isolation_is_incompatible_even_with_valid_signature(tmp_path):
    a = package(tmp_path, "alpha")
    with pytest.raises(ModuleLibraryPreviewRejected, match="target OS/architecture"):
        preview((a,), (a,), target_host=target(os_arch="darwin-arm64"))
    with pytest.raises(ModuleLibraryPreviewRejected, match="required isolation profile"):
        preview((a,), (a,), target_host=target(allowed_isolation_profiles=()))


def test_wrong_digest_forged_projection_and_unlisted_selected_are_denied(tmp_path):
    a = package(tmp_path, "alpha")
    forged = replace(a, package_digest="f" * 64)
    with pytest.raises(ModuleLibraryPreviewRejected, match="identity digest"):
        preview((forged,), (forged,))
    with pytest.raises(ModuleLibraryPreviewRejected, match="exact module digest"):
        plan_module_library_preview(
            selected=(("org.sofia.alpha", "a" * 64),), candidates=(a,),
            installed=(), target=target(),
        )
    with pytest.raises(ModuleLibraryPreviewRejected, match="duplicate indexed"):
        preview((a,), (a, a))


@pytest.mark.parametrize("bad", [
    (), (("org.sofia.alpha", "A" * 64),),
    (("org.sofia.alpha", "a" * 64), ("org.sofia.alpha", "b" * 64)),
    (("org.sofia.alpha", "x" * 64),),
    (("org.sofia.alpha", "a" * 64), ("org.sofia.alpha", "a" * 64)),
])
def test_bad_or_missing_exact_selection_is_refused(tmp_path, bad):
    a = package(tmp_path, "alpha")
    with pytest.raises(ModuleLibraryPreviewRejected):
        plan_module_library_preview(
            selected=bad, candidates=(a,), installed=(), target=target(),
        )


def test_same_signed_package_does_not_assert_a_new_install(tmp_path):
    a = package(tmp_path, "alpha")
    p = preview((a,), (a,), installed=(a,))
    assert len(p.items) == 1
    assert p.items[0].existing_same_digest
    assert not p.items[0].replaces_existing_version
    assert not p.items[0].stage_required
    assert not p.executable
