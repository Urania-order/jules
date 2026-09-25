"""
Emergence Analysis Service — PHENOMENON-CENTRIC emergence analysis.

Given a phenomenon_id, this service identifies the CONDITIONS under
which the phenomenon could emerge, from two read-only sources:
  (a) DomainRelation edges incident to the phenomenon (TASK 07),
  (b) PotentialPhenomenon records with matching phenomenon name (TASK 05).

IMPORTANT:
- This service is READ-ONLY.
- Output is POSSIBILITY ANALYSIS, NOT prediction. No forecast is
  produced. No probability is computed. Human review is required.
- Complementary to:
    * PhenomenonPerspective (TASK 08) — perspective answers
    * BlockageAnalysisService (TASK 11) — blockage focus
  This service focuses on CONDITIONS of emergence (modal).
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple
import enum
from sqlalchemy.orm import Session

from smos.models.models import RelationType, EpistemicStatus
from smos.models.phenomenon import Phenomenon
from smos.models.potential import PotentialPhenomenon, PotentialStatus
from smos.models.constraint import Constraint
from smos.models.context import Context
from smos.services.domain_relation_service import DomainRelationService


@dataclass
class EmergenceAnalysis:
    """Emergence analysis — POSSIBILITY, NOT prediction."""

    kind: str = "emergence_analysis"
    phenomenon_id: Optional[int] = None
    necessary_conditions: List[Dict[str, Any]] = field(default_factory=list)
    supporting_conditions: List[Dict[str, Any]] = field(default_factory=list)
    blocking_conditions: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    context_transitions: List[Dict[str, Any]] = field(default_factory=list)
    possible_downstream_effects: List[Dict[str, Any]] = field(default_factory=list)
    unknowns: List[Dict[str, Any]] = field(default_factory=list)
    epistemic_status: str = EpistemicStatus.HYPOTHESIZED.value
    note: str = (
        "Possibility analysis — NOT prediction. "
        "No forecast provided. Human review required."
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EmergenceAnalysisService:
    NECESSARY_RELATION_TYPES = (
        RelationType.REQUIRES,
    )
    SUPPORTING_RELATION_TYPES = (
        RelationType.ENABLES,
        RelationType.SUPPORTS,
        RelationType.AMPLIFIES,
    )
    BLOCKING_RELATION_TYPES = (
        RelationType.BLOCKS,
        RelationType.PREVENTS,
        RelationType.SUPPRESSES,
    )
    DEPENDENCY_RELATION_TYPES = (
        RelationType.DEPENDS_ON,
    )
    CONTEXT_TRANSITION_RELATION_TYPES = (
        RelationType.CHANGES_CONTEXT,
        RelationType.CREATES_CONTEXT,
    )
    DOWNSTREAM_RELATION_TYPES = (
        RelationType.CREATES_CONTEXT,
        RelationType.CHANGES_CONTEXT,
        RelationType.TRANSFORMS,
    )
    LOW_CONFIDENCE_THRESHOLD = 0.5

    def __init__(
        self,
        db: Session,
        domain_service: Optional[DomainRelationService] = None,
    ):
        self.db = db
        self.domain_service = domain_service or DomainRelationService(db)

    def analyze_emergence(self, phenomenon_id: int) -> EmergenceAnalysis:
        """Analyze emergence for a phenomenon. READ-ONLY."""
        phenomenon = (
            self.db.query(Phenomenon)
            .filter(Phenomenon.id == phenomenon_id)
            .first()
        )
        if not phenomenon:
            return EmergenceAnalysis(
                kind="emergence_analysis",
                phenomenon_id=phenomenon_id,
                necessary_conditions=[],
                supporting_conditions=[],
                blocking_conditions=[],
                dependencies=[],
                context_transitions=[],
                possible_downstream_effects=[],
                unknowns=[],
                epistemic_status=EpistemicStatus.HYPOTHESIZED.value,
                note=(
                    "Possibility analysis — NOT prediction. "
                    "No forecast provided. Human review required."
                ),
            )

        incoming = self._incoming(phenomenon_id)
        outgoing = self._outgoing(phenomenon_id)

        necessary = self._relations_by_type(incoming, self.NECESSARY_RELATION_TYPES)
        supporting = self._relations_by_type(incoming, self.SUPPORTING_RELATION_TYPES)
        blocking = self._relations_by_type(incoming, self.BLOCKING_RELATION_TYPES)
        deps = self._relations_by_type(outgoing, self.DEPENDENCY_RELATION_TYPES)

        context_trans = [
            rel for rel in self._relations_by_type(outgoing, self.CONTEXT_TRANSITION_RELATION_TYPES)
            if rel.get("target_type") == "context"
        ]
        downstream = self._relations_by_type(outgoing, self.DOWNSTREAM_RELATION_TYPES)

        # Integrate PotentialPhenomenon records by matching phenomenon name
        pp_records = self._potential_records_for(phenomenon.name)
        for pp in pp_records:
            status_str = (
                pp.status.value
                if isinstance(pp.status, enum.Enum)
                else str(pp.status)
            ) if pp.status else PotentialStatus.UNKNOWN.value

            req_conds = pp.required_conditions if pp.required_conditions is not None else []
            for item in req_conds:
                necessary.append({
                    "source": "potential_phenomenon",
                    "potential_id": pp.id,
                    "condition": item,
                    "status": status_str,
                })

            supp_ctxs = pp.supporting_contexts if pp.supporting_contexts is not None else []
            for item in supp_ctxs:
                supporting.append({
                    "source": "potential_phenomenon",
                    "potential_id": pp.id,
                    "context": item,
                    "status": status_str,
                })

            block_constraints = pp.blocking_constraints if pp.blocking_constraints is not None else []
            for item in block_constraints:
                blocking.append({
                    "source": "potential_phenomenon",
                    "potential_id": pp.id,
                    "constraint": item,
                    "status": status_str,
                })

            pp_deps = pp.dependencies if pp.dependencies is not None else []
            for item in pp_deps:
                deps.append({
                    "source": "potential_phenomenon",
                    "potential_id": pp.id,
                    "dependency": item,
                    "status": status_str,
                })

            exp_impacts = pp.expected_impacts if pp.expected_impacts is not None else []
            for item in exp_impacts:
                downstream.append({
                    "source": "potential_phenomenon",
                    "potential_id": pp.id,
                    "impact": item,
                    "status": status_str,
                })

        unknowns = self._unknowns(
            necessary, supporting, blocking, deps, context_trans, downstream
        )

        return EmergenceAnalysis(
            kind="emergence_analysis",
            phenomenon_id=phenomenon_id,
            necessary_conditions=necessary,
            supporting_conditions=supporting,
            blocking_conditions=blocking,
            dependencies=deps,
            context_transitions=context_trans,
            possible_downstream_effects=downstream,
            unknowns=unknowns,
            epistemic_status=EpistemicStatus.HYPOTHESIZED.value,
            note=(
                "Possibility analysis — NOT prediction. "
                "No forecast provided. Human review required."
            ),
        )

    def _incoming(self, phenomenon_id: int):
        return self.domain_service.list_into("phenomenon", phenomenon_id)

    def _outgoing(self, phenomenon_id: int):
        return self.domain_service.list_for("phenomenon", phenomenon_id)

    def _relations_by_type(self, relations: List[Any], types: Tuple[RelationType, ...]) -> List[Dict[str, Any]]:
        result = []
        for rel in relations:
            if rel.relation_type in types:
                enriched = self._enrich(rel)
                result.append(enriched)
        return result

    def _potential_records_for(self, phenomenon_name: str) -> List[PotentialPhenomenon]:
        return (
            self.db.query(PotentialPhenomenon)
            .filter(PotentialPhenomenon.phenomenon == phenomenon_name)
            .all()
        )

    def _enrich(self, relation: Any) -> Dict[str, Any]:
        rel_type_str = (
            relation.relation_type.value
            if isinstance(relation.relation_type, enum.Enum)
            else str(relation.relation_type)
        )
        data = {
            "relation_id": relation.id,
            "relation_type": rel_type_str,
            "source_type": relation.source_type,
            "source_id": relation.source_id,
            "target_type": relation.target_type,
            "target_id": relation.target_id,
            "confidence": relation.confidence,
            "evidence": relation.evidence if relation.evidence is not None else [],
        }

        # Enrich source or target entity info if source/target is constraint, context, phenomenon
        if relation.source_type == "constraint":
            c = self.db.query(Constraint).filter(Constraint.id == relation.source_id).first()
            if c:
                c_type = c.type.value if isinstance(c.type, enum.Enum) else str(c.type) if c.type else None
                data["constraint_name"] = c.name
                data["constraint_type"] = c_type
                data["strength"] = c.strength
        elif relation.source_type == "context":
            ctx = self.db.query(Context).filter(Context.id == relation.source_id).first()
            if ctx:
                data["context_name"] = ctx.name
        elif relation.source_type == "phenomenon":
            p = self.db.query(Phenomenon).filter(Phenomenon.id == relation.source_id).first()
            if p:
                data["source_phenomenon_name"] = p.name

        if relation.target_type == "constraint":
            c = self.db.query(Constraint).filter(Constraint.id == relation.target_id).first()
            if c:
                c_type = c.type.value if isinstance(c.type, enum.Enum) else str(c.type) if c.type else None
                data["target_constraint_name"] = c.name
                data["constraint_type"] = c_type
                data["strength"] = c.strength
        elif relation.target_type == "context":
            ctx = self.db.query(Context).filter(Context.id == relation.target_id).first()
            if ctx:
                data["context_name"] = ctx.name
        elif relation.target_type == "phenomenon":
            p = self.db.query(Phenomenon).filter(Phenomenon.id == relation.target_id).first()
            if p:
                data["target_phenomenon_name"] = p.name

        return data

    def _unknowns(self, *collections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unknowns = []
        seen = set()

        for col in collections:
            for item in col:
                rel_id = item.get("relation_id")
                if rel_id is not None:
                    if rel_id in seen:
                        continue

                    conf = item.get("confidence")
                    ev = item.get("evidence")

                    is_low_conf = (conf is None) or (conf < self.LOW_CONFIDENCE_THRESHOLD)
                    is_missing_ev = (ev is None) or (len(ev) == 0)

                    if is_low_conf or is_missing_ev:
                        seen.add(rel_id)
                        if is_low_conf and is_missing_ev:
                            reason = "low_confidence_and_missing_evidence"
                        elif is_low_conf:
                            reason = "low_confidence"
                        else:
                            reason = "missing_evidence"

                        unknowns.append(
                            {
                                "relation_id": rel_id,
                                "source_type": item.get("source_type"),
                                "source_id": item.get("source_id"),
                                "target_type": item.get("target_type"),
                                "target_id": item.get("target_id"),
                                "reason": reason,
                                "confidence": conf,
                                "threshold": self.LOW_CONFIDENCE_THRESHOLD,
                            }
                        )

        return unknowns
