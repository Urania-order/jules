"""Pytest configuration: force SQLite in-memory before any smos import."""
import importlib
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("SQLALCHEMY_SILENCE_UBER_WARNING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import smos.core.database as db_module
import smos.core.init_db as init_db_module

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

_MODEL_MODULES = [
    "smos.models.cognitive",
    "smos.models.coevolution",
    "smos.models.consensus",
    "smos.models.constraint",
    "smos.models.context",
    "smos.models.context_exposure",
    "smos.models.discovery",
    "smos.models.discussion",
    "smos.models.domain_event",
    "smos.models.domain_relation",
    "smos.models.ecology",
    "smos.models.entities",
    "smos.models.epistemic",
    "smos.models.experience",
    "smos.models.goals",
    "smos.models.models",
    "smos.models.phenomenon",
    "smos.models.potential",
    "smos.models.observation",
    "smos.models.prediction",
    "smos.models.semantic_index",
]


def _ensure_metadata_populated():
    if len(db_module.Base.metadata.tables) == 0:
        for mod_name in sorted(_MODEL_MODULES):
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])
            else:
                importlib.import_module(mod_name)


# Import all model modules initially
_ensure_metadata_populated()

db_module.Base.metadata.create_all(bind=_engine)
db_module.engine = _engine
db_module.SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_engine
)


@pytest.fixture(autouse=True, scope="function")
def _fresh_engine(monkeypatch):
    _ensure_metadata_populated()
    orig_engine = getattr(db_module.SessionLocal, "kw", {}).get("bind", db_module.engine)
    new_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db_module.Base.metadata.create_all(bind=new_engine)
    db_module.SessionLocal.configure(bind=new_engine)
    monkeypatch.setattr(db_module, "engine", new_engine)
    if hasattr(init_db_module, "engine"):
        monkeypatch.setattr(init_db_module, "engine", new_engine)

    # Seed default user for legacy tests expecting an existing user
    session = db_module.SessionLocal()
    try:
        user = sys.modules["smos.models.models"].User(display_name="Default User")
        session.add(user)
        session.commit()
    finally:
        session.close()

    try:
        yield new_engine
    finally:
        db_module.SessionLocal.configure(bind=orig_engine)
        new_engine.dispose()


@pytest.fixture(scope="function")
def db():
    session = db_module.SessionLocal()
    try:
        yield session
    finally:
        session.close()
