"""
Convergent Resonance Service — AGENT-LEVEL convergence detection.

IMPORTANT DISTINCTION:
- Knowledge-level resonance (smos/services/resonance_service.py stub):
    links between memory nodes / clusters (ecology).
- Agent-level resonance (THIS service):
    different roles + independent trajectories + converging hypothesis
    derived from ContextExposure records (TASK 09).

These two are ORTHOGONAL. This service does NOT modify:
- smos/services/resonance_service.py
- smos/models/epistemic.py (IntellectualCluster.resonance)
- smos/services/ecology_engine.py

Resonance is a candidate — NEVER auto-promoted to fact.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from sqlalchemy.orm import Session
from smos.models.context_exposure import ContextExposure, AgentType
from smos.models.models import EpistemicStatus
from smos.services.context_exposure_service import ContextExposureService
from smos.models.conclusion_contract import get_claim, get_confidence
from smos.services.semantic_search_service import SemanticSearchService
from smos.services.embedding_fallback import HashFallbackAdapter


@dataclass
class ResonanceCandidate:
    """Candidate resonance — NOT fact.

    Different roles + independent trajectories + converging hypothesis.
    Requires human review; never auto-becomes truth.
    """
    kind: str = "candidate_resonance"
    supporting_trajectories: List[Dict[str, Any]] = field(default_factory=list)
    shared_context: List[int] = field(default_factory=list)
    independent_contexts: List[List[int]] = field(default_factory=list)
    converging_conclusion: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    epistemic_status: str = EpistemicStatus.HYPOTHESIZED.value
    note: str = (
        "Candidate resonance — NOT fact. "
        "Requires human review; never auto-becomes truth."
    )
    generation_source: str = "exact_claim_match"
    semantic_candidates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _get_claim(conclusion: Optional[Dict[str, Any]]) -> str:
    return get_claim(conclusion).lower()


class ConvergentResonanceService:
    DEFAULT_MIN_AGENTS = 2
    DEFAULT_MAX_CONTEXT_OVERLAP = 0.5   # Jaccard <= 0.5 = independent
    DEFAULT_MIN_CONFIDENCE = 0.0

    def __init__(
        self,
        db: Session,
        semantic_service: Optional[SemanticSearchService] = None,
    ):
        self.db = db
        self.semantic_service = (
            semantic_service
            or SemanticSearchService(db, HashFallbackAdapter())
        )

    def jaccard(self, a: List[int], b: List[int]) -> float:
        """Jaccard index — 0.0 = disjoint, 1.0 = identical."""
        s1 = set(a or [])
        s2 = set(b or [])
        if not s1 and not s2:
            return 1.0
        union = s1.union(s2)
        if not union:
            return 0.0
        return len(s1.intersection(s2)) / len(union)

    def are_independent_trajectories(self, e1: ContextExposure, e2: ContextExposure, max_overlap: float) -> bool:
        """Different roles AND context Jaccard <= max_overlap.

        - If both roles present and equal: NOT independent (unless agent_type differs).
        - If context Jaccard > max_overlap: NOT independent.
        """
        diff_agent = (e1.role != e2.role) or (e1.agent_type != e2.agent_type)
        if not diff_agent:
            return False
        overlap = self.jaccard(e1.context_ids, e2.context_ids)
        return overlap <= max_overlap

    def conclusions_match(self, c1: Dict[str, Any], c2: Dict[str, Any]) -> bool:
        """Key-based conclusion match.

        Match if normalized claim text equal:
        c1.get("claim", "").strip().lower() == c2.get("claim", "").strip().lower()
        AND claim is non-empty.
        """
        claim1 = _get_claim(c1)
        claim2 = _get_claim(c2)
        return bool(claim1) and claim1 == claim2

    def detect(
        self,
        min_agents: int = DEFAULT_MIN_AGENTS,
        max_context_overlap: float = DEFAULT_MAX_CONTEXT_OVERLAP,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        limit: int = 500,
        include_semantic: bool = False,
    ) -> List[ResonanceCandidate]:
        """Detect candidate resonances. READ-ONLY.

        Algorithm:
        1. Fetch ContextExposure records (via ContextExposureService.list).
        2. Path 1: Group exposures by normalized conclusion claim (exact claim match).
        3. Path 2 (optional, if include_semantic=True):
           Use semantic_service.similar("context_exposure", exposure.id) to retrieve
           semantic neighbor references.
        4. ALL candidate groups must pass strict TASK 10 validation:
           - min_agents threshold
           - role diversity + independent trajectories (Jaccard <= max_context_overlap)
           - conclusions_match (TASK 10 rule, UNCHANGED)
           - TASK 10 confidence formula (UNCHANGED)
        5. Assign generation_source ("exact_claim_match", "semantic_neighbors", "both")
           and populate semantic_candidates references.
        6. Return sorted by confidence descending.
        """
        exposure_service = ContextExposureService(self.db)
        exposures = exposure_service.list(limit=limit)
        exposure_map = {e.id: e for e in exposures if e.id is not None}

        # Step 1: Group exposures by normalized conclusion claim
        groups: Dict[str, List[ContextExposure]] = {}
        for e in exposures:
            claim = _get_claim(e.conclusion)
            if claim:
                groups.setdefault(claim, []).append(e)

        exact_claim_claims = set()
        semantic_references_by_claim: Dict[str, List[Dict[str, Any]]] = {}

        # Step 2: Semantic candidate retrieval (if include_semantic=True)
        if include_semantic and self.semantic_service:
            for e in exposures:
                if e.id is None:
                    continue
                claim = _get_claim(e.conclusion)
                if not claim:
                    continue

                neighbors = self.semantic_service.similar(
                    "context_exposure",
                    e.id,
                    k=10,
                    entity_types=["context_exposure", "conclusion"],
                )

                for neighbor in neighbors:
                    neighbor_id = neighbor.get("entity_id")
                    neighbor_exp = exposure_map.get(neighbor_id)
                    if not neighbor_exp:
                        continue

                    # Strictly enforce TASK 10 conclusions_match rule
                    if self.conclusions_match(e.conclusion, neighbor_exp.conclusion):
                        ref = {
                            "entity_type": neighbor.get("entity_type"),
                            "entity_id": neighbor_id,
                            "similarity": neighbor.get("similarity"),
                            "model_name": neighbor.get("model_name"),
                        }
                        semantic_references_by_claim.setdefault(claim, []).append(ref)

        candidates: List[ResonanceCandidate] = []

        for claim, group in groups.items():
            if len(group) < min_agents:
                continue

            # Check for at least 1 pair of independent trajectories
            has_independent = False
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    if self.are_independent_trajectories(group[i], group[j], max_context_overlap):
                        has_independent = True
                        break
                if has_independent:
                    break

            if not has_independent:
                continue

            # Compute confidence (strictly TASK 10 formula)
            confidences = [
                conf
                for e in group
                if (conf := get_confidence(e.conclusion)) is not None
            ]
            base = sum(confidences) / len(confidences) if confidences else 0.5
            scaled = min(1.0, base * (len(group) / max(min_agents, 1)) ** 0.5)

            if scaled < min_confidence:
                continue

            # Determine generation_source and semantic_candidates
            claim_sem_refs = semantic_references_by_claim.get(claim, [])
            if claim_sem_refs:
                gen_source = "both" if claim in groups else "semantic_neighbors"
                # Deduplicate semantic references by (entity_type, entity_id, model_name)
                seen_refs = set()
                deduped_refs = []
                for ref in claim_sem_refs:
                    ref_key = (ref["entity_type"], ref["entity_id"], ref["model_name"])
                    if ref_key not in seen_refs:
                        seen_refs.add(ref_key)
                        deduped_refs.append(ref)
                sem_candidates = deduped_refs
            else:
                gen_source = "exact_claim_match"
                sem_candidates = []

            # Compute shared context (intersection of all context_ids in group)
            shared_set = set(group[0].context_ids or [])
            for e in group[1:]:
                shared_set.intersection_update(e.context_ids or [])
            shared_context = sorted(list(shared_set))

            independent_contexts = [sorted(list(e.context_ids or [])) for e in group]

            supporting_trajectories = [
                {
                    "agent_type": e.agent_type.value if isinstance(e.agent_type, AgentType) else str(e.agent_type),
                    "agent_id": e.agent_id,
                    "role": e.role,
                }
                for e in group
            ]

            converging_conclusion = group[0].conclusion if group and isinstance(group[0].conclusion, dict) else {}

            candidate = ResonanceCandidate(
                kind="candidate_resonance",
                supporting_trajectories=supporting_trajectories,
                shared_context=shared_context,
                independent_contexts=independent_contexts,
                converging_conclusion=converging_conclusion,
                confidence=scaled,
                epistemic_status=EpistemicStatus.HYPOTHESIZED.value,
                note=(
                    "Candidate resonance — NOT fact. "
                    "Requires human review; never auto-becomes truth."
                ),
                generation_source=gen_source,
                semantic_candidates=sem_candidates,
            )
            candidates.append(candidate)

        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates

    def detect_for_conclusion(
        self,
        conclusion_claim: str,
        min_agents: int = DEFAULT_MIN_AGENTS,
        max_context_overlap: float = DEFAULT_MAX_CONTEXT_OVERLAP,
        include_semantic: bool = False,
    ) -> Optional[ResonanceCandidate]:
        """Detect resonance for a specific conclusion claim."""
        target_claim = conclusion_claim.strip().lower()
        if not target_claim:
            return None

        candidates = self.detect(
            min_agents=min_agents,
            max_context_overlap=max_context_overlap,
            min_confidence=0.0,
            limit=500,
            include_semantic=include_semantic,
        )

        for c in candidates:
            claim = _get_claim(c.converging_conclusion)
            if claim == target_claim:
                return c

        return None
