"""The release CI fixture never stands in for live canonical state acceptance."""
from sofia.verify import semantic


def test_isolated_semantic_verification_requires_negative_and_positive_proof(
    capsys, monkeypatch,
):
    def forbid_production_configuration():
        raise AssertionError("fixture must not discover the owner's live state")

    monkeypatch.setattr(
        semantic, "create_production_configuration",
        forbid_production_configuration,
    )
    assert semantic.main(["--isolated-fixture"]) == 0
    output = capsys.readouterr().out
    assert "NOT a live-host state integrity attestation" in output
    assert "Semantic integrity: accepted" in output


def test_live_semantic_verification_never_bootstraps_missing_state(
    capsys, monkeypatch, tmp_path,
):
    from types import SimpleNamespace

    missing = tmp_path / "not-installed" / "sofia.db"
    monkeypatch.setattr(
        semantic, "create_production_configuration",
        lambda: SimpleNamespace(state_path=missing),
    )
    assert semantic.main([]) == 3
    assert not missing.exists()
    assert not missing.parent.exists()
    assert "existing application state database required" in capsys.readouterr().err
