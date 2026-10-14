"""Controlled Experiment Execution Engine (TASK L-04).

Provides an allowlisted executor registry and an execution engine that executes
explicitly requested, approved experiment runs without interpreting tool blueprints
as executable code or promoting epistemic claims.

CRITICAL INVARIANTS:
1. Strict allowlist registry: Executors must be explicitly registered.
2. Observation.experiment_run_id is String: converted via str(run.id).
3. Reuses ExperimentRunService lifecycle transitions (execute, complete, fail).
4. Failure paths handled according to strict contract rules:
   - Executor exception / malformed output -> fail(run_id), no observations, status=FAILED.
   - Partial observation ingestion -> partial_persistence=True, status=FAILED, no complete(), no retry.
   - Successful execution and ingestion -> complete(run_id), status=SUCCEEDED.
5. No automatic evaluation, retry, or epistemic status modification.
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from smos.models.experiment_execution_contract import (
    EXECUTION_STATUS_FAILED,
    EXECUTION_STATUS_SUCCEEDED,
    normalize_execution_result,
    validate_execution_request,
    validate_execution_result,
    validate_parameters_against_blueprint,
)
from smos.models.tool_blueprint_contract import validate_tool_blueprint
from smos.services.experiment_run_service import ExperimentRunService
from smos.services.observation_service import ObservationService

# Executor callable type signature:
# executor(parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]
ExecutorCallable = Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


class ExecutorRegistry:
    """Explicit allowlisted registry for research tool executors."""

    def __init__(self):
        self._executors: Dict[str, ExecutorCallable] = {}

    def register(self, executor_id: str, executor: ExecutorCallable) -> None:
        """Register an executor for a specific executor_id.

        Raises ValueError if executor_id is invalid or already registered.
        """
        if not isinstance(executor_id, str) or not executor_id.strip():
            raise ValueError("executor_id must be a non-empty string")

        if not callable(executor):
            raise ValueError("executor must be callable")

        if executor_id in self._executors:
            raise ValueError(f"Executor '{executor_id}' is already registered")

        self._executors[executor_id] = executor

    def resolve(self, executor_id: str) -> Optional[ExecutorCallable]:
        """Resolve a registered executor by executor_id."""
        return self._executors.get(executor_id)

    def is_registered(self, executor_id: str) -> bool:
        """Check if an executor_id is registered."""
        return executor_id in self._executors

    def unregister(self, executor_id: str) -> bool:
        """Unregister an executor_id if present."""
        if executor_id in self._executors:
            del self._executors[executor_id]
            return True
        return False

    def list_executors(self) -> List[str]:
        """Return a sorted list of registered executor identifiers."""
        return sorted(list(self._executors.keys()))


class ExperimentExecutionEngine:
    """Controlled execution engine for approved experiment runs."""

    def __init__(
        self,
        db: Session,
        registry: Optional[ExecutorRegistry] = None,
        blueprint_provider: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
    ):
        self.db = db
        self.registry = registry if registry is not None else ExecutorRegistry()
        self.blueprint_provider = blueprint_provider
        self.run_service = ExperimentRunService(db)
        self.obs_service = ObservationService(db)

    def execute_run(
        self,
        request: Dict[str, Any],
        blueprint: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute an eligible approved ExperimentRun.

        Args:
            request: Execution request dict (experiment_run_id, parameters, etc.)
            blueprint: Optional explicit ToolBlueprint dictionary. If not provided,
                       blueprint_provider is used to resolve by run.tool_blueprint_id.

        Returns:
            Normalized execution result dictionary.
        """
        req_valid, req_errors = validate_execution_request(request)
        if not req_valid:
            return normalize_execution_result({
                "experiment_run_id": request.get("experiment_run_id", 0) if isinstance(request, dict) else 0,
                "executor_id": "UNKNOWN",
                "status": EXECUTION_STATUS_FAILED,
                "error_message": f"Invalid execution request: {'; '.join(req_errors)}",
            })

        run_id = request["experiment_run_id"]
        # Ensure run_id is integer
        if isinstance(run_id, str) and run_id.isdigit():
            run_id_int = int(run_id)
        elif isinstance(run_id, int):
            run_id_int = run_id
        else:
            return normalize_execution_result({
                "experiment_run_id": run_id,
                "executor_id": "UNKNOWN",
                "status": EXECUTION_STATUS_FAILED,
                "error_message": f"Invalid experiment_run_id type: {run_id!r}",
            })

        # 1. Load run
        run = self.run_service.get(run_id_int)
        if not run:
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": "UNKNOWN",
                "status": EXECUTION_STATUS_FAILED,
                "error_message": f"ExperimentRun with ID {run_id_int} not found",
            })

        # 2. Verify eligibility (status must be APPROVED)
        if run.status != "APPROVED":
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id or "UNKNOWN",
                "status": EXECUTION_STATUS_FAILED,
                "error_message": f"ExperimentRun {run_id_int} is in ineligible status '{run.status}' (must be 'APPROVED')",
            })

        # 3. Resolve and validate blueprint
        resolved_blueprint = blueprint
        if resolved_blueprint is None and self.blueprint_provider is not None:
            resolved_blueprint = self.blueprint_provider(run.tool_blueprint_id)

        if resolved_blueprint is None:
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "error_message": f"ToolBlueprint '{run.tool_blueprint_id}' could not be resolved",
            })

        bp_valid, bp_errors = validate_tool_blueprint(resolved_blueprint)
        if not bp_valid:
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "error_message": f"Resolved ToolBlueprint is invalid: {'; '.join(bp_errors)}",
            })

        bp_id = resolved_blueprint.get("blueprint_id")
        if bp_id != run.tool_blueprint_id:
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "error_message": f"Blueprint ID mismatch: run references '{run.tool_blueprint_id}' but resolved blueprint ID is '{bp_id}'",
            })

        # 4. Resolve executor from allowlist
        executor = self.registry.resolve(run.tool_blueprint_id)
        if executor is None:
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "error_message": f"No executor registered for tool_blueprint_id '{run.tool_blueprint_id}'",
            })

        # 5. Validate execution parameters
        actual_parameters = request.get("parameters") or run.actual_parameters or {}
        p_valid, p_errors = validate_parameters_against_blueprint(actual_parameters, resolved_blueprint)
        if not p_valid:
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "error_message": f"Parameter validation failed: {'; '.join(p_errors)}",
            })

        execution_conditions = request.get("execution_conditions") or run.execution_conditions or {}
        executed_by = request.get("executed_by") or run.approved_by or "execution_engine"

        # 6. Transition state APPROVED -> EXECUTED
        executed_run = self.run_service.execute(
            run_id=run_id_int,
            actual_parameters=actual_parameters,
            execution_conditions=execution_conditions,
            executed_by=executed_by,
        )
        if executed_run is None:
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "error_message": f"Lifecycle transition APPROVED -> EXECUTED rejected for run {run_id_int}",
            })

        # 7. Execute executor
        started_at = datetime.now(timezone.utc)
        context = {
            "experiment_run_id": run_id_int,
            "tool_blueprint_id": run.tool_blueprint_id,
            "blueprint_version": run.blueprint_version,
            "executed_by": executed_by,
            "execution_conditions": execution_conditions,
        }

        try:
            exec_output = executor(actual_parameters, context)
        except Exception as e:
            self.run_service.fail(run_id_int, reason=f"Executor exception: {str(e)}", failed_by=executed_by)
            finished_at = datetime.now(timezone.utc)
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "started_at": started_at,
                "finished_at": finished_at,
                "error_message": f"Executor raised exception: {str(e)}",
            })

        finished_at = datetime.now(timezone.utc)

        # 8. Validate executor output format
        if not isinstance(exec_output, dict):
            self.run_service.fail(run_id_int, reason="Executor returned non-dict output", failed_by=executed_by)
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "started_at": started_at,
                "finished_at": finished_at,
                "error_message": f"Executor returned invalid output type {type(exec_output).__name__}, expected dict",
            })

        if exec_output.get("status") == EXECUTION_STATUS_FAILED or "error" in exec_output:
            err_msg = exec_output.get("error_message") or exec_output.get("error") or "Executor reported failure"
            self.run_service.fail(run_id_int, reason=str(err_msg), failed_by=executed_by)
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "started_at": started_at,
                "finished_at": finished_at,
                "structured_output": exec_output.get("structured_output", {}),
                "error_message": str(err_msg),
                "error_details": exec_output.get("error_details"),
            })

        measurements = exec_output.get("measurements", [])
        if not isinstance(measurements, list):
            self.run_service.fail(run_id_int, reason="Executor output measurements field must be a list", failed_by=executed_by)
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "started_at": started_at,
                "finished_at": finished_at,
                "error_message": "Executor output measurements field must be a list",
            })

        # Extract research context references from blueprint
        rc = resolved_blueprint.get("research_context", {})
        hyp_refs = rc.get("assumption_refs", [])  # note: hypothesis_refs in observation
        pred_refs = rc.get("prediction_refs", [])
        phen_refs = [rc["phenomenon_id"]] if rc.get("phenomenon_id") is not None else []
        assump_refs = rc.get("assumption_refs", [])

        # 9. Ingest observations
        ingested_obs_ids: List[int] = []
        ingestion_failed = False
        ingestion_error = None

        for idx, meas in enumerate(measurements):
            if not isinstance(meas, dict) or "metric_name" not in meas or "metric_value" not in meas:
                ingestion_failed = True
                ingestion_error = f"Measurement at index {idx} missing metric_name or metric_value"
                break

            obs_payload = {
                "metric_name": meas["metric_name"],
                "metric_value": meas["metric_value"],
                "metric_unit": meas.get("metric_unit"),
                "tool_blueprint_id": run.tool_blueprint_id,
                "tool_id": meas.get("tool_id") or run.tool_blueprint_id,
                # NOTE 2: Observation.experiment_run_id is String, NO FK -> convert str(run.id)
                "experiment_run_id": str(run.id),
                "execution_id": run.recipe_execution_id,
                "prediction_refs": pred_refs,
                "assumption_refs": assump_refs,
                "phenomenon_refs": phen_refs,
                "execution_conditions": execution_conditions,
                "observed_at": meas.get("observed_at") or finished_at.isoformat(),
                "provenance": {
                    "executed_by": executed_by,
                    "idempotency_key": request.get("idempotency_key"),
                    "meas_provenance": meas.get("provenance", {}),
                },
            }

            obs = self.obs_service.ingest(obs_payload)
            if obs is None:
                ingestion_failed = True
                ingestion_error = f"ObservationService.ingest failed for measurement '{meas.get('metric_name')}'"
                break
            else:
                ingested_obs_ids.append(obs.id)

        # 10. Handle observation outcome
        if ingestion_failed:
            # NOTE 8 Path B: Partial persistence failure path
            # Do NOT call complete(), report partial_persistence explicitly.
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "started_at": started_at,
                "finished_at": finished_at,
                "structured_output": exec_output.get("structured_output", {}),
                "measurements": measurements,
                "observation_refs": ingested_obs_ids,
                "partial_persistence": len(ingested_obs_ids) > 0,
                "error_message": f"Observation ingestion failed: {ingestion_error}",
            })

        # NOTE 8 Path C/D: Successful ingestion -> transition EXECUTED -> COMPLETED
        completed_run = self.run_service.complete(
            run_id=run_id_int,
            observation_refs=ingested_obs_ids,
            completed_by=executed_by,
        )
        if completed_run is None:
            return normalize_execution_result({
                "experiment_run_id": run_id_int,
                "executor_id": run.tool_blueprint_id,
                "status": EXECUTION_STATUS_FAILED,
                "started_at": started_at,
                "finished_at": finished_at,
                "observation_refs": ingested_obs_ids,
                "error_message": f"Lifecycle transition EXECUTED -> COMPLETED rejected for run {run_id_int}",
            })

        return normalize_execution_result({
            "experiment_run_id": run_id_int,
            "executor_id": run.tool_blueprint_id,
            "status": EXECUTION_STATUS_SUCCEEDED,
            "started_at": started_at,
            "finished_at": finished_at,
            "structured_output": exec_output.get("structured_output", {}),
            "measurements": measurements,
            "observation_refs": ingested_obs_ids,
            "partial_persistence": False,
            "provenance": {
                "executed_by": executed_by,
                "idempotency_key": request.get("idempotency_key"),
            },
        })
