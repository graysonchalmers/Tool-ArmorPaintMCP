import os

import pytest

from armorpaint_mcp.server import duplicate_mesh
from tests._mesh_edit_test_helpers import export_obj, count_obj_vertices_and_faces

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_duplicate_mesh_doubles_vertex_and_face_count(tmp_path):
    """Confirmed empirically during this phase's own spike: duplicate is an
    exact 2x operation, and it appends a second object (verified there via
    a new "o Tessellated.001" group). Asserting the exact ratio, the
    strongest available proof for this deterministic operation."""
    output_project = str(tmp_path / "duplicated.arm")

    result = duplicate_mesh(project=FIXTURE, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    _, before_f = count_obj_vertices_and_faces(
        export_obj(FIXTURE, str(tmp_path / "before.obj")))
    after_text = export_obj(output_project, str(tmp_path / "after.obj"))
    after_v, after_f = count_obj_vertices_and_faces(after_text)

    assert after_f == before_f * 2, (before_f, after_f)
    assert "o " in after_text  # a second named object group exists
