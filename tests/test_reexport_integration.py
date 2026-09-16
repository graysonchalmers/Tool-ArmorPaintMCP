# tests/test_reexport_integration.py
"""Real ArmorPaint required. Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_reexport_integration.py -v
(needs AP_BINARY set to a working build -- see .env.example)
"""
import os

import pytest

from armorpaint_mcp.server import reexport_project

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_reexport_project_produces_real_files(tmp_path):
    output_dir = tmp_path / "out"

    result = reexport_project(project=FIXTURE, preset="generic",
                               output_dir=str(output_dir))

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    assert len(result["files"]) == 5  # base, nor, occ, rough, metal
    for f in result["files"]:
        assert os.path.isfile(f)
        assert os.path.getsize(f) > 0
