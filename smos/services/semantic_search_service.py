import hashlib
from typing import List, Optional, Dict, Any
import numpy as np
from sqlalchemy.orm import Session

from smos.services.semantic_adapter import SemanticAdapter
from smos.models.semantic_index import SemanticIndexEntry

from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint
from smos.models.potential import PotentialPhenomenon
from smos.models.domain_relation import DomainRelation
from smos.models.prediction import Prediction
from smos.models.experience import Recipe
from smos.models.context_exposure import ContextExposure
from smos.models.conclusion_contract import get_claim, get_confidence


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Computes deterministic cosine similarity between two numeric vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    arr_a = np.array(a, dtype=float)
    arr_b = np.array(b, dtype=float)
    norm_a = np.linalg.norm(arr_a)
    norm_b = np.linalg.norm(arr_b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))


def build_canonical_semantic_text(entity_type: str, entity: Any) -> str:
    """Builds a minimal, deterministic text representation for a canonical entity.

    Excludes technical database IDs, timestamps, and unstable provenance fields.
    """
    etype = entity_type.lower().strip()

    if etype == "phenomenon":
        name = getattr(entity, "name", "")
        desc = getattr(entity, "description", "") or ""
        status = getattr(entity, "epistemic_status", "") or ""
        return f"Phenomenon: {name}\nDescription: {desc}\nStatus: {status}".strip()

    elif etype == "context":
        name = getattr(entity, "name", "")
        desc = getattr(entity, "description", "") or ""
        return f"Context: {name}\nDescription: {desc}".strip()

    elif etype == "constraint":
        name = getattr(entity, "name", "")
        desc = getattr(entity, "description", "") or ""
        ctype = getattr(entity, "type", "") or ""
        return f"Constraint: {name}\nType: {ctype}\nDescription: {desc}".strip()

    elif etype in ("potential", "potential_phenomenon"):
        phenom = getattr(entity, "phenomenon", "")
        status = getattr(entity, "status", "") or ""
        return f"Potential Phenomenon: {phenom}\nStatus: {status}".strip()

    elif etype == "domain_relation":
        stype = getattr(entity, "source_type", "")
        sid = getattr(entity, "source_id", "")
        rtype = getattr(entity, "relation_type", "")
        ttype = getattr(entity, "target_type", "")
        tid = getattr(entity, "target_id", "")
        desc = getattr(entity, "description", "") or ""
        return f"Domain Relation: {stype}:{sid} {rtype} {ttype}:{tid}\nDescription: {desc}".strip()

    elif etype == "prediction":
        expected = getattr(entity, "expected_state", "")
        conds = getattr(entity, "conditions", "") or ""
        status = getattr(entity, "epistemic_status", "") or ""
        return f"Prediction: {expected}\nConditions: {conds}\nStatus: {status}".strip()

    elif etype == "recipe":
        title = getattr(entity, "title", getattr(entity, "name", ""))
        desc = getattr(entity, "description", "") or ""
        return f"Recipe: {title}\nDescription: {desc}".strip()

    elif etype in ("conclusion", "context_exposure"):
        conclusion = getattr(entity, "conclusion", {})
        if not isinstance(conclusion, dict) and hasattr(entity, "to_dict"):
            # If entity is not a dict or context exposure itself
            conclusion = getattr(entity, "conclusion", {})
        claim = get_claim(conclusion)
        conf = get_confidence(conclusion)
        if conf is not None:
            return f"Conclusion: {claim}\nConfidence: {conf}".strip()
        return f"Conclusion: {claim}".strip()

    # Generic fallback using attributes if present
    name_val = getattr(entity, "name", getattr(entity, "title", str(entity)))
    desc_val = getattr(entity, "description", "")
    return f"{entity_type}: {name_val}\nDescription: {desc_val}".strip()


class SemanticSearchService:
    """Service providing derived semantic indexing, similarity search, and retrieval.

    Operates purely on derived SemanticIndexEntry records without mutating canonical entities,
    creating relations, or altering epistemic status.
    """

    def __init__(self, db: Session, adapter: SemanticAdapter):
        self.db = db
        self.adapter = adapter

    def _hash_text(self, text: str) -> str:
        text_bytes = (text or "").encode("utf-8")
        return hashlib.sha256(text_bytes).hexdigest()

    def index(self, entity_type: str, entity_id: int, text: str) -> None:
        """Indexes or updates a vector representation for a polymorphic entity reference."""
        etype = entity_type.lower().strip()
        text_hash = self._hash_text(text)

        entry = (
            self.db.query(SemanticIndexEntry)
            .filter(
                SemanticIndexEntry.entity_type == etype,
                SemanticIndexEntry.entity_id == entity_id,
                SemanticIndexEntry.model_name == self.adapter.model_name,
            )
            .first()
        )

        if entry and entry.text_hash == text_hash:
            # Entry is already up to date for this exact model and text content
            return

        vector = self.adapter.embed(text)

        if entry:
            entry.text_hash = text_hash
            entry.vector = vector
            entry.dimension = self.adapter.dimension
        else:
            entry = SemanticIndexEntry(
                entity_type=etype,
                entity_id=entity_id,
                text_hash=text_hash,
                vector=vector,
                dimension=self.adapter.dimension,
                model_name=self.adapter.model_name,
            )
            self.db.add(entry)

        self.db.commit()

    def index_canonical(self, entity_type: str, entity_id: int) -> None:
        """Indexes a canonical domain entity by building its deterministic semantic text representation."""
        etype = entity_type.lower().strip()
        entity = None

        if etype == "phenomenon":
            entity = self.db.query(Phenomenon).filter(Phenomenon.id == entity_id).first()
        elif etype == "context":
            entity = self.db.query(Context).filter(Context.id == entity_id).first()
        elif etype == "constraint":
            entity = self.db.query(Constraint).filter(Constraint.id == entity_id).first()
        elif etype in ("potential", "potential_phenomenon"):
            entity = self.db.query(PotentialPhenomenon).filter(PotentialPhenomenon.id == entity_id).first()
        elif etype == "domain_relation":
            entity = self.db.query(DomainRelation).filter(DomainRelation.id == entity_id).first()
        elif etype == "prediction":
            entity = self.db.query(Prediction).filter(Prediction.id == entity_id).first()
        elif etype == "recipe":
            entity = self.db.query(Recipe).filter(Recipe.id == entity_id).first()
        elif etype in ("conclusion", "context_exposure"):
            entity = self.db.query(ContextExposure).filter(ContextExposure.id == entity_id).first()

        if not entity:
            raise ValueError(f"Canonical entity not found: {entity_type}:{entity_id}")

        semantic_text = build_canonical_semantic_text(etype, entity)
        self.index(etype, entity_id, semantic_text)

    def search(
        self,
        query: str,
        k: int = 10,
        entity_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Searches the semantic index for top-k entries closest to the query text."""
        query_vector = self.adapter.embed(query)

        query_builder = self.db.query(SemanticIndexEntry).filter(
            SemanticIndexEntry.model_name == self.adapter.model_name
        )

        if entity_types:
            norm_types = [t.lower().strip() for t in entity_types]
            query_builder = query_builder.filter(SemanticIndexEntry.entity_type.in_(norm_types))

        entries = query_builder.all()

        results = []
        for entry in entries:
            sim = cosine_similarity(query_vector, entry.vector)
            results.append({
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "similarity": sim,
                "model_name": entry.model_name,
            })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:k]

    def similar(
        self,
        entity_type: str,
        entity_id: int,
        k: int = 10,
        entity_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Returns top-k neighboring entries similar to the specified entity, excluding self."""
        etype = entity_type.lower().strip()

        target_entry = (
            self.db.query(SemanticIndexEntry)
            .filter(
                SemanticIndexEntry.entity_type == etype,
                SemanticIndexEntry.entity_id == entity_id,
                SemanticIndexEntry.model_name == self.adapter.model_name,
            )
            .first()
        )

        if not target_entry:
            return []

        target_vector = target_entry.vector

        query_builder = self.db.query(SemanticIndexEntry).filter(
            SemanticIndexEntry.model_name == self.adapter.model_name,
            ~(
                (SemanticIndexEntry.entity_type == etype)
                & (SemanticIndexEntry.entity_id == entity_id)
            ),
        )

        if entity_types:
            norm_types = [t.lower().strip() for t in entity_types]
            query_builder = query_builder.filter(SemanticIndexEntry.entity_type.in_(norm_types))

        entries = query_builder.all()

        results = []
        for entry in entries:
            sim = cosine_similarity(target_vector, entry.vector)
            results.append({
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "similarity": sim,
                "model_name": entry.model_name,
            })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:k]

    def delete(self, entity_type: str, entity_id: int) -> bool:
        """Deletes index entries for a specific entity reference."""
        etype = entity_type.lower().strip()
        entries = (
            self.db.query(SemanticIndexEntry)
            .filter(
                SemanticIndexEntry.entity_type == etype,
                SemanticIndexEntry.entity_id == entity_id,
            )
            .all()
        )

        if not entries:
            return False

        for entry in entries:
            self.db.delete(entry)

        self.db.commit()
        return True
