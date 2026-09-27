"""Unit tests for catalog.py's --api output parsing. The sample text below
is a trimmed, hand-built excerpt matching the real structure captured from
`ArmorPaint.exe <project> --api` on 2026-09-16 (see docs/PLAN.md Phase 3) --
real field names and real ENUM option text, shortened for a fast, offline
unit test. The real end-to-end shape is checked separately by
tests/test_inspect_project_integration.py against actual ArmorPaint output.
"""
import re
from unittest.mock import patch

import pytest

from armorpaint_mcp import server
from armorpaint_mcp.catalog import (
    CatalogError,
    EMITTED_MINIC_FUNCTIONS,
    blend_modes,
    extract_project_state,
    layer_blend_modes,
    missing_minic_functions,
    scene_objects,
)
from armorpaint_mcp.runner import ScriptResult
from armorpaint_mcp.script_gen import generate_script

_C_KEYWORDS = {"main", "if", "for", "while", "return", "sizeof"}


def _called_identifiers(script: str) -> set[str]:
    """Every `name(` in a minic script, ignoring string literals (a path like
    'Program Files (x86)' must not register 'Files' as a call)."""
    without_strings = re.sub(r'"(?:[^"\\]|\\.)*"', '""', script)
    return set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", without_strings)) - _C_KEYWORDS


def _captured_scripts(tmp_path) -> list[str]:
    """Scripts produced by the REAL builders: every create_procedural_material
    node type and every mesh-edit tool (run_minic_script patched to capture)."""
    scripts = [generate_script({"type": t}, str(tmp_path / "Program Files (x86)"))
               for t in ("checker", "solid", "noise", "voronoi")]
    project = tmp_path / "p.arm"
    project.write_bytes(b"x")
    captured = []

    def capture(binary, project_, script, timeout_s):
        captured.append(script)
        return ScriptResult(ok=False, stdout="", stderr="", error="captured")

    calls = [
        lambda: server.decimate_mesh(str(project), 0.5, str(tmp_path / "o.arm")),
        lambda: server.bevel_mesh(str(project), 0.1, str(tmp_path / "o.arm")),
        lambda: server.subdivide_mesh(str(project), str(tmp_path / "o.arm")),
        lambda: server.smooth_mesh(str(project), str(tmp_path / "o.arm")),
        lambda: server.duplicate_mesh(str(project), str(tmp_path / "o.arm")),
        lambda: server.unwrap_mesh_uvs(str(project), str(tmp_path / "o.arm")),
        lambda: server.check_mesh_uvs(str(project)),
    ]
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=capture):
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        for call in calls:
            call()
    # merge_mesh_geometry runs run_api first; its minic call is the same shape
    scripts += captured + [server._save_script(["util_mesh_merge_geometry();"],
                                               str(tmp_path / "f.arm"))]
    return scripts

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


def test_every_emitted_minic_call_is_in_the_registry(tmp_path):
    called = set().union(*(_called_identifiers(s) for s in _captured_scripts(tmp_path)))
    assert called <= set(EMITTED_MINIC_FUNCTIONS), sorted(called - set(EMITTED_MINIC_FUNCTIONS))


def test_missing_minic_functions_matches_whole_names_only():
    api = "void util_mesh_merge_geometry_down(mesh_object_t *a);\nvoid project_save(i32 x);\n"
    missing = missing_minic_functions(api)
    assert "util_mesh_merge_geometry" in missing   # a longer name doesn't count
    assert "project_save" not in missing


def test_missing_minic_functions_empty_when_all_declared():
    api = "\n".join(f"void {n}();" for n in EMITTED_MINIC_FUNCTIONS)
    assert missing_minic_functions(api) == []


def test_extract_project_state_keeps_windows_backslash_paths_literal():
    """ArmorPaint's armpack_to_json_value writes strings with NO escaping
    (base/sources/iron_armpack.c:799-801), so every backslash in the dump is
    a literal character, never a JSON escape (Known Issue #10)."""
    api_text = ('/* Current project state:\n'
                '{"mesh_assets": ["C:\\Users\\x\\tmp\\new\\grid.obj"], "n": 1}'
                '\n\nScene objects in world space\n*/\n')

    state = extract_project_state(api_text)

    assert state["mesh_assets"] == ["C:\\Users\\x\\tmp\\new\\grid.obj"]
    assert state["n"] == 1
