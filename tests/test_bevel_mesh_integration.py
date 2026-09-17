import os

import pytest

from armorpaint_mcp.server import bevel_mesh
from tests._mesh_edit_test_helpers import export_obj, count_obj_vertices_and_faces

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_bevel_mesh_adds_geometry(tmp_path):
    output_project = str(tmp_path / "beveled.arm")

    result = bevel_mesh(project=FIXTURE, amount=0.1, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    before_v, before_f = count_obj_vertices_and_faces(
        export_obj(FIXTURE, str(tmp_path / "before.obj")))
    after_v, after_f = count_obj_vertices_and_faces(
        export_obj(output_project, str(tmp_path / "after.obj")))

    assert after_v > before_v, (before_v, after_v)
    assert after_f > before_f, (before_f, after_f)
