# Phase 1 — `reexport_project` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first real MCP tool, `reexport_project`, which re-exports
an existing `.arm` project's textures at a chosen preset using ArmorPaint's
native `--export-textures` flag — no source patching, no minic script for
this operation — plus visible proof it works (a README gallery of real
exported textures).

**Architecture:** A subprocess-driven tool. `runner.py` launches the real
ArmorPaint binary against a project file and a chosen export preset, polls
the output directory for new files, and terminates the process once export
is detected complete. `paths.py` bounds every client-supplied path to
`AP_ALLOWED_ROOTS` when set. The MCP tool (`reexport_project`, wired into
`server.py`) is a thin validation + call-through layer over these two units.
A small standalone script builds a tracked binary test fixture (`.arm`
project) headlessly via `--background --script`, used by both the
integration test and the demo gallery.

**Tech Stack:** Python 3.13, `subprocess`, `pytest` (with an `integration`
marker), the already-scaffolded `armorpaint_mcp` package
(`config.py`/`doctor.py`/`server.py` exist with zero tools).

---

## Empirically confirmed facts this plan depends on (2026-09-15, tested against the real local build)

Do not re-derive these from source reading alone — they were verified by
actually running the local ArmorPaint build (`C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe`):

1. **`--background` + `--export-textures` is broken.** `iron_stop()` fires in
   the same frame that merely *schedules* the export for the next frame, so
   the process exits (code 0!) having produced nothing. Confirmed: an export
   with `--background` produced zero files in the output dir.
2. **Without `--background`, export works.** `ArmorPaint.exe <project.arm>
   --export-textures png generic <output_dir>` produced 5 real PNGs
   (`_base`, `_nor`, `_occ`, `_rough`, `_metal`) for the "generic" preset.
   The process stays open afterward (GUI, responsive) — it does not
   self-exit. The runner must poll for output, then terminate the process.
3. **Resolution has no CLI flag and no confirmed minic setter.** It reads
   from a static app config (`config_get_texture_res_x/y`). `reexport_project`
   takes `preset` only in this phase, not `resolution`.
4. **`--background --script <path>` works correctly** for calling minic
   functions. `void main() { script_project_new(); project_filepath_set("<abs path>"); project_save(0); }`
   produced a real, loadable `.arm` project file (217,931 bytes) in ~1
   second, exit code 0.
5. **Minic scripts require a `void main() { ... }` wrapper.** Bare top-level
   statements silently do nothing — no error, no output, exit code 0. This
   bit the first fixture-creation attempt in this session; don't repeat it.
6. **`.arm` is MessagePack-encoded binary**, small (a fresh default project
   is ~213 KB). Safe to commit as a tracked binary git fixture.
7. **Export presets are files, not hardcoded**: `<binary_dir>\data\export_presets\*.json`.
   This checkout has: `base_color`, `generic`, `minecraft_mer`, `specular`,
   `unigine`, `unity`, `unreal`, `xplane`.

---

## Task 1: Path sandboxing (`paths.py`)

**Files:**
- Create: `src/armorpaint_mcp/paths.py`
- Test: `tests/test_paths.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_paths.py
import os
import pytest

from armorpaint_mcp.paths import ensure_within_roots, reject_path_fragment, PathNotAllowed


def test_ensure_within_roots_passthrough_when_empty(tmp_path):
    p = tmp_path / "anywhere.arm"
    assert ensure_within_roots(str(p), []) == os.path.realpath(str(p))


def test_ensure_within_roots_allows_path_inside_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    p = root / "project.arm"
    assert ensure_within_roots(str(p), [str(root)]) == os.path.realpath(str(p))


def test_ensure_within_roots_rejects_path_outside_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.arm"
    with pytest.raises(PathNotAllowed):
        ensure_within_roots(str(outside), [str(root)])


def test_reject_path_fragment_allows_bare_name():
    assert reject_path_fragment("generic") == "generic"


def test_reject_path_fragment_rejects_separator():
    with pytest.raises(PathNotAllowed):
        reject_path_fragment("../generic")


def test_reject_path_fragment_rejects_dotdot():
    with pytest.raises(PathNotAllowed):
        reject_path_fragment("..")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_paths.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'armorpaint_mcp.paths'`

- [ ] **Step 3: Write the implementation**

```python
# src/armorpaint_mcp/paths.py
"""Client-facing path guards for the MCP tools.

Two shapes:
  * ensure_within_roots  -- bounds a whole client-supplied path to
    AP_ALLOWED_ROOTS. Opt-in: empty roots means passthrough.
  * reject_path_fragment -- rejects traversal in a client-supplied *name*
    (e.g. an export preset) that gets joined onto a trusted dir. Always on.
"""

import os


class PathNotAllowed(Exception):
    """A client-supplied path or fragment is not permitted."""


def ensure_within_roots(path: str, roots: list[str]) -> str:
    """Return realpath(path). If roots is non-empty, require the realpath to
    lie within one of them (else raise PathNotAllowed). Empty roots is
    passthrough. realpath resolves symlinks before comparison, so a link
    inside a root cannot point outside it."""
    resolved = os.path.realpath(path)
    if not roots:
        return resolved
    cand = os.path.normcase(resolved)
    for root in roots:
        root_norm = os.path.normcase(os.path.realpath(root))
        if cand == root_norm or cand.startswith(root_norm + os.sep):
            return resolved
    raise PathNotAllowed(
        f"path '{path}' is outside the allowed roots "
        f"(AP_ALLOWED_ROOTS): {roots}")


def reject_path_fragment(name: str) -> str:
    """Return name if it is a bare path component. Raise PathNotAllowed if it
    contains a path separator or equals '..'. Always enforced, independent of
    AP_ALLOWED_ROOTS: a separator or '..' in a 'name' (e.g. an export preset)
    is never legitimate."""
    seps = [s for s in (os.sep, os.altsep) if s]
    if any(s in name for s in seps):
        raise PathNotAllowed(
            f"'{name}' must be a bare name with no path separators")
    if name == "..":
        raise PathNotAllowed(f"'{name}' is not a valid name")
    return name
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_paths.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```powershell
git add src/armorpaint_mcp/paths.py tests/test_paths.py
git commit -m "feat: path sandboxing for MCP tool arguments"
```

---

## Task 2: Subprocess runner (`runner.py`)

**Files:**
- Create: `src/armorpaint_mcp/runner.py`
- Test: `tests/test_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_runner.py
import os
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
        # Simulate ArmorPaint writing a file shortly after launch.
        (output_dir / "project_base.png").write_bytes(b"fake png")
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'armorpaint_mcp.runner'`

- [ ] **Step 3: Write the implementation**

```python
# src/armorpaint_mcp/runner.py
"""Drives the real ArmorPaint binary as a subprocess.

--background is deliberately NEVER passed for --export-textures: that
combination is broken on this build (iron_stop() fires before the scheduled
export runs, producing zero output at exit code 0 -- confirmed empirically,
see docs/PLAN.md's Phase 1 section and the design spec's amendment). Instead
this launches the normal GUI process, polls the output directory for new
files, and terminates the process once export is detected complete.
"""

import glob
import os
import subprocess
import time
from dataclasses import dataclass

DEFAULT_TIMEOUT_S = 30.0
POLL_INTERVAL_S = 0.25
SETTLE_S = 0.5  # grace period after the first new file appears, so a
                # multi-file export (5 PNGs for "generic") finishes writing
                # before we terminate the process.


@dataclass
class ExportResult:
    ok: bool
    files: list[str]
    error: str | None = None


def list_export_presets(binary: str) -> list[str]:
    """Preset names discoverable from the ArmorPaint install next to
    `binary` (<binary_dir>/data/export_presets/*.json) -- read from disk,
    never hardcoded, so this can't silently go stale the way the reference
    project's hardcoded bake-type/blend-mode constants can."""
    presets_dir = os.path.join(os.path.dirname(binary), "data", "export_presets")
    return sorted(
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(presets_dir, "*.json"))
    )


def export_textures(binary: str, project: str, texture_type: str, preset: str,
                     output_dir: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> ExportResult:
    """Launch ArmorPaint against `project` and export textures at `preset`.
    Returns ExportResult(ok, files, error). Never raises for a normal
    export-didn't-happen failure -- that's ExportResult(ok=False, ...)."""
    os.makedirs(output_dir, exist_ok=True)
    before = set(os.listdir(output_dir))

    proc = subprocess.Popen(
        [binary, project, "--export-textures", texture_type, preset, output_dir],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )

    deadline = time.monotonic() + timeout_s
    new_files: list[str] = []
    while time.monotonic() < deadline:
        after = set(os.listdir(output_dir))
        new_files = sorted(after - before)
        if new_files:
            time.sleep(SETTLE_S)
            after = set(os.listdir(output_dir))
            new_files = sorted(after - before)
            break
        time.sleep(POLL_INTERVAL_S)

    proc.terminate()
    try:
        _, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        _, stderr = proc.communicate(timeout=5)

    if not new_files:
        detail = f": {stderr.strip()}" if stderr and stderr.strip() else ""
        return ExportResult(ok=False, files=[], error=(
            f"no new files appeared in '{output_dir}' within {timeout_s}s{detail}"))
    return ExportResult(ok=True, files=[os.path.join(output_dir, f) for f in new_files])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runner.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```powershell
git add src/armorpaint_mcp/runner.py tests/test_runner.py
git commit -m "feat: subprocess runner for native texture export"
```

---

## Task 3: Register the `integration` pytest marker

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the marker registration**

Add this section to `pyproject.toml` (after `[project.urls]`, before
`[build-system]`):

```toml
[tool.pytest.ini_options]
markers = [
    "integration: real ArmorPaint process required (needs AP_BINARY set to a working build)",
]
```

- [ ] **Step 2: Verify it registers cleanly**

Run: `.venv\Scripts\python.exe -m pytest --markers`
Expected: output includes `@pytest.mark.integration: real ArmorPaint process required...`

- [ ] **Step 3: Commit**

```powershell
git add pyproject.toml
git commit -m "chore: register the integration pytest marker"
```

---

## Task 4: Sample project fixture

**Files:**
- Create: `tests/fixtures/generate_fixture.py`
- Create (generated by the script above, then committed): `tests/fixtures/sample_project.arm`

This is not TDD (it's a one-time data-generation utility, not logic to unit
test) — write it, run it for real against the local ArmorPaint build, verify
the output, commit the binary fixture.

- [ ] **Step 1: Write the fixture generator**

```python
# tests/fixtures/generate_fixture.py
"""Regenerates tests/fixtures/sample_project.arm.

Run manually whenever the fixture needs to change:
    .venv\\Scripts\\python.exe tests\\fixtures\\generate_fixture.py

Requires AP_BINARY set (env var or .env) to a working ArmorPaint.exe.
Uses --background --script (NOT the broken --background + --export-textures
combo -- see docs/PLAN.md Phase 1) to call ArmorPaint's own minic scripting
API headlessly: script_project_new() creates a new project (defaults to the
cube_bevel primitive mesh + a default material + initialized layers),
project_filepath_set() points it at this fixture's path, project_save(0)
writes it without quitting (the --background flag's own args_run_script_stop
callback handles quitting afterward).
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from armorpaint_mcp.config import load_config  # noqa: E402

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "sample_project.arm")

# minic requires a void main() wrapper -- bare top-level statements silently
# no-op (confirmed the hard way while planning this phase).
SCRIPT_TEMPLATE = """\
void main() {{
	script_project_new();
	project_filepath_set("{path}");
	project_save(0);
	printf("fixture created\\n");
}}
"""


def main() -> int:
    cfg = load_config()
    if not cfg.binary or not os.path.isfile(cfg.binary):
        print(f"AP_BINARY not set to a valid ArmorPaint.exe (got '{cfg.binary}')",
              file=sys.stderr)
        return 1

    # minic wants forward slashes even on Windows (matches the ArmorPaint
    # source's own iron_file path handling); os.path.abspath keeps backslashes,
    # so normalize explicitly.
    fixture_path = os.path.abspath(FIXTURE_PATH).replace("\\", "/")
    script_content = SCRIPT_TEMPLATE.format(path=fixture_path)

    with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
        f.write(script_content)
        script_path = f.name

    try:
        proc = subprocess.run(
            [cfg.binary, "--background", "--script", script_path],
            capture_output=True, text=True, timeout=30,
        )
    finally:
        os.unlink(script_path)

    if proc.returncode != 0:
        print(f"ArmorPaint exited {proc.returncode}\nstdout: {proc.stdout}\n"
              f"stderr: {proc.stderr}", file=sys.stderr)
        return 1
    if not os.path.isfile(FIXTURE_PATH):
        print(f"expected fixture at '{FIXTURE_PATH}' but it wasn't created",
              file=sys.stderr)
        return 1

    size = os.path.getsize(FIXTURE_PATH)
    print(f"wrote {FIXTURE_PATH} ({size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it for real against the local ArmorPaint build**

Run:
```powershell
$env:AP_BINARY = "C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe"
.venv\Scripts\python.exe tests\fixtures\generate_fixture.py
```
Expected: `wrote ...\tests\fixtures\sample_project.arm (NNNNNN bytes)`, exit code 0.
(A run during planning produced a 217,931-byte file in ~1 second — expect
something in that range.)

- [ ] **Step 3: Verify the fixture is a real, non-empty MessagePack file**

Run: `.venv\Scripts\python.exe -c "d = open('tests/fixtures/sample_project.arm','rb').read(4); print(d)"`
Expected: non-empty bytes starting with a MessagePack map/array marker (e.g.
`b'\xdf\x0b\x00\x00'` or similar `\xdb`/\xdd`/`\xdf`-prefixed bytes — NOT an
empty result and not readable as UTF-8 text).

- [ ] **Step 4: Commit (binary fixture included)**

```powershell
git add tests/fixtures/generate_fixture.py tests/fixtures/sample_project.arm
git commit -m "test: add headlessly-generated sample .arm project fixture"
```

---

## Task 5: `reexport_project` MCP tool

**Files:**
- Modify: `src/armorpaint_mcp/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_server.py
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

    with patch("armorpaint_mcp.server.load_config") as mock_cfg:
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -v`
Expected: FAIL with `ImportError: cannot import name 'reexport_project'`

- [ ] **Step 3: Implement the tool in `server.py`**

Replace the whole contents of `src/armorpaint_mcp/server.py` with:

```python
import sys

from mcp.server.mcpserver import MCPServer

from armorpaint_mcp import __version__
from armorpaint_mcp.config import load_config, require_valid
from armorpaint_mcp.doctor import run_check
from armorpaint_mcp.paths import ensure_within_roots, PathNotAllowed
from armorpaint_mcp.runner import export_textures, list_export_presets

# Startup is lazy: importing this module must NOT validate config, so
# `ap-mcp --check` / `--version` work even when config is broken (the exact
# case the doctor exists for), and tests can import cheaply.
_cfg = None

mcp = MCPServer("armorpaint-mcp")


def _ensure_ready():
    global _cfg
    if _cfg is None:
        _cfg = load_config()
        require_valid(_cfg)
    return _cfg


def reexport_project(project: str, preset: str, output_dir: str) -> dict:
    """Re-export an existing .arm project's textures at a given preset,
    using ArmorPaint's native --export-textures flag (PNG). No resolution
    parameter: ArmorPaint has no CLI flag or confirmed scripting call for it
    in this version -- see docs/PLAN.md's Phase 1 section. `preset` must be
    one of the names returned by listing <ArmorPaint install>/data/export_presets/*.json
    (this checkout has: base_color, generic, minecraft_mer, specular,
    unigine, unity, unreal, xplane). Bounded by AP_ALLOWED_ROOTS when set.
    Returns {"ok": bool, "files": [str] | None, "error": str | None}."""
    cfg = load_config()

    available = list_export_presets(cfg.binary)
    if preset not in available:
        return {"ok": False, "files": None,
                "error": f"unknown preset '{preset}'; available: {', '.join(available)}"}

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
        output_dir = ensure_within_roots(output_dir, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return {"ok": False, "files": None, "error": str(exc)}

    result = export_textures(cfg.binary, project, "png", preset, output_dir)
    return {"ok": result.ok, "files": result.files if result.ok else None,
            "error": result.error}


mcp.tool()(reexport_project)


_USAGE = (
    "usage: ap-mcp [--check | --version | --help]\n"
    "  (no args)   start the MCP server over stdio\n"
    "  --check     run the setup preflight (green/red checklist), exit 1 if any fail\n"
    "  --version   print the version\n"
    "  --help      show this message"
)


def main(argv: list | None = None) -> int:
    """Console entry point (`ap-mcp`). Returns a process exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--help" in args or "-h" in args:
        print(_USAGE)
        return 0
    if "--version" in args:
        print(f"ap-mcp {__version__}")
        return 0
    if "--check" in args:
        return run_check()
    if args:
        print(f"ap-mcp: unrecognized argument(s): {' '.join(args)}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    _ensure_ready()
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -v`
Expected: 3 passed

- [ ] **Step 5: Re-run the full unit suite and the smoke test**

Run: `.venv\Scripts\python.exe -m pytest -q -m "not integration"`
Expected: 14 passed (6 paths + 5 runner + 3 server)

Run: `pwsh smoke\smoke.ps1`
Expected: `SMOKE OK`

- [ ] **Step 6: Commit**

```powershell
git add src/armorpaint_mcp/server.py tests/test_server.py
git commit -m "feat: reexport_project MCP tool"
```

---

## Task 6: Integration test against the real ArmorPaint build

**Files:**
- Create: `tests/test_reexport_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/test_reexport_integration.py
"""Real ArmorPaint required. Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_reexport_integration.py -v
(needs AP_BINARY set to a working build -- see .env.example)
"""
import os

import pytest

from armorpaint_mcp.server import reexport_project

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_reexport_project_produces_real_files(tmp_path):
    output_dir = tmp_path / "out"

    result = reexport_project(project=FIXTURE, preset="generic",
                               output_dir=str(output_dir))

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    assert len(result["files"]) == 5  # base, nor, occ, rough, metal
    for f in result["files"]:
        assert os.path.isfile(f)
        assert os.path.getsize(f) > 0
```

- [ ] **Step 2: Run it for real**

Run:
```powershell
$env:AP_BINARY = "C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe"
.venv\Scripts\python.exe -m pytest tests\test_reexport_integration.py -v
```
Expected: `1 passed` (takes a few seconds — it launches the real app).

- [ ] **Step 3: Confirm it's excluded from the default fast run**

Run: `.venv\Scripts\python.exe -m pytest -q -m "not integration"`
Expected: same 14 passed as Task 5, this new test not among them (it's
`integration`-marked, excluded by the `-m "not integration"` filter).

- [ ] **Step 4: Update `docs/PLAN.md` and `STATUS.md`**

In `docs/PLAN.md`, Phase 1's gate is now met — leave the phase description
as-is (already accurate from this plan's empirical corrections).

In `STATUS.md`:
- Change the Phase 1 row to `| 1 | reexport_project tool (native export flags, no script) | ✅ 2026-09-15 | tests/test_reexport_integration.py: 1 passed, 5 real PNG files produced from tests/fixtures/sample_project.arm |`
- Update `**Open phase:**` to `2`.
- Add a row under Current Phase Detail for each new file (`paths.py`,
  `runner.py`, `server.py` reexport_project, the fixture) as `✅`.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_reexport_integration.py STATUS.md docs/PLAN.md
git commit -m "test: integration coverage for reexport_project; record Phase 1 gate"
```

---

## Task 7: Demo gallery (the media Grayson asked for)

**Files:**
- Create: `docs/images/gallery/generic_base.png`, `docs/images/gallery/unreal_packed.png` (or similar — exact filenames chosen in Step 1 below)
- Modify: `README.md`

- [ ] **Step 1: Generate two real export passes from the sample project**

Run:
```powershell
$env:AP_BINARY = "C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe"
.venv\Scripts\python.exe -c "
from armorpaint_mcp.server import reexport_project
import json
print(json.dumps(reexport_project('tests/fixtures/sample_project.arm', 'generic', 'docs/images/gallery/_tmp_generic')))
print(json.dumps(reexport_project('tests/fixtures/sample_project.arm', 'unreal', 'docs/images/gallery/_tmp_unreal')))
"
```
Expected: two JSON lines, both `"ok": true`. `generic`'s preset JSON
(`export_presets/generic.json`) declares 5 textures (`base`, `nor`, `occ`,
`rough`, `metal`), so its result has 5 file paths named
`sample_project_base.png`, `sample_project_nor.png`, `sample_project_occ.png`,
`sample_project_rough.png`, `sample_project_metal.png`. `unreal`'s preset
JSON (`export_presets/unreal.json`) declares 3 textures (`base`, `nor`,
`orm` — occlusion/roughness/metal packed into one RGB texture), so its
result has 3 file paths: `sample_project_base.png`, `sample_project_nor.png`,
`sample_project_orm.png`.

- [ ] **Step 2: Pick the base-color map from each pass for the gallery**

Copy the base-color output from `generic`, and the packed ORM map from
`unreal` (the visually distinct "packed vs. separate channels" story), into
`docs/images/gallery/`:
```powershell
Copy-Item docs\images\gallery\_tmp_generic\sample_project_base.png docs\images\gallery\generic_base.png
Copy-Item docs\images\gallery\_tmp_unreal\sample_project_orm.png docs\images\gallery\unreal_packed.png
```

Remove the temp directories once the two chosen files are copied out:
```powershell
Remove-Item -Recurse docs\images\gallery\_tmp_generic, docs\images\gallery\_tmp_unreal
```

- [ ] **Step 3: Add a Gallery section to README.md**

Insert this section into `README.md`, right after the "## Status" section
and before "## How it works":

```markdown
## Gallery

Real output from `reexport_project`, run against the tracked sample project
(`tests/fixtures/sample_project.arm` — ArmorPaint's own default cube-bevel
primitive + default material, generated headlessly, see
`tests/fixtures/generate_fixture.py`). Same project, two export presets:

| `generic` preset (separate channels) | `unreal` preset (packed) |
|:--:|:--:|
| ![generic preset base color export](docs/images/gallery/generic_base.png) | ![unreal preset packed export](docs/images/gallery/unreal_packed.png) |
```

- [ ] **Step 4: Verify the images actually render**

Run: `.venv\Scripts\python.exe -c "from PIL import Image; Image.open('docs/images/gallery/generic_base.png').verify(); Image.open('docs/images/gallery/unreal_packed.png').verify(); print('both valid PNGs')"`

(If Pillow isn't installed: `pip install Pillow` first — dev-only, don't add
it as a project dependency for this one-off check.)

Expected: `both valid PNGs`

- [ ] **Step 5: Commit**

```powershell
git add docs/images/gallery/generic_base.png docs/images/gallery/unreal_packed.png README.md
git commit -m "docs: add gallery — real reexport_project output"
```

---

## Task 8: Push and wrap up

**Files:** none (verification + push only)

- [ ] **Step 1: Full verification sweep**

Run each of these and confirm the stated result:
- `.venv\Scripts\python.exe -m pytest -q -m "not integration"` → all pass
- `.venv\Scripts\python.exe -m pytest -q -m integration` (with `AP_BINARY`
  set) → 1 passed
- `pwsh smoke\smoke.ps1` → `SMOKE OK`
- `.venv\Scripts\python.exe -m armorpaint_mcp.server --check` → exits 0 if
  `AP_BINARY`/`.env` are set on this machine (expected to pass, since this is
  the same machine Phase 0 verified against)

- [ ] **Step 2: Push**

```powershell
git push origin main
```

- [ ] **Step 3: Update HANDOFF.md**

Update "Current state" / "Where we stopped" / "Next concrete step" to reflect
Phase 1 shipped, gallery live, and Phase 2 (`rebake_and_export` — the first
tool needing a minic script template) as next. Commit and push that too.

```powershell
git add HANDOFF.md
git commit -m "docs: update handoff — Phase 1 shipped"
git push origin main
```

---

## Self-review notes (for whoever executes this plan)

- **Spec coverage:** Task 1-2 cover the design spec's `runner.py`/`paths.py`
  components. Task 5 covers `reexport_project`. Task 4/6 cover the design
  spec's testing section (unit + one real integration test). Task 7 is new
  scope Grayson added this session (media/gallery), not in the original
  design spec — that's expected, the spec predates this ask.
- **Two things this plan deliberately does NOT do**, both flagged as v1
  gaps, not oversights: `resolution` is not a `reexport_project` parameter
  (no confirmed way to control it — see the empirically-confirmed-facts
  section), and `rebake_and_export`/`list_export_presets` (the standalone
  tool)/`inspect_project` are Phase 2/3, not this plan.
- **The `--background` + `--export-textures` bug** should probably be
  reported upstream to armory3d/armorpaint at some point — out of scope for
  this plan, worth a note in a future session.
