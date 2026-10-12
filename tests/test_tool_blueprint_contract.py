import pytest
import math
from smos.models.tool_blueprint_contract import (
    ToolBlueprint,
    ToolType,
    ParameterType,
    OutputType,
    validate_tool_blueprint,
    normalize_tool_blueprint,
    canonical_serialize_blueprint,
    calculate_version_hash,
    diff_tool_blueprints,
)
from smos.services.tool_blueprint_service import ToolBlueprintService


def get_sample_valid_blueprint():
    return {
        "blueprint_id": "bp-sensor-grid-01",
        "version": "1.0.0",
        "research_context": {
            "research_project_id": "proj-air-quality",
            "phenomenon_id": 12,
            "assumption_refs": ["asm-flow-laminar"],
            "prediction_refs": [101, 102],
            "experiment_refs": ["exp-grid-run-1"],
        },
        "specification": {
            "title": "Air Particle Density Collector",
            "description": "Collects PM2.5 and PM10 density telemetry",
            "tool_type": "DATA_COLLECTION",
            "parameters": [
                {
                    "name": "sample_interval_sec",
                    "type": "int",
                    "unit": "seconds",
                    "min": 1,
                    "max": 3600,
                    "default": 10,
                    "required": True,
                    "description": "Sampling rate interval",
                },
                {
                    "name": "sensor_mode",
                    "type": "enum",
                    "allowed_values": ["HIGH_PRECISION", "POWER_SAVE"],
                    "default": "HIGH_PRECISION",
                    "required": False,
                    "description": "Operating mode",
                },
                {
                    "name": "calibration_factor",
                    "type": "float",
                    "min": 0.1,
                    "max": 2.0,
                    "default": 1.0,
                    "required": False,
                },
                {
                    "name": "enable_filtering",
                    "type": "bool",
                    "default": True,
                    "required": True,
                },
                {
                    "name": "station_label",
                    "type": "string",
                    "default": "default-station",
                    "required": False,
                },
            ],
            "expected_outputs": [
                {
                    "name": "pm25_series",
                    "type": "timeseries",
                    "unit": "ug/m3",
                    "description": "PM2.5 time series",
                },
                {
                    "name": "mean_pm25",
                    "type": "float",
                    "unit": "ug/m3",
                },
            ],
        },
        "environment": {
            "runtime_requirements": {"python_version": ">=3.10"},
            "security_policy": {"network_access": "read_only"},
        },
        "provenance": {
            "created_by": "cosmonaut-42",
            "created_at": "2026-10-12T18:00:00Z",
            "parent_version": None,
            "provenance_metadata": {"source_repo": "jules"},
        },
        "extensions": {
            "lab": {"bench_id": "bench-7"},
        },
    }


# Contract Creation Tests
def test_valid_blueprint_contract():
    data = get_sample_valid_blueprint()
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is True, f"Validation errors: {errors}"
    bp = ToolBlueprint.from_dict(data)
    assert bp.to_dict()["blueprint_id"] == "bp-sensor-grid-01"


def test_minimal_blueprint_contract():
    data = {
        "blueprint_id": "bp-min-01",
        "version": "0.1.0",
        "specification": {
            "title": "Minimal Tool",
            "description": "Minimal description",
            "tool_type": "SIMULATION",
            "parameters": [],
            "expected_outputs": [],
        },
    }
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is True, f"Validation errors: {errors}"
    norm = normalize_tool_blueprint(data)
    assert norm["blueprint_id"] == "bp-min-01"
    assert norm["version"] == "0.1.0"
    assert norm["research_context"]["prediction_refs"] == []


def test_blueprint_requires_id():
    data = get_sample_valid_blueprint()
    del data["blueprint_id"]
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("blueprint_id" in e for e in errors)


def test_blueprint_requires_version():
    data = get_sample_valid_blueprint()
    del data["version"]
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("version" in e for e in errors)


def test_blueprint_version_semver():
    data = get_sample_valid_blueprint()
    data["version"] = "1.0"  # Invalid semver
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("valid SemVer" in e for e in errors)


# Validation — types
def test_parameter_int_rejects_float():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][0]["default"] = 10.5  # int default got float
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("must be an int" in e for e in errors)


def test_parameter_int_rejects_bool():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][0]["default"] = True  # bool passed as int
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("must be an int" in e for e in errors)


def test_parameter_bool_rejects_int():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][3]["default"] = 1  # int passed as bool
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("must be a bool" in e for e in errors)


def test_parameter_float_rejects_nan():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][2]["default"] = float("nan")
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("finite float" in e for e in errors)


def test_parameter_float_rejects_inf():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][2]["default"] = float("inf")
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("finite float" in e for e in errors)


def test_parameter_string_rejects_bytes():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][4]["default"] = b"bytes_val"
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("must be a string" in e for e in errors)


def test_parameter_default_matches_type():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][4]["default"] = 123  # string type got int default
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("must be a string" in e for e in errors)


# Validation — ranges
def test_parameter_range_min_max():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][0]["min"] = 100
    data["specification"]["parameters"][0]["max"] = 10  # min > max
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("strictly less than max" in e for e in errors)


def test_parameter_default_in_range():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][0]["default"] = 5000  # max is 3600
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("greater than max" in e for e in errors)


def test_parameter_numeric_bounds_only_numeric_types():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][4]["min"] = 1.0  # string parameter with min
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("min MUST be absent or None for non-numeric type" in e for e in errors)


def test_parameter_enum_requires_allowed_values():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][1]["allowed_values"] = []  # Empty allowed_values
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("non-empty list for enum type" in e for e in errors)


def test_parameter_enum_default_in_allowed_values():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][1]["default"] = "INVALID_MODE"
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("MUST be in allowed_values" in e for e in errors)


def test_parameter_non_enum_no_allowed_values():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][0]["allowed_values"] = [1, 2, 3]  # int got allowed_values
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("allowed_values MUST be absent or None for non-enum type" in e for e in errors)


# Validation — required/default
def test_required_parameter_may_have_default():
    data = get_sample_valid_blueprint()
    # parameter 0 is required=True and has default=10
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is True


def test_required_parameter_unknown_at_blueprint_creation():
    data = get_sample_valid_blueprint()
    data["specification"]["parameters"][0]["default"] = None  # required parameter without default
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is True, f"Errors: {errors}"


# Validation — tool_type
def test_unknown_tool_type_rejected():
    data = get_sample_valid_blueprint()
    data["specification"]["tool_type"] = "MAGIC_INTERFACE"
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("Unknown or unsupported tool_type" in e for e in errors)


def test_core_tool_types_accepted():
    for tt in ToolType:
        data = get_sample_valid_blueprint()
        data["specification"]["tool_type"] = tt.value
        is_valid, errors = validate_tool_blueprint(data)
        assert is_valid is True, f"Failed for tool_type {tt.value}: {errors}"


# Validation — strict input
def test_from_dict_rejects_unknown_core_fields():
    data = get_sample_valid_blueprint()
    data["unknown_top_level"] = "foo"
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("Unknown core field at top level" in e for e in errors)
    with pytest.raises(ValueError):
        ToolBlueprint.from_dict(data)


def test_from_dict_rejects_epistemic_status_field():
    data = get_sample_valid_blueprint()
    data["epistemic_status"] = "OBSERVED"
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("Forbidden epistemic/result field" in e for e in errors)


def test_from_dict_rejects_evidence_field():
    data = get_sample_valid_blueprint()
    data["evidence"] = [1, 2, 3]
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("Forbidden epistemic/result field" in e for e in errors)


def test_from_dict_rejects_actual_outcome_field():
    data = get_sample_valid_blueprint()
    data["actual_outcome"] = {"result": "success"}
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("Forbidden epistemic/result field" in e for e in errors)


# Extensions
def test_extensions_namespaced():
    data = get_sample_valid_blueprint()
    data["extensions"] = {
        "multi_agent": {"agent_roles": ["researcher", "engineer"]},
        "lab": {"bench": "bench-1"},
    }
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is True, f"Errors: {errors}"


def test_extensions_rejects_reserved_keys():
    data = get_sample_valid_blueprint()
    data["extensions"] = {
        "recipe": {"epistemic_status": "PROMOTED"},
    }
    is_valid, errors = validate_tool_blueprint(data)
    assert is_valid is False
    assert any("contains reserved forbidden key" in e for e in errors)


def test_extensions_does_not_break_core_validation():
    data = get_sample_valid_blueprint()
    data["extensions"] = {"custom": {"some_field": 123}}
    bp = ToolBlueprint.from_dict(data)
    assert bp.to_dict()["extensions"]["custom"]["some_field"] == 123


# Serialization & Version Hash
def test_to_dict_roundtrip():
    data = get_sample_valid_blueprint()
    bp = ToolBlueprint.from_dict(data)
    bp2 = ToolBlueprint.from_dict(bp.to_dict())
    assert bp.to_dict() == bp2.to_dict()


def test_canonical_serialization_sorted_keys():
    data = get_sample_valid_blueprint()
    s1 = canonical_serialize_blueprint(data)
    # Reorder keys in dict
    reordered_data = {k: data[k] for k in sorted(data.keys(), reverse=True)}
    s2 = canonical_serialize_blueprint(reordered_data)
    assert s1 == s2


def test_version_hash_stable():
    data = get_sample_valid_blueprint()
    h1 = calculate_version_hash(data)
    h2 = calculate_version_hash(data)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex string


def test_version_hash_changes_on_content():
    data1 = get_sample_valid_blueprint()
    data2 = get_sample_valid_blueprint()
    data2["specification"]["title"] = "Updated Title"
    assert calculate_version_hash(data1) != calculate_version_hash(data2)


def test_version_hash_changes_on_version():
    data1 = get_sample_valid_blueprint()
    data2 = get_sample_valid_blueprint()
    data2["version"] = "1.0.1"
    assert calculate_version_hash(data1) != calculate_version_hash(data2)


def test_version_hash_includes_version():
    data = get_sample_valid_blueprint()
    h1 = calculate_version_hash(data)
    data["version"] = "2.0.0"
    h2 = calculate_version_hash(data)
    assert h1 != h2


# Diff
def test_diff_same_blueprint_empty():
    data = get_sample_valid_blueprint()
    d = diff_tool_blueprints(data, data)
    assert d == {}


def test_diff_detects_field_changes():
    data1 = get_sample_valid_blueprint()
    data2 = get_sample_valid_blueprint()
    data2["specification"]["title"] = "New Title"
    data2["version"] = "1.1.0"
    d = diff_tool_blueprints(data1, data2)
    assert "specification.title" in d
    assert d["specification.title"] == {"old": "Air Particle Density Collector", "new": "New Title"}
    assert "version" in d
    assert d["version"] == {"old": "1.0.0", "new": "1.1.0"}


def test_diff_deterministic():
    data1 = get_sample_valid_blueprint()
    data2 = get_sample_valid_blueprint()
    data2["specification"]["title"] = "New Title"
    d1 = diff_tool_blueprints(data1, data2)
    d2 = diff_tool_blueprints(data1, data2)
    assert d1 == d2


# Epistemic guarantees
def test_blueprint_no_epistemic_status_field():
    data = get_sample_valid_blueprint()
    assert "epistemic_status" not in data
    data["epistemic_status"] = "OBSERVED"
    is_valid, _ = validate_tool_blueprint(data)
    assert is_valid is False


def test_blueprint_no_evidence_field():
    data = get_sample_valid_blueprint()
    assert "evidence" not in data
    data["evidence"] = [1]
    is_valid, _ = validate_tool_blueprint(data)
    assert is_valid is False


def test_blueprint_references_only():
    data = get_sample_valid_blueprint()
    rc = data["research_context"]
    assert "prediction_refs" in rc
    assert "phenomenon_id" in rc
    # Verify no outcome or fact-bearing fields inside research_context
    assert "actual_outcome" not in rc
    assert "epistemic_status" not in rc


def test_tool_blueprint_service():
    data = get_sample_valid_blueprint()
    is_valid, errors = ToolBlueprintService.validate(data)
    assert is_valid is True
    bp = ToolBlueprintService.create_blueprint(data)
    assert bp.version_hash() == calculate_version_hash(data)
