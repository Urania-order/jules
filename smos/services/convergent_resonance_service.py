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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _get_claim(conclusion: Optional[Dict[str, Any]]) -> str:
    return get_claim(conclusion).lower()


class ConvergentResonanceService:
    DEFAULT_MIN_AGENTS = 2
    DEFAULT_MAX_CONTEXT_OVERLAP = 0.5   # Jaccard <= 0.5 = independent
    DEFAULT_MIN_CONFIDENCE = 0.0

    def __init__(self, db: Session):
        self.db = db

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
    ) -> List[ResonanceCandidate]:
        """Detect candidate resonances. READ-ONLY.

        Algorithm (minimal):
        1. Fetch ContextExposure records (via ContextExposureService.list).
        2. Group exposures by normalized conclusion claim.
        3. For each group with >= min_agents:
           a. Check that at least 2 agents have DIFFERENT roles
              (or DIFFERENT agent_type).
           b. Check that at least 2 agents have context Jaccard
              <= max_context_overlap (independent trajectories).
           c. Compute confidence from conclusions' confidence.
           d. Build ResonanceCandidate.
        4. Return sorted by confidence descending.
        """
        exposure_service = ContextExposureService(self.db)
        exposures = exposure_service.list(limit=limit)

        groups: Dict[str, List[ContextExposure]] = {}
        for e in exposures:
            claim = _get_claim(e.conclusion)
            if claim:
                groups.setdefault(claim, []).append(e)

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

            # Compute confidence
            confidences = [
                conf
                for e in group
                if (conf := get_confidence(e.conclusion)) is not None
            ]
            base = sum(confidences) / len(confidences) if confidences else 0.5
            scaled = min(1.0, base * (len(group) / max(min_agents, 1)) ** 0.5)

            if scaled < min_confidence:
                continue

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
            )
            candidates.append(candidate)

        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates

    def detect_for_conclusion(
        self,
        conclusion_claim: str,
        min_agents: int = DEFAULT_MIN_AGENTS,
        max_context_overlap: float = DEFAULT_MAX_CONTEXT_OVERLAP,
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
        )

        for c in candidates:
            claim = _get_claim(c.converging_conclusion)
            if claim == target_claim:
                return c

        return None
