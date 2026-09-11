from sqlalchemy.orm import Session
from smos.models.coevolution import UnderstandingValidation, ComprehensionTest
from smos.models.epistemic import IntellectualCluster

class CoevolutionService:
    def __init__(self, db: Session):
        self.db = db

    def validate_understanding(self, agent_id: int, human_id: int, original: str, feedback: str):
        validation = UnderstandingValidation(
            agent_id=agent_id,
            human_id=human_id,
            original_interpretation=original,
            human_feedback=feedback,
            revised_interpretation=f"Revised: {original} considering {feedback}",
            confidence=0.8
        )
        self.db.add(validation)
        self.db.commit()
        self.db.refresh(validation)
        return validation

    def run_comprehension_test(self, llm_exp: str, human_exp: str):
        # Mock similarity score
        score = 0.85
        test = ComprehensionTest(
            llm_explanation=llm_exp,
            human_explanation=human_exp,
            similarity_score=score
        )
        self.db.add(test)
        self.db.commit()
        self.db.refresh(test)
        return test

    def sponsor_cluster(self, cluster_id: int, user_id: int):
        cluster = self.db.query(IntellectualCluster).get(cluster_id)
        if cluster:
            cluster.human_sponsor_id = user_id
            cluster.status = "ACTIVE"
            cluster.is_provisional = False
            self.db.commit()
        return cluster
