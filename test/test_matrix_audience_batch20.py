"""Twenty independently named Matrix boundary acceptance cases.

These are focused regression scenarios, not 20 completed roadmap tasks.
Each case uses the actual canonical MatrixTraceStore SQLite implementation.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from sofia.cognition.matrix.model import (
    CognitionExecutionTrace, HistoryPolicy, MatrixConfidence, MatrixIntent,
    MatrixTrace, ResponseStrategy, TurnEnvelope, TurnMatrix,
)
from sofia.cognition.matrix.trace import MatrixTraceStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_verify]
NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


@pytest.fixture
def traces(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = MatrixTraceStore(path)
    turn = TurnMatrix(
        intent=MatrixIntent.GENERAL,
        confidence=MatrixConfidence.HIGH,
        history_policy=HistoryPolicy.BOUNDED_RECENT,
        response_strategy=ResponseStrategy.GENERATIVE,
        domains=(),
    )
    def put(message_id, session, principal, channel, seconds, execution=False):
        trace = MatrixTrace(
            envelope=TurnEnvelope(
                message_id=message_id, session_id=session,
                principal_id=principal, channel=channel,
                content="never expose this private user content",
                created_at=NOW,
            ),
            turn=turn,
            created_at=NOW + timedelta(seconds=seconds),
            cognition_execution=(
                CognitionExecutionTrace(serial=seconds, actual_route="fast")
                if execution else None
            ),
        )
        store.record(trace)
    put("desktop-owner", "s1", "principal:one", "desktop", 1, True)
    put("discord-owner", "s1", "principal:one", "discord", 2, True)
    put("desktop-other", "s1", "principal:two", "desktop", 3, True)
    put("other-session", "s2", "principal:one", "desktop", 4, True)
    put("anonymous", "s1", None, "desktop", 5, True)
    put("newer-metadata", "s1", "principal:one", "desktop", 6, False)
    return store


# Each row is an individual collected pytest case. 7 exact-message,
# 7 most-recent, and 6 execution-provenance cases: 20 total.
CASES = [
    # exact message ID, matching and cross-audience negative controls
    ("get_owner", "get", "desktop-owner", "s1", "principal:one", "desktop", "desktop-owner"),
    ("get_wrong_session", "get", "desktop-owner", "s2", "principal:one", "desktop", None),
    ("get_wrong_principal", "get", "desktop-owner", "s1", "principal:two", "desktop", None),
    ("get_wrong_channel", "get", "desktop-owner", "s1", "principal:one", "discord", None),
    ("get_anonymous", "get", "anonymous", "s1", "", "desktop", "anonymous"),
    ("get_authenticated_cannot_read_anonymous", "get", "anonymous", "s1", "principal:one", "desktop", None),
    ("get_anonymous_cannot_read_authenticated", "get", "desktop-owner", "s1", "", "desktop", None),
    # latest bounded by complete scope, not merely session ID
    ("latest_owner", "latest", None, "s1", "principal:one", "desktop", "newer-metadata"),
    ("latest_discord", "latest", None, "s1", "principal:one", "discord", "discord-owner"),
    ("latest_other_principal", "latest", None, "s1", "principal:two", "desktop", "desktop-other"),
    ("latest_other_session", "latest", None, "s2", "principal:one", "desktop", "other-session"),
    ("latest_anonymous", "latest", None, "s1", "", "desktop", "anonymous"),
    ("latest_missing_session", "latest", None, "missing", "principal:one", "desktop", None),
    ("latest_missing_channel", "latest", None, "s1", "principal:one", "voice", None),
    # real execution, not simply the newest metadata-only extension
    ("execution_owner", "execution", None, "s1", "principal:one", "desktop", "desktop-owner"),
    ("execution_discord", "execution", None, "s1", "principal:one", "discord", "discord-owner"),
    ("execution_other_principal", "execution", None, "s1", "principal:two", "desktop", "desktop-other"),
    ("execution_other_session", "execution", None, "s2", "principal:one", "desktop", "other-session"),
    ("execution_anonymous", "execution", None, "s1", "", "desktop", "anonymous"),
    ("execution_missing_audience", "execution", None, "s1", "principal:one", "voice", None),
]


@pytest.mark.parametrize(
    ("case", "mode", "message_id", "session", "principal", "channel", "expected"),
    CASES,
    ids=[case[0] for case in CASES],
)
def test_matrix_twenty_audience_and_execution_boundaries(
    traces, case, mode, message_id, session, principal, channel, expected,
):
    if mode == "get":
        result = traces.get_scoped(
            message_id, session_id=session, principal_id=principal, channel=channel,
        )
    elif mode == "latest":
        result = traces.latest_scoped(
            session_id=session, principal_id=principal, channel=channel,
        )
    else:
        result = traces.latest_execution_scoped(
            session_id=session, principal_id=principal, channel=channel,
        )
    assert (None if result is None else result.envelope.message_id) == expected, case
    if result is not None:
        assert result.envelope.session_id == session
        assert (result.envelope.principal_id or "") == principal
        assert result.envelope.channel == channel
        assert "never expose this private user content" not in repr(result)
