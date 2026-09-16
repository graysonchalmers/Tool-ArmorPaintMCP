from unittest.mock import patch

from armorpaint_mcp.runner import ExportResult
from armorpaint_mcp.server import reexport_project


def test_reexport_project_returns_error_for_unknown_preset(tmp_path):
    with patch("armorpaint_mcp.server.load_config") as mock_cfg, \
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

    with patch("armorpaint_mcp.server.load_config") as mock_cfg, \
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

    with patch("armorpaint_mcp.server.load_config") as mock_cfg, \
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
