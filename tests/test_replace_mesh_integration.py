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
from armorpaint_mcp.server import replace_mesh, run_script

PHASE6 = os.path.join(os.path.dirname(__file__), "fixtures", "phase6")
UV = os.path.join(PHASE6, "uv")
SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


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


@pytest.fixture(scope="module")
def base_project(tmp_path_factory):
    """One-object project holding tests/fixtures/phase6/uv/base.obj as 'Base'."""
    out = str(tmp_path_factory.mktemp("uv") / "base.arm")
    mesh = os.path.abspath(os.path.join(UV, "base.obj")).replace("\\", "\\\\")
    script = ("void main() {\n"
              f'\tscript_append_mesh("{mesh}");\n'
              '\tobject_t *t = script_get_object("Tessellated");\n'
              "\tscript_object_remove(t);\n"
              f'\tproject_filepath_set("{os.path.abspath(out).replace(os.sep, "/")}");\n'
              "\tproject_save(0);\n}\n")
    result = run_script(project=SAMPLE, script=script)
    assert result["ok"] and os.path.isfile(out), result["error"]
    return out


@pytest.mark.integration
def test_round_trip_accepts_an_edited_mesh_with_kept_uvs(base_project, tmp_path):
    r = replace_mesh(base_project, "Base", os.path.join(UV, "r5_decimate.obj"),
                     output_project=str(tmp_path / "o.arm"))
    assert r["ok"] is True, r["error"]
    # Real numbers, not None, on success (controller addition 2).
    assert isinstance(r["iou"], float) and isinstance(r["retention"], float)
    assert r["iou"] >= 0.95 and r["retention"] >= 0.85


@pytest.mark.integration
def test_round_trip_rejects_a_re_unwrap_and_writes_nothing(base_project, tmp_path):
    out = tmp_path / "o.arm"
    r = replace_mesh(base_project, "Base", os.path.join(UV, "d1_smartuv45.obj"),
                     output_project=str(out))
    assert r["ok"] is False
    # "IoU" alone also appears in the passing-gate message; pin the actual
    # failure reason (controller addition 2).
    assert "the UV layout changed" in r["error"] and "IoU" in r["error"]
    assert r["output_project"] is None and r["iou"] is None and r["retention"] is None
    assert r["warnings"] is None
    assert not out.exists() and os.listdir(tmp_path) == []


@pytest.mark.integration
def test_round_trip_rejects_an_island_swap_that_iou_cannot_see(base_project, tmp_path):
    out = tmp_path / "o.arm"
    r = replace_mesh(base_project, "Base", os.path.join(UV, "d4_swap.obj"),
                     output_project=str(out))
    assert r["ok"] is False
    # Pin the retention-specific failure reason, not just the word
    # "retention" which also appears in the passing-gate message
    # (controller addition 2).
    assert "painted texels would stay in place" in r["error"] and "retention" in r["error"]
    assert r["output_project"] is None and r["iou"] is None and r["retention"] is None
    assert r["warnings"] is None
    assert not out.exists() and os.listdir(tmp_path) == []


@pytest.mark.integration
def test_swap_accepts_the_island_swap_and_reports_the_numbers(base_project, tmp_path):
    r = replace_mesh(base_project, "Base", os.path.join(UV, "d4_swap.obj"), mode="swap",
                     output_project=str(tmp_path / "o.arm"))
    assert r["ok"] is True, r["error"]
    assert isinstance(r["iou"], float) and isinstance(r["retention"], float)
    assert r["retention"] < 0.85


@pytest.mark.integration
def test_in_place_failure_leaves_the_caller_s_project_byte_identical(base_project, tmp_path):
    project = str(tmp_path / "mine.arm")
    shutil.copy2(base_project, project)
    before = _md5(project)
    r = replace_mesh(project, "Base", os.path.join(UV, "d1_smartuv45.obj"), in_place=True)
    assert r["ok"] is False
    assert _md5(project) == before
    assert os.listdir(tmp_path) == ["mine.arm"]


@pytest.mark.integration
def test_replace_root_with_glb_on_a_multi_object_project_warns_about_reimport(tmp_path):
    r = replace_mesh(os.path.join(PHASE6, "objects3_v2.arm"), "Tessellated",
                     os.path.join(PHASE6, "repl_grid5.glb"), mode="swap",
                     output_project=str(tmp_path / "o.arm"))
    assert r["ok"] is True, r["error"]
    assert any("Reimport Mesh" in w for w in r["warnings"])


@pytest.mark.integration
def test_fbx_from_blender_is_accepted_with_a_size_warning(tmp_path):
    r = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "Cone",
                     os.path.join(PHASE6, "repl_grid5.fbx"), mode="swap",
                     output_project=str(tmp_path / "o.arm"))
    assert r["ok"] is True, r["error"]
    assert any("size" in w for w in r["warnings"])


@pytest.mark.integration
def test_blend_without_armorpaint_blender_path_fails_closed(tmp_path):
    out = tmp_path / "o.arm"
    r = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "Cone",
                     os.path.join(PHASE6, "repl_grid5.blend"), mode="swap",
                     output_project=str(out))
    if r["ok"]:
        pytest.skip("ArmorPaint's Blender path is configured on this machine")
    assert "append_failed" in r["error"]
    assert not out.exists()


@pytest.mark.integration
def test_obj_without_uvs_and_multi_object_obj_are_rejected_before_launch(tmp_path):
    no_uv = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "Cone",
                         os.path.join(PHASE6, "repl_grid5_nouv.obj"), mode="swap",
                         output_project=str(tmp_path / "a.arm"))
    assert no_uv["ok"] is False and "no UVs" in no_uv["error"]
    two = tmp_path / "two.obj"
    grid = open(os.path.join(PHASE6, "repl_grid5.obj"), encoding="utf-8").read()
    two.write_text(grid + "\no Second\nv 9 9 9\nv 10 9 9\nv 9 10 9\nvt 0 0\nvt 1 0\nvt 0 1\n"
                   "f -3/-3 -2/-2 -1/-1\n", encoding="utf-8")
    multi = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "Cone", str(two),
                         mode="swap", output_project=str(tmp_path / "b.arm"))
    assert multi["ok"] is False and "2 objects" in multi["error"]


@pytest.mark.integration
def test_wrong_old_name_fails_and_writes_nothing(tmp_path):
    out = tmp_path / "o.arm"
    r = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "NoSuchObject",
                     os.path.join(PHASE6, "repl_grid5.obj"), mode="swap",
                     output_project=str(out))
    assert r["ok"] is False and "NoSuchObject" in r["error"]
    assert not out.exists()


@pytest.mark.integration
def test_output_directory_is_created(tmp_path):
    out = tmp_path / "new" / "deeper" / "o.arm"
    r = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "Cone",
                     os.path.join(PHASE6, "repl_grid5.obj"), mode="swap",
                     output_project=str(out))
    assert r["ok"] is True, r["error"]
    assert out.is_file()


@pytest.mark.integration
def test_non_ascii_output_directory_is_handled_cleanly(tmp_path):
    """Review Focus 1 (controller addition), tightened by the final-review
    C1 fix: a known-good fixture pair (objects3.arm/Cone + repl_grid5.obj,
    same pair test_output_directory_is_created uses), output_project under a
    non-ASCII, space-containing directory that doesn't exist yet. replace_mesh
    re-opens its output through ArmorPaint's ANSI argv (Known Issue #12), so
    it must refuse the path before launching and create nothing -- not even
    the directory."""
    out = tmp_path / "\u00d8 dir with spaces" / "o.arm"
    r = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "Cone",
                     os.path.join(PHASE6, "repl_grid5.obj"), mode="swap",
                     output_project=str(out))

    assert r["ok"] is False
    assert str(out) in r["error"] and "ASCII" in r["error"]
    assert r["output_project"] is None and r["iou"] is None and r["retention"] is None
    assert r["warnings"] is None
    assert os.listdir(tmp_path) == []
