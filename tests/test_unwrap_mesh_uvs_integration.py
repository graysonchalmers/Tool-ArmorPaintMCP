import os

import pytest

from armorpaint_mcp.server import unwrap_mesh_uvs
from tests._mesh_edit_test_helpers import export_obj, obj_uv_lines

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_unwrap_mesh_uvs_changes_the_uv_coordinates(tmp_path):
    """Confirmed empirically during this phase's own spike: real UV coords
    change (all 144 vt lines differed on the fixture), the topology does
    not (this is a UV operation, not a geometry operation)."""
    output_project = str(tmp_path / "unwrapped.arm")

    result = unwrap_mesh_uvs(project=FIXTURE, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    before_uvs = obj_uv_lines(export_obj(FIXTURE, str(tmp_path / "before.obj")))
    after_uvs = obj_uv_lines(export_obj(output_project, str(tmp_path / "after.obj")))

    assert len(after_uvs) == len(before_uvs)  # same vertex count, same UV count
    assert after_uvs != before_uvs, "unwrap should produce different UV coordinates"
