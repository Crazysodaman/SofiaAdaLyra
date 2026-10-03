from pathlib import Path

import pytest

from sofia.run.windows_service_spec import (
    RUNTIME_SERVICE,
    WATCHDOG_SERVICE,
    WindowsServiceSpec,
    service_specs,
)


def test_runtime_and_watchdog_are_distinct_real_service_classes():
    assert RUNTIME_SERVICE.name == "SofiaAdaLyra"
    assert WATCHDOG_SERVICE.name == "SofiaAdaLyraWatchdog"
    assert RUNTIME_SERVICE.class_string.endswith(
        ".SofiaRuntimeWindowsService"
    )
    assert WATCHDOG_SERVICE.class_string.endswith(
        ".SofiaWatchdogWindowsService"
    )
    assert RUNTIME_SERVICE.class_string != WATCHDOG_SERVICE.class_string


def test_services_use_delayed_automatic_start_contract():
    assert all(spec.delayed_auto_start for spec in service_specs())


def test_service_specs_are_unique_and_bounded():
    specs = service_specs()
    assert len({spec.name for spec in specs}) == len(specs)
    assert len({spec.class_string for spec in specs}) == len(specs)


@pytest.mark.parametrize(
    "field,value",
    (
        ("name", ""),
        ("display_name", ""),
        ("description", ""),
        ("class_string", ""),
    ),
)
def test_service_spec_rejects_empty_identity_fields(field, value):
    values = dict(
        name="Service",
        display_name="Service",
        description="Description",
        class_string="package.module.Class",
    )
    values[field] = value
    with pytest.raises(ValueError):
        WindowsServiceSpec(**values)
