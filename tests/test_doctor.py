from unittest.mock import patch

from armorpaint_mcp.catalog import EMITTED_MINIC_FUNCTIONS
from armorpaint_mcp.config import Config
from armorpaint_mcp.doctor import check_setup


def _cfg(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_bytes(b"fake")
    (tmp_path / "data").mkdir()
    return Config(binary=str(binary), output_dir=str(tmp_path))


def test_check_setup_flags_every_unregistered_minic_function(tmp_path):
    with patch("armorpaint_mcp.doctor.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "void project_save(i32 x);\n"
        mock_run.return_value.stderr = ""
        checks = check_setup(_cfg(tmp_path))

    row = {c.name: c for c in checks}["minic API"]
    assert row.ok is False
    assert "util_mesh_decimate" in row.detail
    assert "project_save" not in row.detail


def test_check_setup_passes_when_every_minic_function_is_registered(tmp_path):
    api = "\n".join(f"void {n}();" for n in EMITTED_MINIC_FUNCTIONS)
    with patch("armorpaint_mcp.doctor.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = api
        mock_run.return_value.stderr = ""
        checks = check_setup(_cfg(tmp_path))

    row = {c.name: c for c in checks}["minic API"]
    assert row.ok is True
    assert str(len(EMITTED_MINIC_FUNCTIONS)) in row.detail
