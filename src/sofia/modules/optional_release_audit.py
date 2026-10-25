"""Read-only source preflight for Sofía's 47 optional module candidates.

This does not import or execute module code. No source string or generated report
can grant module authority, sign a package, claim host health, or set BETA.
Only the canonical Platform's verified package/lifecycle/evidence owners can.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Mapping

# Reviewed design inventory, from docs/sofia2/MODULE_OWNERSHIP_MATRIX.md.
# This excludes companion releases, two adapters and the attached interaction submodule.
EXPECTED_OPTIONAL_IDS = frozenset('''
MOD-DEV MOD-RESEARCH MOD-CREATIVE MOD-VISION MOD-DESKTOP-ACT MOD-HOMELAB
MOD-ROBOTICS-GAIA MOD-TRAINS MOD-GAMES MOD-PRODUCTIVITY MOD-ML
MOD-GENERALIZATION MOD-VWORLD MOD-MENTOR MOD-BROWSER MOD-MEDIA
MOD-DOCUMENTS MOD-COMMUNICATIONS MOD-SMART-HOME MOD-CAD MOD-SENSORS
MOD-REMOTE-ACCESS MOD-IT-HELPDESK MOD-IT-NETWORK MOD-IT-SYSTEMS
MOD-IT-CONTAINERS MOD-IT-STORAGE MOD-IT-DATABASE MOD-IT-BACKUP-DR
MOD-IT-SECURITY MOD-IT-OBSERVABILITY MOD-IT-DEVOPS MOD-ENGINEERING
MOD-ELECTRONICS MOD-3D-PRINT MOD-ENERGY MOD-AVATAR3D MOD-AVATAR-STUDIO
MOD-WORKSHOP MOD-DIGITAL-TWIN MOD-KNOWLEDGE-LIBRARY MOD-PROJECT-FORGE
MOD-FILE-WATCH MOD-HOUSEHOLD MOD-FINANCE MOD-DATA-ANALYTICS MOD-CALENDAR
'''.split())
assert len(EXPECTED_OPTIONAL_IDS) == 47
_CAP = re.compile(r'^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$')
_SEMVER = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
_PACK_ID = re.compile(r'^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$')
_PROFILES = frozenset({'OBSERVE', 'ADVISORY', 'SIMULATE', 'EXECUTE_SCOPED', 'SUPERVISED'})
# Flag direct-effect boundaries for human review. A static import check cannot
# prove that a module is sandboxed, non-executing, or free of indirect effects.
_EFFECT_MODULES = frozenset({'subprocess', 'socket', 'sqlite3', 'requests', 'http',
                            'os', 'shutil', 'ctypes', 'winreg'})


@dataclass(frozen=True)
class CandidateFinding:
    module_id: str
    package_id_proposal: str
    capability_id: str | None
    profile: str | None
    version: str | None
    source_path: str | None
    source_sha256: str | None
    source_scope: str
    resources: tuple[tuple[str, int], ...]
    source_issues: tuple[str, ...]
    beta_gate: str = 'NOT_VERIFIED'

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result['resources'] = dict(self.resources)
        result['source_issues'] = list(self.source_issues)
        return result


def package_id_proposal(catalog_id: str) -> str:
    if catalog_id not in EXPECTED_OPTIONAL_IDS:
        raise ValueError('module is not an approved optional catalog identity')
    candidate = 'mod.' + catalog_id.removeprefix('MOD-').lower().replace('-', '.')
    if not _PACK_ID.fullmatch(candidate):
        raise ValueError('catalog identity cannot produce valid Platform package ID')
    # This is only a *proposal*; authoritative package IDs require owner review.
    return candidate


def _static_metadata(file: Path) -> tuple[dict[str, object], ast.Module]:
    content = file.read_text(encoding='utf-8')
    module = ast.parse(content, filename=file.as_posix())
    values: dict[str, object] = {}
    for node in module.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        try:
            values[node.targets[0].id] = ast.literal_eval(node.value)
        except (ValueError, TypeError, RecursionError, MemoryError):
            # Dynamic values are never executed. Missing metadata stays missing.
            continue
    return values, module


def _resources(value: object) -> tuple[tuple[str, int], ...] | None:
    if isinstance(value, dict):
        pairs = tuple(value.items())
    elif type(value) in (tuple, list):
        pairs = tuple(value)
    else:
        return None
    try:
        if not pairs or any(type(entry) not in (tuple, list) or len(entry) != 2 for entry in pairs):
            return None
        result = tuple((name, quantity) for name, quantity in pairs)
        if len(set(name for name, _ in result)) != len(result):
            return None
        if any(not isinstance(name, str) or not name or type(qty) is not int
               or qty < 0 or qty > 1_000_000 for name, qty in result):
            return None
        return tuple(sorted(result))
    except (TypeError, ValueError):
        return None


def _inspect_file(root: Path, source: Path, expected_id: str) -> CandidateFinding:
    meta, tree = _static_metadata(source)
    errors: list[str] = []
    module_id = meta.get('MODULE_ID')
    if module_id != expected_id:
        errors.append('module_identity_mismatch')
    version = meta.get('MODULE_VERSION')
    if not isinstance(version, str) or not _SEMVER.fullmatch(version):
        errors.append('invalid_or_missing_semver')
        version = None
    capability = meta.get('CAPABILITY_ID')
    if not isinstance(capability, str) or not _CAP.fullmatch(capability):
        errors.append('invalid_or_missing_capability')
        capability = None
    profile = meta.get('PROFILE', meta.get('OPERATION_PROFILE'))
    if not isinstance(profile, str) or profile not in _PROFILES:
        errors.append('invalid_or_missing_profile')
        profile = None
    resources = _resources(meta.get('RESOURCES', meta.get('RESOURCE_REQUIREMENTS')))
    if resources is None:
        errors.append('invalid_or_missing_resources')
        resources = ()
    functions = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if 'capability_registrations' not in functions:
        errors.append('missing_capability_registrations')
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split('.')[0])
            # Parsing a URL is not a network operation; urllib.request is.
            if node.module.startswith(('urllib.request', 'urllib3')):
                imports.add('network_urllib')
        if isinstance(node, ast.Import):
            if any(a.name.startswith(('urllib.request', 'urllib3')) for a in node.names):
                imports.add('network_urllib')
    for module_name in sorted((_EFFECT_MODULES | {'network_urllib'}) & imports):
        errors.append('direct_effect_dependency_requires_review:' + module_name)
    relative = source.relative_to(root).as_posix()
    return CandidateFinding(
        expected_id, package_id_proposal(expected_id), capability, profile, version,
        relative, sha256(source.read_bytes()).hexdigest(), 'locally_parsed_ast',
        resources, tuple(sorted(errors)),
    )


def audit_optional_source_tree(root: Path, *, remote_observations: Mapping[str, Mapping[str, object]] | None = None) -> dict[str, object]:
    """Inspect a checkout without importing modules or touching Platform state.

    `remote_observations` only fills an unavailable *source visibility* slot. It
    cannot certify code, package signatures, adapter factories, or BETA. Callers
    must authenticate provenance separately; this argument never grants trust.
    """
    root = Path(root).resolve()
    candidates: dict[str, CandidateFinding] = {}
    duplicate: set[str] = set()
    base = root / 'src' / 'sofia' / 'modules'
    for source in sorted(base.glob('*/*.py')):
        try:
            meta, _ = _static_metadata(source)
        except (OSError, ValueError, SyntaxError, UnicodeError) as exc:
            # Fail closed for module source that cannot be parsed.
            if source.name in {'analysis.py', 'correlation.py', 'readings.py', 'kinematics.py', 'diagnostics.py', 'triage.py', 'projection_review.py'}:
                duplicate.add('unparseable:' + source.relative_to(root).as_posix())
            continue
        module_id = meta.get('MODULE_ID')
        if module_id in EXPECTED_OPTIONAL_IDS:
            if module_id in candidates:
                duplicate.add(module_id)
            else:
                candidates[module_id] = _inspect_file(root, source, module_id)
    for module_id in EXPECTED_OPTIONAL_IDS - candidates.keys():
        observation = (remote_observations or {}).get(module_id)
        if observation is not None and observation.get('catalog_id') == module_id:
            # Remote assertions stay unverified by this offline AST audit.
            candidates[module_id] = CandidateFinding(
                module_id, package_id_proposal(module_id), None, None, None,
                str(observation.get('source_path') or '') or None,
                None, 'remote_source_report_not_locally_parsed', (),
                ('local_source_unavailable',),
            )
        else:
            candidates[module_id] = CandidateFinding(
                module_id, package_id_proposal(module_id), None, None, None,
                None, None, 'not_observed', (), ('source_not_observed',),
            )
    values = tuple(candidates[key] for key in sorted(candidates))
    # Catalog names are not valid signed manifest module IDs without a reviewed
    # alias mapping. No unsigned source inventory can assert lifecycle/BETA.
    duplicate_caps = sorted(name for name in {f.capability_id for f in values if f.capability_id}
                            if sum(x.capability_id == name for x in values) > 1)
    issues = tuple(sorted(duplicate | {'capability_collision:' + cap for cap in duplicate_caps}))
    return {
        'schema': 'sofia.optional.beta_source_preflight.v1',
        'claim': 'source-only; never Platform readiness evidence',
        'expected_optional_modules': len(EXPECTED_OPTIONAL_IDS),
        'source_locally_parsed': sum(f.source_scope == 'locally_parsed_ast' for f in values),
        'source_reported_remotely': sum(f.source_scope == 'remote_source_report_not_locally_parsed' for f in values),
        'source_unobserved': sum(f.source_scope == 'not_observed' for f in values),
        'source_issues': sum(bool(f.source_issues) for f in values),
        'beta_verified': 0,
        'beta_gates_missing_evidence': [
            'owner_reviewed_package_id_mapping',
            'exact_artifact_digests_and_approved_ed25519_signature',
            'trusted_package_verification_and_manifest_parsing',
            'reviewed_adapter_factory_matching_signed_digest',
            'signed_maintenance_and_operation_profiles',
            'authoritative_Platform_compatibility_and_resource_admission',
            'Platform_lifecycle_staged_or_installed_record',
            'RUN_SAFE_principal_target_and_approval_checks',
            'isolation_and_restart_fault_testing',
            'full_repository_CI_and_host_integration_evidence',
        ],
        'cross_module_issues': list(issues),
        'candidates': [item.to_dict() for item in values],
    }
