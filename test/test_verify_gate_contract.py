from sofia.verify.gate import GateCommandEvidence, VerificationEvidence, _PHASES


def test_static_gate_compiles_all_python_surfaces_and_checks_dependencies():
    commands = dict(_PHASES["static"])

    compile_args = commands["compile"]
    assert compile_args[:3] == ("-m", "compileall", "-q")
    assert "src/sofia" in compile_args
    assert "test" in compile_args
    assert "tools" in compile_args
    assert commands["dependency-check"] == ("-m", "pip", "check")


def test_full_and_prelive_include_static_gate_before_runtime_tests():
    for phase in ("full", "prelive"):
        names = tuple(name for name, _ in _PHASES[phase])
        assert names[:2] == ("compile", "dependency-check")
        assert "pytest" in names


def test_candidate_gate_can_accept_reviewed_dirty_tree_but_release_gate_cannot():
    command = GateCommandEvidence(
        name="pytest",
        argv=("python", "-m", "pytest"),
        returncode=0,
        started_at="2026-10-05T00:00:00+00:00",
        finished_at="2026-10-05T00:00:01+00:00",
        duration_seconds=1.0,
    )
    common = {
        "git_revision": "a" * 40,
        "python_version": "3.12",
        "tracked_tree_clean": False,
        "generated_at": "2026-10-05T00:00:01+00:00",
        "commands": (command,),
    }

    assert VerificationEvidence(phase="candidate", **common).accepted is True
    assert VerificationEvidence(phase="full", **common).accepted is False
