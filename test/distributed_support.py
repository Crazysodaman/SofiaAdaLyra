"""Fixtures using the production durable remote authorization owner."""
import pytest

from sofia.distributed.durable import DurableRemoteAuthorization


@pytest.fixture
def remote_authorization(tmp_path):
    authorization = DurableRemoteAuthorization(tmp_path / "grants.db")
    try:
        yield authorization
    finally:
        authorization.close()
