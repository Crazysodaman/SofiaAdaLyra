from sofia.verify.gate import GateCommandEvidence, VerificationEvidence, _PHASES


def test_static_gate_compiles_all_python_surfaces_and_checks_dependencies():
    commands = dict(_PHASES["static"])

    compile_args = commands["compile"]
    assert compile_args[:3] == ("-m", "compileall", "-q")
    assert "src/sofia" in compile_args
    assert "test" in compile_args
    assert "tools" in compile_args
    assert commands["dependency-check"] == ("-m", "pip", "check")


def test_full_and_prelive_include_all_static_commands_before_runtime_tests():
    static_names = tuple(name for name, _ in _PHASES["static"])
    for phase in ("full", "prelive"):
        names = tuple(name for name, _ in _PHASES[phase])
        assert names[:len(static_names)] == static_names
        assert "pytest" in names
        assert "semantic" in names


def _gate_commands(phase: str):
    return tuple(
        GateCommandEvidence(
            name=name,
            argv=("python", *argv),
            returncode=0,
            started_at="2026-10-05T00:00:00+00:00",
            finished_at="2026-10-05T00:00:01+00:00",
            duration_seconds=1.0,
        )
        for name, argv in _PHASES[phase]
    )


def _evidence(phase: str, *, clean: bool, commands=None):
    return VerificationEvidence(
        phase=phase,
        git_revision="a" * 40,
        python_version="3.12",
        tracked_tree_clean=clean,
        generated_at="2026-10-05T00:00:01+00:00",
        commands=_gate_commands(phase) if commands is None else commands,
    )


def test_candidate_gate_accepts_only_complete_reviewed_dirty_tree_commands():
    assert _evidence("candidate", clean=False).accepted is True
    assert _evidence("full", clean=False).accepted is False
    assert _evidence("full", clean=True).accepted is True


def test_gate_rejects_empty_partial_and_reordered_evidence():
    complete = _gate_commands("full")
    assert not _evidence("full", clean=True, commands=()).accepted
    assert not _evidence("full", clean=True, commands=complete[:-1]).accepted
    swapped = (complete[1], complete[0], *complete[2:])
    assert not _evidence("full", clean=True, commands=swapped).accepted


def test_gate_rejects_forged_command_identity_and_failed_exit():
    original = _gate_commands("full")
    forged = GateCommandEvidence(
        name=original[0].name,
        argv=("python", "-c", "print('green')"),
        returncode=0,
        started_at=original[0].started_at,
        finished_at=original[0].finished_at,
        duration_seconds=1.0,
    )
    assert not _evidence(
        "full", clean=True, commands=(forged, *original[1:]),
    ).accepted
    failed = GateCommandEvidence(
        name=original[-1].name,
        argv=original[-1].argv,
        returncode=1,
        started_at=original[-1].started_at,
        finished_at=original[-1].finished_at,
        duration_seconds=1.0,
    )
    assert not _evidence(
        "full", clean=True, commands=(*original[:-1], failed),
    ).accepted


def test_installed_wheel_pytest_import_override_is_the_only_allowed_trailing_arg():
    base = list(_gate_commands("full"))
    pytest_index = next(i for i, command in enumerate(base) if command.name == "pytest")
    command = base[pytest_index]
    base[pytest_index] = GateCommandEvidence(
        name=command.name,
        argv=(*command.argv, "--override-ini", "pythonpath=."),
        returncode=0,
        started_at=command.started_at,
        finished_at=command.finished_at,
        duration_seconds=command.duration_seconds,
    )
    assert _evidence("full", clean=True, commands=tuple(base)).accepted
    base[pytest_index] = GateCommandEvidence(
        name=command.name,
        argv=(*command.argv, "--ignore", "test"),
        returncode=0,
        started_at=command.started_at,
        finished_at=command.finished_at,
        duration_seconds=command.duration_seconds,
    )
    assert not _evidence("full", clean=True, commands=tuple(base)).accepted


def test_same_command_results_are_rejected_if_git_head_moved_mid_gate():
    from dataclasses import replace

    stable = _evidence("full", clean=True)
    assert stable.accepted
    moved = replace(stable, revision_stable=False)
    assert moved.git_revision == stable.git_revision
    assert moved.commands == stable.commands
    assert not moved.accepted


def test_release_gate_rejects_dirty_start_even_when_tree_later_cleans():
    from dataclasses import replace

    passing = _evidence("prelive", clean=True)
    assert passing.accepted
    dirty_start = replace(passing, source_clean_at_start=False)
    assert not dirty_start.accepted
    # Candidate is explicitly a non-release development gate.
    assert _evidence("candidate", clean=False).accepted
    assert replace(
        _evidence("candidate", clean=False),
        source_clean_at_start=False,
    ).accepted


def test_git_tree_cleanliness_detects_untracked_source(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import sofia.verify.gate as gate

    def git_status(argv, **kwargs):
        assert tuple(argv) == (
            "git", "status", "--porcelain=v1", "--untracked-files=all", "--",
        )
        assert kwargs["cwd"] == tmp_path
        return SimpleNamespace(returncode=0, stdout="?? src/sofia/unsafe.py\\n")

    monkeypatch.setattr(gate.subprocess, "run", git_status)
    assert not gate._tracked_tree_clean(tmp_path)


def test_git_tree_cleanliness_fails_closed_on_git_error(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import sofia.verify.gate as gate
    import pytest

    monkeypatch.setattr(
        gate.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=128, stdout=""),
    )
    with pytest.raises(RuntimeError, match="working-tree"):
        gate._tracked_tree_clean(tmp_path)
