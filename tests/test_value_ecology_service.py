import pytest
from smos.services.value_ecology_service import ValueEcologyService
from smos.models.models import MemoryNode, User, Timeline, TimelineType
from smos.models.ecology import ValueAssessment

def test_value_ecology_service_assess_knowledge_value(db):
    user = User(display_name="Eco User")
    db.add(user)
    tl = Timeline(type=TimelineType.REAL)
    db.add(tl)
    db.commit()

    node = MemoryNode(content="Sustainable Cooling System", owner_id=user.id, timeline_id=tl.id)
    db.add(node)
    db.commit()

    svc = ValueEcologyService(db)

    # First call: human_benefit=0.9, social_impact=0.8, assert knowledge_value == 0.72
    assessment1 = svc.assess_knowledge_value(node.id, 0.9, 0.8)
    assert assessment1.human_benefit == 0.9
    assert assessment1.social_impact == 0.8
    assert abs(assessment1.knowledge_value - 0.72) < 1e-9
    assessment1_id = assessment1.id

    # Second call: human_benefit=0.95, social_impact=0.85, assert knowledge_value == 0.8075
    assessment2 = svc.assess_knowledge_value(node.id, 0.95, 0.85)
    assert assessment2.human_benefit == 0.95
    assert assessment2.social_impact == 0.85
    assert abs(assessment2.knowledge_value - 0.8075) < 1e-9

    # Assert assessment ID is unchanged
    assert assessment2.id == assessment1_id

    # Assert count for that node is exactly 1
    count = db.query(ValueAssessment).filter(ValueAssessment.node_id == node.id).count()
    assert count == 1
