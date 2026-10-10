from threading import Event

from sofia.voice import (
    SpeechInputProbe, SpeechInputReceipt, SpeechInputReceiptStore,
    SpeechInputService, SpeechInputState,
    WindowsSpeechRecognitionBackend,
)


class FakeBackend:
    name = "fixture-stt"

    def probe(self, *, device_id=None):
        return SpeechInputProbe(self.name, True, True, ("default",), device_id, "ready")

    def transcribe(self, *, capture_id, device_id, timeout_seconds, cancel):
        return SpeechInputReceipt(
            capture_id, SpeechInputState.COMPLETED, self.name, device_id,
            "Hello Sofía", .92,
        )


def test_push_to_talk_is_disabled_by_default_and_never_opens_backend():
    service = SpeechInputService(FakeBackend())
    receipts = []
    initial = service.listen(receipts.append)
    assert initial.state is SpeechInputState.REJECTED
    assert receipts == [initial]


def test_push_to_talk_emits_listening_then_typed_transcript():
    service = SpeechInputService(FakeBackend(), enabled=True)
    done = Event()
    receipts = []

    def receive(receipt):
        receipts.append(receipt)
        if receipt.state is SpeechInputState.COMPLETED:
            done.set()

    initial = service.listen(receive)
    assert initial.state is SpeechInputState.LISTENING
    assert done.wait(2)
    assert receipts[-1].transcript == "Hello Sofía"
    assert receipts[-1].confidence == .92


def test_non_windows_probe_is_explicitly_unavailable(monkeypatch):
    monkeypatch.setattr("sofia.voice.stt.sys.platform", "linux")
    probe = WindowsSpeechRecognitionBackend().probe()
    assert probe.available is False
    assert probe.healthy is False
    assert probe.devices == ("default",)


def test_input_receipt_store_keeps_only_transcript_digest(tmp_path):
    path = tmp_path / "sofia.db"
    path.touch()
    store = SpeechInputReceiptStore(path)
    receipt = SpeechInputReceipt(
        "capture-1", SpeechInputState.COMPLETED, "fixture", "default",
        "private spoken words", .8,
    )
    store.record(receipt)
    import sqlite3
    with sqlite3.connect(path) as database:
        row = database.execute(
            "SELECT transcript_sha256,error FROM voice_input_receipt"
        ).fetchone()
    assert row[0] is not None
    assert "private spoken words" not in row[0]
    assert row[1] is None
