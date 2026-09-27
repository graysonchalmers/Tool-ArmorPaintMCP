"""Real ArmorPaint required.
    .venv\\Scripts\\python.exe -m pytest tests/test_replace_mesh_integration.py -v -m integration
"""
import hashlib
import os
import shutil

import pytest

from armorpaint_mcp import replace as rp
from armorpaint_mcp.catalog import extract_project_state
from armorpaint_mcp.config import load_config
from armorpaint_mcp.runner import run_api
from armorpaint_mcp.server import replace_mesh

PHASE6 = os.path.join(os.path.dirname(__file__), "fixtures", "phase6")


def _state(project):
    return extract_project_state(run_api(load_config().binary, project).text)


def _md5(path):
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


@pytest.mark.integration
def test_replace_keeps_name_parent_transform_and_material_with_a_differently_named_mesh(tmp_path):
    """The replacement's `o` name (ReplGrid) differs from the old object's
    (Cone), so this proves mesh_datas names follow script_object_set_name --
    every post-verify lookup is keyed on that."""
    project = os.path.join(PHASE6, "objects3_v4_parented.arm")
    before = _state(project)
    output = str(tmp_path / "out.arm")

    result = replace_mesh(project=project, old_object="Cone",
                          new_mesh=os.path.join(PHASE6, "repl_grid5.obj"),
                          mode="swap", output_project=output)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    after = _state(output)
    assert sorted(rp.object_names(after)) == ["Cone", "Tessellated", "Torus"]
    assert rp.parent_name(after, "Cone") == "Tessellated"
    assert rp.local_transform(after, "Cone") == pytest.approx(rp.local_transform(before, "Cone"), abs=1e-5)
    assert rp.material_override_name(after, "Cone") == "MatB"
    assert len(after["layer_datas"]) == len(before["layer_datas"])
