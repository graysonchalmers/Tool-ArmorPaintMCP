"""Real ArmorPaint required. Phase 6.1 hardening (docs/PLAN.md).
Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_phase6_hardening_integration.py -v -m integration
"""
import os
import shutil

import pytest

from armorpaint_mcp.server import inspect_project, run_script

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE = os.path.join(FIXTURES, "sample_project.arm")
PHASE6 = os.path.join(FIXTURES, "phase6")


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


def _bk(path: str) -> str:
    """Backslash path, each backslash doubled, for a minic string literal
    (script_append_mesh needs backslashes -- spike S5)."""
    return os.path.abspath(path).replace("/", "\\").replace("\\", "\\\\")


def build_post_append_project(directory) -> str:
    """A real project in `directory` whose mesh_assets holds a backslash path
    to an OBJ next to it: sample_project.arm + an appended ReplGrid mesh,
    saved as <directory>/appended.arm. Returns that path."""
    os.makedirs(directory, exist_ok=True)
    grid = os.path.join(directory, "repl_grid5.obj")
    shutil.copy2(os.path.join(PHASE6, "repl_grid5.obj"), grid)
    out = os.path.join(directory, "appended.arm")
    script = ("void main() {\n"
              f'\tscript_append_mesh("{_bk(grid)}");\n'
              f'\tproject_filepath_set("{os.path.abspath(out).replace(os.sep, "/")}");\n'
              "\tproject_save(0);\n}\n")
    result = run_script(project=SAMPLE, script=script)
    assert result["ok"], result["error"]
    assert os.path.isfile(out), "fixture build did not save"
    return out


@pytest.mark.integration
def test_inspect_project_reads_a_project_with_backslash_asset_paths(tmp_path):
    project = build_post_append_project(tmp_path / "a")

    result = inspect_project(project)

    assert result["error"] is None
    assert result["ok"] is True
    assert {o["name"] for o in result["objects"]} >= {"ReplGrid"}
