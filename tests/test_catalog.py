"""Unit tests for catalog.py's --api output parsing. The sample text below
is a trimmed, hand-built excerpt matching the real structure captured from
`ArmorPaint.exe <project> --api` on 2026-09-16 (see docs/PLAN.md Phase 3) --
real field names and real ENUM option text, shortened for a fast, offline
unit test. The real end-to-end shape is checked separately by
tests/test_inspect_project_integration.py against actual ArmorPaint output.
"""
import pytest

from armorpaint_mcp.catalog import (
    CatalogError,
    blend_modes,
    extract_project_state,
    layer_blend_modes,
    mesh_edit_patch_missing,
    scene_objects,
)

SAMPLE_API_TEXT = '''\
// Material nodes reference:
// TEX_CHECKER | in: 0 Vector, 1 Color 1, 2 Color 2, 3 Scale | out: 0 Color, 1 Factor
// MIX_RGB | in: 0 Factor, 1 Color 1, 2 Color 2 | out: 0 Color
//     button 0 blend_type ENUM: 0 Mix, 1 Darken, 2 Multiply, 3 Burn, 4 Lighten, 5 Screen, 6 Dodge, 7 Add, 8 Overlay, 9 Soft Light, 10 Linear Light, 11 Difference, 12 Exclusion, 13 Subtract, 14 Divide, 15 Hue, 16 Saturation, 17 Color, 18 Value
//     button 1 Clamp Factor BOOL
// MIX_NORMAL_MAP | in: 0 Normal Map 1, 1 Normal Map 2 | out: 0 Normal Map
//     button 0 blend_type ENUM: 0 Partial Derivative, 1 Whiteout, 2 Reoriented
//
// Pre-created material output node:
// OUTPUT_MATERIAL_PBR | in: 0 Base Color | out:

/* Current project state:
{"version":"16","material_nodes":[{"name":"Material 1","nodes":[],"links":[]}],"layer_datas":[{"name":"Layer 1","res":2048,"bpp":8,"blending":0,"visible":true,"opacity_mask":1.0,"fill_material":-1,"parent":-1}],"mesh_datas":[{"name":"Tessellated"}]}

Scene objects in world space, z axis up:
"Tessellated": location (0.000, 0.000, 0.000), size (1.039, 1.039, 1.039), bounds min (-0.520, -0.520, -0.520) max (0.520, 0.520, 0.520)

script_shape_add() shapes:
"cone"
"cube"
*/

Reply with C code only wrapped in a ```c markdown fence.
'''


def test_blend_modes_reads_mix_rgb_enum_not_mix_normal_map():
    modes = blend_modes(SAMPLE_API_TEXT)

    assert modes[0] == "Mix"
    assert modes[1] == "Darken"
    assert modes[-1] == "Value"
    assert len(modes) == 19
    assert "Partial Derivative" not in modes  # that's MIX_NORMAL_MAP's list, not MIX_RGB's


def test_blend_modes_raises_when_mix_rgb_not_found():
    with pytest.raises(CatalogError, match="MIX_RGB"):
        blend_modes("no material node reference here")


def test_extract_project_state_parses_the_json_block():
    state = extract_project_state(SAMPLE_API_TEXT)

    assert state["version"] == "16"
    assert state["material_nodes"][0]["name"] == "Material 1"
    assert state["layer_datas"][0]["name"] == "Layer 1"
    assert state["mesh_datas"][0]["name"] == "Tessellated"


def test_extract_project_state_raises_when_marker_missing():
    with pytest.raises(CatalogError, match="Current project state"):
        extract_project_state("no state block here")


def test_scene_objects_parses_name_location_size():
    objects = scene_objects(SAMPLE_API_TEXT)

    assert objects == [{
        "name": "Tessellated",
        "location": [0.0, 0.0, 0.0],
        "size": [1.039, 1.039, 1.039],
    }]


def test_scene_objects_raises_when_marker_missing():
    with pytest.raises(CatalogError, match="Scene objects in world space"):
        scene_objects("nothing here")


def test_scene_objects_empty_list_when_section_present_but_no_objects():
    text = (
        "Scene objects in world space, z axis up:\n"
        "\n"
        "script_shape_add() shapes:\n"
        '"cone"\n'
    )
    assert scene_objects(text) == []


def test_layer_blend_modes_has_18_entries_and_no_exclusion():
    """Regression test for the layer/MIX_RGB enum mix-up (Finding 1 of the
    Phase 3 review): layer_datas[].blending indexes ArmorPaint's own
    blend_type_t (enums.h), an 18-entry enum, NOT the 19-entry MIX_RGB
    material-node ENUM that blend_modes() parses (that one inserts an extra
    "Exclusion" at index 12). Using blend_modes() for a layer's blending
    mislabels index 12 as "Exclusion" (real value: "Subtract") and index 17
    as "Color" (real value: "Value")."""
    modes = layer_blend_modes()

    assert len(modes) == 18
    assert modes[12] == "Subtract"
    assert modes[17] == "Value"
    assert "Exclusion" not in modes


def test_mesh_edit_patch_missing_reports_all_seven_when_none_present():
    stock_api_text = "// ArmorPaint script API\n\ntypedef struct i8_array_t {\n"
    missing = mesh_edit_patch_missing(stock_api_text)
    assert sorted(missing) == sorted([
        "util_mesh_decimate", "util_mesh_smooth", "util_mesh_bevel",
        "util_mesh_subdivide", "util_mesh_merge_geometry",
        "util_mesh_duplicate", "plugin_uv_unwrap_button",
    ])


def test_mesh_edit_patch_missing_empty_when_all_present():
    patched_api_text = (
        "util_mesh_decimate(f strength)\n"
        "util_mesh_smooth()\n"
        "util_mesh_bevel(f amount)\n"
        "util_mesh_subdivide()\n"
        "util_mesh_merge_geometry()\n"
        "util_mesh_duplicate()\n"
        "plugin_uv_unwrap_button()\n"
    )
    assert mesh_edit_patch_missing(patched_api_text) == []


def test_mesh_edit_patch_missing_reports_only_the_absent_ones():
    partial = "util_mesh_decimate(f strength)\nutil_mesh_smooth()\n"
    missing = mesh_edit_patch_missing(partial)
    assert "util_mesh_decimate" not in missing
    assert "util_mesh_smooth" not in missing
    assert "util_mesh_bevel" in missing
    assert len(missing) == 5
