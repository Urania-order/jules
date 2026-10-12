"""
ToolBlueprint Service — minimal service for declarative ToolBlueprint validation and serialization.

This service is a thin orchestration layer that delegates directly to the authoritative contract
in `smos.models.tool_blueprint_contract`.
"""

from typing import Any, Dict, List, Optional, Tuple
from smos.models.tool_blueprint_contract import (
    ToolBlueprint,
    validate_tool_blueprint,
    normalize_tool_blueprint,
    canonical_serialize_blueprint,
    calculate_version_hash,
    diff_tool_blueprints,
)


class ToolBlueprintService:
    """Service providing helper operations for declarative ToolBlueprints."""

    @staticmethod
    def validate(blueprint: Any) -> Tuple[bool, List[str]]:
        """Validate a ToolBlueprint payload against the contract."""
        return validate_tool_blueprint(blueprint)

    @staticmethod
    def normalize(blueprint: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize a ToolBlueprint dictionary."""
        return normalize_tool_blueprint(blueprint)

    @staticmethod
    def canonical_serialize(blueprint: Dict[str, Any]) -> str:
        """Return canonical JSON string of a ToolBlueprint."""
        return canonical_serialize_blueprint(blueprint)

    @staticmethod
    def version_hash(blueprint: Dict[str, Any]) -> str:
        """Calculate SHA-256 version hash of a ToolBlueprint."""
        return calculate_version_hash(blueprint)

    @staticmethod
    def diff(bp1: Dict[str, Any], bp2: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate structured diff between two ToolBlueprints."""
        return diff_tool_blueprints(bp1, bp2)

    @staticmethod
    def create_blueprint(data: Dict[str, Any]) -> ToolBlueprint:
        """Instantiate and validate a ToolBlueprint object."""
        return ToolBlueprint.from_dict(data)
