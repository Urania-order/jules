"""
Blockage Analysis Service — PHENOMENON-CENTRIC blockage analysis.

Given a phenomenon_id, this service identifies constraints that
may block the phenomenon, using existing DomainRelation records
(TASK 07) and existing ontology models (TASK 02-04).

IMPORTANT:
- This service is READ-ONLY (no writes to relations or models).
- Output is ANALYSIS, NOT prescription. No intervention is
  recommended/provided. Human review is required for any action.
- Complementary to ConstraintPerspective (TASK 08), which is
  constraint-centric. This service is phenomenon-centric.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
import enum

from smos.models.models import RelationType, EpistemicStatus
from smos.models.constraint import Constraint, ConstraintType
from smos.models.context import Context
from smos.models.phenomenon import Phenomenon
from smos.services.domain_relation_service import DomainRelationService


@dataclass
class BlockageAnalysis:
    """Blockage analysis — ANALYSIS, NOT prescription."""

    kind: str = "blockage_analysis"
    phenomenon_id: Optional[int] = None
    direct_constraints: List[Dict[str, Any]] = field(default_factory=list)
    indirect_constraints: List[Dict[str, Any]] = field(default_factory=list)
    dependency_constraints: List[Dict[str, Any]] = field(default_factory=list)
    context_constraints: List[Dict[str, Any]] = field(default_factory=list)
    unknowns: List[Dict[str, Any]] = field(default_factory=list)
    epistemic_status: str = EpistemicStatus.HYPOTHESIZED.value
    note: str = (
        "Analysis only — NOT prescription. "
        "No intervention provided. Human review required."
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BlockageAnalysisService:
    BLOCKING_RELATION_TYPES = (
        RelationType.BLOCKS,
        RelationType.PREVENTS,
        RelationType.SUPPRESSES,
    )
    DEPENDENCY_RELATION_TYPES = (
        RelationType.REQUIRES,
        RelationType.DEPENDS_ON,
    )
    LOW_CONFIDENCE_THRESHOLD = 0.5

    def __init__(
        self,
        db: Session,
        domain_service: Optional[DomainRelationService] = None,
    ):
        self.db = db
        self.domain_service = domain_service or DomainRelationService(db)

    def analyze_blockage(
        self,
        phenomenon_id: int,
        indirect_max_hops: int = 2,
    ) -> BlockageAnalysis:
        """Analyze blockage for a phenomenon. READ-ONLY."""
        phenomenon = (
            self.db.query(Phenomenon)
            .filter(Phenomenon.id == phenomenon_id)
            .first()
        )
        if not phenomenon:
            return BlockageAnalysis(
                kind="blockage_analysis",
                phenomenon_id=phenomenon_id,
                direct_constraints=[],
                indirect_constraints=[],
                dependency_constraints=[],
                context_constraints=[],
                unknowns=[],
                epistemic_status=EpistemicStatus.HYPOTHESIZED.value,
                note=(
                    "Analysis only — NOT prescription. "
                    "No intervention provided. Human review required."
                ),
            )

        direct = self._direct_blocking_constraints(phenomenon_id)
        indirect = self._indirect_blocking_constraints(
            phenomenon_id, max_hops=indirect_max_hops
        )
        dependency = self._dependency_constraints(phenomenon_id)
        context = self._context_constraints(phenomenon_id, direct, indirect, dependency)
        unknowns = self._unknowns(direct, indirect, dependency)

        return BlockageAnalysis(
            kind="blockage_analysis",
            phenomenon_id=phenomenon_id,
            direct_constraints=direct,
            indirect_constraints=indirect,
            dependency_constraints=dependency,
            context_constraints=context,
            unknowns=unknowns,
            epistemic_status=EpistemicStatus.HYPOTHESIZED.value,
            note=(
                "Analysis only — NOT prescription. "
                "No intervention provided. Human review required."
            ),
        )

    def _get_constraint_info(self, constraint_id: int) -> Dict[str, Any]:
        """Fetch basic details of a Constraint."""
        c = (
            self.db.query(Constraint)
            .filter(Constraint.id == constraint_id)
            .first()
        )
        if not c:
            return {
                "constraint_name": None,
                "constraint_type": None,
                "strength": None,
                "evidence": [],
                "confidence": None,
            }
        c_type = (
            c.type.value if isinstance(c.type, enum.Enum) else str(c.type)
        ) if c.type else None
        return {
            "constraint_name": c.name,
            "constraint_type": c_type,
            "strength": c.strength,
            "evidence": c.evidence if c.evidence is not None else [],
            "confidence": c.confidence,
        }

    def _direct_blocking_constraints(
        self, phenomenon_id: int
    ) -> List[Dict[str, Any]]:
        """Constraints with BLOCKS/PREVENTS/SUPPRESSES -> phenomenon."""
        rels = self.domain_service.list_into("phenomenon", phenomenon_id)
        direct = []
        for rel in rels:
            if (
                rel.relation_type in self.BLOCKING_RELATION_TYPES
                and rel.source_type == "constraint"
            ):
                c_info = self._get_constraint_info(rel.source_id)
                confidence = (
                    rel.confidence
                    if rel.confidence is not None
                    else c_info["confidence"]
                )
                evidence = (
                    rel.evidence
                    if (rel.evidence is not None and len(rel.evidence) > 0)
                    else c_info["evidence"]
                )
                direct.append(
                    {
                        "constraint_id": rel.source_id,
                        "relation_type": (
                            rel.relation_type.value
                            if isinstance(rel.relation_type, enum.Enum)
                            else str(rel.relation_type)
                        ),
                        "confidence": confidence,
                        "evidence": evidence,
                        "constraint_name": c_info["constraint_name"],
                        "constraint_type": c_info["constraint_type"],
                        "strength": c_info["strength"],
                    }
                )
        return direct

    def _indirect_blocking_constraints(
        self, phenomenon_id: int, max_hops: int = 2
    ) -> List[Dict[str, Any]]:
        """Constraints blocking intermediates that block the phenomenon.

        Multi-hop paths (bounded by max_hops). Starts from phenomenon target
        and searches backwards along BLOCKING relations.
        """
        if max_hops < 2:
            return []

        indirect = []
        seen: Set[Tuple[int, str, int]] = set()

        hop1_rels = self.domain_service.list_into("phenomenon", phenomenon_id)
        queue = []

        for rel in hop1_rels:
            if rel.relation_type in self.BLOCKING_RELATION_TYPES:
                rel_type_str = (
                    rel.relation_type.value
                    if isinstance(rel.relation_type, enum.Enum)
                    else str(rel.relation_type)
                )
                conf = rel.confidence
                if rel.source_type == "phenomenon":
                    queue.append(
                        (
                            "phenomenon",
                            rel.source_id,
                            [rel_type_str],
                            [conf] if conf is not None else [],
                            {"type": "phenomenon", "id": rel.source_id},
                            2,
                        )
                    )

        while queue:
            target_type, target_id, path_types, confs, via, current_hop = queue.pop(0)

            if current_hop > max_hops:
                continue

            incoming_rels = self.domain_service.list_into(target_type, target_id)
            for rel in incoming_rels:
                if rel.relation_type in self.BLOCKING_RELATION_TYPES:
                    rel_type_str = (
                        rel.relation_type.value
                        if isinstance(rel.relation_type, enum.Enum)
                        else str(rel.relation_type)
                    )
                    new_path = [rel_type_str] + path_types
                    new_confs = list(confs)
                    if rel.confidence is not None:
                        new_confs.append(rel.confidence)

                    if rel.source_type == "constraint":
                        c_id = rel.source_id
                        key = (c_id, via["type"], via["id"])
                        if key not in seen:
                            seen.add(key)
                            c_info = self._get_constraint_info(c_id)
                            min_conf = min(new_confs) if new_confs else c_info["confidence"]
                            indirect.append(
                                {
                                    "constraint_id": c_id,
                                    "via": via,
                                    "path": new_path,
                                    "hops": current_hop,
                                    "confidence": min_conf,
                                    "evidence": rel.evidence if rel.evidence else c_info["evidence"],
                                    "constraint_name": c_info["constraint_name"],
                                    "constraint_type": c_info["constraint_type"],
                                    "strength": c_info["strength"],
                                }
                            )
                    elif rel.source_type == "phenomenon" and current_hop < max_hops:
                        queue.append(
                            (
                                "phenomenon",
                                rel.source_id,
                                new_path,
                                new_confs,
                                via,
                                current_hop + 1,
                            )
                        )

        return indirect

    def _dependency_constraints(self, phenomenon_id: int) -> List[Dict[str, Any]]:
        """Phenomenon -> REQUIRES/DEPENDS_ON -> X; X blocked by constraints."""
        deps = self.domain_service.list_for("phenomenon", phenomenon_id)
        dependency = []
        seen = set()

        for dep in deps:
            if dep.relation_type in self.DEPENDENCY_RELATION_TYPES:
                dep_type_str = (
                    dep.relation_type.value
                    if isinstance(dep.relation_type, enum.Enum)
                    else str(dep.relation_type)
                )

                if dep.target_type == "constraint":
                    c_id = dep.target_id
                    key = (c_id, "constraint", dep.target_id)
                    if key not in seen:
                        seen.add(key)
                        c_info = self._get_constraint_info(c_id)
                        conf = dep.confidence if dep.confidence is not None else c_info["confidence"]
                        ev = dep.evidence if dep.evidence else c_info["evidence"]
                        dependency.append(
                            {
                                "constraint_id": c_id,
                                "depends_via": {"type": "constraint", "id": dep.target_id},
                                "relation_type": dep_type_str,
                                "confidence": conf,
                                "evidence": ev,
                                "constraint_name": c_info["constraint_name"],
                                "constraint_type": c_info["constraint_type"],
                                "strength": c_info["strength"],
                            }
                        )
                else:
                    target_blockers = self.domain_service.list_into(
                        dep.target_type, dep.target_id
                    )
                    for rel in target_blockers:
                        if (
                            rel.relation_type in self.BLOCKING_RELATION_TYPES
                            and rel.source_type == "constraint"
                        ):
                            c_id = rel.source_id
                            key = (c_id, dep.target_type, dep.target_id)
                            if key not in seen:
                                seen.add(key)
                                c_info = self._get_constraint_info(c_id)
                                confs = [
                                    c for c in [dep.confidence, rel.confidence, c_info["confidence"]]
                                    if c is not None
                                ]
                                min_conf = min(confs) if confs else None
                                ev = rel.evidence if rel.evidence else c_info["evidence"]
                                dependency.append(
                                    {
                                        "constraint_id": c_id,
                                        "depends_via": {
                                            "type": dep.target_type,
                                            "id": dep.target_id,
                                        },
                                        "relation_type": dep_type_str,
                                        "confidence": min_conf,
                                        "evidence": ev,
                                        "constraint_name": c_info["constraint_name"],
                                        "constraint_type": c_info["constraint_type"],
                                        "strength": c_info["strength"],
                                    }
                                )
        return dependency

    def _context_constraints(
        self,
        phenomenon_id: int,
        direct: List[Dict[str, Any]],
        indirect: List[Dict[str, Any]],
        dependency: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Contexts hosting relevant constraints, or explicitly linked via DomainRelation."""
        context_map: Dict[int, Dict[str, Any]] = {}

        all_constraints = direct + indirect + dependency
        c_ids = {item["constraint_id"] for item in all_constraints if "constraint_id" in item}

        for c_id in c_ids:
            c = (
                self.db.query(Constraint)
                .filter(Constraint.id == c_id)
                .first()
            )
            if c and c.context:
                ctx_name = c.context
                matched_ctx = None
                if ctx_name.startswith("context:"):
                    try:
                        ctx_id = int(ctx_name.split(":", 1)[1])
                        matched_ctx = (
                            self.db.query(Context)
                            .filter(Context.id == ctx_id)
                            .first()
                        )
                    except ValueError:
                        pass
                if not matched_ctx:
                    matched_ctx = (
                        self.db.query(Context)
                        .filter(Context.name == ctx_name)
                        .first()
                    )

                if matched_ctx:
                    if matched_ctx.id not in context_map:
                        context_map[matched_ctx.id] = {
                            "context_id": matched_ctx.id,
                            "context_name": matched_ctx.name,
                            "reason": "hosts_constraint",
                            "constraint_ids": set(),
                        }
                    context_map[matched_ctx.id]["constraint_ids"].add(c_id)

            c_ctx_rels = self.domain_service.list(
                source_type="constraint",
                target_type="context",
            )
            for rel in c_ctx_rels:
                if rel.source_id == c_id:
                    matched_ctx = (
                        self.db.query(Context)
                        .filter(Context.id == rel.target_id)
                        .first()
                    )
                    if matched_ctx:
                        if matched_ctx.id not in context_map:
                            context_map[matched_ctx.id] = {
                                "context_id": matched_ctx.id,
                                "context_name": matched_ctx.name,
                                "reason": "hosts_constraint",
                                "constraint_ids": set(),
                            }
                        context_map[matched_ctx.id]["constraint_ids"].add(c_id)

        ctx_blocking_rels = self.domain_service.list_into("phenomenon", phenomenon_id)
        for rel in ctx_blocking_rels:
            if (
                rel.source_type == "context"
                and rel.relation_type in self.BLOCKING_RELATION_TYPES
            ):
                matched_ctx = (
                    self.db.query(Context)
                    .filter(Context.id == rel.source_id)
                    .first()
                )
                if matched_ctx:
                    if matched_ctx.id not in context_map:
                        context_map[matched_ctx.id] = {
                            "context_id": matched_ctx.id,
                            "context_name": matched_ctx.name,
                            "reason": "direct_block",
                            "constraint_ids": set(),
                        }

        result = []
        for ctx_id, item in context_map.items():
            result.append(
                {
                    "context_id": item["context_id"],
                    "context_name": item["context_name"],
                    "reason": item["reason"],
                    "constraint_ids": sorted(list(item["constraint_ids"])),
                }
            )
        return result

    def _unknowns(
        self,
        direct: List[Dict[str, Any]],
        indirect: List[Dict[str, Any]],
        dependency: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Constraints with low confidence OR missing evidence."""
        unknowns = []
        seen = set()

        all_items = direct + indirect + dependency
        for item in all_items:
            c_id = item.get("constraint_id")
            if not c_id or c_id in seen:
                continue

            conf = item.get("confidence")
            ev = item.get("evidence")

            is_low_conf = (conf is None) or (conf < self.LOW_CONFIDENCE_THRESHOLD)
            is_missing_ev = (ev is None) or (len(ev) == 0)

            if is_low_conf or is_missing_ev:
                seen.add(c_id)
                if is_low_conf and is_missing_ev:
                    reason = "low_confidence_and_missing_evidence"
                elif is_low_conf:
                    reason = "low_confidence"
                else:
                    reason = "missing_evidence"

                unknowns.append(
                    {
                        "constraint_id": c_id,
                        "reason": reason,
                        "confidence": conf,
                        "threshold": self.LOW_CONFIDENCE_THRESHOLD,
                    }
                )

        return unknowns
