"""Real ArmorPaint required.
    .venv\\Scripts\\python.exe -m pytest tests/test_check_mesh_uvs_integration.py -v -m integration
"""
import os

import pytest

from armorpaint_mcp.server import check_mesh_uvs

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.mark.integration
def test_check_mesh_uvs_reports_the_sample_project():
    result = check_mesh_uvs(os.path.join(FIXTURES, "sample_project.arm"))

    assert result["error"] is None
    assert result["ok"] is True
    assert isinstance(result["valid"], bool)
    (obj,) = result["objects"]
    assert obj["name"] == "Tessellated"
    assert obj["metrics"]["coverage_pct"] > 0
    assert obj["metrics"]["faces_without_uv"] == 0


@pytest.mark.integration
def test_check_mesh_uvs_reports_every_object_by_name():
    result = check_mesh_uvs(os.path.join(FIXTURES, "phase6", "objects3.arm"))

    assert result["ok"] is True, result["error"]
    assert sorted(o["name"] for o in result["objects"]) == ["Cone", "Tessellated", "Torus"]
