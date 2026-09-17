import os

import pytest

from armorpaint_mcp.server import smooth_mesh
from tests._mesh_edit_test_helpers import (export_obj, count_obj_vertices_and_faces,
                                           obj_normal_lines)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_smooth_mesh_preserves_topology_but_changes_normals(tmp_path):
    """Smoothing does not change vertex/face counts (it moves vertices and
    recomputes normals, it doesn't add or remove geometry). Confirmed
    empirically during this phase's own spike; asserted live here via
    before/after comparison rather than a hardcoded normal count, since the
    spike's own transcript had an internal inconsistency on the exact
    number -- the topology-preserved + normals-changed relationship is the
    robust, reproducible claim."""
    output_project = str(tmp_path / "smoothed.arm")

    result = smooth_mesh(project=FIXTURE, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    before_text = export_obj(FIXTURE, str(tmp_path / "before.obj"))
    after_text = export_obj(output_project, str(tmp_path / "after.obj"))

    before_v, before_f = count_obj_vertices_and_faces(before_text)
    after_v, after_f = count_obj_vertices_and_faces(after_text)
    assert (after_v, after_f) == (before_v, before_f), "smooth should not change topology"

    assert obj_normal_lines(after_text) != obj_normal_lines(before_text), (
        "smooth should change vertex normals even though topology is unchanged")
