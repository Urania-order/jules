from smos.core.database import SessionLocal
from smos.models.entities import Cosmonaut, BehaviorProfile
from smos.services.translator_service import TranslatorService

def test_translator_service():
    db = SessionLocal()

    c = Cosmonaut(name="Sender", type="HUMAN")
    p = BehaviorProfile(name="Phlegmatic")
    db.add_all([c, p])
    db.commit()

    svc = TranslatorService(db)
    trans = svc.translate_message(c.id, p.id, "Hurry up!")
    assert "Translated" in trans.suggested_rewrite

    mediation = svc.mediate_conflict("Slow", "Fast")
    assert "neutral_ground" in mediation

    db.close()

if __name__ == "__main__":
    test_translator_service()
