from unittest.mock import patch

from armorpaint_mcp.config import Config
from armorpaint_mcp.doctor import check_setup


def test_check_setup_flags_a_binary_missing_the_mesh_edit_patch(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_bytes(b"fake")
    (tmp_path / "data").mkdir()
    cfg = Config(binary=str(binary), output_dir=str(tmp_path))

    with patch("armorpaint_mcp.doctor.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "// ArmorPaint script API\n"
        mock_run.return_value.stderr = ""
        checks = check_setup(cfg)

    by_name = {c.name: c for c in checks}
    assert "mesh-edit patch" in by_name
    assert by_name["mesh-edit patch"].ok is False
    assert "util_mesh_decimate" in by_name["mesh-edit patch"].detail


def test_check_setup_passes_when_the_mesh_edit_patch_is_present(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_bytes(b"fake")
    (tmp_path / "data").mkdir()
    cfg = Config(binary=str(binary), output_dir=str(tmp_path))

    patched_text = "\n".join(
        f"{name}()" for name in [
            "util_mesh_decimate", "util_mesh_smooth", "util_mesh_bevel",
            "util_mesh_subdivide", "util_mesh_merge_geometry",
            "util_mesh_duplicate", "plugin_uv_unwrap_button",
        ])

    with patch("armorpaint_mcp.doctor.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = patched_text
        mock_run.return_value.stderr = ""
        checks = check_setup(cfg)

    by_name = {c.name: c for c in checks}
    assert by_name["mesh-edit patch"].ok is True
