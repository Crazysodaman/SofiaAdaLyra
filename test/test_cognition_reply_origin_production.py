"""Source-only, deferred tests for canonical per-reply model provenance."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
import sqlite3
import pytest

from sofia.application.conversation_service import ConversationService
from sofia.cognition.matrix.model import CognitionExecutionStep, CognitionExecutionTrace
from sofia.cognition.model import CognitiveResponse
from sofia.cognition.reply_origin import ReplyModelOriginStore
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.social.principals import local_sparks_principal, discord_sparks_principal

pytestmark = pytest.mark.pkg_core
NOW=datetime(2026,10,11,tzinfo=timezone.utc)


def trace():
    return CognitionExecutionTrace(
        serial=17,actual_route="verify",
        steps=(
            CognitionExecutionStep("primary","deep:model","venus",True),
            CognitionExecutionStep("secondary","fast:model","artemis",True),
            CognitionExecutionStep("primary","deep:model","venus",True),
        ),verification_passes=1,
    )


def setup(tmp_path):
    path=tmp_path/"sofia.db"
    store=ConversationStore(path)
    session=store.create_session()
    return path,store,session


def saved(store,session):
    msg=ConversationMessage(
        id=str(uuid4()),session_id=session.id,
        role=ConversationRole.ASSISTANT,
        content="Actual user-facing reply is not copied into model metadata",
        created_at=NOW,
    )
    store.save(msg)
    return msg


def test_model_steps_bind_exact_saved_reply_and_private_scope(tmp_path):
    path,store,session=setup(tmp_path)
    msg=saved(store,session)
    origin=ReplyModelOriginStore(path)
    kwargs=dict(
        assistant_message_id=msg.id,session_id=session.id,
        execution=trace(),principal=local_sparks_principal(),at=NOW,
    )
    origin.record(**kwargs)
    origin.record(**kwargs)
    receipt=origin.inspect(
        assistant_message_id=msg.id,
        principal=local_sparks_principal(),
    )
    assert receipt["kind"]=="model"
    assert [step["model"] for step in receipt["steps"]]==[
        "deep:model","fast:model","deep:model",
    ]
    assert receipt["steps"][1]["host"]=="artemis"
    assert origin.inspect(
        assistant_message_id=msg.id,
        principal=discord_sparks_principal(22222),
    ) is None
    with pytest.raises(PermissionError,match="cannot be rewritten"):
        origin.record(**{
            **kwargs,
            "execution":CognitionExecutionTrace(
                serial=18,actual_route="fast",
                steps=(CognitionExecutionStep("secondary","wrong","venus",True),),
            ),
        })
    with sqlite3.connect(path) as db:
        raw=db.execute(
            "SELECT steps_json FROM cognition_reply_model_origin"
        ).fetchone()[0]
        assert msg.content not in raw
        db.execute("DELETE FROM conversation_messages WHERE id=?",(msg.id,))
    assert origin.inspect(
        assistant_message_id=msg.id,
        principal=local_sparks_principal(),
    ) is None
    store.close()


def test_real_service_reply_writer_records_observed_model_without_new_session(tmp_path):
    path,store,session=setup(tmp_path)
    service=object.__new__(ConversationService)
    service._conversation_store=store
    service._session=session
    service._current_coordinated_turn=None
    service._current_turn_admission=None
    service._social_store=SimpleNamespace(get=lambda _:local_sparks_principal())
    service._link_main_lifelong_message=lambda *_:None
    service._reply_model_origin_store=None
    service._current_cognition_execution=trace()
    service._last_reply_model_origin_error=None
    ConversationService._persist_response(
        service,CognitiveResponse(content="Actual reply"),
    )
    assert service._session.id==session.id
    assert service.last_reply_model_origin_error is None
    with sqlite3.connect(path) as db:
        msg_id=db.execute(
            "SELECT id FROM conversation_messages WHERE role='assistant'"
        ).fetchone()[0]
    result=ReplyModelOriginStore(path).inspect(
        assistant_message_id=msg_id,
        principal=local_sparks_principal(),
    )
    assert result["steps"][-1]["model"]=="deep:model"
    store.close()


def test_unknown_model_origin_is_honestly_unknown(tmp_path):
    path,store,session=setup(tmp_path)
    msg=saved(store,session)
    origin=ReplyModelOriginStore(path)
    origin.record(
        assistant_message_id=msg.id,session_id=session.id,
        execution=None,principal=local_sparks_principal(),at=NOW,
    )
    result=origin.inspect(
        assistant_message_id=msg.id,
        principal=local_sparks_principal(),
    )
    assert result["kind"]=="unknown" and result["steps"]==()
    assert "not proof" in result["note"]
    store.close()
