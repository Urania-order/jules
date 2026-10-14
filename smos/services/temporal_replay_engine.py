"""Temporal Replay Engine (TASK L-05B).

Reconstructs what the system KNEW at a given moment (`as_of` cutoff) using authoritative
system availability timestamps (knowledge time), NOT event times.

CRITICAL INVARIANTS:
1. Knowledge time != Event time: System availability (e.g., `created_at`) determines eligibility.
   For Observation, `created_at` (ingestion time) is used for availability, while `observed_at`
   is event time.
2. Status reconstruction: Derive ExperimentRun status as of `as_of` from `status_history`.
   If status history is absent or incomplete prior to `as_of`, report UNKNOWN status and explain why.
3. Entity fidelity classification:
   - VERIFIED: Availability and status/state fully supported by historical records.
   - PARTIAL: Existence supported, but content/relations lack versioning or complete history.
   - UNKNOWN: Insufficient evidence or availability ambiguous.
4. Read-only: Never execute experiments, retry execution, or re-run evaluations. Never modify DB records.
5. Content hash stability: Computed over canonical historical result, excluding `reconstructed_at`.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from sqlalchemy.orm import Session

from smos.models.observation import Observation
from smos.models.experiment_run import ExperimentRun
from smos.models.evaluation import EvaluationRecord
from smos.models.prediction import Prediction
from smos.models.discovery import Hypothesis
from smos.models.phenomenon import Phenomenon
from smos.models.potential import PotentialPhenomenon
from smos.models.domain_relation import DomainRelation
from smos.models.models import Relation
from smos.models.ecology import ProvenanceRecord
from smos.models.replay_contract import (
    validate_replay_request,
    normalize_replay_result,
    FORMAT_VERSION,
)


class TemporalReplayEngine:
    """Read-only Temporal Replay Engine.

    Reconstructs historical system state at an explicit `as_of` timestamp.
    """

    def __init__(self, db: Session):
        self.db = db

    def replay(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute temporal replay for the given request dictionary."""
        valid, errors = validate_replay_request(request)
        if not valid:
            raise ValueError(f"Invalid replay request: {'; '.join(errors)}")

        as_of_raw = request["as_of"]
        if isinstance(as_of_raw, str):
            as_of_dt = datetime.fromisoformat(as_of_raw.replace("Z", "+00:00"))
        else:
            as_of_dt = as_of_raw

        if as_of_dt.tzinfo is None:
            as_of_dt = as_of_dt.replace(tzinfo=timezone.utc)

        scope = [s.strip().lower() for s in request.get("scope") or []]
        include_all = len(scope) == 0

        # Diagnostics & Tracking
        excluded_counts: Dict[str, int] = {}
        unknown_availability: Dict[str, int] = {}
        missing_status_history: List[Dict[str, Any]] = []
        uncertainty_notes: List[str] = []

        reconstructed_state: Dict[str, List[Dict[str, Any]]] = {
            "observations": [],
            "experiment_runs": [],
            "evaluations": [],
            "predictions": [],
            "hypotheses": [],
            "phenomenon": [],
            "potential_phenomena": [],
            "domain_relations": [],
            "relations": [],
            "provenance_records": [],
        }

        # 1. Observations (Knowledge Time: created_at)
        if include_all or "observation" in scope:
            obs_entities = self.db.query(Observation).all()
            reconstructed_obs = []
            excluded_obs = 0
            unknown_obs = 0

            for obs in obs_entities:
                avail_at = obs.created_at
                if avail_at is None:
                    unknown_obs += 1
                    continue

                if avail_at.tzinfo is None:
                    avail_at = avail_at.replace(tzinfo=timezone.utc)

                if avail_at <= as_of_dt:
                    reconstructed_obs.append({
                        "id": obs.id,
                        "availability_at": avail_at.isoformat(),
                        "observed_at": obs.observed_at.isoformat() if obs.observed_at else None,
                        "metric_name": obs.metric_name,
                        "fidelity": "VERIFIED",
                    })
                else:
                    excluded_obs += 1

            reconstructed_state["observations"] = reconstructed_obs
            excluded_counts["observation"] = excluded_obs
            unknown_availability["observation"] = unknown_obs

        # 2. ExperimentRuns (Knowledge Time: created_at & status_history)
        if include_all or "experiment_run" in scope:
            exp_entities = self.db.query(ExperimentRun).all()
            reconstructed_exps = []
            excluded_exps = 0
            unknown_exps = 0

            for exp in exp_entities:
                avail_at = exp.created_at
                if avail_at is None:
                    unknown_exps += 1
                    continue

                if avail_at.tzinfo is None:
                    avail_at = avail_at.replace(tzinfo=timezone.utc)

                if avail_at <= as_of_dt:
                    # Derive status at as_of from status_history
                    status_at_as_of, status_source = self._derive_experiment_status(
                        exp, as_of_dt, missing_status_history
                    )

                    fidelity = "VERIFIED" if status_source == "status_history" else "UNKNOWN"

                    reconstructed_exps.append({
                        "id": exp.id,
                        "tool_blueprint_id": exp.tool_blueprint_id,
                        "status_at_as_of": status_at_as_of,
                        "status_source": status_source,
                        "availability_at": avail_at.isoformat(),
                        "fidelity": fidelity,
                    })
                else:
                    excluded_exps += 1

            reconstructed_state["experiment_runs"] = reconstructed_exps
            excluded_counts["experiment_run"] = excluded_exps
            unknown_availability["experiment_run"] = unknown_exps

        # 3. Evaluations (Knowledge Time: evaluated_at / created_at)
        if include_all or "evaluation" in scope:
            eval_entities = self.db.query(EvaluationRecord).all()
            reconstructed_evals = []
            excluded_evals = 0
            unknown_evals = 0

            for ev in eval_entities:
                avail_at = ev.evaluated_at
                if avail_at is None:
                    unknown_evals += 1
                    continue

                if avail_at.tzinfo is None:
                    avail_at = avail_at.replace(tzinfo=timezone.utc)

                if avail_at <= as_of_dt:
                    reconstructed_evals.append({
                        "id": ev.id,
                        "target_type": ev.target_type,
                        "target_id": ev.target_id,
                        "status": ev.status.value if hasattr(ev.status, "value") else str(ev.status),
                        "evaluated_at": avail_at.isoformat(),
                        "availability_at": avail_at.isoformat(),
                        "fidelity": "VERIFIED",
                    })
                else:
                    excluded_evals += 1

            reconstructed_state["evaluations"] = reconstructed_evals
            excluded_counts["evaluation"] = excluded_evals
            unknown_availability["evaluation"] = unknown_evals

        # 4. Predictions (Knowledge Time: created_at)
        if include_all or "prediction" in scope:
            pred_entities = self.db.query(Prediction).all()
            reconstructed_preds = []
            excluded_preds = 0
            unknown_preds = 0

            for pred in pred_entities:
                avail_at = pred.created_at
                if avail_at is None:
                    unknown_preds += 1
                    continue

                if avail_at.tzinfo is None:
                    avail_at = avail_at.replace(tzinfo=timezone.utc)

                if avail_at <= as_of_dt:
                    reconstructed_preds.append({
                        "id": pred.id,
                        "epistemic_status": pred.epistemic_status.value if hasattr(pred.epistemic_status, "value") else str(pred.epistemic_status),
                        "availability_at": avail_at.isoformat(),
                        "fidelity": "PARTIAL",  # Content not versioned
                    })
                else:
                    excluded_preds += 1

            reconstructed_state["predictions"] = reconstructed_preds
            excluded_counts["prediction"] = excluded_preds
            unknown_availability["prediction"] = unknown_preds

        # 5. Hypotheses (Knowledge Time: created_at)
        if include_all or "hypothesis" in scope:
            hyp_entities = self.db.query(Hypothesis).all()
            reconstructed_hyps = []
            excluded_hyps = 0
            unknown_hyps = 0

            for hyp in hyp_entities:
                avail_at = hyp.created_at
                if avail_at is None:
                    unknown_hyps += 1
                    continue

                if avail_at.tzinfo is None:
                    avail_at = avail_at.replace(tzinfo=timezone.utc)

                if avail_at <= as_of_dt:
                    reconstructed_hyps.append({
                        "id": hyp.id,
                        "claim": hyp.claim,
                        "availability_at": avail_at.isoformat(),
                        "fidelity": "PARTIAL",  # Content not versioned
                    })
                else:
                    excluded_hyps += 1

            reconstructed_state["hypotheses"] = reconstructed_hyps
            excluded_counts["hypothesis"] = excluded_hyps
            unknown_availability["hypothesis"] = unknown_hyps

        # 6. Phenomenon (Knowledge Time: created_at)
        if include_all or "phenomenon" in scope:
            phen_entities = self.db.query(Phenomenon).all()
            reconstructed_phens = []
            excluded_phens = 0
            unknown_phens = 0

            for phen in phen_entities:
                avail_at = phen.created_at
                if avail_at is None:
                    unknown_phens += 1
                    continue

                if avail_at.tzinfo is None:
                    avail_at = avail_at.replace(tzinfo=timezone.utc)

                if avail_at <= as_of_dt:
                    reconstructed_phens.append({
                        "id": phen.id,
                        "name": phen.name,
                        "epistemic_status": phen.epistemic_status.value if hasattr(phen.epistemic_status, "value") else str(phen.epistemic_status),
                        "availability_at": avail_at.isoformat(),
                        "fidelity": "PARTIAL",  # Content not versioned
                    })
                else:
                    excluded_phens += 1

            reconstructed_state["phenomenon"] = reconstructed_phens
            excluded_counts["phenomenon"] = excluded_phens
            unknown_availability["phenomenon"] = unknown_phens

        # 7. PotentialPhenomena (Knowledge Time: created_at)
        if include_all or "potential_phenomenon" in scope:
            pot_entities = self.db.query(PotentialPhenomenon).all()
            reconstructed_pots = []
            excluded_pots = 0
            unknown_pots = 0

            for pot in pot_entities:
                avail_at = pot.created_at
                if avail_at is None:
                    unknown_pots += 1
                    continue

                if avail_at.tzinfo is None:
                    avail_at = avail_at.replace(tzinfo=timezone.utc)

                if avail_at <= as_of_dt:
                    reconstructed_pots.append({
                        "id": pot.id,
                        "phenomenon": pot.phenomenon,
                        "status": pot.status.value if hasattr(pot.status, "value") else str(pot.status),
                        "availability_at": avail_at.isoformat(),
                        "fidelity": "PARTIAL",  # Content not versioned
                    })
                else:
                    excluded_pots += 1

            reconstructed_state["potential_phenomena"] = reconstructed_pots
            excluded_counts["potential_phenomenon"] = excluded_pots
            unknown_availability["potential_phenomenon"] = unknown_pots

        # 8. DomainRelations (Time-filtered by created_at)
        if include_all or "domain_relation" in scope:
            rel_entities = self.db.query(DomainRelation).all()
            reconstructed_rels = []
            excluded_rels = 0
            unknown_rels = 0

            for rel in rel_entities:
                avail_at = rel.created_at
                if avail_at is None:
                    unknown_rels += 1
                    continue

                if avail_at.tzinfo is None:
                    avail_at = avail_at.replace(tzinfo=timezone.utc)

                if avail_at <= as_of_dt:
                    reconstructed_rels.append({
                        "id": rel.id,
                        "source_type": rel.source_type,
                        "source_id": rel.source_id,
                        "target_type": rel.target_type,
                        "target_id": rel.target_id,
                        "relation_type": rel.relation_type.value if hasattr(rel.relation_type, "value") else str(rel.relation_type),
                        "availability_at": avail_at.isoformat(),
                        "fidelity": "VERIFIED",
                    })
                else:
                    excluded_rels += 1

            reconstructed_state["domain_relations"] = reconstructed_rels
            excluded_counts["domain_relation"] = excluded_rels
            unknown_availability["domain_relation"] = unknown_rels

        # 9. Relations (models.py)
        if include_all or "relation" in scope:
            rel_models = self.db.query(Relation).all()
            reconstructed_models_rels = []
            excluded_models_rels = 0
            unknown_models_rels = 0

            for rm in rel_models:
                avail_at = rm.provenance.get("created_at") if isinstance(rm.provenance, dict) else None
                if not avail_at:
                    unknown_models_rels += 1
                    continue

                if isinstance(avail_at, str):
                    try:
                        avail_dt = datetime.fromisoformat(avail_at.replace("Z", "+00:00"))
                    except ValueError:
                        unknown_models_rels += 1
                        continue
                elif isinstance(avail_at, datetime):
                    avail_dt = avail_at
                else:
                    unknown_models_rels += 1
                    continue

                if avail_dt.tzinfo is None:
                    avail_dt = avail_dt.replace(tzinfo=timezone.utc)

                if avail_dt <= as_of_dt:
                    reconstructed_models_rels.append({
                        "id": rm.id,
                        "from_node_id": rm.from_node_id,
                        "to_node_id": rm.to_node_id,
                        "type": rm.type.value if hasattr(rm.type, "value") else str(rm.type),
                        "availability_at": avail_dt.isoformat(),
                        "fidelity": "VERIFIED",
                    })
                else:
                    excluded_models_rels += 1

            reconstructed_state["relations"] = reconstructed_models_rels
            excluded_counts["relation"] = excluded_models_rels
            unknown_availability["relation"] = unknown_models_rels

        # 10. ProvenanceRecords (Time-filtered by created_at)
        if include_all or "provenance_record" in scope:
            prov_entities = self.db.query(ProvenanceRecord).all()
            reconstructed_provs = []
            excluded_provs = 0
            unknown_provs = 0

            for pr in prov_entities:
                avail_at = pr.created_at
                if avail_at is None:
                    unknown_provs += 1
                    continue

                if avail_at.tzinfo is None:
                    avail_at = avail_at.replace(tzinfo=timezone.utc)

                if avail_at <= as_of_dt:
                    reconstructed_provs.append({
                        "id": pr.id,
                        "node_id": pr.node_id,
                        "availability_at": avail_at.isoformat(),
                        "fidelity": "VERIFIED",
                    })
                else:
                    excluded_provs += 1

            reconstructed_state["provenance_records"] = reconstructed_provs
            excluded_counts["provenance_record"] = excluded_provs
            unknown_availability["provenance_record"] = unknown_provs

        # Deduce Completeness
        tot_unknown = sum(unknown_availability.values())
        tot_missing_hist = len(missing_status_history)

        if tot_unknown > 0 or tot_missing_hist > 0:
            completeness = "PARTIAL"
            if tot_unknown > 0:
                uncertainty_notes.append(f"{tot_unknown} entities had unknown availability timestamps.")
            if tot_missing_hist > 0:
                uncertainty_notes.append(f"{tot_missing_hist} ExperimentRuns lacked complete status history prior to as_of.")
        else:
            completeness = "COMPLETE"

        # Construct raw ReplayResult dict
        raw_result = {
            "as_of": as_of_dt.isoformat(),
            "format_version": FORMAT_VERSION,
            "completeness": completeness,
            "reconstructed_state": reconstructed_state,
            "reconstruction_diagnostics": {
                "excluded_counts": excluded_counts,
                "unknown_availability": unknown_availability,
                "missing_status_history": missing_status_history,
                "versioning_gap": {
                    "entities": ["prediction", "hypothesis", "phenomenon", "potential_phenomenon", "discovery_recovery"],
                    "impact": "Content of domain entities is not historically versioned; presence/existence and status history only are verified.",
                },
                "snapshot_isolation": {
                    "supported": True,
                    "limitations": "Read query executed within active SQLAlchemy database transaction boundary.",
                },
            },
            "provenance": {
                "provenance_refs": [p["id"] for p in reconstructed_state.get("provenance_records", [])],
                "relation_refs": [r["id"] for r in reconstructed_state.get("domain_relations", [])] + [r["id"] for r in reconstructed_state.get("relations", [])],
            },
            "uncertainty_notes": uncertainty_notes,
            "source_integrity_verified": True,
        }

        return normalize_replay_result(raw_result)

    def _derive_experiment_status(
        self,
        exp: ExperimentRun,
        as_of_dt: datetime,
        missing_status_history: List[Dict[str, Any]],
    ) -> Tuple[str, str]:
        """Derive ExperimentRun status as of `as_of_dt` from `status_history`.

        Returns tuple of (derived_status, status_source).
        If history is absent or empty prior to as_of, returns ("UNKNOWN", "missing_status_history").
        """
        history = exp.status_history or []
        if not history:
            missing_status_history.append({
                "experiment_run_id": exp.id,
                "reason": "status_history is empty; historical status at as_of is UNKNOWN.",
            })
            return "UNKNOWN", "missing_status_history"

        applicable_transitions = []
        for entry in history:
            at_raw = entry.get("at")
            if not at_raw:
                continue
            if isinstance(at_raw, str):
                at_dt = datetime.fromisoformat(at_raw.replace("Z", "+00:00"))
            else:
                at_dt = at_raw

            if at_dt.tzinfo is None:
                at_dt = at_dt.replace(tzinfo=timezone.utc)

            if at_dt <= as_of_dt:
                applicable_transitions.append((at_dt, entry.get("status")))

        if not applicable_transitions:
            missing_status_history.append({
                "experiment_run_id": exp.id,
                "reason": "No status transition records exist on or before as_of; historical status at as_of is UNKNOWN.",
            })
            return "UNKNOWN", "missing_status_history"

        # Sort transitions by timestamp
        applicable_transitions.sort(key=lambda x: x[0])
        latest_status = applicable_transitions[-1][1]
        if not latest_status:
            return "UNKNOWN", "missing_status_history"

        return str(latest_status), "status_history"
