"""Real ArmorPaint required. Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_inspect_project_integration.py -v
(needs AP_BINARY set to a working build -- see .env.example)
"""
import os

import pytest

from armorpaint_mcp.server import inspect_project

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_inspect_project_reports_real_object_from_the_fixture():
    result = inspect_project(project=FIXTURE)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    assert len(result["objects"]) == 1
    assert result["objects"][0]["name"]  # a real, non-empty object name
    assert isinstance(result["materials"], list)
    assert isinstance(result["layers"], list)
