import importlib
import sys


def _clear_package(prefix: str) -> None:
    for name in tuple(sys.modules):
        if name == prefix or name.startswith(prefix + "."):
            sys.modules.pop(name, None)


def test_secret_store_import_does_not_eager_load_dev_capability():
    _clear_package("sofia.safe")
    _clear_package("sofia.dev")

    module = importlib.import_module("sofia.safe.secret_store")

    assert hasattr(module, "ProtectedSecretStore")
    assert "sofia.safe.dev_approval" not in sys.modules
    assert "sofia.dev.capability" not in sys.modules


def test_discord_provisioning_import_avoids_safe_dev_cycle():
    _clear_package("sofia.discord.provisioning")
    _clear_package("sofia.safe")
    _clear_package("sofia.dev")

    module = importlib.import_module("sofia.discord.provisioning")

    assert hasattr(module, "DiscordProvisioning")
    assert "sofia.dev.capability" not in sys.modules


def test_safe_public_dev_approval_export_remains_available():
    _clear_package("sofia.safe")
    _clear_package("sofia.dev")

    safe = importlib.import_module("sofia.safe")

    assert safe.DevApprovalVerifier.__name__ == "DevApprovalVerifier"


def test_dev_public_capability_export_remains_available():
    _clear_package("sofia.safe")
    _clear_package("sofia.dev")

    dev = importlib.import_module("sofia.dev")

    assert dev.DevToolService.__name__ == "DevToolService"
