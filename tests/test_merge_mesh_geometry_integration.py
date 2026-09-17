import os

import pytest

from armorpaint_mcp.server import merge_mesh_geometry, duplicate_mesh, inspect_project

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_merge_mesh_geometry_rejects_a_single_object_project():
    """No multi-object fixture exists (ROADMAP.md's "Known gaps" -- ArmorPaint
    silently no-ops when fewer than 2 objects exist, per util_mesh_merge_geometry's
    own internal guard, confirmed during this phase's spike). This must surface
    as a clear, explicit failure -- never a false ok=True with zero visible
    effect."""
    result = merge_mesh_geometry(project=FIXTURE, output_project="unused.arm")

    assert result["ok"] is False
    assert "only 1 object" in result["error"]
    assert "merge_mesh_geometry" in result["error"]
    assert result["output_project"] is None


@pytest.mark.integration
def test_merge_mesh_geometry_collapses_two_objects_into_one(tmp_path):
    duplicated = str(tmp_path / "duplicated.arm")
    dup_result = duplicate_mesh(project=FIXTURE, output_project=duplicated)
    assert dup_result["ok"] is True, dup_result["error"]

    merged = str(tmp_path / "merged.arm")
    result = merge_mesh_geometry(project=duplicated, output_project=merged)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    inspected = inspect_project(project=merged)
    assert inspected["ok"] is True, inspected["error"]
    assert len(inspected["objects"]) == 1, inspected["objects"]
