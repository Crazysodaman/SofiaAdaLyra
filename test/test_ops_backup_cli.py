from pathlib import Path

from sofia.ops import backup_cli


class Result:
    backup_id = "backup-1"
    verifier = "test"
    verified_at = __import__("datetime").datetime(
        2026,
        10,
        3,
        tzinfo=__import__("datetime").timezone.utc,
    )


class Manifest:
    backup_id = "backup-1"
    source_host_id = "venus"
    failure_domain = "external"
    created_at = Result.verified_at
    entries = (object(),)
    digest = "a" * 64


class FakeEngine:
    def __init__(self):
        self.restore_calls = []

    def verify(self, backup_dir):
        assert isinstance(backup_dir, Path)
        return Manifest()

    def restore(self, **kwargs):
        target = kwargs["target_state_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"db")
        self.restore_calls.append(kwargs)
        return Result()


def test_rehearse_restores_only_to_temporary_location(
    monkeypatch,
    tmp_path,
):
    fake = FakeEngine()
    monkeypatch.setattr(
        backup_cli,
        "_engine",
        lambda _key: fake,
    )

    code = backup_cli.main(
        [
            "rehearse",
            "--key",
            str(tmp_path / "key"),
            "--backup-dir",
            str(tmp_path / "backup"),
            "--verifier",
            "test",
        ]
    )

    assert code == 0
    assert len(fake.restore_calls) == 1
    call = fake.restore_calls[0]
    assert call["replace_existing"] is False
    assert call["target_state_path"].name == "sofia.db"
    assert call["target_state_path"].parent != tmp_path


def test_restore_requires_explicit_replace_flag(
    monkeypatch,
    tmp_path,
):
    fake = FakeEngine()
    monkeypatch.setattr(
        backup_cli,
        "_engine",
        lambda _key: fake,
    )

    target = tmp_path / "restore" / "sofia.db"
    code = backup_cli.main(
        [
            "restore",
            "--key",
            str(tmp_path / "key"),
            "--backup-dir",
            str(tmp_path / "backup"),
            "--target-state",
            str(target),
            "--verifier",
            "test",
        ]
    )

    assert code == 0
    assert fake.restore_calls[0]["replace_existing"] is False


def test_objectives_command_reports_declared_targets(capsys):
    code = backup_cli.main(["objectives"])

    assert code == 0
    output = capsys.readouterr().out
    assert "rpo_seconds=3600" in output
    assert "rto_seconds=1800" in output
