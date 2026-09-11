from smos.core.database import SessionLocal
from smos.models.models import MemoryNode, User, Timeline, TimelineType
from smos.services.epistemic_service import EpistemicService


def test_epistemic_service():
    db = SessionLocal()

    user = User(display_name="Epistemic User")
    db.add(user)
    db.commit()
    db.refresh(user)

    tl = Timeline(type=TimelineType.REAL, description="Main")
    db.add(tl)
    db.commit()
    db.refresh(tl)

    node = MemoryNode(
        content="Ancient aliens built the pyramids",
        owner_id=user.id,
        timeline_id=tl.id,
    )
    db.add(node)
    db.commit()
    db.refresh(node)

    svc = EpistemicService(db)
    layer = svc.create_layer("MYTHOLOGY", 0.1, "TRADITIONAL")

    updated_node = svc.assign_to_layer(node.id, layer.id, "Beyond All Consensus")
    assert layer.id in updated_node.layer_ids
    assert updated_node.epistemic_status == "Beyond All Consensus"

    bc_nodes = svc.get_beyond_consensus_nodes()
    assert len(bc_nodes) > 0

    db.close()


if __name__ == "__main__":
    test_epistemic_service()
