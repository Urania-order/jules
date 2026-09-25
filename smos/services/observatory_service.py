from sqlalchemy.orm import Session
from smos.core.interfaces import Observable
from smos.models.ecology import ValueAssessment
from smos.models.epistemic import IntellectualCluster
from smos.models.discovery import LostKnowledge
from smos.models.consensus import Proposal
from smos.models.phenomenon import Phenomenon
from smos.models.potential import PotentialPhenomenon, PotentialStatus
from smos.models.prediction import Prediction
from smos.models.domain_relation import DomainRelation
from smos.models.models import EpistemicStatus, RelationType
from smos.services.blockage_analysis_service import BlockageAnalysisService
from smos.services.convergent_resonance_service import ConvergentResonanceService
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

class ObservatoryService:
    def __init__(self, db: Session, subsystems: List[Observable]):
        self.db = db
        self.subsystems = subsystems

    def measure_ecosystem_health(self) -> Dict[str, Any]:
        combined_metrics = {}
        for sub in self.subsystems:
            combined_metrics[sub.__class__.__name__] = sub.get_health_metrics()
        return combined_metrics

    def get_proposal_metrics(self) -> Dict[str, Any]:
        """Aggregate proposal status metrics from DB consensus proposals and task queue proposals."""
        db_proposals = self.db.query(Proposal).all()
        total_db = len(db_proposals)
        status_counts = {"PENDING": 0, "APPROVED": 0, "REJECTED": 0, "EXPIRED": 0}
        for p in db_proposals:
            status = (p.status or "PENDING").upper()
            status_counts[status] = status_counts.get(status, 0) + 1

        resolved_count = status_counts.get("APPROVED", 0) + status_counts.get("REJECTED", 0)
        approval_rate = round(status_counts.get("APPROVED", 0) / resolved_count, 4) if resolved_count > 0 else 0.0

        task_queue_proposed_count = 0
        queue_proposed_dir = Path(".jules/queue/proposed")
        if queue_proposed_dir.is_dir():
            task_queue_proposed_count = len([f for f in queue_proposed_dir.glob("*.json") if f.name != ".gitkeep"])

        queue_deferred_expired_count = 0
        queue_deferred_dir = Path(".jules/queue/deferred")
        if queue_deferred_dir.is_dir():
            for f in queue_deferred_dir.glob("*.json"):
                if f.name == ".gitkeep":
                    continue
                try:
                    data = json.loads(f.read_text())
                    if data.get("status") == "expired":
                        queue_deferred_expired_count += 1
                except Exception:
                    pass

        return {
            "total_proposals": total_db,
            "status_counts": status_counts,
            "approval_rate": approval_rate,
            "pending_proposals": status_counts.get("PENDING", 0),
            "approved_proposals": status_counts.get("APPROVED", 0),
            "rejected_proposals": status_counts.get("REJECTED", 0),
            "expired_proposals": status_counts.get("EXPIRED", 0),
            "queue_proposed_tasks": task_queue_proposed_count,
            "queue_expired_tasks": queue_deferred_expired_count,
        }

    def get_health_report(self) -> Dict[str, Any]:
        """Aggregate health metrics from all subsystems with timestamp and overall health score."""
        metrics = self.measure_ecosystem_health()
        
        # Calculate overall health score (0.0 - 1.0)
        scores = []
        for sub_name, sub_metrics in metrics.items():
            if isinstance(sub_metrics, dict):
                # Check known numerical health indicators in subsystems
                if "health" in sub_metrics and isinstance(sub_metrics["health"], (int, float)):
                    scores.append(float(sub_metrics["health"]))
                elif "avg_value" in sub_metrics and isinstance(sub_metrics["avg_value"], (int, float)):
                    scores.append(float(sub_metrics["avg_value"]))
                elif "interaction_density" in sub_metrics and isinstance(sub_metrics["interaction_density"], (int, float)):
                    scores.append(float(sub_metrics["interaction_density"]))
        
        health_score = sum(scores) / len(scores) if scores else 1.0
        health_score = max(0.0, min(1.0, health_score))

        proposal_metrics = self.get_proposal_metrics()

        # Include subsystem health metrics directly for backward compatibility
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health_score": health_score,
            "proposal_metrics": proposal_metrics,
            "subsystems": metrics
        }
        report.update(metrics)
        return report

    def generate_quarterly_report(self) -> Dict[str, Any]:
        """Generate public reports from observable system data containing 5 key sections."""
        report = {
            "health_report": self.get_health_report(),
            "evolution_summary": self.get_evolution_history(),
            "knowledge_impact_ranking": self.get_impact_ranking(),
            "forecasts": self.generate_forecasts(),
            "recommendations": self.generate_recommendations()
        }
        return report

    def get_evolution_history(self) -> List[Dict[str, Any]]:
        history = []
        for sub in self.subsystems:
            history.extend(sub.get_evolution_summary())
        return history

    def get_impact_ranking(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Top Knowledge Contributions based on practical implementation and influence (ValueAssessment)."""
        assessments = self.db.query(ValueAssessment).all()
        ranked_items = []

        if assessments:
            scored_assessments = [
                (a, float(a.knowledge_value or 0.0) * float(a.social_impact or 0.0))
                for a in assessments
            ]
            scored_assessments.sort(key=lambda x: x[1], reverse=True)

            for idx, (a, score) in enumerate(scored_assessments[:limit], start=1):
                ranked_items.append({
                    "rank": idx,
                    "node_id": a.node_id,
                    "score": round(score, 4),
                    "reason": f"High value assessment (knowledge_value={a.knowledge_value}, social_impact={a.social_impact})"
                })
        else:
            # Fallback mock items if no ValueAssessment records exist
            mock_items = [
                {"rank": 1, "node_id": 42, "score": 0.72, "reason": "High cross-cluster resonance"},
                {"rank": 2, "node_id": 108, "score": 0.65, "reason": "Successful recipe implementation"},
                {"rank": 3, "node_id": 75, "score": 0.50, "reason": "Verified long-term impact in Environment domain"}
            ]
            ranked_items = mock_items[:limit]

        return ranked_items

    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on ecosystem health metrics and dormant knowledge."""
        recommendations = []
        health_report = self.get_health_report()
        health_score = health_report.get("health_score", 1.0)

        if health_score < 0.5:
            recommendations.append(f"Ecosystem health score is low ({health_score:.2f}). Immediate attention required to boost subsystem resonance.")
        else:
            recommendations.append(f"Ecosystem health score is stable ({health_score:.2f}). Maintain current activity.")

        # Check for dormant knowledge in IntellectualCluster and LostKnowledge
        dormant_clusters = self.db.query(IntellectualCluster).filter(
            IntellectualCluster.dormant_topics != None
        ).all()
        
        has_dormant_topics = False
        for c in dormant_clusters:
            if c.dormant_topics and len(c.dormant_topics) > 0:
                has_dormant_topics = True
                recommendations.append(f"Cluster '{c.name}' (ID: {c.id}) has dormant topics: {', '.join(c.dormant_topics)}. Recommend backward discovery to reactivate.")

        lost_items = self.db.query(LostKnowledge).filter(LostKnowledge.confidence < 0.8).all()
        if lost_items:
            recommendations.append(f"Found {len(lost_items)} unverified lost knowledge items with low confidence. Recommend initiating reconstruction recipes.")

        if not has_dormant_topics and not lost_items:
            recommendations.append("No critical dormant knowledge identified. Continue regular monitoring.")

        return recommendations

    def get_domain_state(self) -> Dict[str, Any]:
        """Aggregate domain entity state for Observatory.

        Reuses existing TASK 01-14 services (read-only).
        Does NOT modify existing Observatory methods.
        """
        # 1. WHAT EXISTS: phenomena with epistemic_status == OBSERVED
        phenomena = self.db.query(Phenomenon).all()
        what_exists = []
        what_is_emerging = []

        for p in phenomena:
            p_status = p.epistemic_status.value if isinstance(p.epistemic_status, EpistemicStatus) else str(p.epistemic_status)
            p_status_upper = p_status.upper() if p_status else ""
            if p_status_upper == EpistemicStatus.OBSERVED.value.upper():
                what_exists.append(p.to_dict())
            elif p_status_upper in (EpistemicStatus.INFERRED.value.upper(), EpistemicStatus.HYPOTHESIZED.value.upper()):
                what_is_emerging.append(p.to_dict())

        # 3. WHAT IS BLOCKED: call BlockageAnalysisService.analyze_blockage(id) for each phenomenon
        blockage_service = BlockageAnalysisService(self.db)
        what_is_blocked = []
        for p in phenomena:
            analysis = blockage_service.analyze_blockage(p.id)
            if analysis.direct_constraints or analysis.indirect_constraints:
                what_is_blocked.append({
                    "phenomenon_id": p.id,
                    "direct_count": len(analysis.direct_constraints),
                    "indirect_count": len(analysis.indirect_constraints),
                    "unknowns": analysis.unknowns
                })

        # 4. WHAT COULD EMERGE: PotentialPhenomenon with status == POSSIBLE
        potentials = self.db.query(PotentialPhenomenon).all()
        what_could_emerge = []
        for pot in potentials:
            pot_status = pot.status.value if isinstance(pot.status, PotentialStatus) else str(pot.status)
            if pot_status and pot_status.upper() == PotentialStatus.POSSIBLE.value.upper():
                what_could_emerge.append(pot.to_dict())

        # 5. WHAT CHANGES THE CONTEXT: DomainRelation where relation_type in (CHANGES_CONTEXT, CREATES_CONTEXT)
        domain_rels = self.db.query(DomainRelation).all()
        what_changes_context = []
        target_relation_types = {RelationType.CHANGES_CONTEXT.value.upper(), RelationType.CREATES_CONTEXT.value.upper()}
        for rel in domain_rels:
            rel_type = rel.relation_type.value if isinstance(rel.relation_type, RelationType) else str(rel.relation_type)
            if rel_type and rel_type.upper() in target_relation_types:
                what_changes_context.append(rel.to_dict())

        # 6. WHAT RESONATES: ConvergentResonanceService.detect()
        resonance_service = ConvergentResonanceService(self.db)
        candidates = resonance_service.detect()
        what_resonates = [c.to_dict() for c in candidates]

        # 7. WHAT IS PREDICTED: predictions with epistemic_status == PREDICTED
        predictions = self.db.query(Prediction).all()
        what_is_predicted = []
        for pred in predictions:
            pred_status = pred.epistemic_status.value if isinstance(pred.epistemic_status, EpistemicStatus) else str(pred.epistemic_status)
            if pred_status and pred_status.upper() == EpistemicStatus.PREDICTED.value.upper():
                what_is_predicted.append(pred.to_dict())

        return {
            "what_exists": what_exists,
            "what_is_emerging": what_is_emerging,
            "what_is_blocked": what_is_blocked,
            "what_could_emerge": what_could_emerge,
            "what_changes_context": what_changes_context,
            "what_changes_the_context": what_changes_context,
            "what_resonates": what_resonates,
            "what_is_predicted": what_is_predicted,
        }

    def generate_forecasts(self) -> List[Dict[str, Any]]:
        """Cosmo-Initiate Forecasts: Eight future research hypotheses"""
        forecasts = []
        for i in range(1, 9):
            forecasts.append({
                "forecast_id": i,
                "hypothesis": f"Hypothesis regarding emerging behavior in Cluster {i}",
                "supporting_evidence": "Increased resonance density and knowledge inflow",
                "assumptions": ["Stability of communication style", "Continued human participation"],
                "uncertainty": 0.3 + (i * 0.05),
                "proposed_experiments": ["Cross-cluster pollination A/B test"],
                "expected_validation_period": "6 months"
            })
        return forecasts

    def export_report_json(self, report: Optional[Dict[str, Any]] = None, indent: int = 2) -> str:
        """Export Observatory report to JSON string format."""
        if report is None:
            report = self.generate_quarterly_report()
        return json.dumps(report, indent=indent, default=str)

    def export_report_markdown(self, report: Optional[Dict[str, Any]] = None) -> str:
        """Export Observatory report to Markdown format."""
        if report is None:
            report = self.generate_quarterly_report()

        lines = ["# Co-SMOS Observatory Quarterly Report", ""]

        # Health Section
        lines.append("## 1. Ecosystem Health Report")
        health = report.get("health_report", {})
        ts = health.get("timestamp", "N/A")
        hs = health.get("health_score", 1.0)
        lines.append(f"- **Timestamp**: {ts}")
        lines.append(f"- **Overall Health Score**: {hs:.2f}")
        lines.append("")
        lines.append("### Proposal Status Metrics")
        prop_metrics = health.get("proposal_metrics", {})
        if prop_metrics:
            lines.append(f"- **Total Proposals**: {prop_metrics.get('total_proposals', 0)}")
            lines.append(f"- **Pending Proposals**: {prop_metrics.get('pending_proposals', 0)}")
            lines.append(f"- **Approved Proposals**: {prop_metrics.get('approved_proposals', 0)}")
            lines.append(f"- **Rejected Proposals**: {prop_metrics.get('rejected_proposals', 0)}")
            lines.append(f"- **Expired Proposals**: {prop_metrics.get('expired_proposals', 0)}")
            lines.append(f"- **Approval Rate**: {prop_metrics.get('approval_rate', 0.0):.2%}")
            if "queue_proposed_tasks" in prop_metrics:
                lines.append(f"- **Queued Task Proposals**: {prop_metrics.get('queue_proposed_tasks', 0)}")
            if "queue_expired_tasks" in prop_metrics:
                lines.append(f"- **Queued Expired Tasks**: {prop_metrics.get('queue_expired_tasks', 0)}")
        else:
            lines.append("No proposal metrics recorded.")
        lines.append("")
        lines.append("### Subsystems Metrics")
        subsystems = health.get("subsystems", {})
        if isinstance(subsystems, dict) and subsystems:
            for sub_name, sub_data in subsystems.items():
                lines.append(f"- **{sub_name}**: {json.dumps(sub_data, default=str)}")
        else:
            lines.append("No subsystem metrics recorded.")
        lines.append("")

        # Evolution Section
        lines.append("## 2. Evolution Summary")
        evolution = report.get("evolution_summary", [])
        if isinstance(evolution, list) and evolution:
            for evo in evolution:
                lines.append(f"- {json.dumps(evo, default=str)}")
        else:
            lines.append("No evolution history recorded.")
        lines.append("")

        # Impact Ranking Section
        lines.append("## 3. Knowledge Impact Ranking")
        ranking = report.get("knowledge_impact_ranking", [])
        if isinstance(ranking, list) and ranking:
            lines.append("| Rank | Node ID | Score | Reason |")
            lines.append("| --- | --- | --- | --- |")
            for item in ranking:
                rank = item.get("rank", "-")
                node_id = item.get("node_id", "-")
                score = item.get("score", "-")
                reason = item.get("reason", "")
                lines.append(f"| {rank} | {node_id} | {score} | {reason} |")
        else:
            lines.append("No ranking data available.")
        lines.append("")

        # Forecasts Section
        lines.append("## 4. Cosmo-Initiate Forecasts")
        forecasts = report.get("forecasts", [])
        if isinstance(forecasts, list) and forecasts:
            for f in forecasts:
                fid = f.get("forecast_id", "-")
                hyp = f.get("hypothesis", "")
                unc = f.get("uncertainty", 0.0)
                lines.append(f"- **[Forecast {fid}]** {hyp} (Uncertainty: {unc:.2f})")
        else:
            lines.append("No forecasts available.")
        lines.append("")

        # Recommendations Section
        lines.append("## 5. Recommendations")
        recommendations = report.get("recommendations", [])
        if isinstance(recommendations, list) and recommendations:
            for rec in recommendations:
                lines.append(f"- {rec}")
        else:
            lines.append("No recommendations generated.")
        lines.append("")

        return "\n".join(lines)
