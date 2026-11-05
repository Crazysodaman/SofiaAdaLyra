from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from datetime import datetime, timezone

import pytest

from sofia.sdk.core_link import CoreLinkRequest, CoreLinkResponse
from sofia.sdk.core_link import CoreLinkResponseStatus
from sofia.platform.core_link.transport import CoreLinkServer, CoreLinkServerConfiguration
from sofia.platform.distributed.tls import public_key_fingerprint_from_pem_certificate
sys.path.insert(0, str(Path(__file__).parent))
from test_core_link_conversation import tls_material  # noqa: E402


FIXTURES = Path(__file__).parents[1] / "contracts" / "core-link"


@pytest.mark.parametrize(
    "name",
    [
        "valid-status-request.json",
        "valid-history-request.json",
        "valid-history-page-2-request.json",
    ],
)
def test_python_accepts_r2_request_fixtures(name: str) -> None:
    CoreLinkRequest.from_payload(json.loads((FIXTURES / name).read_text(encoding="utf-8")))



def test_page_two_history_cursor_is_accepted_by_python_contract() -> None:
    payload = json.loads(
        (FIXTURES / "valid-history-page-2-request.json").read_text(encoding="utf-8")
    )
    request = CoreLinkRequest.from_payload(payload)
    assert request.operation == "conversation.history"
    assert request.payload["after"] == {
        "created_at": "2025-12-31T23:59:59+00:00",
        "message_id": "message:1",
    }

@pytest.mark.parametrize("name", ["valid-status-response.json", "valid-history-response.json"])
def test_python_accepts_r2_response_fixtures(name: str) -> None:
    CoreLinkResponse.from_payload(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


@pytest.mark.parametrize("name", ["invalid-authority-field.json"])
def test_python_rejects_unreviewed_r2_fields(name: str) -> None:
    with pytest.raises(ValueError, match="unreviewed fields"):
        CoreLinkRequest.from_payload(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def test_r2_mutation_fixture_is_valid_python_but_outside_rust_read_only_scope() -> None:
    request = CoreLinkRequest.from_payload(
        json.loads((FIXTURES / "invalid-mutation-request.json").read_text(encoding="utf-8"))
    )
    assert request.operation == "conversation.send"


def test_rust_read_only_client_uses_disposable_python_mtls_server(tmp_path: Path) -> None:
    probe = os.environ.get("SOFIA_R2_PROBE")
    if not probe:
        pytest.skip("SOFIA_R2_PROBE is set by the R2 compatibility job")
    ca, (server_cert, server_key), (client_cert, client_key) = tls_material(tmp_path)

    class Gateway:
        def dispatch(self, *, certificate_public_key_sha256, request):
            assert certificate_public_key_sha256 == public_key_fingerprint_from_pem_certificate(client_cert)
            assert request.operation in {"status", "conversation.history"}
            payload = (
                {"ready": True, "generation": 7}
                if request.operation == "status"
                else {
                    "session_id": "session:existing",
                    "messages": [{"content": "PRIVATE_HISTORY_DO_NOT_LOG"}],
                    "next_cursor": None,
                }
            )
            return CoreLinkResponse(
                request.request_id,
                CoreLinkResponseStatus.COMPLETED,
                payload,
                datetime.now(timezone.utc),
            )

        def close(self):
            return None

    server = CoreLinkServer(
        CoreLinkServerConfiguration(
            "127.0.0.1", 0, server_cert, server_key, ca, socket_timeout_seconds=3
        ),
        Gateway(),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            [
                probe,
                f"https://localhost:{server.address[1]}/v1/core-link",
                public_key_fingerprint_from_pem_certificate(server_cert),
                str(ca),
                str(client_cert),
                str(client_key),
                "platform:windows",
                "platform:canonical",
                "core:sofia",
                "7",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {
            "operation": "status",
            "status": "completed",
        }
        assert "ready" not in result.stdout
        assert "generation" not in result.stdout
        history = subprocess.run(
            result.args + ["session:existing"], check=False, capture_output=True,
            text=True, timeout=10,
        )
        assert history.returncode == 0, history.stderr
        assert json.loads(history.stdout) == {
            "operation": "conversation.history",
            "status": "completed",
            "message_count": 1,
        }
        assert "PRIVATE_HISTORY_DO_NOT_LOG" not in history.stdout
        assert "PRIVATE_HISTORY_DO_NOT_LOG" not in history.stderr
        assert "session:existing" not in history.stdout
        bad_pin_args = list(result.args)
        bad_pin_args[2] = "0" * 64
        rejected = subprocess.run(
            bad_pin_args, check=False, capture_output=True, text=True, timeout=10,
        )
        assert rejected.returncode != 0
        assert "request does not match enrolled binding" in rejected.stderr
    finally:
        server.close()
        thread.join(timeout=3)
