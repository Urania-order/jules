"""
Four-Position Analysis Service.

Projects canonical Phenomenon₀ and existing analytical evidence into the
Four-Position Analysis contract defined by TASK 24.

This service is an ORCHESTRATION / PROJECTION layer.
It is NOT a new reasoning engine and DOES NOT invent conclusions
unsupported by canonical evidence.

Positions for hypothesis/phenomenon H:
  I.   PRESENT_EXISTS  "What would exist / happen if H exists?"
  II.  ABSENT_ABSENT   "What would NOT exist / happen if H does NOT exist?"
  III. ABSENT_EXISTS   "What would exist / happen if H does NOT exist?"
  IV.  PRESENT_ABSENT  "What would NOT exist / happen if H exists?"

READ-ONLY GUARANTEE:
  build_analysis() NEVER creates or modifies any persistent models or graph edges.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
import enum

from smos.models.models import RelationType, EpistemicStatus
from smos.models.phenomenon import Phenomenon
from smos.models.context import Context
from smos.models.constraint import Constraint
from smos.models.potential import PotentialPhenomenon
from smos.models.four_position_contract import (
    FourPosition,
    normalize_four_position_analysis,
)
import logging
from smos.services.domain_relation_service import DomainRelationService
from smos.services.emergence_analysis_service import EmergenceAnalysisService
from smos.services.blockage_analysis_service import BlockageAnalysisService
from smos.services.semantic_search_service import SemanticSearchService
from smos.services.embedding_fallback import HashFallbackAdapter

logger = logging.getLogger(__name__)


class FourPositionService:
    """Orchestration service projecting canonical state into Four-Position analysis."""

    DEFAULT_CANDIDATE_ENTITY_TYPES = [
        "phenomenon",
        "context",
        "constraint",
        "potential_phenomenon",
    ]

    POSITION_I_RELATION_TYPES = (
        RelationType.CAUSES,
        RelationType.ENABLES,
        RelationType.TRANSFORMS,
        RelationType.CREATES_CONTEXT,
        RelationType.CHANGES_CONTEXT,
        RelationType.AMPLIFIES,
        RelationType.SUPPORTS,
    )

    POSITION_II_RELATION_TYPES = (
        RelationType.REQUIRES,
        RelationType.DEPENDS_ON,
        RelationType.EMERGES_FROM,
    )

    POSITION_III_RELATION_TYPES = (
        RelationType.ALTERNATIVE_TO,
    )

    POSITION_IV_RELATION_TYPES = (
        RelationType.BLOCKS,
        RelationType.PREVENTS,
        RelationType.SUPPRESSES,
        RelationType.CONTRADICTS,
        RelationType.SOLVES,
    )

    def __init__(
        self,
        db: Session,
        domain_service: Optional[DomainRelationService] = None,
        emergence_service: Optional[EmergenceAnalysisService] = None,
        blockage_service: Optional[BlockageAnalysisService] = None,
        semantic_service: Optional[SemanticSearchService] = None,
    ):
        self.db = db
        self.domain_service = domain_service or DomainRelationService(db)
        self.emergence_service = emergence_service or EmergenceAnalysisService(
            db, self.domain_service
        )
        self.blockage_service = blockage_service or BlockageAnalysisService(
            db, self.domain_service
        )
        self.semantic_service = semantic_service or SemanticSearchService(
            db, HashFallbackAdapter()
        )

    def build_analysis(
        self,
        phenomenon_id: int,
        include_semantic: bool = False,
    ) -> Dict[str, Any]:
        """Build Four-Position analysis for a phenomenon. READ-ONLY projection."""
        phenomenon = (
            self.db.query(Phenomenon)
            .filter(Phenomenon.id == phenomenon_id)
            .first()
        )

        if not phenomenon:
            analysis = {
                "phenomenon_id": phenomenon_id,
                "positions": {
                    pos.value: self._build_unresolved_position(pos.value)
                    for pos in FourPosition
                },
                "created_at": None,
            }
            return normalize_four_position_analysis(analysis)

        p_name = phenomenon.name

        # Query outgoing and incoming domain relations for this phenomenon
        outgoing_rels = sorted(
            self.domain_service.list_for("phenomenon", phenomenon_id),
            key=lambda r: r.id,
        )
        incoming_rels = sorted(
            self.domain_service.list_into("phenomenon", phenomenon_id),
            key=lambda r: r.id,
        )

        pos_i = self._resolve_position_i(phenomenon_id, p_name, outgoing_rels)
        pos_ii = self._resolve_position_ii(phenomenon_id, p_name, incoming_rels)
        pos_iii = self._resolve_position_iii(phenomenon_id, p_name, outgoing_rels, incoming_rels)
        pos_iv = self._resolve_position_iv(phenomenon_id, p_name, outgoing_rels)

        analysis = {
            "phenomenon_id": phenomenon_id,
            "positions": {
                FourPosition.PRESENT_EXISTS.value: pos_i,
                FourPosition.ABSENT_ABSENT.value: pos_ii,
                FourPosition.ABSENT_EXISTS.value: pos_iii,
                FourPosition.PRESENT_ABSENT.value: pos_iv,
            },
            "created_at": phenomenon.created_at.isoformat() if phenomenon.created_at else None,
        }

        if include_semantic:
            try:
                neighbors = self.semantic_service.similar(
                    "phenomenon",
                    phenomenon_id,
                    entity_types=self.DEFAULT_CANDIDATE_ENTITY_TYPES,
                )
                analysis.setdefault("provenance", {})
                if "semantic_candidates" not in analysis["provenance"]:
                    analysis["provenance"]["semantic_candidates"] = neighbors
            except Exception as e:
                logger.warning(
                    "TASK 34: semantic retrieval for phenomenon %s failed: %s",
                    phenomenon_id,
                    e,
                )

        return normalize_four_position_analysis(analysis)

    def _resolve_position_i(
        self, phenomenon_id: int, p_name: str, outgoing_rels: List[Any]
    ) -> Dict[str, Any]:
        """Position I — PRESENT_EXISTS: H exists -> what exists/happens."""
        matching_rels = [
            r for r in outgoing_rels if r.relation_type in self.POSITION_I_RELATION_TYPES
        ]

        if not matching_rels:
            return self._build_unresolved_position(FourPosition.PRESENT_EXISTS.value)

        claims = []
        evidence_ids: Set[int] = set()
        context_ids: Set[int] = set()
        provenance: Dict[str, Any] = {}
        confidences: List[float] = []
        epistemic_statuses: List[str] = []

        for r in matching_rels:
            target_name = self._get_entity_name(r.target_type, r.target_id)
            rel_type_str = (
                r.relation_type.value
                if isinstance(r.relation_type, enum.Enum)
                else str(r.relation_type)
            )
            claims.append(f"{p_name} {rel_type_str.lower()} {target_name}")

            if r.id is not None:
                evidence_ids.add(r.id)
            if r.evidence:
                evidence_ids.update(r.evidence)

            if r.target_type == "context" and r.target_id is not None:
                context_ids.add(r.target_id)

            if r.confidence is not None:
                confidences.append(float(r.confidence))

            if r.epistemic_status:
                st_val = (
                    r.epistemic_status.value
                    if isinstance(r.epistemic_status, enum.Enum)
                    else str(r.epistemic_status)
                )
                epistemic_statuses.append(st_val)

            if r.provenance and isinstance(r.provenance, dict):
                provenance.update(r.provenance)

        claim_text = f"If {p_name} exists: " + "; ".join(claims) + "."
        status_val = self._select_epistemic_status(epistemic_statuses)

        return {
            "position": FourPosition.PRESENT_EXISTS.value,
            "claim": claim_text,
            "confidence": min(confidences) if confidences else None,
            "evidence": sorted(list(evidence_ids)),
            "context": sorted(list(context_ids)),
            "provenance": provenance,
            "epistemic_status": status_val,
            "status": "RESOLVED",
        }

    def _resolve_position_ii(
        self, phenomenon_id: int, p_name: str, incoming_rels: List[Any]
    ) -> Dict[str, Any]:
        """Position II — ABSENT_ABSENT: H absent -> what does not exist/happen."""
        matching_rels = [
            r for r in incoming_rels if r.relation_type in self.POSITION_II_RELATION_TYPES
        ]

        if not matching_rels:
            return self._build_unresolved_position(FourPosition.ABSENT_ABSENT.value)

        claims = []
        evidence_ids: Set[int] = set()
        context_ids: Set[int] = set()
        provenance: Dict[str, Any] = {}
        confidences: List[float] = []
        epistemic_statuses: List[str] = []

        for r in matching_rels:
            source_name = self._get_entity_name(r.source_type, r.source_id)
            rel_type_str = (
                r.relation_type.value
                if isinstance(r.relation_type, enum.Enum)
                else str(r.relation_type)
            )
            claims.append(f"{source_name} (which {rel_type_str.lower()} {p_name}) will not occur")

            if r.id is not None:
                evidence_ids.add(r.id)
            if r.evidence:
                evidence_ids.update(r.evidence)

            if r.source_type == "context" and r.source_id is not None:
                context_ids.add(r.source_id)

            if r.confidence is not None:
                confidences.append(float(r.confidence))

            if r.epistemic_status:
                st_val = (
                    r.epistemic_status.value
                    if isinstance(r.epistemic_status, enum.Enum)
                    else str(r.epistemic_status)
                )
                epistemic_statuses.append(st_val)

            if r.provenance and isinstance(r.provenance, dict):
                provenance.update(r.provenance)

        claim_text = f"If {p_name} does not exist: " + "; ".join(claims) + "."
        status_val = self._select_epistemic_status(epistemic_statuses)

        return {
            "position": FourPosition.ABSENT_ABSENT.value,
            "claim": claim_text,
            "confidence": min(confidences) if confidences else None,
            "evidence": sorted(list(evidence_ids)),
            "context": sorted(list(context_ids)),
            "provenance": provenance,
            "epistemic_status": status_val,
            "status": "RESOLVED",
        }

    def _resolve_position_iii(
        self,
        phenomenon_id: int,
        p_name: str,
        outgoing_rels: List[Any],
        incoming_rels: List[Any],
    ) -> Dict[str, Any]:
        """Position III — ABSENT_EXISTS: H absent -> what exists/happens instead."""
        matching_rels = [
            r for r in outgoing_rels if r.relation_type in self.POSITION_III_RELATION_TYPES
        ] + [
            r for r in incoming_rels if r.relation_type in self.POSITION_III_RELATION_TYPES
        ]

        if not matching_rels:
            return self._build_unresolved_position(FourPosition.ABSENT_EXISTS.value)

        claims = []
        evidence_ids: Set[int] = set()
        context_ids: Set[int] = set()
        provenance: Dict[str, Any] = {}
        confidences: List[float] = []
        epistemic_statuses: List[str] = []

        for r in matching_rels:
            other_type = r.target_type if r.source_type == "phenomenon" and r.source_id == phenomenon_id else r.source_type
            other_id = r.target_id if r.source_type == "phenomenon" and r.source_id == phenomenon_id else r.source_id
            other_name = self._get_entity_name(other_type, other_id)
            claims.append(f"alternative state {other_name} exists")

            if r.id is not None:
                evidence_ids.add(r.id)
            if r.evidence:
                evidence_ids.update(r.evidence)

            if other_type == "context" and other_id is not None:
                context_ids.add(other_id)

            if r.confidence is not None:
                confidences.append(float(r.confidence))

            if r.epistemic_status:
                st_val = (
                    r.epistemic_status.value
                    if isinstance(r.epistemic_status, enum.Enum)
                    else str(r.epistemic_status)
                )
                epistemic_statuses.append(st_val)

            if r.provenance and isinstance(r.provenance, dict):
                provenance.update(r.provenance)

        claim_text = f"If {p_name} does not exist: " + "; ".join(claims) + "."
        status_val = self._select_epistemic_status(epistemic_statuses)

        return {
            "position": FourPosition.ABSENT_EXISTS.value,
            "claim": claim_text,
            "confidence": min(confidences) if confidences else None,
            "evidence": sorted(list(evidence_ids)),
            "context": sorted(list(context_ids)),
            "provenance": provenance,
            "epistemic_status": status_val,
            "status": "RESOLVED",
        }

    def _resolve_position_iv(
        self, phenomenon_id: int, p_name: str, outgoing_rels: List[Any]
    ) -> Dict[str, Any]:
        """Position IV — PRESENT_ABSENT: H exists -> what does not exist/happen (displaced)."""
        matching_rels = [
            r for r in outgoing_rels if r.relation_type in self.POSITION_IV_RELATION_TYPES
        ]

        if not matching_rels:
            return self._build_unresolved_position(FourPosition.PRESENT_ABSENT.value)

        claims = []
        evidence_ids: Set[int] = set()
        context_ids: Set[int] = set()
        provenance: Dict[str, Any] = {}
        confidences: List[float] = []
        epistemic_statuses: List[str] = []

        for r in matching_rels:
            target_name = self._get_entity_name(r.target_type, r.target_id)
            rel_type_str = (
                r.relation_type.value
                if isinstance(r.relation_type, enum.Enum)
                else str(r.relation_type)
            )
            claims.append(f"{target_name} is displaced/prevented ({rel_type_str.lower()} by {p_name})")

            if r.id is not None:
                evidence_ids.add(r.id)
            if r.evidence:
                evidence_ids.update(r.evidence)

            if r.target_type == "context" and r.target_id is not None:
                context_ids.add(r.target_id)

            if r.confidence is not None:
                confidences.append(float(r.confidence))

            if r.epistemic_status:
                st_val = (
                    r.epistemic_status.value
                    if isinstance(r.epistemic_status, enum.Enum)
                    else str(r.epistemic_status)
                )
                epistemic_statuses.append(st_val)

            if r.provenance and isinstance(r.provenance, dict):
                provenance.update(r.provenance)

        claim_text = f"If {p_name} exists: " + "; ".join(claims) + "."
        status_val = self._select_epistemic_status(epistemic_statuses)

        return {
            "position": FourPosition.PRESENT_ABSENT.value,
            "claim": claim_text,
            "confidence": min(confidences) if confidences else None,
            "evidence": sorted(list(evidence_ids)),
            "context": sorted(list(context_ids)),
            "provenance": provenance,
            "epistemic_status": status_val,
            "status": "RESOLVED",
        }

    def _build_unresolved_position(self, position_name: str) -> Dict[str, Any]:
        """Return explicit UNRESOLVED position representation."""
        return {
            "position": position_name,
            "claim": None,
            "confidence": None,
            "evidence": [],
            "context": [],
            "provenance": {},
            "epistemic_status": EpistemicStatus.UNVALIDATED.value,
            "status": "UNRESOLVED",
        }

    def _get_entity_name(self, entity_type: str, entity_id: int) -> str:
        """Fetch human-readable name for an entity."""
        if entity_type == "phenomenon":
            p = self.db.query(Phenomenon).filter(Phenomenon.id == entity_id).first()
            if p:
                return p.name
        elif entity_type == "context":
            c = self.db.query(Context).filter(Context.id == entity_id).first()
            if c:
                return c.name
        elif entity_type == "constraint":
            c = self.db.query(Constraint).filter(Constraint.id == entity_id).first()
            if c:
                return c.name
        elif entity_type == "potential":
            p = self.db.query(PotentialPhenomenon).filter(PotentialPhenomenon.id == entity_id).first()
            if p:
                return p.phenomenon
        return f"{entity_type}:{entity_id}"

    def _select_epistemic_status(self, statuses: List[str]) -> str:
        """Preserve source epistemic status without promotion."""
        if not statuses:
            return EpistemicStatus.HYPOTHESIZED.value

        # If all source statuses are OBSERVED, keep OBSERVED
        if all(s == EpistemicStatus.OBSERVED.value for s in statuses):
            return EpistemicStatus.OBSERVED.value

        # Priority order for canonical statuses (conservative mapping)
        priority = [
            EpistemicStatus.REFUTED.value,
            EpistemicStatus.CONTESTED.value,
            EpistemicStatus.UNVALIDATED.value,
            EpistemicStatus.HYPOTHESIZED.value,
            EpistemicStatus.PREDICTED.value,
            EpistemicStatus.INFERRED.value,
            EpistemicStatus.OBSERVED.value,
        ]

        for p in priority:
            if p in statuses:
                return p

        return statuses[0]
