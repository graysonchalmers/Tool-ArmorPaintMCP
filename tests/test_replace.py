import os

import pytest

from armorpaint_mcp import replace as rp
from armorpaint_mcp.script_gen import NodeSpecError

GOOD_OBJ = ("o ReplGrid\nv 0 0 0\nv 1 0 0\nv 1 1 0\n"
            "vt 0 0\nvt 1 0\nvt 1 1\nf 1/1 2/2 3/3\n")

STATE = {
    "mesh_datas": [{"name": "Tessellated"}, {"name": "Cone"}, {"name": "Torus"}],
    "mesh_transforms": [[1.0] * 16, [2.0] * 16, [3.0] * 16],
    "mesh_parents[i32]": [-1, 0, -1],
    "mesh_materials[i32]": [-1, 1, -1],
    "material_nodes": [{"name": "Material"}, {"name": "MatB"}],
}


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_precheck_accepts_a_single_object_obj_with_uvs(tmp_path):
    rp.precheck_replacement(_write(tmp_path, "g.obj", GOOD_OBJ), allow_udim=False)


@pytest.mark.parametrize("ext", ["fbx", "glb", "gltf", "blend"])
def test_precheck_accepts_other_native_formats_without_parsing(tmp_path, ext):
    rp.precheck_replacement(_write(tmp_path, f"m.{ext}", "binary"), allow_udim=False)


def test_precheck_rejects_an_unsupported_extension(tmp_path):
    with pytest.raises(rp.ReplaceError, match="stl"):
        rp.precheck_replacement(_write(tmp_path, "m.stl", "x"), allow_udim=False)


def test_precheck_rejects_an_obj_without_uvs(tmp_path):
    no_uv = "o G\nv 0 0 0\nv 1 0 0\nv 1 1 0\nf 1 2 3\n"
    with pytest.raises(rp.ReplaceError, match="no UVs"):
        rp.precheck_replacement(_write(tmp_path, "g.obj", no_uv), allow_udim=False)


def test_precheck_rejects_an_obj_with_two_objects(tmp_path):
    two = GOOD_OBJ + "o Second\nv 5 5 5\nv 6 5 5\nv 5 6 5\nvt 0 0\nvt 1 0\nvt 0 1\nf 4/4 5/5 6/6\n"
    with pytest.raises(rp.ReplaceError, match="2 objects"):
        rp.precheck_replacement(_write(tmp_path, "g.obj", two), allow_udim=False)


def test_precheck_rejects_out_of_range_uvs_unless_allow_udim(tmp_path):
    path = _write(tmp_path, "g.obj", GOOD_OBJ.replace("vt 1 1", "vt 1.5 1"))
    with pytest.raises(rp.ReplaceError, match=r"outside \[0,1\]"):
        rp.precheck_replacement(path, allow_udim=False)
    rp.precheck_replacement(path, allow_udim=True)


def test_state_lookups_follow_mesh_datas_order():
    assert rp.object_names(STATE) == ["Tessellated", "Cone", "Torus"]
    assert rp.local_transform(STATE, "Cone") == [2.0] * 16
    assert rp.parent_name(STATE, "Cone") == "Tessellated"
    assert rp.parent_name(STATE, "Torus") is None
    assert rp.material_override_name(STATE, "Cone") == "MatB"
    assert rp.material_override_name(STATE, "Torus") is None


def test_material_override_fails_closed_on_a_duplicate_material_name():
    dup = dict(STATE, material_nodes=[{"name": "MatB"}, {"name": "MatB"}])
    with pytest.raises(rp.ReplaceError, match="MatB"):
        rp.material_override_name(dup, "Cone")


def test_build_replace_script_shape(tmp_path):
    new_mesh = str(tmp_path / "Program Files (x86)" / "grid.obj")
    fresh = str(tmp_path / "out.ap-mcp-abc.tmp.arm")
    script = rp.build_replace_script("Cone", new_mesh, fresh, "MatB")

    assert script.startswith("void main() {\n")
    assert 'script_get_object("Cone");' in script
    assert f'script_object_set_name(old, "{rp.REPLACED_PLACEHOLDER}");' in script
    assert '"' + new_mesh.replace("\\", "\\\\") + '"' in script      # doubled backslashes
    assert 'script_get_material("MatB");' in script
    body = script.strip().splitlines()
    assert body[-3].strip().startswith("project_filepath_set(")
    assert body[-2].strip() == "project_save(0);"                     # save is last
    assert script.index("script_append_mesh(") < script.index("script_object_remove(old);")


def test_build_replace_script_without_an_override_clears_the_material(tmp_path):
    script = rp.build_replace_script("Torus", str(tmp_path / "g.obj"),
                                     str(tmp_path / "f.arm"), None)
    assert "script_object_set_material(nw, NULL);" in script
    assert "script_get_material" not in script


@pytest.mark.parametrize("bad", ['Co"ne', "Co\\ne"])
def test_build_replace_script_rejects_names_minic_cannot_carry(tmp_path, bad):
    with pytest.raises(NodeSpecError):
        rp.build_replace_script(bad, str(tmp_path / "g.obj"), str(tmp_path / "f.arm"), None)


def test_marker_error_reads_the_first_reason():
    assert rp.marker_error("x\nREPLACE_ERR old_not_found\nREPLACE_ERR other\n") == "old_not_found"
    assert rp.marker_error("Project saved\n") is None
