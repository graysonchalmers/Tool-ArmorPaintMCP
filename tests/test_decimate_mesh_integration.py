"""Real ArmorPaint required (with the mesh-edit patch built -- see Task 1).
Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_decimate_mesh_integration.py -v -m integration
"""
import os
import shutil

import pytest

from armorpaint_mcp.server import decimate_mesh
from tests._mesh_edit_test_helpers import export_obj, count_obj_vertices_and_faces

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_decimate_mesh_reduces_vertex_and_face_count(tmp_path):
    output_project = str(tmp_path / "decimated.arm")

    result = decimate_mesh(project=FIXTURE, strength=0.5, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    assert result["output_project"] == output_project
    assert os.path.isfile(output_project)

    before_text = export_obj(FIXTURE, str(tmp_path / "before.obj"))
    after_text = export_obj(output_project, str(tmp_path / "after.obj"))
    before_v, before_f = count_obj_vertices_and_faces(before_text)
    after_v, after_f = count_obj_vertices_and_faces(after_text)

    assert after_v < before_v, (before_v, after_v)
    assert after_f < before_f, (before_f, after_f)


@pytest.mark.integration
def test_decimate_mesh_in_place_mutates_the_caller_s_own_file(tmp_path):
    project = str(tmp_path / "project.arm")
    shutil.copy2(FIXTURE, project)
    before_text = export_obj(project, str(tmp_path / "before.obj"))
    before_v, _ = count_obj_vertices_and_faces(before_text)

    result = decimate_mesh(project=project, strength=0.5, in_place=True)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    assert result["output_project"] == project

    after_text = export_obj(project, str(tmp_path / "after.obj"))
    after_v, _ = count_obj_vertices_and_faces(after_text)
    assert after_v < before_v
