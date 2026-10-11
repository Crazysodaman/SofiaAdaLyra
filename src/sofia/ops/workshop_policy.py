"""Hephaestus lab experiment admission, no VM creation/execution.

An empty VM without guest OS cannot install itself. A separate, operator-
approved hypervisor-side controller must own guest creation and onboarding.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import re


_SHA = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class LaboratoryExperiment:
    experiment_id: str
    guest_image_sha256: str
    hypervisor_host_id: str
    guest_name: str
    max_vcpu: int
    max_memory_mb: int
    max_storage_gib: int
    max_duration_minutes: int
    network_mode: str
    operator_approval_ref: str | None = None


@dataclass(frozen=True, slots=True)
class LaboratoryAdmission:
    experiment_id: str
    review_eligible: bool
    blockers: tuple[str, ...]
    may_create_vm: bool = False


def review_lab_experiment(spec: LaboratoryExperiment) -> LaboratoryAdmission:
    if not isinstance(spec, LaboratoryExperiment):
        raise TypeError("typed lab experiment required")
    issues=[]
    if any(not isinstance(v,str) or not v.strip() for v in (
        spec.experiment_id,spec.hypervisor_host_id,spec.guest_name
    )):
        issues.append("missing experiment/host/guest identity")
    # The experimental guest must never impersonate the reserved canonical
    # production runtime VM, even under a different case or trailing spaces.
    if spec.guest_name.strip().casefold() == "sofia":
        issues.append("workshop guest cannot use reserved canonical VM name Sofia")
    if _SHA.fullmatch(spec.guest_image_sha256) is None:
        issues.append("guest installer image not pinned by sha256")
    if type(spec.max_vcpu) is not int or not 1<=spec.max_vcpu<=16:
        issues.append("vCPU budget outside research policy")
    if type(spec.max_memory_mb) is not int or not 512<=spec.max_memory_mb<=65536:
        issues.append("memory budget outside research policy")
    if type(spec.max_storage_gib) is not int or not 8<=spec.max_storage_gib<=256:
        issues.append("storage budget outside research policy")
    if type(spec.max_duration_minutes) is not int or not 1<=spec.max_duration_minutes<=1440:
        issues.append("experiment time budget outside policy")
    if spec.network_mode!="isolated":
        issues.append("workshop guest must default to isolated networking")
    if not spec.operator_approval_ref:
        issues.append("hypervisor control requires exact operator approval")
    return LaboratoryAdmission(spec.experiment_id,not issues,tuple(issues),False)
