"""Tests for distributed service configuration during app bootstrap."""

import pytest
from pydantic import BaseModel

from n3tx_core import config
from n3tx_core.app import N3TXApp
from n3tx_core.models.ref import Ref

pytestmark = pytest.mark.unit


class File(BaseModel):
    id: int = 0


class TestAppRemoteConfiguration:

    def test_builder_overrides_distributed_config(self, tmp_path):
        old_remotes = config.REMOTES
        old_service_name = config.SERVICE_NAME
        old_service_token = config.SERVICE_TOKEN
        try:
            N3TXApp(
                storage=f"sqlite:///{tmp_path / 'app.db'}",
                remotes={'storage': {'url': 'http://storage:7100', 'token': 'remote-token'}},
                service_name='api-test',
                service_token='local-token',
            )

            assert config.REMOTES == {
                'storage': {'url': 'http://storage:7100', 'token': 'remote-token'}
            }
            assert config.SERVICE_NAME == 'api-test'
            assert config.SERVICE_TOKEN == 'local-token'
            assert Ref[File]('http://storage:7100/File/12') == 'http://storage:7100/File/12'
        finally:
            config.configure(
                remotes=old_remotes,
                service_name=old_service_name,
                service_token=old_service_token,
            )
