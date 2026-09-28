"""Real ArmorPaint required. Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_run_script_integration.py -v
(needs AP_BINARY set to a working build -- see .env.example)
"""
import os

import pytest

from armorpaint_mcp.server import run_script

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_run_script_fills_and_exports_the_already_open_project(tmp_path):
    """Confirmed empirically during Phase 4 planning (2026-09-16): a script
    that calls script_fill_layer() + export_texture_run() directly (no
    script_project_new()) against a project opened via the positional CLI
    argument produces real output files named after that project, not
    ArmorPaint's 'untitled' fallback -- proof --script genuinely operates on
    the caller's own project, not a fresh throwaway one."""
    out_dir = str(tmp_path).replace("\\", "/")
    script = (
        "void main() {\n"
        "\tscript_fill_layer();\n"
        f'\texport_texture_run("{out_dir}", 0);\n'
        "}\n"
    )

    result = run_script(project=FIXTURE, script=script)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    exported = sorted(os.listdir(tmp_path))
    expected = sorted(f"sample_project_{n}.png"
                      for n in ["base", "metal", "nor", "occ", "rough"])
    assert exported == expected


@pytest.mark.integration
def test_run_script_early_return_is_ok_true_with_no_output(tmp_path):
    """Documents the real, confirmed minic limitation this tool's docstring
    still warns about after Fix round 1's finding 2 (script errors are now
    caught -- see test_run_script_reports_an_undefined_minic_call_as_a_failure
    in test_phase6_hardening_integration.py): a script that `return`s early,
    before doing its work, prints no error and exits 0 -- ok=True alone does
    not prove the work happened. Same body as
    test_run_script_fills_and_exports_the_already_open_project, with an
    early `return;` as the first statement, so the only difference from a
    script proven to write 5 PNGs is that early return -- and an empty
    tmp_path actually means something."""
    out_dir = str(tmp_path).replace("\\", "/")
    script = (
        "void main() {\n"
        "\treturn;\n"
        "\tscript_fill_layer();\n"
        f'\texport_texture_run("{out_dir}", 0);\n'
        "}\n"
    )

    result = run_script(project=FIXTURE, script=script)

    assert result["ok"] is True
    assert result["error"] is None
    assert os.listdir(tmp_path) == []


@pytest.mark.integration
def test_run_script_reports_a_real_timeout():
    """Real-binary timeout path (Phase 4 final-review Minor finding: only a
    mocked TimeoutExpired existed for this before). timeout_s=0.01 is far
    too short for the real ArmorPaint.exe process to even finish starting,
    forcing subprocess.run's actual TimeoutExpired rather than a mocked
    one."""
    result = run_script(project=FIXTURE, script="void main() {}", timeout_s=0.01)

    assert result["ok"] is False
    assert "timed out after 0.01s" in result["error"]
