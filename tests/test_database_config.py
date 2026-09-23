import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

import smos.core.database as db_mod
from smos.api.main import app


@pytest.fixture(autouse=True)
def restore_db_module():
    orig_engine = db_mod.engine
    orig_sessionlocal = db_mod.SessionLocal
    yield
    db_mod.engine = orig_engine
    db_mod.SessionLocal = orig_sessionlocal


def test_database_url_default_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(db_mod)
    assert db_mod.DATABASE_URL == "sqlite:///./smos.db"
    assert db_mod.engine.dialect.name == "sqlite"


def test_database_url_respects_env(monkeypatch):
    custom_url = "sqlite:///./test_custom.db"
    monkeypatch.setenv("DATABASE_URL", custom_url)
    importlib.reload(db_mod)
    assert db_mod.DATABASE_URL == custom_url
    assert db_mod.engine.dialect.name == "sqlite"


def test_sqlite_connect_args(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./smos.db")
    importlib.reload(db_mod)
    assert db_mod.engine.dialect.name == "sqlite"


def test_lifespan_calls_init_db():
    mock_init = MagicMock()
    with patch("smos.core.init_db.init_db", mock_init):
        with TestClient(app):
            pass
    mock_init.assert_called_once()


def test_env_example_exists():
    env_example_path = Path(".env.example")
    assert env_example_path.exists()
    content = env_example_path.read_text(encoding="utf-8")
    assert "DATABASE_URL=sqlite:///./smos.db" in content
