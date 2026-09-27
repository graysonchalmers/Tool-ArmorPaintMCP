"""Real ArmorPaint required. Known Issue #12 / final-review C1: ArmorPaint's
Windows build reads argv as ANSI (base/sources/backends/windows_system.c
WinMain -> kickstart(__argc, __argv)), so a non-ASCII project path never
opens -- ArmorPaint logs "Could not open file" (paint/sources/io/import_arm.c
import_arm_run_project), keeps its default scene, and still runs --script.
Before the guard, decimate_mesh on such a path returned ok=True and saved the
DEFAULT scene (one 'Tessellated' object) as the output.
Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_non_ascii_path_integration.py -v -m integration
"""
import os
import shutil

import pytest

from armorpaint_mcp.server import decimate_mesh

PHASE6 = os.path.join(os.path.dirname(__file__), "fixtures", "phase6")


def _files(root) -> set[str]:
    return {os.path.relpath(os.path.join(d, f), root)
            for d, _, fs in os.walk(root) for f in fs}


@pytest.mark.integration
def test_decimate_on_a_non_ascii_project_path_fails_cleanly_and_writes_nothing(tmp_path):
    project_dir = tmp_path / "Ø"
    project_dir.mkdir()
    project = project_dir / "objects3.arm"
    shutil.copy2(os.path.join(PHASE6, "objects3.arm"), project)
    out = tmp_path / "out" / "decimated.arm"

    result = decimate_mesh(project=str(project), strength=0.5, output_project=str(out))

    assert result["ok"] is False
    assert result["output_project"] is None
    assert str(project) in result["error"]
    assert "ASCII" in result["error"]
    assert _files(tmp_path) == {os.path.join("Ø", "objects3.arm")}
