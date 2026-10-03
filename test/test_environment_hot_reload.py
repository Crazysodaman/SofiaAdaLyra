from dataclasses import replace
from types import SimpleNamespace

from sofia.application import bootstrap
from sofia.application.bootstrap import SofiaApplication
from sofia.config.user_settings import RuntimeUserSettingsStore


class FakeRuntime:
    def __init__(self) -> None:
        self.replaced = []
        self.state_plane = object()

    def replace_environment_service(self, service) -> None:
        self.replaced.append(service)


def application_shell(tmp_path):
    state = tmp_path / "sofia.db"
    store = RuntimeUserSettingsStore(state)
    initial = store.load()

    app = object.__new__(SofiaApplication)
    app._configuration = SimpleNamespace(state_path=state)
    app._environment_settings_store = store
    app._environment_settings_fingerprint = (
        SofiaApplication._environment_fingerprint(initial)
    )
    app._runtime = FakeRuntime()
    app._presentation_routine = None
    return app, store, initial


def test_saved_environment_settings_hot_reload_once(
    tmp_path,
    monkeypatch,
):
    app, store, initial = application_shell(tmp_path)
    updated = replace(
        initial,
        location_label="New Homelab",
        location_timezone="America/Denver",
        location_latitude=39.7,
        location_longitude=-104.9,
        nws_enabled=False,
    )
    store.save(updated)

    rebuilt_configuration = object()
    reviewed_configuration = object()
    rebuilt_service = object()
    monkeypatch.setattr(
        bootstrap,
        "create_production_configuration",
        lambda *, state_path: rebuilt_configuration,
    )
    monkeypatch.setattr(
        bootstrap,
        "apply_reviewed_configuration",
        lambda configuration, state_plane: (
            reviewed_configuration
            if (
                configuration is rebuilt_configuration
                and state_plane is app._runtime.state_plane
            )
            else (_ for _ in ()).throw(
                AssertionError("reviewed configuration inputs changed")
            )
        ),
    )
    monkeypatch.setattr(
        bootstrap,
        "create_environment_service",
        lambda configuration: (
            rebuilt_service
            if configuration is reviewed_configuration
            else (_ for _ in ()).throw(
                AssertionError("environment service must use reviewed config")
            )
        ),
    )

    assert app._reload_environment_if_settings_changed() is True
    assert app._runtime.replaced == [rebuilt_service]
    assert app._reload_environment_if_settings_changed() is False
    assert app._runtime.replaced == [rebuilt_service]


def test_unrelated_runtime_setting_does_not_reload_environment(
    tmp_path,
    monkeypatch,
):
    app, store, initial = application_shell(tmp_path)
    updated = replace(
        initial,
        provider_context_size=initial.provider_context_size + 1024,
    )
    store.save(updated)

    monkeypatch.setattr(
        bootstrap,
        "create_production_configuration",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("environment should not rebuild")
        ),
    )

    assert app._reload_environment_if_settings_changed() is False
    assert app._runtime.replaced == []
