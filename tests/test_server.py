import asyncio
from unittest.mock import patch

import pytest

from armorpaint_mcp import server
from armorpaint_mcp.catalog import CatalogError
from armorpaint_mcp.runner import ExportResult, ApiResult
from armorpaint_mcp.server import (mcp, reexport_project, create_procedural_material,
                                   list_available_presets, inspect_project)


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
