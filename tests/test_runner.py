import os
import threading
from unittest.mock import patch, MagicMock

from armorpaint_mcp.runner import list_export_presets, export_textures


def test_list_export_presets_reads_json_files_next_to_binary(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    presets_dir = tmp_path / "data" / "export_presets"
    presets_dir.mkdir(parents=True)
    (presets_dir / "generic.json").write_text("{}")
    (presets_dir / "unity.json").write_text("{}")
    (presets_dir / "not_a_preset.txt").write_text("")

    result = list_export_presets(str(binary))

    assert result == ["generic", "unity"]


def test_list_export_presets_empty_when_dir_missing(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")

    assert list_export_presets(str(binary)) == []


def test_export_textures_reports_failure_when_no_files_appear(tmp_path):
    binary = str(tmp_path / "ArmorPaint.exe")
    project = str(tmp_path / "project.arm")
    output_dir = str(tmp_path / "out")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    with patch("armorpaint_mcp.runner.subprocess.Popen", return_value=mock_proc):
        result = export_textures(binary, project, "png", "generic", output_dir,
                                  timeout_s=0.3)

    assert result.ok is False
    assert result.files == []
    assert "no new files" in result.error
    mock_proc.terminate.assert_called_once()


def test_export_textures_reports_success_when_files_appear(tmp_path):
    binary = str(tmp_path / "ArmorPaint.exe")
    project = str(tmp_path / "project.arm")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")

    def fake_popen(args, **kwargs):
        # Simulate ArmorPaint writing a file after a short delay (not synchronously).
        # This exercises the polling loop's multi-iteration behavior.
        def write_file():
            (output_dir / "project_base.png").write_bytes(b"fake png")
        timer = threading.Timer(0.3, write_file)
        timer.daemon = True
        timer.start()
        return mock_proc

    with patch("armorpaint_mcp.runner.subprocess.Popen", side_effect=fake_popen):
        result = export_textures(binary, project, "png", "generic",
                                  str(output_dir), timeout_s=2.0)

    assert result.ok is True
    assert result.files == [str(output_dir / "project_base.png")]
    mock_proc.terminate.assert_called_once()


def test_export_textures_builds_correct_argv(tmp_path):
    binary = str(tmp_path / "ArmorPaint.exe")
    project = str(tmp_path / "project.arm")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        return mock_proc

    with patch("armorpaint_mcp.runner.subprocess.Popen", side_effect=fake_popen):
        export_textures(binary, project, "png", "generic", str(output_dir),
                         timeout_s=0.2)

    assert captured["args"] == [
        binary, project, "--export-textures", "png", "generic", str(output_dir),
    ]
