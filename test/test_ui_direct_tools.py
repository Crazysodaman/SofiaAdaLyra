from pathlib import Path

import pytest

from sofia.ui.direct_tools import validate_tool_parameters


def test_direct_tool_parameters_validate_required_types_and_unknown_keys():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "count": {"type": "integer", "minimum": 1, "maximum": 3},
            "paths": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    validate_tool_parameters(
        {"name": "status", "count": 2, "paths": ["src"]},
        schema,
    )

    with pytest.raises(ValueError, match="missing required"):
        validate_tool_parameters({}, schema)
    with pytest.raises(ValueError, match="unknown parameter"):
        validate_tool_parameters({"name": "status", "extra": True}, schema)
    with pytest.raises(ValueError, match="must be integer"):
        validate_tool_parameters({"name": "status", "count": "2"}, schema)
    with pytest.raises(ValueError, match="contain only string"):
        validate_tool_parameters(
            {"name": "status", "paths": [Path("src")]},
            schema,
        )
