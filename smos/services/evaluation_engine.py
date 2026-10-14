"""Evaluation Engine (TASK L-05A).

Provides EvaluationEngine service for explicitly interpreting observations against criteria for
Prediction, Phenomenon, or PotentialPhenomenon targets without mutating epistemic status or
invoking execution tools.

CRITICAL INVARIANTS:
1. No epistemic mutation: Never changes target.epistemic_status or promotes claims.
2. Read-only domain evaluation: Consumes existing Observation records only. No L-04 tool execution.
3. Temporal cutoff: Enforces as_of filtering on observed_at and created_at.
4. Preserves uncertainty: Distinguishes CONFIRMED, REFUTED, INCONCLUSIVE, and UNDETERMINED.
5. Append-only persistence: Saves EvaluationRecord without overwriting prior evaluations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import or_
from sqlalchemy.orm import Session

from smos.models.evaluation import EvaluationRecord, EvaluationStatus
from smos.models.evaluation_contract import (
    normalize_evaluation_result,
    validate_evaluation_request,
)
from smos.models.observation import Observation
from smos.models.phenomenon import Phenomenon
from smos.models.potential import PotentialPhenomenon
from smos.models.prediction import Prediction


class EvaluationEngine:
    """Service responsible for explicit target evaluation against eligible observations."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Perform explicit evaluation for a target entity against eligible observations and criteria.

        Args:
            request: Evaluation request dict containing target_type, target_id, criteria, as_of, etc.

        Returns:
            Normalized evaluation result dictionary.
        """
        req_valid, req_errors = validate_evaluation_request(request)
        if not req_valid:
            return normalize_evaluation_result({
                "target_type": request.get("target_type") if isinstance(request, dict) else "unknown",
                "target_id": request.get("target_id") if isinstance(request, dict) and isinstance(request.get("target_id"), int) else 0,
                "prediction_id": request.get("prediction_id") if isinstance(request, dict) else None,
                "status": EvaluationStatus.UNDETERMINED.value,
                "criteria_id": "INVALID_REQUEST",
                "rationale": f"Invalid evaluation request: {'; '.join(req_errors)}",
                "uncertainty_notes": req_errors,
            })

        target_type = str(request["target_type"]).strip().lower()
        target_id = request["target_id"]
        prediction_id = request.get("prediction_id")
        raw_criteria = request.get("criteria")
        evaluated_by = request.get("evaluated_by")
        req_provenance = request.get("provenance") or {}

        # Parse cutoff as_of
        as_of_dt: Optional[datetime] = None
        as_of_raw = request.get("as_of")
        if isinstance(as_of_raw, datetime):
            as_of_dt = as_of_raw
        elif isinstance(as_of_raw, str):
            try:
                as_of_dt = datetime.fromisoformat(as_of_raw.replace("Z", "+00:00"))
            except ValueError:
                pass

        # 1. Resolve Target Entity
        target_obj = None
        pred_obj: Optional[Prediction] = None

        if target_type == "prediction":
            pred_obj = self.db.get(Prediction, target_id)
            target_obj = pred_obj
            if prediction_id is None:
                prediction_id = target_id
            elif prediction_id != target_id:
                return self._persist_and_return({
                    "target_type": target_type,
                    "target_id": target_id,
                    "prediction_id": prediction_id,
                    "status": EvaluationStatus.UNDETERMINED.value,
                    "criteria_id": "PREDICTION_MISMATCH",
                    "rationale": f"Target ID {target_id} does not match prediction_id {prediction_id}",
                    "uncertainty_notes": ["prediction_id mismatch"],
                    "as_of": as_of_dt,
                    "evaluated_by": evaluated_by,
                    "provenance": req_provenance,
                })
        elif target_type == "phenomenon":
            target_obj = self.db.get(Phenomenon, target_id)
            if prediction_id is not None:
                pred_obj = self.db.get(Prediction, prediction_id)
        elif target_type == "potential_phenomenon":
            target_obj = self.db.get(PotentialPhenomenon, target_id)
            if prediction_id is not None:
                pred_obj = self.db.get(Prediction, prediction_id)

        if target_obj is None:
            return self._persist_and_return({
                "target_type": target_type,
                "target_id": target_id,
                "prediction_id": prediction_id,
                "status": EvaluationStatus.UNDETERMINED.value,
                "criteria_id": "TARGET_NOT_FOUND",
                "rationale": f"Target entity '{target_type}' with ID {target_id} was not found",
                "uncertainty_notes": [f"Missing target entity {target_type}:{target_id}"],
                "as_of": as_of_dt,
                "evaluated_by": evaluated_by,
                "provenance": req_provenance,
            })

        if prediction_id is not None and pred_obj is None:
            return self._persist_and_return({
                "target_type": target_type,
                "target_id": target_id,
                "prediction_id": prediction_id,
                "status": EvaluationStatus.UNDETERMINED.value,
                "criteria_id": "PREDICTION_NOT_FOUND",
                "rationale": f"Referenced Prediction with ID {prediction_id} was not found",
                "uncertainty_notes": [f"Missing referenced prediction:{prediction_id}"],
                "as_of": as_of_dt,
                "evaluated_by": evaluated_by,
                "provenance": req_provenance,
            })

        # 2. Select Eligible Observations
        all_obs = self.db.query(Observation).all()
        eligible_obs: List[Observation] = []
        excluded_obs_ids: List[int] = []
        exclusion_reasons: List[str] = []

        for obs in all_obs:
            # Temporal cutoff check
            obs_time = obs.observed_at or obs.created_at
            if as_of_dt is not None and obs_time is not None:
                # Ensure timezone aware comparison
                compare_obs_time = obs_time
                if compare_obs_time.tzinfo is None:
                    compare_obs_time = compare_obs_time.replace(tzinfo=timezone.utc)
                compare_as_of = as_of_dt
                if compare_as_of.tzinfo is None:
                    compare_as_of = compare_as_of.replace(tzinfo=timezone.utc)

                if compare_obs_time > compare_as_of:
                    excluded_obs_ids.append(obs.id)
                    exclusion_reasons.append(f"Observation {obs.id} time ({compare_obs_time.isoformat()}) is after cutoff as_of ({compare_as_of.isoformat()})")
                    continue

            # Scope matching
            is_relevant = False
            p_refs = obs.prediction_refs or []
            phen_refs = obs.phenomenon_refs or []
            hyp_refs = obs.hypothesis_refs or []

            if target_type == "prediction" and target_id in p_refs:
                is_relevant = True
            elif target_type == "phenomenon" and target_id in phen_refs:
                is_relevant = True
            elif target_type == "potential_phenomenon" and (target_id in hyp_refs or target_id in phen_refs):
                is_relevant = True

            if not is_relevant and prediction_id is not None and prediction_id in p_refs:
                is_relevant = True

            if is_relevant:
                eligible_obs.append(obs)
            else:
                excluded_obs_ids.append(obs.id)

        # 3. Resolve & Apply Evaluation Criteria
        criteria_id = "DEFAULT_METRIC_CRITERIA"
        criteria_version = "1.0.0"
        criteria_specs: List[Dict[str, Any]] = []

        if isinstance(raw_criteria, dict):
            criteria_id = str(raw_criteria.get("criteria_id") or raw_criteria.get("id") or "CUSTOM_CRITERIA")
            criteria_version = str(raw_criteria.get("version") or "1.0.0")
            specs = raw_criteria.get("specs") or raw_criteria.get("metrics") or [raw_criteria]
            if isinstance(specs, list):
                criteria_specs = [s for s in specs if isinstance(s, dict)]
            elif isinstance(specs, dict):
                criteria_specs = [specs]
        elif isinstance(raw_criteria, str):
            criteria_id = raw_criteria
            criteria_specs = []

        # Default criteria from Prediction expected_state if available and criteria_specs empty
        if not criteria_specs and pred_obj is not None and isinstance(pred_obj.expected_state, dict) and pred_obj.expected_state:
            for k, v in pred_obj.expected_state.items():
                if isinstance(v, (int, float)):
                    criteria_specs.append({"metric_name": k, "expected_value": float(v), "tolerance": 0.05})
                elif isinstance(v, dict) and "value" in v:
                    criteria_specs.append({
                        "metric_name": k,
                        "expected_value": float(v["value"]),
                        "tolerance": float(v.get("tolerance", 0.05)),
                    })

        # 4. Perform Evaluation Logic
        if not eligible_obs:
            return self._persist_and_return({
                "target_type": target_type,
                "target_id": target_id,
                "prediction_id": prediction_id,
                "status": EvaluationStatus.INCONCLUSIVE.value if all_obs else EvaluationStatus.UNDETERMINED.value,
                "criteria_id": criteria_id,
                "criteria_version": criteria_version,
                "as_of": as_of_dt,
                "observation_refs": [],
                "excluded_observation_refs": excluded_obs_ids,
                "criterion_findings": [],
                "rationale": "No eligible observations found for target within temporal cutoff and scope",
                "uncertainty_notes": ["Zero eligible observations"] + exclusion_reasons,
                "evaluated_by": evaluated_by,
                "provenance": req_provenance,
            })

        if not criteria_specs:
            return self._persist_and_return({
                "target_type": target_type,
                "target_id": target_id,
                "prediction_id": prediction_id,
                "status": EvaluationStatus.UNDETERMINED.value,
                "criteria_id": criteria_id,
                "criteria_version": criteria_version,
                "as_of": as_of_dt,
                "observation_refs": [o.id for o in eligible_obs],
                "excluded_observation_refs": excluded_obs_ids,
                "criterion_findings": [],
                "rationale": "No evaluable metric criteria specifications provided or derived from target",
                "uncertainty_notes": ["Missing evaluable criteria specifications"],
                "evaluated_by": evaluated_by,
                "provenance": req_provenance,
            })

        # Evaluate metrics against eligible observations
        criterion_findings: List[Dict[str, Any]] = []
        confirmed_count = 0
        refuted_count = 0
        uncertainty_notes: List[str] = []

        for spec in criteria_specs:
            metric_name = spec.get("metric_name")
            expected_val = spec.get("expected_value")
            tolerance = float(spec.get("tolerance", 0.0))
            min_val = spec.get("min")
            max_val = spec.get("max")

            matching_obs = [o for o in eligible_obs if o.metric_name == metric_name]
            if not matching_obs:
                criterion_findings.append({
                    "metric_name": metric_name,
                    "status": EvaluationStatus.UNDETERMINED.value,
                    "reason": f"No observations recorded for metric '{metric_name}'",
                })
                uncertainty_notes.append(f"Missing observations for metric '{metric_name}'")
                continue

            metric_confirmed = 0
            metric_refuted = 0

            for obs in matching_obs:
                m_val = obs.metric_value
                if isinstance(m_val, dict) and "value" in m_val:
                    m_val = m_val["value"]

                if not isinstance(m_val, (int, float)):
                    uncertainty_notes.append(f"Non-numeric metric_value {m_val!r} in observation {obs.id}")
                    continue

                val_float = float(m_val)
                obs_passed = True

                if expected_val is not None:
                    diff = abs(val_float - float(expected_val))
                    if diff > tolerance:
                        obs_passed = False

                if min_val is not None and val_float < float(min_val):
                    obs_passed = False

                if max_val is not None and val_float > float(max_val):
                    obs_passed = False

                if obs_passed:
                    metric_confirmed += 1
                else:
                    metric_refuted += 1

            if metric_confirmed > 0 and metric_refuted == 0:
                criterion_findings.append({
                    "metric_name": metric_name,
                    "status": EvaluationStatus.CONFIRMED.value,
                    "confirmed_obs": metric_confirmed,
                    "refuted_obs": 0,
                })
                confirmed_count += 1
            elif metric_refuted > 0 and metric_confirmed == 0:
                criterion_findings.append({
                    "metric_name": metric_name,
                    "status": EvaluationStatus.REFUTED.value,
                    "confirmed_obs": 0,
                    "refuted_obs": metric_refuted,
                })
                refuted_count += 1
            elif metric_confirmed > 0 and metric_refuted > 0:
                criterion_findings.append({
                    "metric_name": metric_name,
                    "status": EvaluationStatus.INCONCLUSIVE.value,
                    "confirmed_obs": metric_confirmed,
                    "refuted_obs": metric_refuted,
                    "reason": "Conflicting observations for metric",
                })
                uncertainty_notes.append(f"Conflicting observations detected for metric '{metric_name}' ({metric_confirmed} confirmed, {metric_refuted} refuted)")
            else:
                criterion_findings.append({
                    "metric_name": metric_name,
                    "status": EvaluationStatus.UNDETERMINED.value,
                    "reason": "Could not determine metric status from observations",
                })

        # Overall synthesis status
        if refuted_count > 0 and confirmed_count == 0:
            final_status = EvaluationStatus.REFUTED.value
            rationale = "Observations contradict criteria specifications"
        elif confirmed_count > 0 and refuted_count == 0 and len(criterion_findings) == confirmed_count:
            final_status = EvaluationStatus.CONFIRMED.value
            rationale = "Eligible observations satisfy all criteria specifications"
        elif confirmed_count > 0 or refuted_count > 0 or any(f.get("status") == EvaluationStatus.INCONCLUSIVE.value for f in criterion_findings):
            final_status = EvaluationStatus.INCONCLUSIVE.value
            rationale = "Evaluation completed but findings contain conflicting or partial evidence"
        else:
            final_status = EvaluationStatus.UNDETERMINED.value
            rationale = "Evaluation cannot establish a definitive conclusion with available criteria and observations"

        return self._persist_and_return({
            "target_type": target_type,
            "target_id": target_id,
            "prediction_id": prediction_id,
            "status": final_status,
            "criteria_id": criteria_id,
            "criteria_version": criteria_version,
            "as_of": as_of_dt,
            "observation_refs": [o.id for o in eligible_obs],
            "excluded_observation_refs": excluded_obs_ids,
            "criterion_findings": criterion_findings,
            "rationale": rationale,
            "uncertainty_notes": uncertainty_notes + exclusion_reasons,
            "evaluated_by": evaluated_by,
            "provenance": req_provenance,
        })

    def _persist_and_return(self, result_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize result dictionary, create append-only EvaluationRecord in database, and return result."""
        normalized = normalize_evaluation_result(result_dict)

        # Parse datetime for DB storage
        evaluated_at_dt = datetime.now(timezone.utc)
        if normalized.get("evaluated_at"):
            try:
                evaluated_at_dt = datetime.fromisoformat(normalized["evaluated_at"].replace("Z", "+00:00"))
            except ValueError:
                pass

        as_of_dt = None
        if normalized.get("as_of"):
            try:
                as_of_dt = datetime.fromisoformat(normalized["as_of"].replace("Z", "+00:00"))
            except ValueError:
                pass

        record = EvaluationRecord(
            target_type=normalized["target_type"],
            target_id=normalized["target_id"],
            prediction_id=normalized.get("prediction_id"),
            status=EvaluationStatus(normalized["status"]),
            criteria_id=normalized["criteria_id"],
            criteria_version=normalized["criteria_version"],
            evaluated_at=evaluated_at_dt,
            as_of=as_of_dt,
            observation_refs=normalized["observation_refs"],
            excluded_observation_refs=normalized["excluded_observation_refs"],
            criterion_findings=normalized["criterion_findings"],
            rationale=normalized.get("rationale"),
            uncertainty_notes=normalized["uncertainty_notes"],
            evaluated_by=normalized.get("evaluated_by"),
            provenance=normalized["provenance"],
            record_hash=normalized["record_hash"],
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        normalized["id"] = record.id
        return normalized

    def get_evaluation(self, evaluation_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific evaluation record by ID."""
        rec = self.db.get(EvaluationRecord, evaluation_id)
        if not rec:
            return None
        return normalize_evaluation_result(rec.to_dict())

    def list_evaluations(
        self,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List evaluation records, optionally filtered by target."""
        query = self.db.query(EvaluationRecord)
        if target_type:
            query = query.filter(EvaluationRecord.target_type == target_type.strip().lower())
        if target_id is not None:
            query = query.filter(EvaluationRecord.target_id == target_id)

        records = query.order_by(EvaluationRecord.evaluated_at.desc()).all()
        return [normalize_evaluation_result(r.to_dict()) for r in records]
