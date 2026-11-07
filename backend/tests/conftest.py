import os

os.environ["HF_HUB_OFFLINE"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def settings():
    return Settings(_env_file=None)


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings))
