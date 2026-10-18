import importlib.util
from pathlib import Path

import mongomock
import pytest

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
TEST_SECRET = "test-signing-key"


def load_app_module(name="forwardauth_app"):
    spec = importlib.util.spec_from_file_location(name, APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def forwardauth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    module = load_app_module()
    module.db = mongomock.MongoClient()["Archimedes-Rest"]
    return module


@pytest.fixture
def client(forwardauth):
    return forwardauth.app.test_client()
