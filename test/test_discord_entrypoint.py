"""Discord module entry-point dispatch tests. No network is started."""

import sofia.discord.__main__ as entry


def test_no_argument_runs_live_entrypoint(monkeypatch) -> None:
    monkeypatch.setattr(entry, "live_main", lambda: 11)
    assert entry.main([]) == 11


def test_run_argument_runs_live_entrypoint(monkeypatch) -> None:
    monkeypatch.setattr(entry, "live_main", lambda: 12)
    assert entry.main(["run"]) == 12


def test_operator_action_is_dispatched_without_live_runner(monkeypatch) -> None:
    seen = []
    monkeypatch.setattr(entry, "operator_main", lambda action: seen.append(action) or 13)
    monkeypatch.setattr(entry, "live_main", lambda: (_ for _ in ()).throw(AssertionError()))
    assert entry.main(["pause"]) == 13
    assert seen == ["pause"]


def test_unknown_arguments_are_refused(capsys) -> None:
    assert entry.main(["launch-the-fox-cannon"]) == 2
    assert "Usage:" in capsys.readouterr().err
