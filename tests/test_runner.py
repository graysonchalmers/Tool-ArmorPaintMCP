import json
import os
import subprocess
import threading
from unittest.mock import patch, MagicMock

import pytest

from armorpaint_mcp.runner import (
    expected_output_files,
    export_textures,
    list_export_presets,
    preset_texture_names,
    run_api,
    run_procedural_material,
)

# The two real presets these tests lean on, copied from an actual ArmorPaint
# install (data/export_presets/*.json). "unreal" is a 3-name subset of
# "generic"'s names -- base and nor overlap, orm does not -- which is exactly
# the overlap that made the old "new filenames since we started" detection
# report a partial file list as if it were the whole export.
GENERIC_NAMES = ["base", "nor", "occ", "rough", "metal"]
UNREAL_NAMES = ["base", "nor", "orm"]


def _install(tmp_path, presets: dict[str, list[str]]) -> str:
    """Lay out a fake ArmorPaint install (binary + data/export_presets/*.json)
    and return the binary path."""
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    presets_dir = tmp_path / "data" / "export_presets"
    presets_dir.mkdir(parents=True, exist_ok=True)
    for name, textures in presets.items():
        (presets_dir / f"{name}.json").write_text(json.dumps(
            {"textures": [{"name": t, "channels": [], "color_space": "linear"}
                           for t in textures]}))
    return str(binary)


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


def test_preset_texture_names_reads_definition_order(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})

    assert preset_texture_names(binary, "generic") == GENERIC_NAMES


def test_expected_output_files_matches_armorpaint_naming(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    out = str(tmp_path / "out")

    files = expected_output_files(binary, r"C:\proj\sample_project.arm", "png",
                                   "generic", out)

    assert files == [os.path.join(out, f"sample_project_{n}.png")
                     for n in GENERIC_NAMES]


def test_expected_output_files_omits_suffix_for_unnamed_texture(tmp_path):
    # minecraft_mer's first entry really is {"name": ""} -- ArmorPaint appends
    # nothing at all for it (export_texture.c), not a trailing underscore.
    binary = _install(tmp_path, {"minecraft_mer": ["", "normal", "mer"]})
    out = str(tmp_path / "out")

    files = expected_output_files(binary, "sample_project.arm", "png",
                                   "minecraft_mer", out)

    assert files == [
        os.path.join(out, "sample_project.png"),
        os.path.join(out, "sample_project_normal.png"),
        os.path.join(out, "sample_project_mer.png"),
    ]


def test_expected_output_files_rejects_unknown_texture_type(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})

    with pytest.raises(ValueError, match="unknown texture type"):
        expected_output_files(binary, "p.arm", "tiff", "generic", str(tmp_path))


def test_export_textures_fails_before_launching_when_preset_unreadable(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    output_dir = str(tmp_path / "out")

    with patch("armorpaint_mcp.runner.subprocess.Popen") as mock_popen:
        result = export_textures(binary, str(tmp_path / "p.arm"), "png",
                                  "no_such_preset", output_dir, timeout_s=0.3)

    assert result.ok is False
    assert "could not determine which files preset 'no_such_preset' exports" in result.error
    mock_popen.assert_not_called()


def test_export_textures_reports_failure_when_no_files_appear(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    project = str(tmp_path / "project.arm")
    output_dir = str(tmp_path / "out")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    with patch("armorpaint_mcp.runner.subprocess.Popen", return_value=mock_proc):
        result = export_textures(binary, project, "png", "generic", output_dir,
                                  timeout_s=0.3)

    assert result.ok is False
    assert result.files == []
    assert "export outcome uncertain" in result.error
    assert "5 of 5" in result.error
    assert "project_base.png" in result.error
    mock_proc.terminate.assert_called_once()


def test_export_textures_reports_success_when_all_expected_files_appear(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    project = str(tmp_path / "project.arm")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")

    def fake_popen(args, **kwargs):
        # Simulate ArmorPaint writing its files after a short delay, one
        # preset texture at a time (not synchronously, not all at once).
        # This exercises the polling loop's multi-iteration behavior and
        # proves a partially-written export isn't reported as complete.
        def write_files():
            for name in GENERIC_NAMES:
                (output_dir / f"project_{name}.png").write_bytes(b"fake png")
        timer = threading.Timer(0.3, write_files)
        timer.daemon = True
        timer.start()
        return mock_proc

    with patch("armorpaint_mcp.runner.subprocess.Popen", side_effect=fake_popen):
        result = export_textures(binary, project, "png", "generic",
                                  str(output_dir), timeout_s=5.0)

    assert result.ok is True
    assert result.files == [str(output_dir / f"project_{n}.png")
                            for n in GENERIC_NAMES]
    mock_proc.terminate.assert_called_once()


def test_export_textures_reports_partial_export_as_uncertain(tmp_path):
    """Only some of the preset's files land: that is NOT a success, and the
    error names the ones that never arrived."""
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    project = str(tmp_path / "project.arm")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")

    def fake_popen(args, **kwargs):
        def write_two():
            (output_dir / "project_base.png").write_bytes(b"fake png")
            (output_dir / "project_nor.png").write_bytes(b"fake png")
        timer = threading.Timer(0.1, write_two)
        timer.daemon = True
        timer.start()
        return mock_proc

    with patch("armorpaint_mcp.runner.subprocess.Popen", side_effect=fake_popen):
        result = export_textures(binary, project, "png", "generic",
                                  str(output_dir), timeout_s=0.6)

    assert result.ok is False
    assert "3 of 5" in result.error
    assert "project_occ.png" in result.error
    assert result.files == [str(output_dir / "project_base.png"),
                            str(output_dir / "project_nor.png")]


def test_export_textures_succeeds_re_exporting_into_a_non_empty_output_dir(tmp_path):
    """Regression for the 'new filenames' bug: ArmorPaint OVERWRITES, so on a
    second run into the same dir nothing is new by name. Detection keyed on
    new names reported a false failure here even though the export worked."""
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    project = str(tmp_path / "project.arm")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    # Every file this export will produce already exists, from a prior run.
    for name in GENERIC_NAMES:
        (output_dir / f"project_{name}.png").write_bytes(b"stale run 1")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")

    def fake_popen(args, **kwargs):
        def overwrite_files():
            for name in GENERIC_NAMES:
                (output_dir / f"project_{name}.png").write_bytes(
                    b"fresh bytes written by run 2")
        timer = threading.Timer(0.3, overwrite_files)
        timer.daemon = True
        timer.start()
        return mock_proc

    with patch("armorpaint_mcp.runner.subprocess.Popen", side_effect=fake_popen):
        result = export_textures(binary, project, "png", "generic",
                                  str(output_dir), timeout_s=5.0)

    assert result.ok is True, result.error
    assert result.files == [str(output_dir / f"project_{n}.png")
                            for n in GENERIC_NAMES]
    # ...and the files reported are the ones THIS run wrote, not the stale
    # leftovers that happened to already carry the right names.
    for f in result.files:
        assert open(f, "rb").read() == b"fresh bytes written by run 2"


def test_export_textures_does_not_pass_off_stale_files_as_a_fresh_export(tmp_path):
    """The flip side of the re-export case: if the process writes nothing,
    run 1's leftovers must NOT be reported as this run's output."""
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    project = str(tmp_path / "project.arm")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    for name in GENERIC_NAMES:
        (output_dir / f"project_{name}.png").write_bytes(b"stale run 1")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    with patch("armorpaint_mcp.runner.subprocess.Popen", return_value=mock_proc):
        result = export_textures(binary, project, "png", "generic",
                                  str(output_dir), timeout_s=0.6)

    assert result.ok is False
    assert "5 of 5" in result.error
    assert "unchanged" in result.error
    assert result.files == []


def test_export_textures_accepts_a_same_size_rewrite(tmp_path):
    """Freshness is (size, mtime), not size alone -- an export that happens
    to write the same byte count as the previous run still counts."""
    binary = _install(tmp_path, {"unreal": UNREAL_NAMES})
    project = str(tmp_path / "project.arm")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    for name in UNREAL_NAMES:
        (output_dir / f"project_{name}.png").write_bytes(b"AAAA")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")

    def fake_popen(args, **kwargs):
        def rewrite_same_size():
            for name in UNREAL_NAMES:
                (output_dir / f"project_{name}.png").write_bytes(b"BBBB")
        timer = threading.Timer(0.3, rewrite_same_size)
        timer.daemon = True
        timer.start()
        return mock_proc

    with patch("armorpaint_mcp.runner.subprocess.Popen", side_effect=fake_popen):
        result = export_textures(binary, project, "png", "unreal",
                                  str(output_dir), timeout_s=5.0)

    assert result.ok is True, result.error
    assert len(result.files) == 3


def test_export_textures_second_preset_into_same_dir_reports_its_full_set(tmp_path):
    """Regression for the same bug's silent-wrong-data half: 'generic' then
    'unreal' into one dir. base/nor already exist from run 1, so a
    name-difference reported only ['project_orm.png'] with ok=True while
    three files were actually written."""
    binary = _install(tmp_path, {"generic": GENERIC_NAMES, "unreal": UNREAL_NAMES})
    project = str(tmp_path / "project.arm")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")

    def popen_writing(names, marker):
        def fake_popen(args, **kwargs):
            def write_files():
                for name in names:
                    (output_dir / f"project_{name}.png").write_bytes(marker)
            timer = threading.Timer(0.3, write_files)
            timer.daemon = True
            timer.start()
            return mock_proc
        return fake_popen

    with patch("armorpaint_mcp.runner.subprocess.Popen",
                side_effect=popen_writing(GENERIC_NAMES, b"generic run")):
        first = export_textures(binary, project, "png", "generic",
                                 str(output_dir), timeout_s=5.0)
    assert first.ok is True, first.error
    assert len(first.files) == 5

    with patch("armorpaint_mcp.runner.subprocess.Popen",
                side_effect=popen_writing(UNREAL_NAMES, b"unreal run")):
        second = export_textures(binary, project, "png", "unreal",
                                  str(output_dir), timeout_s=5.0)

    assert second.ok is True, second.error
    # The full unreal set -- including base and nor, which the first run had
    # already created -- not just the one filename that happened to be new.
    assert second.files == [str(output_dir / f"project_{n}.png")
                            for n in UNREAL_NAMES]
    for f in second.files:
        assert open(f, "rb").read() == b"unreal run"


def test_export_textures_terminates_process_even_if_polling_raises(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    project = str(tmp_path / "project.arm")
    output_dir = str(tmp_path / "out")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    with patch("armorpaint_mcp.runner.subprocess.Popen", return_value=mock_proc), \
         patch("armorpaint_mcp.runner.time.sleep", side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            export_textures(binary, project, "png", "generic", output_dir,
                             timeout_s=5.0)

    # The GUI process does not self-exit; an interrupted poll must not leak it.
    mock_proc.terminate.assert_called_once()


def test_export_textures_does_not_pipe_stdout(tmp_path):
    """An unread stdout PIPE can fill the OS buffer and deadlock a long
    export; stderr stays piped because it IS read and reported."""
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    output_dir = str(tmp_path / "out")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    captured = {}

    def fake_popen(args, **kwargs):
        captured.update(kwargs)
        return mock_proc

    with patch("armorpaint_mcp.runner.subprocess.Popen", side_effect=fake_popen):
        export_textures(binary, str(tmp_path / "project.arm"), "png", "generic",
                         output_dir, timeout_s=0.2)

    import subprocess as sp
    assert captured["stdout"] == sp.DEVNULL
    assert captured["stderr"] == sp.PIPE


def test_export_textures_builds_correct_argv(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
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


def test_run_procedural_material_builds_correct_argv_and_no_background(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    output_dir = str(tmp_path / "out")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        return mock_proc

    with patch("armorpaint_mcp.runner.subprocess.Popen", side_effect=fake_popen):
        run_procedural_material(binary, "void main() {}", output_dir, "generic",
                                 timeout_s=0.2)

    assert captured["args"][0] == binary
    assert "--script" in captured["args"]
    assert "--background" not in captured["args"]
    script_path = captured["args"][captured["args"].index("--script") + 1]
    assert not os.path.exists(script_path), "temp script must be cleaned up"


def test_run_procedural_material_writes_the_given_script_text(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    output_dir = str(tmp_path / "out")
    written = {}

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")

    def fake_popen(args, **kwargs):
        script_path = args[args.index("--script") + 1]
        with open(script_path, encoding="utf-8") as fh:
            written["content"] = fh.read()
        return mock_proc

    with patch("armorpaint_mcp.runner.subprocess.Popen", side_effect=fake_popen):
        run_procedural_material(binary, "void main() { /* marker */ }",
                                 output_dir, "generic", timeout_s=0.2)

    assert written["content"] == "void main() { /* marker */ }"


def test_run_procedural_material_reports_success_when_files_appear(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")

    def fake_popen(args, **kwargs):
        def write_files():
            for name in GENERIC_NAMES:
                (output_dir / f"untitled_{name}.png").write_bytes(b"fake png")
        timer = threading.Timer(0.3, write_files)
        timer.daemon = True
        timer.start()
        return mock_proc

    with patch("armorpaint_mcp.runner.subprocess.Popen", side_effect=fake_popen):
        result = run_procedural_material(binary, "void main() {}", str(output_dir),
                                          "generic", timeout_s=5.0)

    assert result.ok is True, result.error
    assert result.files == [str(output_dir / f"untitled_{n}.png")
                            for n in GENERIC_NAMES]
    mock_proc.terminate.assert_called_once()


def test_run_procedural_material_reports_failure_when_no_files_appear(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    output_dir = str(tmp_path / "out")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    with patch("armorpaint_mcp.runner.subprocess.Popen", return_value=mock_proc):
        result = run_procedural_material(binary, "void main() {}", output_dir,
                                          "generic", timeout_s=0.3)

    assert result.ok is False
    assert result.files == []
    assert "untitled_base.png" in result.error


def test_run_procedural_material_cleans_up_tempfile_even_on_failure(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    output_dir = str(tmp_path / "out")

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "")
    captured = {}

    def fake_popen(args, **kwargs):
        captured["script_path"] = args[args.index("--script") + 1]
        return mock_proc

    with patch("armorpaint_mcp.runner.subprocess.Popen", side_effect=fake_popen):
        run_procedural_material(binary, "void main() {}", output_dir, "generic",
                                 timeout_s=0.2)

    assert not os.path.exists(captured["script_path"])


def test_run_procedural_material_fails_before_launching_for_unknown_preset(tmp_path):
    binary = _install(tmp_path, {"generic": GENERIC_NAMES})
    output_dir = str(tmp_path / "out")

    with patch("armorpaint_mcp.runner.subprocess.Popen") as mock_popen:
        result = run_procedural_material(binary, "void main() {}", output_dir,
                                          "no_such_preset", timeout_s=0.2)

    assert result.ok is False
    assert "could not determine which files preset 'no_such_preset' exports" in result.error
    mock_popen.assert_not_called()


def test_run_api_returns_stdout_on_success(tmp_path):
    binary = tmp_path / "fake_armorpaint.py"
    binary.write_text(
        "import sys\n"
        "print('fake --api output')\n"
        "sys.exit(0)\n"
    )
    project = tmp_path / "project.arm"
    project.write_text("")

    with patch("armorpaint_mcp.runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="fake --api output\n",
                                           stderr="")
        result = run_api(str(binary), str(project))

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == [str(binary), str(project), "--api"]
    assert result.ok is True
    assert result.text == "fake --api output\n"
    assert result.error is None


def test_run_api_reports_nonzero_exit(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    project = tmp_path / "project.arm"
    project.write_text("")

    with patch("armorpaint_mcp.runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
        result = run_api(str(binary), str(project))

    assert result.ok is False
    assert result.text == ""
    assert "boom" in result.error


def test_run_api_reports_timeout(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    project = tmp_path / "project.arm"
    project.write_text("")

    with patch("armorpaint_mcp.runner.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="x", timeout=5.0)):
        result = run_api(str(binary), str(project), timeout_s=5.0)

    assert result.ok is False
    assert "timed out after 5.0s" in result.error
