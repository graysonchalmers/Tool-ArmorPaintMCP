import asyncio
import os
import re
from unittest.mock import patch

import pytest

from armorpaint_mcp import server
from armorpaint_mcp.catalog import CatalogError
from armorpaint_mcp.runner import DEFAULT_TIMEOUT_S, ExportResult, ApiResult, ScriptResult
from armorpaint_mcp.server import (mcp, reexport_project, create_procedural_material,
                                   list_available_presets, inspect_project, run_script,
                                   decimate_mesh, bevel_mesh, subdivide_mesh, smooth_mesh,
                                   duplicate_mesh, merge_mesh_geometry, unwrap_mesh_uvs,
                                   check_mesh_uvs)


@pytest.fixture(autouse=True)
def reset_config_memo():
    """`server._cfg` is a module global memo. Reset it around every test so a
    config loaded (or mocked) by one test can't leak into the next."""
    server._cfg = None
    yield
    server._cfg = None


def test_reexport_project_returns_error_for_unknown_preset(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets", return_value=["generic"]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = reexport_project(
            project=str(tmp_path / "project.arm"),
            preset="not_a_real_preset",
            output_dir=str(tmp_path / "out"),
        )

    assert result["ok"] is False
    assert "not_a_real_preset" in result["error"]
    assert "generic" in result["error"]
    assert result["files"] is None


def test_reexport_project_rejects_path_outside_allowed_roots(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside_project = tmp_path / "elsewhere" / "project.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets", return_value=["generic"]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = [str(root)]
        result = reexport_project(
            project=str(outside_project),
            preset="generic",
            output_dir=str(root / "out"),
        )

    assert result["ok"] is False
    assert "allowed roots" in result["error"]
    assert result["files"] is None


def test_reexport_project_calls_runner_and_returns_files(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    output_dir = tmp_path / "out"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets", return_value=["generic"]), \
         patch("armorpaint_mcp.server.export_textures") as mock_export:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_export.return_value = ExportResult(
            ok=True, files=[str(output_dir / "project_base.png")])

        result = reexport_project(
            project=str(project), preset="generic", output_dir=str(output_dir))

    assert result == {"ok": True, "files": [str(output_dir / "project_base.png")],
                       "error": None}
    mock_export.assert_called_once_with(
        mock_cfg.return_value.binary, str(project), "png", "generic", str(output_dir))


def test_reexport_project_blames_the_config_not_the_preset_for_a_bad_binary(
        tmp_path, monkeypatch):
    """A missing AP_BINARY used to surface as "unknown preset 'generic';
    available: " -- the preset check running against an install that isn't
    there. Validating config first makes it say what's actually wrong."""
    monkeypatch.setenv("AP_BINARY", str(tmp_path / "nope" / "ArmorPaint.exe"))
    monkeypatch.setenv("AP_DOTENV", str(tmp_path / "absent.env"))

    with pytest.raises(FileNotFoundError, match="AP_BINARY"):
        reexport_project(project=str(tmp_path / "project.arm"), preset="generic",
                          output_dir=str(tmp_path / "out"))


def test_ensure_ready_does_not_memoize_an_invalid_config(tmp_path, monkeypatch):
    """Fail-fast has to fail on EVERY call, not just the first one."""
    monkeypatch.setenv("AP_BINARY", str(tmp_path / "nope" / "ArmorPaint.exe"))
    monkeypatch.setenv("AP_DOTENV", str(tmp_path / "absent.env"))

    for _ in range(2):
        with pytest.raises(FileNotFoundError):
            server._ensure_ready()
    assert server._cfg is None


def test_reexport_project_is_registered_as_an_mcp_tool():
    """The integration test calls reexport_project as a plain function, which
    proves nothing about the MCP layer. This asserts the tool is actually
    registered on the server object an MCP client would talk to."""
    tools = asyncio.run(mcp.list_tools())

    by_name = {t.name: t for t in tools}
    assert "reexport_project" in by_name, sorted(by_name)
    tool = by_name["reexport_project"]
    assert "Re-export" in tool.description
    assert set(tool.input_schema["properties"]) == {"project", "preset", "output_dir"}
    assert set(tool.input_schema.get("required", [])) == {
        "project", "preset", "output_dir"}


def test_create_procedural_material_returns_error_for_unknown_preset(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets", return_value=["generic"]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = create_procedural_material(
            node_spec={"type": "checker"},
            output_dir=str(tmp_path / "out"),
            preset="not_a_real_preset",
        )

    assert result["ok"] is False
    assert "not_a_real_preset" in result["error"]
    assert "generic" in result["error"]
    assert result["files"] is None


def test_create_procedural_material_rejects_path_outside_allowed_roots(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside_dir = tmp_path / "elsewhere" / "out"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets", return_value=["generic"]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = [str(root)]
        result = create_procedural_material(
            node_spec={"type": "checker"},
            output_dir=str(outside_dir),
            preset="generic",
        )

    assert result["ok"] is False
    assert "allowed roots" in result["error"]
    assert result["files"] is None


def test_create_procedural_material_rejects_non_generic_preset(tmp_path):
    """export_texture_run() has no preset argument -- the single-process
    script flow can only ever export whatever preset last configured the
    export box, which is always 'generic' in this headless flow. Requesting
    anything else must be rejected up front, not silently mis-exported."""
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets",
               return_value=["generic", "unreal"]), \
         patch("armorpaint_mcp.server.run_procedural_material") as mock_run:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = create_procedural_material(
            node_spec={"type": "checker"},
            output_dir=str(tmp_path / "out"),
            preset="unreal",
        )

    assert result["ok"] is False
    assert "only supports the 'generic' preset" in result["error"]
    assert result["files"] is None
    mock_run.assert_not_called()


def test_create_procedural_material_rejects_invalid_node_spec(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets", return_value=["generic"]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = create_procedural_material(
            node_spec={"type": "not_a_real_type"},
            output_dir=str(tmp_path / "out"),
            preset="generic",
        )

    assert result["ok"] is False
    assert "unsupported node_spec type" in result["error"]
    assert result["files"] is None


def test_create_procedural_material_calls_runner_and_returns_files(tmp_path):
    output_dir = tmp_path / "out"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets", return_value=["generic"]), \
         patch("armorpaint_mcp.server.run_procedural_material") as mock_run:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run.return_value = ExportResult(
            ok=True, files=[str(output_dir / "untitled_base.png")])

        result = create_procedural_material(
            node_spec={"type": "solid", "params": {"color": [1.0, 0.0, 0.0]}},
            output_dir=str(output_dir), preset="generic")

    assert result == {"ok": True, "files": [str(output_dir / "untitled_base.png")],
                       "error": None}
    mock_run.assert_called_once()
    call_args = mock_run.call_args.args
    assert call_args[0] == mock_cfg.return_value.binary
    assert "script_material_create_node_at(\"RGB\"" in call_args[1]
    assert call_args[2] == str(output_dir)
    assert call_args[3] == "generic"


def test_create_procedural_material_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())

    by_name = {t.name: t for t in tools}
    assert "create_procedural_material" in by_name, sorted(by_name)
    tool = by_name["create_procedural_material"]
    assert set(tool.input_schema["properties"]) == {"node_spec", "output_dir", "preset"}
    assert set(tool.input_schema.get("required", [])) == {"node_spec", "output_dir"}


def test_list_available_presets_returns_presets_dict(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets",
               return_value=["generic", "unity"]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")

        result = list_available_presets()

    assert result == {"presets": ["generic", "unity"]}


def test_list_available_presets_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())

    by_name = {t.name: t for t in tools}
    assert "list_available_presets" in by_name, sorted(by_name)


def test_inspect_project_rejects_path_outside_allowed_roots(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside_project = tmp_path / "elsewhere" / "project.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = [str(root)]
        result = inspect_project(project=str(outside_project))

    assert result["ok"] is False
    assert result["objects"] is None
    assert "allowed" in result["error"]


def test_inspect_project_surfaces_run_api_failure(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_api") as mock_run_api:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run_api.return_value = ApiResult(ok=False, text="", error="'--api' exited 1")

        result = inspect_project(project=str(project))

    assert result["ok"] is False
    assert result["error"] == "'--api' exited 1"


def test_inspect_project_composes_catalog_parses_into_result(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    fake_api_text = "fake api text"
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_api") as mock_run_api, \
         patch("armorpaint_mcp.server.extract_project_state") as mock_state, \
         patch("armorpaint_mcp.server.layer_blend_modes", return_value=["Mix", "Darken"]), \
         patch("armorpaint_mcp.server.scene_objects",
               return_value=[{"name": "Tessellated", "location": [0.0, 0.0, 0.0],
                              "size": [1.0, 1.0, 1.0]}]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run_api.return_value = ApiResult(ok=True, text=fake_api_text)
        mock_state.return_value = {
            "material_nodes": [{"name": "Material 1", "nodes": [1, 2, 3]}],
            "layer_datas": [{"name": "Layer 1", "res": 2048, "visible": True,
                             "blending": 1}],
        }

        result = inspect_project(project=str(project))

    assert result["ok"] is True
    assert result["error"] is None
    assert result["objects"] == [{"name": "Tessellated", "location": [0.0, 0.0, 0.0],
                                  "size": [1.0, 1.0, 1.0]}]
    assert result["materials"] == [{"name": "Material 1", "node_count": 3}]
    assert result["layers"] == [{"name": "Layer 1", "resolution": 2048,
                                 "visible": True, "blending": "Darken"}]


def test_inspect_project_surfaces_catalog_parse_error(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_api") as mock_run_api, \
         patch("armorpaint_mcp.server.extract_project_state",
               side_effect=CatalogError("no state block")):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run_api.return_value = ApiResult(ok=True, text="text")

        result = inspect_project(project=str(project))

    assert result["ok"] is False
    assert "no state block" in result["error"]


def test_inspect_project_surfaces_scene_objects_parse_error(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_api") as mock_run_api, \
         patch("armorpaint_mcp.server.extract_project_state", return_value={}), \
         patch("armorpaint_mcp.server.scene_objects",
               side_effect=CatalogError("no scene objects section")):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run_api.return_value = ApiResult(ok=True, text="text")

        result = inspect_project(project=str(project))

    assert result["ok"] is False
    assert "no scene objects section" in result["error"]


def test_inspect_project_rejects_nonexistent_project_path(tmp_path):
    """Confirmed against the real ArmorPaint binary: a nonexistent (or
    non-.arm) project path makes ArmorPaint silently ignore the bogus
    argument and open its own default empty project instead -- without this
    check, inspect_project would report ok:True with that phantom project's
    data as if it had read the caller's project. The check happens before
    run_api is ever invoked, so no mocking of it is needed here."""
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = inspect_project(project=str(tmp_path / "does_not_exist.arm"))

    assert result["ok"] is False
    assert result["objects"] is None
    assert result["materials"] is None
    assert result["layers"] is None
    assert "does_not_exist.arm" in result["error"]
    assert "not an existing .arm project file" in result["error"]


def test_inspect_project_rejects_existing_file_with_wrong_extension(tmp_path):
    """Same failure mode as the nonexistent-path case: a real file that
    isn't a .arm project (e.g. README.md) also makes ArmorPaint silently
    fall back to its default project."""
    not_arm = tmp_path / "README.md"
    not_arm.write_text("not a project")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = inspect_project(project=str(not_arm))

    assert result["ok"] is False
    assert "not an existing .arm project file" in result["error"]


def test_inspect_project_uses_layer_blend_modes_not_material_blend_modes(tmp_path):
    """Regression test for the layer/MIX_RGB blend-enum mix-up (Finding 1):
    layer_datas[].blending is an index into ArmorPaint's own blend_type_t
    (paint/sources/enums.h), an 18-entry enum with no "Exclusion" -- NOT the
    19-entry MIX_RGB material-node ENUM that blend_modes() parses. Index 12
    is "Subtract" in the real layer enum but would be misreported as
    "Exclusion" if the material-node list were used instead."""
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_api") as mock_run_api, \
         patch("armorpaint_mcp.server.extract_project_state") as mock_state, \
         patch("armorpaint_mcp.server.scene_objects", return_value=[]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run_api.return_value = ApiResult(ok=True, text="fake api text")
        mock_state.return_value = {
            "material_nodes": [],
            "layer_datas": [{"name": "Layer 1", "res": 2048, "visible": True,
                             "blending": 12}],
        }

        result = inspect_project(project=str(project))

    assert result["ok"] is True
    assert result["layers"] == [{"name": "Layer 1", "resolution": 2048,
                                 "visible": True, "blending": "Subtract"}]


def test_inspect_project_registered_as_mcp_tool():
    names = [t.name for t in asyncio.run(mcp.list_tools())]
    assert "inspect_project" in names


def test_run_script_rejects_path_outside_allowed_roots(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside_project = tmp_path / "elsewhere" / "project.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = [str(root)]
        result = run_script(project=str(outside_project), script="void main() {}")

    assert result["ok"] is False
    assert result["stdout"] is None
    assert "allowed" in result["error"]


def test_run_script_rejects_nonexistent_project_path(tmp_path):
    """Same phantom-default-project trap inspect_project guards against
    (Phase 3 Finding 2): a bogus project path would otherwise make
    ArmorPaint silently run the caller's script against its own empty
    default project instead of failing."""
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = run_script(project=str(tmp_path / "does_not_exist.arm"),
                            script="void main() {}")

    assert result["ok"] is False
    assert result["stdout"] is None
    assert "not an existing .arm project file" in result["error"]


def test_run_script_rejects_existing_file_with_wrong_extension(tmp_path):
    not_arm = tmp_path / "README.md"
    not_arm.write_text("not a project")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = run_script(project=str(not_arm), script="void main() {}")

    assert result["ok"] is False
    assert "not an existing .arm project file" in result["error"]
    assert result["stdout"] is None
    assert result["stderr"] is None


def test_run_script_calls_runner_and_returns_result(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        # NOTE: this "out" is a mocked value for plumbing verification only --
        # the real ArmorPaint binary's script-facing console output
        # (console_log() etc.) writes via WriteConsoleW directly to the
        # console handle, which subprocess pipe capture does not see on this
        # platform, so stdout/stderr are typically empty in practice even on
        # a successful real run. This test only checks that server.run_script
        # forwards whatever runner.run_minic_script returns.
        mock_run.return_value = ScriptResult(ok=True, stdout="out", stderr="")

        result = run_script(project=str(project), script="void main() {}")

    assert result == {"ok": True, "stdout": "out", "stderr": "", "error": None}
    mock_run.assert_called_once_with(
        mock_cfg.return_value.binary, str(project), "void main() {}", DEFAULT_TIMEOUT_S)


def test_run_script_passes_custom_timeout_s_through(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run.return_value = ScriptResult(ok=True, stdout="", stderr="")

        run_script(project=str(project), script="void main() {}", timeout_s=120.0)

    mock_run.assert_called_once_with(
        mock_cfg.return_value.binary, str(project), "void main() {}", 120.0)


def test_run_script_keeps_stdout_stderr_on_runner_failure(tmp_path):
    """Fix round 1, Finding 1: once the runner has actually launched
    ArmorPaint, its stdout/stderr are diagnostic evidence (e.g. the
    "<script>:N: error: ..." line that caused ok=False) -- nulling them on
    failure would throw that evidence away. Only a failure that never
    reaches the runner (bad project path, outside allowed_roots -- see the
    rejects_* tests above) nulls stdout/stderr, because the runner never
    produced any."""
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run.return_value = ScriptResult(ok=False, stdout="partial",
                                             stderr="err", error="'--script' exited 1: err")

        result = run_script(project=str(project), script="void main() {}")

    assert result == {"ok": False, "stdout": "partial", "stderr": "err",
                       "error": "'--script' exited 1: err"}
    assert set(result) == {"ok", "stdout", "stderr", "error"}


def test_run_script_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())

    by_name = {t.name: t for t in tools}
    assert "run_script" in by_name, sorted(by_name)
    tool = by_name["run_script"]
    assert set(tool.input_schema["properties"]) == {"project", "script", "timeout_s"}
    assert set(tool.input_schema.get("required", [])) == {"project", "script"}


def test_decimate_mesh_requires_output_project_unless_in_place(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = decimate_mesh(project=str(project), strength=0.5)

    assert result["ok"] is False
    assert "output_project is required" in result["error"]


def test_decimate_mesh_rejects_output_project_together_with_in_place(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(tmp_path / "out.arm"), in_place=True)

    assert result["ok"] is False
    assert "in_place=True" in result["error"]


def test_decimate_mesh_rejects_a_nonexistent_project_path(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = decimate_mesh(project=str(tmp_path / "nope.arm"), strength=0.5,
                               output_project=str(tmp_path / "out.arm"))

    assert result["ok"] is False
    assert "not an existing .arm project file" in result["error"]
    assert result["output_project"] is None


def test_decimate_mesh_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert "decimate_mesh" in by_name, sorted(by_name)
    tool = by_name["decimate_mesh"]
    assert set(tool.input_schema["properties"]) == {
        "project", "strength", "output_project", "in_place", "timeout_s"}
    assert set(tool.input_schema.get("required", [])) == {"project", "strength"}


def test_decimate_mesh_rejects_output_project_same_as_project(tmp_path):
    """Cross-task finding (final whole-branch review): output_project naming
    the same file as project (directly, or via a directory path that
    resolves to it) used to make shutil.copy2 raise uncaught -- observed as
    PermissionError [WinError 32] on this machine, though shutil.copy2
    documents SameFileError for the exact-same-path case. Either way, the
    exception escaped _run_mesh_edit entirely, which the MCP layer surfaces
    as an opaque UnexpectedToolError instead of this project's established
    {"ok": False, ...} contract every tool's docstring promises. This must
    return a clean failure instead of raising -- shares _run_mesh_edit with
    every other mesh-edit tool, so decimate_mesh alone proves the fix for
    all of them."""
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        # No mock on run_minic_script -- if this reaches it (i.e. the guard
        # didn't catch the same-file case), the test would raise/hang instead
        # of asserting cleanly, which is itself a signal something's wrong.
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(project))

    assert result["ok"] is False
    assert result["output_project"] is None
    assert "same file" in result["error"]
    assert "in_place=True" in result["error"]


def _fresh_path_in(script: str) -> str:
    """The path _save_script told ArmorPaint to save to."""
    return re.search(r'project_filepath_set\("([^"]+)"\);', script).group(1)


def _saving_run(stdout="", write=True):
    """A run_minic_script stand-in that 'saves' the fresh sibling the script
    names (as real ArmorPaint would) and returns ok."""
    def fake(binary, project, script, timeout_s):
        if write:
            with open(_fresh_path_in(script), "wb") as fh:
                fh.write(b"edited")
        return ScriptResult(ok=True, stdout=stdout, stderr="")
    return fake


def _cfg(mock_cfg):
    mock_cfg.return_value.binary = "ArmorPaint.exe"
    mock_cfg.return_value.allowed_roots = []


def test_decimate_mesh_edits_the_original_and_saves_to_a_fresh_sibling(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")
    output_project = tmp_path / "out" / "new" / "out.arm"  # dirs don't exist yet

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_saving_run()) as mock_run:
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(output_project))

    assert result == {"ok": True, "output_project": str(output_project), "error": None}
    assert output_project.read_bytes() == b"edited"
    assert project.read_bytes() == b"original"
    opened, script = mock_run.call_args[0][1], mock_run.call_args[0][2]
    assert opened == str(project)                      # the ORIGINAL is opened
    fresh = _fresh_path_in(script)
    assert os.path.dirname(fresh) == str(output_project.parent).replace("\\", "/")
    assert "util_mesh_decimate(0.5);" in script
    assert script.rstrip().endswith("project_save(0);\n}")         # save is last
    assert not os.path.exists(fresh)                   # moved, not copied
    assert os.listdir(output_project.parent) == ["out.arm"]


def test_decimate_mesh_fails_when_the_script_ran_but_never_saved(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_saving_run(write=False)):
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(output_project))

    assert result["ok"] is False
    assert "without saving" in result["error"]
    assert not output_project.exists()
    assert sorted(os.listdir(tmp_path)) == ["project.arm"]


def test_decimate_mesh_timeout_after_a_complete_write_is_a_failure(tmp_path):
    """Review Focus 5: the spike saw a run hang to its timeout after saving a
    complete file. The timeout wins; the fresh file must not survive."""
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")
    output_project = tmp_path / "out.arm"

    def wrote_then_timed_out(binary, project_, script, timeout_s):
        with open(_fresh_path_in(script), "wb") as fh:
            fh.write(b"complete")
        return ScriptResult(ok=False, stdout="", stderr="",
                            error="'--script' timed out after 30.0s")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=wrote_then_timed_out):
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(output_project))

    assert result["ok"] is False
    assert "timed out" in result["error"]
    assert sorted(os.listdir(tmp_path)) == ["project.arm"]


def test_decimate_mesh_in_place_replaces_the_project_only_after_success(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_saving_run()):
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5, in_place=True)

    assert result == {"ok": True, "output_project": str(project), "error": None}
    assert project.read_bytes() == b"edited"
    assert os.listdir(tmp_path) == ["project.arm"]


def test_decimate_mesh_ignores_a_leftover_fresh_sibling_from_a_crashed_run(tmp_path):
    """Review Focus 3."""
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")
    stranger = tmp_path / "out.ap-mcp-0123456789ab.tmp.arm"
    stranger.write_bytes(b"old crash")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_saving_run()):
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(output_project))

    assert result["ok"] is True
    assert stranger.read_bytes() == b"old crash"


def test_decimate_mesh_rejects_a_target_path_minic_cannot_carry(tmp_path):
    """A '"' can't reach minic: Windows refuses it in a directory name
    (makedirs fails) and minic_path_literal refuses it in the literal.
    Either way: a clean failure, and ArmorPaint never launches."""
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(tmp_path / 'we"ird' / "out.arm"))

    assert result["ok"] is False
    assert result["output_project"] is None
    mock_run.assert_not_called()


def test_decimate_mesh_converts_a_replace_failure_to_a_clean_error(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_saving_run()), \
         patch("armorpaint_mcp.server.os.replace", side_effect=OSError("disk full")):
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(output_project))

    assert result["ok"] is False
    assert "disk full" in result["error"]
    assert sorted(os.listdir(tmp_path)) == ["project.arm"]


def test_decimate_mesh_in_place_failure_does_not_delete_project(tmp_path):
    """The in_place=True counterpart: target IS the caller's own project
    there, so a failure must never delete it -- the timeout/failure error
    message already tells the caller to "inspect the project directly",
    which is only correct if the file is still there to inspect."""
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_run.return_value = ScriptResult(
            ok=False, stdout="", stderr="", error="'--script' exited 1")

        result = decimate_mesh(project=str(project), strength=0.5, in_place=True)

    assert result["ok"] is False
    assert project.exists()
    assert project.read_bytes() == b"fake"


def test_bevel_mesh_calls_the_right_minic_function(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_run.side_effect = _saving_run()

        result = bevel_mesh(project=str(project), amount=0.1,
                            output_project=str(output_project))

    assert result["ok"] is True
    assert "util_mesh_bevel(0.1);" in mock_run.call_args[0][2]


def test_subdivide_mesh_calls_the_right_minic_function(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_run.side_effect = _saving_run()

        result = subdivide_mesh(project=str(project), output_project=str(output_project))

    assert result["ok"] is True
    assert "util_mesh_subdivide();" in mock_run.call_args[0][2]


def test_bevel_mesh_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert "bevel_mesh" in by_name, sorted(by_name)
    assert set(by_name["bevel_mesh"].input_schema.get("required", [])) == {"project", "amount"}


def test_subdivide_mesh_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert "subdivide_mesh" in by_name, sorted(by_name)
    assert set(by_name["subdivide_mesh"].input_schema.get("required", [])) == {"project"}


def test_smooth_mesh_calls_the_right_minic_function(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_run.side_effect = _saving_run()

        result = smooth_mesh(project=str(project), output_project=str(output_project))

    assert result["ok"] is True
    assert "util_mesh_smooth();" in mock_run.call_args[0][2]


def test_duplicate_mesh_calls_the_right_minic_function(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_run.side_effect = _saving_run()

        result = duplicate_mesh(project=str(project), output_project=str(output_project))

    assert result["ok"] is True
    assert "util_mesh_duplicate();" in mock_run.call_args[0][2]


def test_smooth_mesh_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert "smooth_mesh" in by_name, sorted(by_name)


def test_duplicate_mesh_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert "duplicate_mesh" in by_name, sorted(by_name)


def test_merge_mesh_geometry_rejects_fewer_than_two_objects(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")

    api_text = (
        "/* Current project state:\n{}\n\nScene objects in world space:\n"
        '"Tessellated": location (0.0, 0.0, 0.0), size (1.0, 1.0, 1.0)\n')

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_api") as mock_api:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_api.return_value = ApiResult(ok=True, text=api_text)

        result = merge_mesh_geometry(project=str(project), output_project=str(tmp_path / "out.arm"))

    assert result["ok"] is False
    assert "only 1 object" in result["error"]


def test_merge_mesh_geometry_calls_the_right_minic_function_when_enough_objects(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    output_project = tmp_path / "out.arm"

    api_text = (
        "/* Current project state:\n{}\n\nScene objects in world space:\n"
        '"A": location (0.0, 0.0, 0.0), size (1.0, 1.0, 1.0)\n'
        '"B": location (1.0, 0.0, 0.0), size (1.0, 1.0, 1.0)\n')

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_api") as mock_api, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_api.return_value = ApiResult(ok=True, text=api_text)
        mock_run.side_effect = _saving_run()

        result = merge_mesh_geometry(project=str(project), output_project=str(output_project))

    assert result["ok"] is True
    assert "util_mesh_merge_geometry();" in mock_run.call_args[0][2]


def test_merge_mesh_geometry_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert "merge_mesh_geometry" in by_name, sorted(by_name)


def test_unwrap_mesh_uvs_calls_the_right_minic_function(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_run.side_effect = _saving_run()

        result = unwrap_mesh_uvs(project=str(project), output_project=str(output_project))

    assert result["ok"] is True
    assert "util_mesh_uv_unwrap();" in mock_run.call_args[0][2]


def test_unwrap_mesh_uvs_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert "unwrap_mesh_uvs" in by_name, sorted(by_name)


QUAD_OBJ = ("o Quad\nv 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
            "vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nf 1/1 2/2 3/3\nf 1/1 3/3 4/4\n")


def _exporting_run(obj_text):
    def fake(binary, project, script, timeout_s):
        path = re.search(r'script_export_mesh\("([^"]+)"\);', script).group(1)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(obj_text)
        return ScriptResult(ok=True, stdout="", stderr="")
    return fake


def test_check_mesh_uvs_reports_per_object_verdicts(tmp_path):
    project = tmp_path / "p.arm"
    project.write_bytes(b"x")
    bad = QUAD_OBJ.replace("vt 1 1", "vt 1.5 1")
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_exporting_run(bad)):
        _cfg(mock_cfg)
        result = check_mesh_uvs(str(project))
        relaxed = check_mesh_uvs(str(project), allow_udim=True)

    assert result["ok"] is True and result["error"] is None
    assert result["valid"] is False
    (obj,) = result["objects"]
    assert obj["name"] == "Quad" and obj["valid"] is False
    assert "coverage_pct" in obj["metrics"]
    assert relaxed["valid"] is True


def test_check_mesh_uvs_fails_cleanly_when_the_export_never_appears(tmp_path):
    project = tmp_path / "p.arm"
    project.write_bytes(b"x")
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script",
               return_value=ScriptResult(ok=True, stdout="", stderr="")):
        _cfg(mock_cfg)
        result = check_mesh_uvs(str(project))

    assert result == {"ok": False, "error": result["error"], "valid": None, "objects": None}
    assert "mesh export" in result["error"]


def test_check_mesh_uvs_rejects_a_non_arm_path(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        _cfg(mock_cfg)
        result = check_mesh_uvs(str(tmp_path / "nope.arm"))
    assert result["ok"] is False and result["objects"] is None


def test_check_mesh_uvs_is_registered_as_an_mcp_tool():
    by_name = {t.name: t for t in asyncio.run(mcp.list_tools())}
    tool = by_name["check_mesh_uvs"]
    assert set(tool.input_schema["properties"]) == {"project", "allow_udim", "timeout_s"}
    assert set(tool.input_schema.get("required", [])) == {"project"}
