import os

import pytest

from armorpaint_mcp.server import subdivide_mesh
from tests._mesh_edit_test_helpers import export_obj, count_obj_vertices_and_faces

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_subdivide_mesh_quadruples_face_count(tmp_path):
    """Confirmed empirically during this phase's own spike: subdivide is an
    exact 4x face-count operation (each triangle -> 4). Asserting the exact
    ratio here, not just an increase, since this one IS deterministic and a
    ratio check is a stronger proof than inequality alone."""
    output_project = str(tmp_path / "subdivided.arm")

    result = subdivide_mesh(project=FIXTURE, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    _, before_f = count_obj_vertices_and_faces(
        export_obj(FIXTURE, str(tmp_path / "before.obj")))
    _, after_f = count_obj_vertices_and_faces(
        export_obj(output_project, str(tmp_path / "after.obj")))

    assert after_f == before_f * 4, (before_f, after_f)
