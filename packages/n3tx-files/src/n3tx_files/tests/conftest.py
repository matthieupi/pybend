import warnings

import pytest

from n3tx_core.utils.registrar import registered_models


@pytest.fixture(autouse=True)
def isolate_model_registry():
    saved_models = dict(registered_models)
    registered_models.clear()
    try:
        yield
    finally:
        registered_models.clear()
        registered_models.update(saved_models)


def pytest_configure(config):
    warnings.filterwarnings(
        "ignore",
        message='Field name "tools" in "AgentActor" shadows an attribute in parent "AgentMixin"',
        category=UserWarning,
    )
