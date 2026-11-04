"""Concurrency pins for in-memory Platform registries.

Module activation and RUN-style dispatch can address the capability
system and adapter factory register concurrently from independent
threads. These regests pin that no mutation/iteration interleaving is
observable, without changing any authorization or ownership semantics.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest

from sofia.platform.capability.model import Capability
from sofia.platform.capability.system import CapabilitySystem
from sofia.platform.modules.adapters import (
    AdapterFactoryContract,
    AdapterFactoryRegistry,
    OperationProfileKind,
    ReviewedAdapterFactory,
)
from sofia.platform.modules.compatibility import ModulePlatformTarget


THREADS = 8
ROUNDS = 40


import hashlib


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def test_capability_system_concurrent_registration_and_runtime_reads(tmp_path=None):
    system = CapabilitySystem(authorization_checker=lambda _request: True)

    errors = []

    def register_worker(index, *_):
        try:
            for round_index in range(ROUNDS):
                name = f"worker:{index}.{round_index}"
                system.register(
                    Capability(name, "Concurrency registration pin."),
                    lambda _request, label=name: {"origin": label},
                )
        except Exception as exc:  # pragma: no cover - surfaced via assertion
            errors.append(exc)

    def read_worker(_index, *_):
        try:
            for _ in range(ROUNDS * THREADS * 2):
                system.capabilities()
                system.resolve("worker:0.0")
        except Exception as exc:  # pragma: no cover - surfaced via assertion
            errors.append(exc)

    jobs = []
    with ThreadPoolExecutor(max_workers=THREADS * 2) as pool:
        for index in range(THREADS):
            jobs.append(pool.submit(register_worker, index))
            jobs.append(pool.submit(read_worker, index))
        for job in jobs:
            job.result()

    assert errors == []
    capability_names = system.capability_names()
    assert len(capability_names) == THREADS * ROUNDS
    assert list(capability_names) == sorted(capability_names)
    for index in range(THREADS):
        capability = system.resolve(f"worker:{index}.0")
        assert capability.name == f"worker:{index}.0"


class _ContractPinFactory(ReviewedAdapterFactory):
    """Minimal reviewed adapter factory used only to drive registry pins."""

    def __init__(self, *, module_id, package_digest, factory_id) -> None:
        self._contract = AdapterFactoryContract(
            factory_id, module_id,
            frozenset({package_digest, _digest(package_digest)}), frozenset({"pin.component"}),
            ("sofia.module.adapter.v1",),
            frozenset({OperationProfileKind.OBSERVE}),
            frozenset({"module.activate"}), "subprocess-restricted",
            (("cpu_millis", 100), ("ram_mib", 128)),
            frozenset({"host:pin"}), frozenset(), True, True, False,
        )

    @property
    def contract(self):
        return self._contract

    @property
    def platform_target(self):
        return ModulePlatformTarget(
            "linux-x86_64", "1.0.0", (),
            (("cpu_millis", 100), ("ram_mib", 128)),
            ("subprocess-restricted",),
        )

    def reconstruct_for_inspection(
        self, *, package, profile, component_id, host_identity,
    ):
        raise AssertionError("pins must not construct adapters")


def test_adapter_factory_registry_concurrent_register_and_resolve(tmp_path=None):
    registry = AdapterFactoryRegistry()

    errors = []

    def register_worker(index, *_):
        try:
            for round_index in range(ROUNDS):
                factory = _ContractPinFactory(
                    module_id=f"pin:{index}.{round_index}",
                    package_digest=_digest(f"pin:{index}.{round_index}"),
                    factory_id=f"factory:{index}.{round_index}",
                )
                registry.register(factory)
                registry.register(factory)  # same-instance is idempotent
        except Exception as exc:  # pragma: no cover - surfaced via assertion
            errors.append(exc)

    def resolve_stable_worker(_index, *_):
        try:
            for _ in range(ROUNDS * 4):
                registry.contracts()
        except LookupError:
            pass  # registry is legitimately empty before any registration
        except Exception as exc:  # pragma: no cover - surfaced via assertion
            errors.append(exc)

    jobs = []
    with ThreadPoolExecutor(max_workers=THREADS * 2) as pool:
        for index in range(THREADS):
            jobs.append(pool.submit(register_worker, index))
            jobs.append(pool.submit(resolve_stable_worker, index))
        for job in jobs:
            job.result()

    assert errors == []
    contracts = registry.contracts()
    assert len(contracts) == THREADS * ROUNDS
    resolved = registry.resolve(
        module_id=f"pin:{THREADS - 1}.{ROUNDS - 1}",
        package_digest=_digest(f"pin:{THREADS - 1}.{ROUNDS - 1}"),
        profile=OperationProfileKind.OBSERVE,
        component_id="pin.component",
        host_identity="host:pin",
    )
    assert resolved.contract.factory_id == (
        f"factory:{THREADS - 1}.{ROUNDS - 1}"
    )

    ambiguous_digest = _digest("pin:ambiguous")
    registry.register(
        _ContractPinFactory(
            module_id="pin:ambiguous",
            package_digest=ambiguous_digest,
            factory_id="factory:ambiguous.a",
        )
    )
    registry.register(
        _ContractPinFactory(
            module_id="pin:ambiguous",
            package_digest=ambiguous_digest,
            factory_id="factory:ambiguous.b",
        )
    )
    with pytest.raises(RuntimeError, match="ambiguous"):
        registry.resolve(
            module_id="pin:ambiguous",
            package_digest=ambiguous_digest,
            profile=OperationProfileKind.OBSERVE,
            component_id="pin.component",
            host_identity="host:pin",
        )
