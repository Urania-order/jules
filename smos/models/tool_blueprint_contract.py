"""
Declarative ToolBlueprint Contract.

Contract-as-code module without persistence layer (no SQLAlchemy model, no DB table).

This module defines a minimal, typed, versioned specification for a declarative research tool.
The contract DESCRIBES the tool, but does NOT execute it.

CRITICAL:
    - Specification only, no execution.
    - No epistemic_status field.
    - No evidence field.
    - No actual_outcome field.
    - Domain extensions live strictly under `extensions`.
"""

import copy
import enum
import hashlib
import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union


class ToolType(str, enum.Enum):
    DATA_COLLECTION = "DATA_COLLECTION"
    SIMULATION = "SIMULATION"
    VISUALIZATION = "VISUALIZATION"
    OBSERVATION_FORM = "OBSERVATION_FORM"
    ANALYSIS_INTERFACE = "ANALYSIS_INTERFACE"
    EXPERIMENT_PLANNER = "EXPERIMENT_PLANNER"


class ParameterType(str, enum.Enum):
    FLOAT = "float"
    INT = "int"
    STRING = "string"
    BOOL = "bool"
    ENUM = "enum"


class OutputType(str, enum.Enum):
    FLOAT = "float"
    INT = "int"
    STRING = "string"
    BOOL = "bool"
    TIMESERIES = "timeseries"
    JSON = "json"


FORBIDDEN_RESERVED_KEYS = {"epistemic_status", "evidence", "actual_outcome"}

ALLOWED_TOP_LEVEL_KEYS = {
    "blueprint_id",
    "version",
    "research_context",
    "specification",
    "environment",
    "provenance",
    "extensions",
}

ALLOWED_RESEARCH_CONTEXT_KEYS = {
    "research_project_id",
    "phenomenon_id",
    "assumption_refs",
    "prediction_refs",
    "experiment_refs",
}

ALLOWED_SPECIFICATION_KEYS = {
    "title",
    "description",
    "tool_type",
    "parameters",
    "expected_outputs",
}

ALLOWED_PARAMETER_KEYS = {
    "name",
    "type",
    "unit",
    "min",
    "max",
    "default",
    "allowed_values",
    "required",
    "description",
}

ALLOWED_OUTPUT_KEYS = {
    "name",
    "type",
    "unit",
    "description",
}

ALLOWED_ENVIRONMENT_KEYS = {
    "runtime_requirements",
    "security_policy",
}

ALLOWED_PROVENANCE_KEYS = {
    "created_by",
    "created_at",
    "parent_version",
    "provenance_metadata",
}

SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _validate_parameter_spec(param: Any, idx: int) -> List[str]:
    errs: List[str] = []
    prefix = f"specification.parameters[{idx}]"
    if not isinstance(param, dict):
        return [f"{prefix} must be a dict"]

    for k in param.keys():
        if k in FORBIDDEN_RESERVED_KEYS:
            errs.append(f"{prefix} contains forbidden field '{k}'")
        elif k not in ALLOWED_PARAMETER_KEYS:
            errs.append(f"{prefix} contains unknown field '{k}'")

    if "name" not in param or not isinstance(param["name"], str) or not param["name"].strip():
        errs.append(f"{prefix}.name must be a non-empty string")

    if "type" not in param:
        errs.append(f"{prefix}.type is required")
        return errs

    ptype = param["type"]
    valid_param_types = {e.value for e in ParameterType}
    if ptype not in valid_param_types:
        errs.append(f"{prefix}.type '{ptype}' is invalid. Must be one of {sorted(valid_param_types)}")
        return errs

    if "required" not in param or not isinstance(param["required"], bool):
        errs.append(f"{prefix}.required must be a boolean")

    if "unit" in param and param["unit"] is not None:
        if not isinstance(param["unit"], str):
            errs.append(f"{prefix}.unit must be a string or None")

    if "description" in param and param["description"] is not None:
        if not isinstance(param["description"], str):
            errs.append(f"{prefix}.description must be a string or None")

    p_min = param.get("min")
    p_max = param.get("max")
    p_default = param.get("default")
    p_allowed = param.get("allowed_values")

    if ptype != ParameterType.ENUM.value:
        if p_allowed is not None:
            errs.append(f"{prefix}.allowed_values MUST be absent or None for non-enum type '{ptype}'")

    if ptype not in (ParameterType.INT.value, ParameterType.FLOAT.value):
        if p_min is not None:
            errs.append(f"{prefix}.min MUST be absent or None for non-numeric type '{ptype}'")
        if p_max is not None:
            errs.append(f"{prefix}.max MUST be absent or None for non-numeric type '{ptype}'")

    if ptype == ParameterType.INT.value:
        if p_min is not None:
            if isinstance(p_min, bool) or not isinstance(p_min, int):
                errs.append(f"{prefix}.min must be an int, got {p_min!r}")
        if p_max is not None:
            if isinstance(p_max, bool) or not isinstance(p_max, int):
                errs.append(f"{prefix}.max must be an int, got {p_max!r}")
        if p_default is not None:
            if isinstance(p_default, bool) or not isinstance(p_default, int):
                errs.append(f"{prefix}.default must be an int, got {p_default!r}")

    elif ptype == ParameterType.FLOAT.value:
        if p_min is not None:
            if isinstance(p_min, bool) or not isinstance(p_min, (int, float)) or math.isnan(p_min) or math.isinf(p_min):
                errs.append(f"{prefix}.min must be a finite float/int, got {p_min!r}")
        if p_max is not None:
            if isinstance(p_max, bool) or not isinstance(p_max, (int, float)) or math.isnan(p_max) or math.isinf(p_max):
                errs.append(f"{prefix}.max must be a finite float/int, got {p_max!r}")
        if p_default is not None:
            if isinstance(p_default, bool) or not isinstance(p_default, (int, float)) or math.isnan(p_default) or math.isinf(p_default):
                errs.append(f"{prefix}.default must be a finite float/int, got {p_default!r}")

    elif ptype == ParameterType.STRING.value:
        if p_default is not None:
            if not isinstance(p_default, str) or isinstance(p_default, bytes):
                errs.append(f"{prefix}.default must be a string, got {p_default!r}")

    elif ptype == ParameterType.BOOL.value:
        if p_default is not None:
            if not isinstance(p_default, bool):
                errs.append(f"{prefix}.default must be a bool, got {p_default!r}")

    elif ptype == ParameterType.ENUM.value:
        if p_allowed is None or not isinstance(p_allowed, list) or len(p_allowed) == 0:
            errs.append(f"{prefix}.allowed_values MUST be a non-empty list for enum type")
        else:
            if p_default is not None and p_default not in p_allowed:
                errs.append(f"{prefix}.default '{p_default!r}' MUST be in allowed_values {p_allowed!r}")

    if ptype in (ParameterType.INT.value, ParameterType.FLOAT.value):
        if p_min is not None and p_max is not None:
            if isinstance(p_min, (int, float)) and isinstance(p_max, (int, float)) and not isinstance(p_min, bool) and not isinstance(p_max, bool):
                if p_min >= p_max:
                    errs.append(f"{prefix}: min ({p_min}) must be strictly less than max ({p_max})")

        if p_default is not None and isinstance(p_default, (int, float)) and not isinstance(p_default, bool):
            if p_min is not None and isinstance(p_min, (int, float)) and not isinstance(p_min, bool):
                if p_default < p_min:
                    errs.append(f"{prefix}: default ({p_default}) is less than min ({p_min})")
            if p_max is not None and isinstance(p_max, (int, float)) and not isinstance(p_max, bool):
                if p_default > p_max:
                    errs.append(f"{prefix}: default ({p_default}) is greater than max ({p_max})")

    return errs


def _validate_output_spec(out: Any, idx: int) -> List[str]:
    errs: List[str] = []
    prefix = f"specification.expected_outputs[{idx}]"
    if not isinstance(out, dict):
        return [f"{prefix} must be a dict"]

    for k in out.keys():
        if k in FORBIDDEN_RESERVED_KEYS:
            errs.append(f"{prefix} contains forbidden field '{k}'")
        elif k not in ALLOWED_OUTPUT_KEYS:
            errs.append(f"{prefix} contains unknown field '{k}'")

    if "name" not in out or not isinstance(out["name"], str) or not out["name"].strip():
        errs.append(f"{prefix}.name must be a non-empty string")

    if "type" not in out:
        errs.append(f"{prefix}.type is required")
        return errs

    otype = out["type"]
    valid_output_types = {e.value for e in OutputType}
    if otype not in valid_output_types:
        errs.append(f"{prefix}.type '{otype}' is invalid. Must be one of {sorted(valid_output_types)}")

    if "unit" in out and out["unit"] is not None:
        if not isinstance(out["unit"], str):
            errs.append(f"{prefix}.unit must be a string or None")

    if "description" in out and out["description"] is not None:
        if not isinstance(out["description"], str):
            errs.append(f"{prefix}.description must be a string or None")

    return errs


def validate_tool_blueprint(blueprint: Any) -> Tuple[bool, List[str]]:
    """Validate a ToolBlueprint dictionary against the contract schema and semantic rules."""
    errors: List[str] = []
    if not isinstance(blueprint, dict):
        return False, ["ToolBlueprint must be a dict"]

    for key in blueprint.keys():
        if key in FORBIDDEN_RESERVED_KEYS:
            errors.append(f"Forbidden epistemic/result field '{key}' is not allowed in ToolBlueprint")
        elif key not in ALLOWED_TOP_LEVEL_KEYS:
            errors.append(f"Unknown core field at top level: '{key}'")

    if "blueprint_id" not in blueprint:
        errors.append("Missing required top-level field 'blueprint_id'")
    else:
        bid = blueprint["blueprint_id"]
        if not isinstance(bid, str) or not bid.strip():
            errors.append("Field 'blueprint_id' must be a non-empty string")

    if "version" not in blueprint:
        errors.append("Missing required top-level field 'version'")
    else:
        ver = blueprint["version"]
        if not isinstance(ver, str) or not SEMVER_REGEX.match(ver):
            errors.append(f"Field 'version' must be a valid SemVer string (MAJOR.MINOR.PATCH), got {ver!r}")

    if "research_context" in blueprint and blueprint["research_context"] is not None:
        rc = blueprint["research_context"]
        if not isinstance(rc, dict):
            errors.append("Field 'research_context' must be a dict")
        else:
            for k in rc.keys():
                if k in FORBIDDEN_RESERVED_KEYS:
                    errors.append(f"Forbidden field '{k}' in research_context")
                elif k not in ALLOWED_RESEARCH_CONTEXT_KEYS:
                    errors.append(f"Unknown field in research_context: '{k}'")

            if "research_project_id" in rc and rc["research_project_id"] is not None:
                if not isinstance(rc["research_project_id"], str):
                    errors.append("research_context.research_project_id must be a string")
            if "phenomenon_id" in rc and rc["phenomenon_id"] is not None:
                if isinstance(rc["phenomenon_id"], bool) or not isinstance(rc["phenomenon_id"], int):
                    errors.append("research_context.phenomenon_id must be an integer")
            if "assumption_refs" in rc and rc["assumption_refs"] is not None:
                refs = rc["assumption_refs"]
                if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs):
                    errors.append("research_context.assumption_refs must be a list of strings")
            if "prediction_refs" in rc and rc["prediction_refs"] is not None:
                refs = rc["prediction_refs"]
                if not isinstance(refs, list) or any(isinstance(x, bool) or not isinstance(x, int) for x in refs):
                    errors.append("research_context.prediction_refs must be a list of integers")
            if "experiment_refs" in rc and rc["experiment_refs"] is not None:
                refs = rc["experiment_refs"]
                if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs):
                    errors.append("research_context.experiment_refs must be a list of strings")

    if "specification" not in blueprint:
        errors.append("Missing required top-level field 'specification'")
    else:
        spec = blueprint["specification"]
        if not isinstance(spec, dict):
            errors.append("Field 'specification' must be a dict")
        else:
            for k in spec.keys():
                if k in FORBIDDEN_RESERVED_KEYS:
                    errors.append(f"Forbidden field '{k}' in specification")
                elif k not in ALLOWED_SPECIFICATION_KEYS:
                    errors.append(f"Unknown field in specification: '{k}'")

            if "title" not in spec:
                errors.append("Missing required field 'specification.title'")
            elif not isinstance(spec["title"], str) or not spec["title"].strip():
                errors.append("Field 'specification.title' must be a non-empty string")

            if "description" not in spec:
                errors.append("Missing required field 'specification.description'")
            elif not isinstance(spec["description"], str):
                errors.append("Field 'specification.description' must be a string")

            if "tool_type" not in spec:
                errors.append("Missing required field 'specification.tool_type'")
            else:
                tt = spec["tool_type"]
                valid_types = {e.value for e in ToolType}
                if tt not in valid_types:
                    errors.append(f"Unknown or unsupported tool_type '{tt}'. Must be one of {sorted(valid_types)}")

            if "parameters" not in spec:
                errors.append("Missing required field 'specification.parameters'")
            elif not isinstance(spec["parameters"], list):
                errors.append("Field 'specification.parameters' must be a list")
            else:
                for idx, param in enumerate(spec["parameters"]):
                    p_errs = _validate_parameter_spec(param, idx)
                    errors.extend(p_errs)

            if "expected_outputs" not in spec:
                errors.append("Missing required field 'specification.expected_outputs'")
            elif not isinstance(spec["expected_outputs"], list):
                errors.append("Field 'specification.expected_outputs' must be a list")
            else:
                for idx, out in enumerate(spec["expected_outputs"]):
                    o_errs = _validate_output_spec(out, idx)
                    errors.extend(o_errs)

    if "environment" in blueprint and blueprint["environment"] is not None:
        env = blueprint["environment"]
        if not isinstance(env, dict):
            errors.append("Field 'environment' must be a dict")
        else:
            for k in env.keys():
                if k in FORBIDDEN_RESERVED_KEYS:
                    errors.append(f"Forbidden field '{k}' in environment")
                elif k not in ALLOWED_ENVIRONMENT_KEYS:
                    errors.append(f"Unknown field in environment: '{k}'")

            if "runtime_requirements" in env and env["runtime_requirements"] is not None:
                if not isinstance(env["runtime_requirements"], dict):
                    errors.append("environment.runtime_requirements must be a dict")
            if "security_policy" in env and env["security_policy"] is not None:
                if not isinstance(env["security_policy"], dict):
                    errors.append("environment.security_policy must be a dict")

    if "provenance" in blueprint and blueprint["provenance"] is not None:
        prov = blueprint["provenance"]
        if not isinstance(prov, dict):
            errors.append("Field 'provenance' must be a dict")
        else:
            for k in prov.keys():
                if k in FORBIDDEN_RESERVED_KEYS:
                    errors.append(f"Forbidden field '{k}' in provenance")
                elif k not in ALLOWED_PROVENANCE_KEYS:
                    errors.append(f"Unknown field in provenance: '{k}'")

            if "created_by" in prov and prov["created_by"] is not None:
                if not isinstance(prov["created_by"], str):
                    errors.append("provenance.created_by must be a string")
            if "created_at" in prov and prov["created_at"] is not None:
                if not isinstance(prov["created_at"], str):
                    errors.append("provenance.created_at must be a string")
            if "parent_version" in prov and prov["parent_version"] is not None:
                pv = prov["parent_version"]
                if not isinstance(pv, str) or not SEMVER_REGEX.match(pv):
                    errors.append("provenance.parent_version must be a valid SemVer string")
            if "provenance_metadata" in prov and prov["provenance_metadata"] is not None:
                if not isinstance(prov["provenance_metadata"], dict):
                    errors.append("provenance.provenance_metadata must be a dict")

    if "extensions" in blueprint and blueprint["extensions"] is not None:
        exts = blueprint["extensions"]
        if not isinstance(exts, dict):
            errors.append("Field 'extensions' must be a dict")
        else:
            for ns, payload in exts.items():
                if not isinstance(ns, str) or not ns.strip():
                    errors.append("Extension namespace key must be a non-empty string")
                if not isinstance(payload, dict):
                    errors.append(f"Extension payload for namespace '{ns}' must be a dict")
                else:
                    for rk in FORBIDDEN_RESERVED_KEYS:
                        if rk in payload:
                            errors.append(f"Extension '{ns}' contains reserved forbidden key '{rk}'")

    return len(errors) == 0, errors


def normalize_tool_blueprint(blueprint: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a normalized ToolBlueprint dictionary with all standard fields populated."""
    if blueprint is None or not isinstance(blueprint, dict):
        return {
            "blueprint_id": "",
            "version": "0.1.0",
            "research_context": {
                "research_project_id": None,
                "phenomenon_id": None,
                "assumption_refs": [],
                "prediction_refs": [],
                "experiment_refs": [],
            },
            "specification": {
                "title": "",
                "description": "",
                "tool_type": ToolType.SIMULATION.value,
                "parameters": [],
                "expected_outputs": [],
            },
            "environment": {
                "runtime_requirements": {},
                "security_policy": {},
            },
            "provenance": {
                "created_by": "",
                "created_at": "",
                "parent_version": None,
                "provenance_metadata": {},
            },
            "extensions": {},
        }
    res = copy.deepcopy(blueprint)
    if "research_context" not in res or not isinstance(res["research_context"], dict):
        res["research_context"] = {}
    rc = res["research_context"]
    rc.setdefault("research_project_id", None)
    rc.setdefault("phenomenon_id", None)
    rc.setdefault("assumption_refs", [])
    rc.setdefault("prediction_refs", [])
    rc.setdefault("experiment_refs", [])

    if "environment" not in res or not isinstance(res["environment"], dict):
        res["environment"] = {}
    env = res["environment"]
    env.setdefault("runtime_requirements", {})
    env.setdefault("security_policy", {})

    if "provenance" not in res or not isinstance(res["provenance"], dict):
        res["provenance"] = {}
    prov = res["provenance"]
    prov.setdefault("created_by", "")
    prov.setdefault("created_at", "")
    prov.setdefault("parent_version", None)
    prov.setdefault("provenance_metadata", {})

    res.setdefault("extensions", {})
    return res


def canonical_serialize_blueprint(blueprint: Dict[str, Any]) -> str:
    """Return canonical deterministic JSON serialization of the ToolBlueprint."""
    return json.dumps(blueprint, sort_keys=True, separators=(",", ":"))


def calculate_version_hash(blueprint: Dict[str, Any]) -> str:
    """Calculate SHA-256 version hash over canonical serialization of the blueprint including version."""
    canonical_str = canonical_serialize_blueprint(blueprint)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def _dict_diff(d1: Any, d2: Any, path: str = "") -> Dict[str, Any]:
    diffs: Dict[str, Any] = {}
    if type(d1) != type(d2):
        return {path: {"old": d1, "new": d2}}

    if isinstance(d1, dict):
        keys = sorted(set(d1.keys()) | set(d2.keys()))
        for k in keys:
            sub_path = f"{path}.{k}" if path else k
            if k not in d1:
                diffs[sub_path] = {"old": None, "new": d2[k]}
            elif k not in d2:
                diffs[sub_path] = {"old": d1[k], "new": None}
            else:
                sub_diff = _dict_diff(d1[k], d2[k], sub_path)
                diffs.update(sub_diff)
    elif isinstance(d1, list):
        if d1 != d2:
            diffs[path] = {"old": d1, "new": d2}
    else:
        if d1 != d2:
            diffs[path] = {"old": d1, "new": d2}

    return diffs


def diff_tool_blueprints(bp1: Dict[str, Any], bp2: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate deterministic diff between two tool blueprints."""
    return _dict_diff(bp1, bp2, path="")


class ToolBlueprint:
    """Class wrapper for declarative ToolBlueprint object."""

    def __init__(self, data: Dict[str, Any]):
        valid, errors = validate_tool_blueprint(data)
        if not valid:
            raise ValueError(f"Invalid ToolBlueprint payload: {'; '.join(errors)}")
        self._data = copy.deepcopy(data)

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self._data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolBlueprint":
        return cls(data)

    def canonical_json(self) -> str:
        return canonical_serialize_blueprint(self._data)

    def version_hash(self) -> str:
        return calculate_version_hash(self._data)

    def diff(self, other: Union["ToolBlueprint", Dict[str, Any]]) -> Dict[str, Any]:
        other_dict = other.to_dict() if isinstance(other, ToolBlueprint) else other
        return diff_tool_blueprints(self._data, other_dict)
