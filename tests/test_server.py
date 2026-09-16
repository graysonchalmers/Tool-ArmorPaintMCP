import asyncio
from unittest.mock import patch

import pytest

from armorpaint_mcp import server
from armorpaint_mcp.runner import ExportResult
from armorpaint_mcp.server import mcp, reexport_project


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
