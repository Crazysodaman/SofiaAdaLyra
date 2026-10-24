"""B07: module manifests, registry trust, compatibility, health."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import pytest

from sofia.core.codebase.model import (
    CodebaseEvidenceKind,
    CodebaseInspectionEvidence,
    PythonModule,
    PythonSymbol,
)
from sofia.core.modreg.manifest import (
    ManifestCandidate,
    ModuleManifestError,
    discover_candidates,
    parse_manifest,
)
from sofia.core.modreg.registry import (
    ModuleHealth,
    ModuleRegistryError,
    ModuleRegistryService,
    ModuleRegistryStore,
    TrustState,
)
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import local_sparks_principal
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

NOW = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)


MANIFEST = {
    "name": "sofia.notesched",
    "version": "1.2.0",
    "purpose": "Keeps the reminder list coherent and honest.",
    "boundary_notes": (
        "Observation only. Nothing here grants write authority over"
        " reminders."
    ),
    "declared_capabilities": ["notes.read", "notes.schedule"],
    "declared_dependencies": ["sofia.core.rel"],
    "authority_boundary": ("owner-session:sparks"),
}


def inspection(
    modules: tuple[PythonModule, ...] = (),
) -> CodebaseInspectionEvidence:
    return CodebaseInspectionEvidence(
        root=Path("."),
        files=(),
        python_modules=modules,
        relationships=(),
        evidence_kind=CodebaseEvidenceKind.OBSERVED,
        file_limit_reached=False,
    )


def py(name: str, *, parse_error: str | None = None) -> PythonModule:
    return PythonModule(
        path=Path(name.replace(".", "/") + ".py"),
        module_name=name,
        symbols=(PythonSymbol(name="placeholder", kind="module", line=1),),
        imports=(),
        parse_error=parse_error,
    )


def observed_noteevidence() -> CodebaseInspectionEvidence:
    return inspection(
        (py("sofia.notesched.model"), py("sofia.notesched.store"))
    )


def test_manifest_validation():
    manifest = parse_manifest(dict(MANIFEST))
    assert manifest.version_parts == (1, 2, 0)
    assert manifest.name == "sofia.notesched"
    for bad, message in (
        ({**MANIFEST, "name": "sofia.Notes"}, "sofia.* dotted"),
        ({**MANIFEST, "version": "1.2"}, "semver"),
        ({**MANIFEST, "purpose": "   "}, "nonempty"),
        (
            {**MANIFEST, "declared_dependencies": ["sofia.notesched"]},
            "cannot depend on itself",
        ),
        (
            {
                **MANIFEST,
                "declared_capabilities": ["OK", "ok"],
            },
            "dotted names",
        ),
        (
            {**MANIFEST, "surprise": 1},
            "unexpected manifest fields",
        ),
    ):
        with pytest.raises(ModuleManifestError, match=message):
            parse_manifest(bad)


def test_explicit_dependency_requirement_validation():
    manifest = parse_manifest(
        {
            **MANIFEST,
            "dependency_requirements": [
                {
                    "name": "sofia.core.rel",
                    "minimum_version": "1.5.0",
                    "maximum_version_exclusive": "2.0.0",
                }
            ],
        }
    )
    [requirement] = manifest.dependency_requirements
    assert requirement.accepts("1.5.0")
    assert requirement.accepts("1.9.9")
    assert not requirement.accepts("2.0.0")
    with pytest.raises(ModuleManifestError, match="declared dependencies"):
        parse_manifest(
            {
                **MANIFEST,
                "dependency_requirements": [
                    {
                        "name": "sofia.core.memory",
                        "minimum_version": "1.0.0",
                    }
                ],
            }
        )


def test_discovery_yields_candidates_only(tmp_path):
    root = tmp_path / "project"
    (root / "src" / "sofia" / "modules" / "notesched").mkdir(parents=True)
    (root / "src" / "sofia" / "modules" / "notesched" / "module_manifest.json").write_text(
        json.dumps(MANIFEST), encoding="utf-8",
    )
    (root / "src" / "sofia" / "modules" / "broken" / "module_manifest.json").parent.mkdir(
        parents=True
    )
    (
        root / "src" / "sofia" / "modules" / "broken" / "module_manifest.json"
    ).write_text("{ not json", encoding="utf-8")
    outside = tmp_path / "elsewhere"
    (outside / "src" / "sofia" / "sneaky").mkdir(parents=True)
    (
        outside / "src" / "sofia" / "sneaky" / "module_manifest.json"
    ).write_text(
        json.dumps({**MANIFEST, "name": "sofia.sneaky"}), encoding="utf-8",
    )
    candidates = discover_candidates(root)
    assert len(candidates) == 2
    assert all(isinstance(c, ManifestCandidate) for c in candidates)
    [good] = [c for c in candidates if c.manifest is not None]
    [broken] = [c for c in candidates if c.manifest is None]
    assert good.path.name == "module_manifest.json"
    assert good.manifest.name == "sofia.notesched"
    assert broken.parse_error is not None and "JSONDecodeError" in (
        broken.parse_error
    )
    assert not any(
        candidate.manifest is not None
        and candidate.manifest.name == "sofia.sneaky"
        for candidate in candidates
    )


def test_registry_owner_and_trust_lifecycle(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ModuleRegistryStore(tmp_path / "sofia.db")
    service = ModuleRegistryService(store)
    sparks = local_sparks_principal()
    foreign = PrincipalContext(
        "person:another", "local:text", AudienceKind.PRIVATE, "Another"
    )
    manifest = parse_manifest(dict(MANIFEST))
    with pytest.raises(PermissionError, match="authenticated owner"):
        service.record_candidate(
            foreign, manifest=manifest, source_path="x", recorded_at=NOW,
        )
    candidate = service.record_candidate(
        sparks,
        manifest=manifest,
        source_path="src/sofia/modules/notesched/module_manifest.json",
        recorded_at=NOW,
    )
    assert candidate.trust_state is TrustState.CANDIDATE
    assert "sofia.core.rel" in candidate.manifest.declared_dependencies
    insulinpection = observed_noteevidence()
    with pytest.raises(ModuleRegistryError, match="cannot verify"):
        service.verify(
            sparks,
            name="sofia.notesched",
            expected_revision=candidate.revision,
            inspection=inspection(()),
            recorded_at=NOW,
        )
    verified = service.verify(
        sparks,
        name="sofia.notesched",
        expected_revision=candidate.revision,
        inspection=insulinpection,
        recorded_at=NOW,
    )
    assert verified.trust_state is TrustState.VERIFIED
    with pytest.raises(ModuleRegistryError, match="only candidate"):
        service.verify(
            sparks,
            name="sofia.notesched",
            expected_revision=CandidateRevision(
                "sofia.notesched", store
            ),
            inspection=insulinpection,
            recorded_at=NOW,
        )
    retired = service.retire(
        sparks,
        name="sofia.notesched",
        expected_revision=verified.revision,
        recorded_at=NOW,
    )
    assert retired.trust_state is TrustState.RETIRED


def test_compatibility_and_health_projection(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = ModuleRegistryStore(tmp_path / "sofia.db")
    service = ModuleRegistryService(store)
    sparks = local_sparks_principal()
    notesched = parse_manifest(dict(MANIFEST))
    rel = parse_manifest(
        {
            **MANIFEST,
            "name": "sofia.core.rel",
            "version": "1.7.0",
            "declared_dependencies": [],
        }
    )
    future = parse_manifest(
        {
            **MANIFEST,
            "name": "sofia.notesched.next",
            "version": "2.0.0",
            "declared_dependencies": ["sofia.core.rel"],
        }
    )
    service.record_candidate(
        sparks, manifest=notesched, source_path="p/note.json",
        recorded_at=NOW,
    )
    rel_candidate = service.record_candidate(
        sparks, manifest=rel, source_path="p/rel.json", recorded_at=NOW,
    )
    entries = service.compatibility_report("sofia.notesched")
    assert dict(entries) == {"sofia.core.rel": "candidate-only"}
    service.verify(
        sparks,
        name="sofia.core.rel",
        expected_revision=rel_candidate.revision,
        inspection=inspection((py("sofia.core.rel.store"),)),
        recorded_at=NOW,
    )
    assert dict(
        service.compatibility_report("sofia.notesched")
    ) == {"sofia.core.rel": "compatible"}
    future_ok = service.record_candidate(
        sparks, manifest=future, source_path="p/rel2.json", recorded_at=NOW,
    )
    service.verify(
        sparks,
        name="sofia.notesched.next",
        expected_revision=future_ok.revision,
        inspection=inspection((py("sofia.notesched.next.model"),)),
        recorded_at=NOW,
    )
    assert dict(
        service.compatibility_report("sofia.notesched.next")
    ) == {"sofia.core.rel": "compatible"}

    ranged = parse_manifest(
        {
            **MANIFEST,
            "name": "sofia.notesched.ranged",
            "dependency_requirements": [
                {
                    "name": "sofia.core.rel",
                    "minimum_version": "2.0.0",
                    "maximum_version_exclusive": "3.0.0",
                }
            ],
        }
    )
    ranged_candidate = service.record_candidate(
        sparks, manifest=ranged, source_path="p/ranged.json",
        recorded_at=NOW,
    )
    service.verify(
        sparks,
        name="sofia.notesched.ranged",
        expected_revision=ranged_candidate.revision,
        inspection=inspection((py("sofia.notesched.ranged.model"),)),
        recorded_at=NOW,
    )
    assert dict(
        service.compatibility_report("sofia.notesched.ranged")
    ) == {
        "sofia.core.rel": (
            "incompatible-version:installed=1.7.0;required=>=2.0.0,<3.0.0"
        )
    }
    notesched_registration = store.current("sofia.notesched")
    assert notesched_registration is not None
    service.verify(
        sparks,
        name="sofia.notesched",
        expected_revision=notesched_registration.revision,
        inspection=inspection(
            (py("sofia.notesched.model"), py("sofia.notesched.store")),
        ),
        recorded_at=NOW,
    )
    degraded = inspection(
        (py("sofia.notesched.model", parse_error="SyntaxError"),),
    )
    reports = {
        r.name: r for r in service.health_projection(degraded)
    }
    assert reports["sofia.notesched"].health is ModuleHealth.DEGRADED
    absent = inspection((py("sofia.core.memory.store"),))
    reports = {
        r.name: r for r in service.health_projection(absent)
    }
    assert reports["sofia.notesched"].health is ModuleHealth.SUSPECT


def test_source_identity_uses_python_package_boundaries(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = ModuleRegistryService(ModuleRegistryStore(tmp_path / "sofia.db"))
    candidate = service.record_candidate(
        local_sparks_principal(), manifest=parse_manifest(dict(MANIFEST)),
        source_path="src/sofia/modules/notesched/module_manifest.json",
        recorded_at=NOW,
    )

    with pytest.raises(ModuleRegistryError, match="implementation not observed"):
        service.verify(
            local_sparks_principal(), name="sofia.notesched",
            expected_revision=candidate.revision,
            inspection=inspection((py("sofia.notescheduler.store"),)),
            recorded_at=NOW,
        )


def test_correlate_health_persists_cache_and_changes(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = ModuleRegistryService(ModuleRegistryStore(tmp_path / "sofia.db"))
    sparks = local_sparks_principal()
    manifest = parse_manifest(dict(MANIFEST))
    service.record_candidate(
        sparks, manifest=manifest, source_path="p/note.json", recorded_at=NOW,
    )
    service.verify(
        sparks,
        name="sofia.notesched",
        expected_revision=1,
        inspection=observed_noteevidence(),
        recorded_at=NOW,
    )
    digest = hashlib.sha256(b"first").hexdigest()
    first = service.correlate_health(
        inspection=observed_noteevidence(),
        inspection_digest=digest,
        now=NOW,
    )
    assert [
        (change.name, change.previous, change.current)
        for change in first
    ] == [
        ("sofia.notesched", ModuleHealth.UNKNOWN, ModuleHealth.OBSERVED)
    ]
    missing = service.correlate_health(
        inspection=inspection(()),
        inspection_digest=hashlib.sha256(b"second").hexdigest(),
        now=NOW,
    )
    assert [
        (change.name, change.previous, change.current)
        for change in missing
    ] == [
        ("sofia.notesched", ModuleHealth.OBSERVED, ModuleHealth.SUSPECT)
    ]
    cached = service.store.cached()
    assert cached["sofia.notesched"][0] is ModuleHealth.SUSPECT
    with pytest.raises(ValueError, match="64-hex"):
        service.correlate_health(
            inspection=observed_noteevidence(), inspection_digest="deadbeef",
        )


def test_manifest_cycle_registration_refused(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = ModuleRegistryService(ModuleRegistryStore(tmp_path / "sofia.db"))
    sparks = local_sparks_principal()
    a = parse_manifest(
        {**MANIFEST, "name": "sofia.a", "declared_dependencies": ["sofia.b"]}
    )
    b = parse_manifest(
        {**MANIFEST, "name": "sofia.b", "declared_dependencies": ["sofia.a"]}
    )
    service.record_candidate(
        sparks, manifest=a, source_path="p/a.json", recorded_at=NOW,
    )
    with pytest.raises(ModuleRegistryError, match="cycle"):
        service.record_candidate(
            sparks, manifest=b, source_path="p/b.json", recorded_at=NOW,
        )


def test_bootstrap_wires_module_registry(tmp_path):
    from sofia.platform.application import SofiaApplication
    from sofia.platform.config.model import (
        ProviderConfiguration,
        SofiaConfiguration,
    )

    project_root = Path(__file__).parent.parent
    personality = tmp_path / "personality.json"
    personality.write_text(
        """{
  "name": "Sofia Ada Lyra",
  "traits": ["rigorous"],
  "communication_style": "Clear and direct."
}""",
        encoding="utf-8",
    )
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    app = SofiaApplication(
        SofiaConfiguration(
            constitution_path=(
                project_root / "src" / "sofia" / "core" / "constitution" /
                "constitution.md"
            ),
            constitution_hash_path=(
                project_root / "src" / "sofia" / "core" / "constitution" /
                "constitution.sha256"
            ),
            identity_path=(
                project_root / "src" / "sofia" / "core" / "identity" / "identity.json"
            ),
            personality_path=personality,
            avatar_path=(
                project_root / "src" / "sofia" / "core" / "embodiment" / "avatar.json"
            ),
            state_path=tmp_path / "sofia.db",
            provider=ProviderConfiguration(provider="test", model="test"),
            filesystem_root=project_root,
        )
    )
    try:
        assert isinstance(app.module_registry, ModuleRegistryService)
        app.start()
    finally:
        app.shutdown()


def CandidateRevision(name: str, store: ModuleRegistryStore) -> int:
    registration = store.current(name)
    assert registration is not None
    return registration.revision
