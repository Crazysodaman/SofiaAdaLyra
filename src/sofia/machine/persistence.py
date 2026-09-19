import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sofia.machine.inventory import MachineInventory
from sofia.machine.model import (
    HardwareProfile,
    MachineIdentity,
    MachineProfile,
    MachineVerification,
    NetworkAdapterInfo,
    OperatingSystemInfo,
    PlatformFamily,
    StorageDeviceInfo,
    VirtualizationInfo,
)
from sofia.machine.observation import (
    MachineObservation,
    ObservationProvenance,
    ObservationSource,
    ObservationState,
)


SCHEMA_VERSION = 1


def _datetime_to_json(value: datetime) -> str:
    return value.isoformat()


def _datetime_from_json(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO-8601 string.")

    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be a valid ISO-8601 datetime."
        ) from exc


def _required_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object.")
    return value


def _optional_string(
    value: Any,
    field_name: str,
) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null.")
    return value


def _serialize_storage(device: StorageDeviceInfo) -> dict[str, Any]:
    return {
        "name": device.name,
        "capacity_bytes": device.capacity_bytes,
        "device_type": device.device_type,
    }


def _deserialize_storage(data: Any) -> StorageDeviceInfo:
    data = _required_mapping(data, "storage")

    return StorageDeviceInfo(
        name=data["name"],
        capacity_bytes=data.get("capacity_bytes"),
        device_type=_optional_string(
            data.get("device_type"),
            "storage.device_type",
        ),
    )


def _serialize_network(
    adapter: NetworkAdapterInfo,
) -> dict[str, Any]:
    return {
        "name": adapter.name,
        "mac_address": adapter.mac_address,
        "interface_type": adapter.interface_type,
    }


def _deserialize_network(data: Any) -> NetworkAdapterInfo:
    data = _required_mapping(data, "network")

    return NetworkAdapterInfo(
        name=data["name"],
        mac_address=_optional_string(
            data.get("mac_address"),
            "network.mac_address",
        ),
        interface_type=_optional_string(
            data.get("interface_type"),
            "network.interface_type",
        ),
    )


def _serialize_profile(profile: MachineProfile) -> dict[str, Any]:
    return {
        "identity": {
            "machine_id": profile.identity.machine_id,
            "hostname": profile.identity.hostname,
        },
        "operating_system": {
            "family": profile.operating_system.family.value,
            "name": profile.operating_system.name,
            "version": profile.operating_system.version,
            "architecture": profile.operating_system.architecture,
            "kernel": profile.operating_system.kernel,
        },
        "virtualization": {
            "is_virtual_machine": (
                profile.virtualization.is_virtual_machine
            ),
            "hypervisor": profile.virtualization.hypervisor,
            "platform": profile.virtualization.platform,
        },
        "hardware": {
            "cpu": profile.hardware.cpu,
            "gpu": list(profile.hardware.gpu),
            "memory_bytes": profile.hardware.memory_bytes,
            "storage": [
                _serialize_storage(device)
                for device in profile.hardware.storage
            ],
            "network_adapters": [
                _serialize_network(adapter)
                for adapter in profile.hardware.network_adapters
            ],
        },
        "verification": {
            "first_observed_at": _datetime_to_json(
                profile.verification.first_observed_at
            ),
            "last_verified_at": _datetime_to_json(
                profile.verification.last_verified_at
            ),
            "source": profile.verification.source,
        },
    }


def _deserialize_profile(data: Any) -> MachineProfile:
    profile = _required_mapping(data, "profile")
    identity = _required_mapping(profile.get("identity"), "identity")
    operating_system = _required_mapping(
        profile.get("operating_system"),
        "operating_system",
    )
    virtualization = _required_mapping(
        profile.get("virtualization"),
        "virtualization",
    )
    hardware = _required_mapping(
        profile.get("hardware"),
        "hardware",
    )
    verification = _required_mapping(
        profile.get("verification"),
        "verification",
    )

    gpu = hardware.get("gpu", [])
    storage = hardware.get("storage", [])
    network_adapters = hardware.get("network_adapters", [])

    if not isinstance(gpu, list):
        raise ValueError("hardware.gpu must be an array.")

    if not isinstance(storage, list):
        raise ValueError("hardware.storage must be an array.")

    if not isinstance(network_adapters, list):
        raise ValueError(
            "hardware.network_adapters must be an array."
        )

    try:
        return MachineProfile(
            identity=MachineIdentity(
                machine_id=identity["machine_id"],
                hostname=identity["hostname"],
            ),
            operating_system=OperatingSystemInfo(
                family=PlatformFamily(
                    operating_system["family"]
                ),
                name=_optional_string(
                    operating_system.get("name"),
                    "operating_system.name",
                ),
                version=_optional_string(
                    operating_system.get("version"),
                    "operating_system.version",
                ),
                architecture=_optional_string(
                    operating_system.get("architecture"),
                    "operating_system.architecture",
                ),
                kernel=_optional_string(
                    operating_system.get("kernel"),
                    "operating_system.kernel",
                ),
            ),
            virtualization=VirtualizationInfo(
                is_virtual_machine=virtualization[
                    "is_virtual_machine"
                ],
                hypervisor=_optional_string(
                    virtualization.get("hypervisor"),
                    "virtualization.hypervisor",
                ),
                platform=_optional_string(
                    virtualization.get("platform"),
                    "virtualization.platform",
                ),
            ),
            hardware=HardwareProfile(
                cpu=_optional_string(
                    hardware.get("cpu"),
                    "hardware.cpu",
                ),
                gpu=tuple(gpu),
                memory_bytes=hardware.get("memory_bytes"),
                storage=tuple(
                    _deserialize_storage(item)
                    for item in storage
                ),
                network_adapters=tuple(
                    _deserialize_network(item)
                    for item in network_adapters
                ),
            ),
            verification=MachineVerification(
                first_observed_at=_datetime_from_json(
                    verification["first_observed_at"],
                    "verification.first_observed_at",
                ),
                last_verified_at=_datetime_from_json(
                    verification["last_verified_at"],
                    "verification.last_verified_at",
                ),
                source=verification["source"],
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "Invalid persisted machine profile."
        ) from exc


def _serialize_observation(
    observation: MachineObservation,
) -> dict[str, Any]:
    return {
        "machine_id": observation.machine_id,
        "observed_at": _datetime_to_json(
            observation.observed_at
        ),
        "verified_at": _datetime_to_json(
            observation.verified_at
        ),
        "provenance": {
            "source_type": (
                observation.provenance.source_type.value
            ),
            "source_name": (
                observation.provenance.source_name
            ),
        },
        "state": observation.state.value,
        "profile": _serialize_profile(
            observation.profile
        ),
    }


def _deserialize_observation(
    data: Any,
) -> MachineObservation:
    observation = _required_mapping(
        data,
        "observation",
    )

    provenance = _required_mapping(
        observation.get("provenance"),
        "provenance",
    )

    try:
        result = MachineObservation(
            profile=_deserialize_profile(
                observation["profile"]
            ),
            observed_at=_datetime_from_json(
                observation["observed_at"],
                "observation.observed_at",
            ),
            verified_at=_datetime_from_json(
                observation["verified_at"],
                "observation.verified_at",
            ),
            provenance=ObservationProvenance(
                source_type=ObservationSource(
                    provenance["source_type"]
                ),
                source_name=provenance["source_name"],
            ),
            state=ObservationState(
                observation["state"]
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "Invalid persisted machine observation."
        ) from exc

    if observation.get("machine_id") != result.machine_id:
        raise ValueError(
            "Persisted observation machine_id does not "
            "match its profile."
        )

    return result


def serialize_inventory(
    inventory: MachineInventory,
) -> dict[str, Any]:
    if not isinstance(inventory, MachineInventory):
        raise TypeError(
            "inventory must be a MachineInventory."
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "current": {
            machine_id: _serialize_observation(
                observation
            )
            for machine_id, observation
            in inventory._current.items()
        },
        "history": {
            machine_id: [
                _serialize_observation(observation)
                for observation in observations
            ]
            for machine_id, observations
            in inventory._history.items()
        },
    }


def deserialize_inventory(
    data: Any,
) -> MachineInventory:
    root = _required_mapping(
        data,
        "inventory",
    )

    if root.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            "Unsupported inventory schema_version: "
            f"{root.get('schema_version')!r}."
        )

    current = _required_mapping(
        root.get("current"),
        "current",
    )

    history = _required_mapping(
        root.get("history"),
        "history",
    )

    current_observations = {
        machine_id: _deserialize_observation(
            observation
        )
        for machine_id, observation
        in current.items()
    }

    history_observations: dict[
        str,
        list[MachineObservation],
    ] = {}

    for machine_id, observations in history.items():
        if not isinstance(observations, list):
            raise ValueError(
                f"history[{machine_id!r}] must be an array."
            )

        history_observations[machine_id] = [
            _deserialize_observation(observation)
            for observation in observations
        ]

    for machine_id, observation in current_observations.items():
        if machine_id != observation.machine_id:
            raise ValueError(
                "Persisted current machine_id does not "
                "match its observation."
            )

    for machine_id, observations in history_observations.items():
        if not observations:
            raise ValueError(
                f"history[{machine_id!r}] must not be empty."
            )

        if any(
            observation.machine_id != machine_id
            for observation in observations
        ):
            raise ValueError(
                "Persisted history machine_id does not "
                "match an observation."
            )

    if set(current_observations) != set(
        history_observations
    ):
        raise ValueError(
            "Current and history machine sets must match."
        )

    return MachineInventory(
        _current=current_observations,
        _history=history_observations,
    )


class MachineInventoryPersistence:
    def __init__(
        self,
        path: str | Path,
    ) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def save(
        self,
        inventory: MachineInventory,
    ) -> None:
        payload = serialize_inventory(inventory)

        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self._path.with_suffix(
            self._path.suffix + ".tmp"
        )

        try:
            temporary_path.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            temporary_path.replace(
                self._path
            )
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def load(self) -> MachineInventory:
        try:
            payload = json.loads(
                self._path.read_text(
                    encoding="utf-8"
                )
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                "Machine inventory file does not exist: "
                f"{self._path}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Machine inventory file contains invalid "
                f"JSON: {self._path}"
            ) from exc

        return deserialize_inventory(payload)