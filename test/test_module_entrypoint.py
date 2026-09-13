import runpy

import pytest


def test_module_entrypoint_runs_application(monkeypatch):
    calls: list[str] = []

    class FakeConfiguration:
        pass

    configuration = FakeConfiguration()

    class FakeApplication:
        def __init__(self, received_configuration):
            calls.append("application")
            assert received_configuration is configuration

    class FakeConversationLoop:
        def __init__(
            self,
            application,
            input_function=input,
            output_function=print,
        ):
            calls.append("conversation")
            assert isinstance(
                application,
                FakeApplication,
            )

        def run(self):
            calls.append("run")

    monkeypatch.setattr(
        "sofia.config.create_default_configuration",
        lambda: configuration,
    )

    monkeypatch.setattr(
        "sofia.application.SofiaApplication",
        FakeApplication,
    )

    monkeypatch.setattr(
        "sofia.application.ConversationLoop",
        FakeConversationLoop,
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(
            "src/sofia/__main__.py",
            run_name="__main__",
        )

    assert exc_info.value.code == 0

    assert calls == [
        "application",
        "conversation",
        "run",
    ]