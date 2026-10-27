"""Portable, non-authoritative module settings schema contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
import re
from typing import Mapping


_FIELD_ID = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$")
_SECRET_REF = re.compile(r"^secret:[a-z][a-z0-9_.-]{1,126}$")


class ModuleSettingType(str, Enum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"
    ENUM = "enum"


class ModuleSettingApplyClass(str, Enum):
    LIVE = "live"
    NEXT_OPERATION = "next_operation"
    COMPONENT_RESTART = "component_restart"


@dataclass(frozen=True, slots=True)
class ModuleSettingField:
    field_id: str
    label: str
    value_type: ModuleSettingType
    apply_class: ModuleSettingApplyClass
    required: bool = False
    secret_reference: bool = False
    enum_values: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.field_id, str) or _FIELD_ID.fullmatch(
            self.field_id
        ) is None:
            raise ValueError("invalid module setting field_id")
        if (
            not isinstance(self.label, str) or not self.label.strip()
            or self.label != self.label.strip() or len(self.label) > 160
        ):
            raise ValueError("module setting label must be bounded text")
        if not isinstance(self.value_type, ModuleSettingType):
            raise TypeError("value_type must be ModuleSettingType")
        if not isinstance(self.apply_class, ModuleSettingApplyClass):
            raise TypeError("apply_class must be ModuleSettingApplyClass")
        if type(self.required) is not bool or type(self.secret_reference) is not bool:
            raise TypeError("module setting flags must be boolean")
        if self.secret_reference and self.value_type is not ModuleSettingType.STRING:
            raise ValueError("secret references must be string fields")
        if type(self.enum_values) is not tuple or len(self.enum_values) > 64 or any(
            not isinstance(item, str) or not item or item != item.strip()
            or len(item) > 160 for item in self.enum_values
        ) or len(set(self.enum_values)) != len(self.enum_values):
            raise ValueError("enum values must be bounded unique text")
        if self.value_type is ModuleSettingType.ENUM and not self.enum_values:
            raise ValueError("enum setting requires allowed values")
        if self.value_type is not ModuleSettingType.ENUM and self.enum_values:
            raise ValueError("enum values apply only to enum settings")
        if self.minimum is not None and (
            type(self.minimum) not in {int, float} or not isfinite(self.minimum)
        ):
            raise TypeError("minimum must be numeric")
        if self.maximum is not None and (
            type(self.maximum) not in {int, float} or not isfinite(self.maximum)
        ):
            raise TypeError("maximum must be numeric")
        if self.minimum is not None and self.maximum is not None and (
            self.minimum > self.maximum
        ):
            raise ValueError("module setting minimum exceeds maximum")
        if self.value_type not in {
            ModuleSettingType.INTEGER, ModuleSettingType.NUMBER,
        } and (self.minimum is not None or self.maximum is not None):
            raise ValueError("numeric bounds apply only to numeric settings")

    def validate(self, value: object) -> object:
        if value is None:
            if self.required:
                raise ValueError(f"{self.field_id} is required")
            return None
        if self.value_type is ModuleSettingType.BOOLEAN:
            valid = type(value) is bool
        elif self.value_type is ModuleSettingType.INTEGER:
            valid = type(value) is int
        elif self.value_type is ModuleSettingType.NUMBER:
            valid = type(value) in {int, float} and isfinite(value)
        else:
            valid = isinstance(value, str) and value == value.strip() and (
                len(value) <= 4096
            )
        if not valid:
            raise ValueError(f"{self.field_id} has invalid value type")
        if self.secret_reference and _SECRET_REF.fullmatch(value) is None:  # type: ignore[arg-type]
            raise ValueError(f"{self.field_id} must be a protected secret reference")
        if self.value_type is ModuleSettingType.ENUM and value not in self.enum_values:
            raise ValueError(f"{self.field_id} is not an allowed value")
        if self.minimum is not None and value < self.minimum:  # type: ignore[operator]
            raise ValueError(f"{self.field_id} is below its minimum")
        if self.maximum is not None and value > self.maximum:  # type: ignore[operator]
            raise ValueError(f"{self.field_id} exceeds its maximum")
        return value


@dataclass(frozen=True, slots=True)
class ModuleSettingsContract:
    schema: str
    contract_version: int
    fields: tuple[ModuleSettingField, ...]

    def __post_init__(self) -> None:
        if self.schema != "sofia.module.settings.v1":
            raise ValueError("unsupported module settings schema")
        if type(self.contract_version) is not int or self.contract_version < 1:
            raise ValueError("module settings contract_version must be positive")
        if type(self.fields) is not tuple or len(self.fields) > 128 or any(
            not isinstance(item, ModuleSettingField) for item in self.fields
        ) or len({item.field_id for item in self.fields}) != len(self.fields):
            raise ValueError("module settings fields must be bounded and unique")

    def validate(self, values: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(values, Mapping) or any(
            not isinstance(key, str) for key in values
        ):
            raise TypeError("module settings values must be a string-keyed mapping")
        fields = {item.field_id: item for item in self.fields}
        unknown = set(values) - set(fields)
        if unknown:
            raise ValueError("unsupported module setting fields")
        result = {
            field_id: fields[field_id].validate(value)
            for field_id, value in values.items()
        }
        for field in self.fields:
            if field.required and field.field_id not in result:
                raise ValueError(f"{field.field_id} is required")
        return result


def module_settings_contract_to_document(
    contract: ModuleSettingsContract,
) -> dict[str, object]:
    if not isinstance(contract, ModuleSettingsContract):
        raise TypeError("ModuleSettingsContract required")
    return {
        "schema": contract.schema,
        "contract_version": contract.contract_version,
        "fields": [{
            "field_id": field.field_id,
            "label": field.label,
            "value_type": field.value_type.value,
            "apply_class": field.apply_class.value,
            "required": field.required,
            "secret_reference": field.secret_reference,
            "enum_values": list(field.enum_values),
            "minimum": field.minimum,
            "maximum": field.maximum,
        } for field in contract.fields],
    }


def module_settings_contract_from_document(
    document: object,
) -> ModuleSettingsContract:
    if not isinstance(document, Mapping) or set(document) != {
        "schema", "contract_version", "fields",
    }:
        raise ValueError("module settings contract has invalid fields")
    raw_fields = document["fields"]
    if not isinstance(raw_fields, list):
        raise ValueError("module settings fields must be a list")
    fields = []
    for raw in raw_fields:
        if not isinstance(raw, Mapping) or set(raw) != {
            "field_id", "label", "value_type", "apply_class", "required",
            "secret_reference", "enum_values", "minimum", "maximum",
        } or not isinstance(raw["enum_values"], list):
            raise ValueError("module setting field has invalid fields")
        fields.append(ModuleSettingField(
            field_id=raw["field_id"],  # type: ignore[arg-type]
            label=raw["label"],  # type: ignore[arg-type]
            value_type=ModuleSettingType(raw["value_type"]),
            apply_class=ModuleSettingApplyClass(raw["apply_class"]),
            required=raw["required"],  # type: ignore[arg-type]
            secret_reference=raw["secret_reference"],  # type: ignore[arg-type]
            enum_values=tuple(raw["enum_values"]),
            minimum=raw["minimum"],  # type: ignore[arg-type]
            maximum=raw["maximum"],  # type: ignore[arg-type]
        ))
    return ModuleSettingsContract(
        schema=document["schema"],  # type: ignore[arg-type]
        contract_version=document["contract_version"],  # type: ignore[arg-type]
        fields=tuple(fields),
    )
