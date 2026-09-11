import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from smos.core.database import Base
from smos.models.models import MemoryNode, KnowledgeLifecycleState
from smos.services.ecology_engine import EcologyEngine
from smos.services.value_ecology_service import ValueEcologyService
from smos.services.commons_service import CommonsService
from smos.services.observatory_service import ObservatoryService

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    # Load all models
    from smos.models import models, goals, consensus, discussion, cognitive, entities, experience, epistemic, discovery, coevolution, ecology
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    yield db
    db.close()

def test_v09_observatory(db):
    eco = EcologyEngine(db)
    val = ValueEcologyService(db)
    com = CommonsService(db)
    obs = ObservatoryService(db, [eco, val, com])

    report = obs.generate_quarterly_report()
    assert "health_report" in report
    assert "EcologyEngine" in report["health_report"]
    assert "ValueEcologyService" in report["health_report"]
    assert "CommonsService" in report["health_report"]
    assert len(report["forecasts"]) == 8

def test_v09_commons_interaction(db):
    com = CommonsService(db)
    result = com.facilitate_collaboration(1, 2, "Develop new recipe")
    assert result["status"] == "active"
    assert result["facilitator"] == "Commons"
