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


def test_scene_objects_empty_list_when_no_objects_section():
    assert scene_objects("nothing here") == []
