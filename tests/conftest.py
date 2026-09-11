"""Pytest configuration: force SQLite in-memory before any smos import."""
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("SQLALCHEMY_SILENCE_UBER_WARNING", "1")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import smos.core.database as db_module

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

import smos.models.models  # noqa: F401, E402
import smos.models.goals  # noqa: F401, E402
import smos.models.consensus  # noqa: F401, E402
import smos.models.discussion  # noqa: F401, E402
import smos.models.cognitive  # noqa: F401, E402
import smos.models.entities  # noqa: F401, E402
import smos.models.experience  # noqa: F401, E402
import smos.models.epistemic  # noqa: F401, E402
import smos.models.discovery  # noqa: F401, E402
import smos.models.coevolution  # noqa: F401, E402
import smos.models.ecology  # noqa: F401, E402

db_module.Base.metadata.create_all(bind=_engine)
db_module.engine = _engine
db_module.SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_engine
)

import pytest  # noqa: E402


@pytest.fixture(scope="function")
def db():
    session = db_module.SessionLocal()
    try:
        yield session
    finally:
        session.close()
