"""Real ArmorPaint required. Phase 6.1 hardening (docs/PLAN.md).
Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_phase6_hardening_integration.py -v -m integration
"""
import os

import pytest

from armorpaint_mcp.server import run_script

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE = os.path.join(FIXTURES, "sample_project.arm")


@pytest.mark.integration
def test_run_script_reports_an_undefined_minic_call_as_a_failure():
    result = run_script(project=SAMPLE,
                        script="void main() {\n\tthis_is_undefined_q();\n}\n")

    assert result["ok"] is False
    assert "unknown function 'this_is_undefined_q'" in result["error"]


@pytest.mark.integration
def test_run_script_still_succeeds_for_a_clean_script():
    result = run_script(project=SAMPLE,
                        script='void main() {\n\tconsole_log("PHASE6_OK");\n}\n')

    assert result["error"] is None
    assert result["ok"] is True
    assert "PHASE6_OK" in result["stdout"]
