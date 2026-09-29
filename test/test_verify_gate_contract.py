from sofia.verify.gate import _PHASES


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
