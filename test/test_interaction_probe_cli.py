"""Probe help must finish before configuration provisioning or inference."""
from importlib import import_module

import pytest


@pytest.mark.parametrize("name", ["ab_probe", "focused_probe"])
def test_probe_help_does_not_initialize_configuration(name, monkeypatch):
    module = import_module("sofia.verify.interaction." + name)

    def unexpected_configuration():
        raise AssertionError("Help attempted configuration provisioning")

    monkeypatch.setattr(module, "create_production_configuration", unexpected_configuration)
    with pytest.raises(SystemExit) as caught:
        module.main(["--help"])
    assert caught.value.code == 0
