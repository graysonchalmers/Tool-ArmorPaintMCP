# Phase 5 — Mesh/UV Editing Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 7 new MCP tools (`decimate_mesh`, `bevel_mesh`, `subdivide_mesh`,
`smooth_mesh`, `duplicate_mesh`, `merge_mesh_geometry`, `unwrap_mesh_uvs`) that
drive ArmorPaint's real mesh-editing algorithms headlessly via a scoped local
patch to its minic scripting engine — ROADMAP.md items 1-7.

**Architecture:** Every tool is a thin wrapper around one shared helper,
`_run_mesh_edit`, that resolves a target project (a copy by default, the
caller's own file only if `in_place=True`), runs a one-line minic script
calling the already-patched C function followed by `project_save(0)`, and
reports the result. `merge_mesh_geometry` adds one precondition check (needs
≥2 objects) using the existing `run_api`/`scene_objects` machinery before it
launches anything. A new preflight check in `doctor.py`, backed by a pure
parser in `catalog.py`, detects whether the connected `AP_BINARY` actually
carries the patch, so a caller pointed at a stock build gets a clear error
instead of a silent no-op.

**Tech Stack:** Python 3.10+, no new dependencies. C patch lives in the
sibling ArmorPaint checkout (`C:\Projects-local\z-Git\ArmorPaint`), not this
repo.

**Spec:** [docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](../specs/2026-09-15-armorpaint-mcp-design.md)
(Amendment 3) and [ROADMAP.md](../../../ROADMAP.md) (the North Star this
phase implements — items 1-7 of its stack-ranked roadmap).

## Global Constraints

- **Copy-by-default.** Every mesh-edit tool operates on a copy of the source
  project by default (`output_project` required, written via `shutil.copy2`
  before any edit runs); an explicit `in_place=True` opts into mutating the
  caller's own file, and `output_project` must be omitted when `in_place=True`
  (never silently ignored). This is the design spec's already-stated
  mutating-operations convention, applied here for the first time to a real
  shipped tool.
- **No hardcoded catalogs where a dynamic source exists.** N/A for the edit
  calls themselves (each is one fixed, already-verified minic function name —
  nothing to enumerate), but `merge_mesh_geometry`'s precondition reuses the
  existing dynamic `scene_objects()` catalog parser, not a hardcoded count.
- **Real integration tests against the actual local `ArmorPaint.exe`**
  (`@pytest.mark.integration`, deselected by default per `pyproject.toml`'s
  `addopts`) are required for every tool that claims to mutate geometry —
  `ok=True` alone proves only that the ArmorPaint process completed (see
  `run_script`'s own docstring and this project's minic-silent-failure
  history), never that the specific edit happened. Verify via a real,
  independent `script_export_mesh` OBJ export before/after, comparing counts
  computed fresh in the test — not hardcoded numbers copied from this
  session's spike (the spike's own smooth-mesh normal count had an internal
  inconsistency between two reported figures; relative/distinctness
  assertions computed live are more robust than trusting a transcribed
  number).
- **Windows shell:** this machine's shell is PowerShell 5.1 (`;` not `&&`).
  Running `ArmorPaint.exe` via Claude Code's Bash tool silently no-ops on
  this machine (confirmed, see project memory) — any manual verification a
  task author does outside pytest must use PowerShell, never the Bash tool.
  pytest's own subprocess calls (via Python's `subprocess` module) are
  unaffected by this — only matters for ad-hoc manual pokes.
- **Phase gate discipline:** `STATUS.md` gets a new Phase 5 row only after
  the final task's real verification sweep (fresh `pytest -q`, `pytest -q -m
  integration`, `smoke/smoke.ps1`) all pass — never marked green on
  assertion alone.
- **`merge_mesh_geometry`'s real scope limit:** `util_mesh_merge_geometry()`
  collapses **every** object in the project into one; there is no way to
  target a specific pair (`util_mesh_merge_geometry_down`'s real signature
  needs a second minic accessor that doesn't exist — ROADMAP.md item 9, out
  of scope for this phase). The tool's docstring must say this explicitly,
  not imply "merge two objects."

---

## Task 1: Rebuild the patched ArmorPaint binary + a preflight check that detects it

**Files:**
- Modify: `C:\Projects-local\z-Git\ArmorPaint` (sibling checkout — rebuild
  only, no new source changes; the patch already exists on branch
  `spike/minic-decimate`)
- Create: `src/armorpaint_mcp/catalog.py` — add `mesh_edit_patch_missing`
- Modify: `src/armorpaint_mcp/doctor.py` — add a check using it
- Create: `tests/test_catalog.py` — add tests for `mesh_edit_patch_missing`
  (this file already exists for `blend_modes`/`scene_objects`; add to it)

**Interfaces:**
- Produces: `catalog.mesh_edit_patch_missing(api_text: str) -> list[str]` —
  every expected mesh-edit function name NOT found in `api_text`, empty list
  means fully patched. Used by Task 2 onward's own manual sanity checks and
  by `doctor.py`'s new check.

- [ ] **Step 1: Rebuild the real `AP_BINARY` target from the patched branch**

The patch already exists, proven, on branch `spike/minic-decimate` in
`C:\Projects-local\z-Git\ArmorPaint` (one file changed,
`paint\sources\minic_api_list.h`, ~19 lines). `AP_BINARY` (per
`.env`/`.env.example`) points at `paint\build\out\ArmorPaint.exe` in that
same checkout — today that's built from stock `main`, not the patch.

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint
git status --short
git checkout spike/minic-decimate
& "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe" paint\build\ArmorPaint.vcxproj /p:Configuration=Release /p:Platform=x64
Pop-Location
```

(Confirm the actual MSBuild path and project file match this checkout's
`make.bat`/README before running — the spike's own build already succeeded
on this machine, so use whatever invocation it used, visible in the spike
agent's transcript if the above path doesn't match.)

- [ ] **Step 2: Verify the rebuild manually, once, via PowerShell**

```powershell
& "C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe" --api | Select-String "util_mesh_decimate"
```

Expected: one matching line (confirms the patched function name now appears
in the static API reference — this exact command against the STOCK binary
was already run this session and printed nothing).

- [ ] **Step 3: Write the failing test for the pure parser**

```python
# tests/test_catalog.py -- add to the existing file
from armorpaint_mcp.catalog import mesh_edit_patch_missing

def test_mesh_edit_patch_missing_reports_all_seven_when_none_present():
    stock_api_text = "// ArmorPaint script API\n\ntypedef struct i8_array_t {\n"
    missing = mesh_edit_patch_missing(stock_api_text)
    assert sorted(missing) == sorted([
        "util_mesh_decimate", "util_mesh_smooth", "util_mesh_bevel",
        "util_mesh_subdivide", "util_mesh_merge_geometry",
        "util_mesh_duplicate", "plugin_uv_unwrap_button",
    ])


def test_mesh_edit_patch_missing_empty_when_all_present():
    patched_api_text = (
        "util_mesh_decimate(f strength)\n"
        "util_mesh_smooth()\n"
        "util_mesh_bevel(f amount)\n"
        "util_mesh_subdivide()\n"
        "util_mesh_merge_geometry()\n"
        "util_mesh_duplicate()\n"
        "plugin_uv_unwrap_button()\n"
    )
    assert mesh_edit_patch_missing(patched_api_text) == []


def test_mesh_edit_patch_missing_reports_only_the_absent_ones():
    partial = "util_mesh_decimate(f strength)\nutil_mesh_smooth()\n"
    missing = mesh_edit_patch_missing(partial)
    assert "util_mesh_decimate" not in missing
    assert "util_mesh_smooth" not in missing
    assert "util_mesh_bevel" in missing
    assert len(missing) == 5
```

- [ ] **Step 4: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_catalog.py -k mesh_edit_patch_missing -v`
Expected: FAIL with `ImportError` / `AttributeError` (`mesh_edit_patch_missing` doesn't exist yet)

- [ ] **Step 5: Implement `mesh_edit_patch_missing` in `catalog.py`**

Add near the bottom of `src/armorpaint_mcp/catalog.py`:

```python
_MESH_EDIT_PATCH_FUNCTIONS = [
    "util_mesh_decimate", "util_mesh_smooth", "util_mesh_bevel",
    "util_mesh_subdivide", "util_mesh_merge_geometry", "util_mesh_duplicate",
    "plugin_uv_unwrap_button",
]


def mesh_edit_patch_missing(api_text: str) -> list[str]:
    """Which of the mesh-edit minic functions this project's Phase 5 tools
    depend on are NOT present in `api_text` (ArmorPaint.exe --api's static
    output, no project needed). Empty list means the connected AP_BINARY
    carries the scoped local patch (see ROADMAP.md's "Patch policy"); a
    non-empty list means it's running stock ArmorPaint, where these calls
    would silently abort the whole script (confirmed empirically during the
    2026-09-16 spike) while still reporting ok=True -- the exact trap this
    check exists to catch before a caller hits it."""
    return [name for name in _MESH_EDIT_PATCH_FUNCTIONS if name not in api_text]
```

- [ ] **Step 6: Run to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_catalog.py -k mesh_edit_patch_missing -v`
Expected: 3 passed

- [ ] **Step 7: Write the failing test for the doctor.py check**

`tests/test_doctor.py` doesn't exist yet — create it:

```python
# tests/test_doctor.py
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
```

- [ ] **Step 8: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_doctor.py -v`
Expected: FAIL — `check_setup` doesn't add a "mesh-edit patch" check yet

- [ ] **Step 9: Implement the check in `doctor.py`**

Add the import at the top: `from armorpaint_mcp.catalog import mesh_edit_patch_missing`

Add this block in `check_setup`, after the existing "binary launches" check
(same `if cfg.binary and os.path.isfile(cfg.binary):` guard shape, reusing
the pattern already there):

```python
    if cfg.binary and os.path.isfile(cfg.binary):
        try:
            out = subprocess.run([cfg.binary, "--api"], capture_output=True,
                                  text=True, timeout=15)
            missing = mesh_edit_patch_missing(out.stdout) if out.returncode == 0 else None
            if missing is None:
                checks.append(Check("mesh-edit patch", False,
                                    f"'--api' exited {out.returncode}, could not check"))
            elif missing:
                checks.append(Check("mesh-edit patch", False,
                                    f"missing minic registration(s): {', '.join(missing)} "
                                    "-- this AP_BINARY is running stock ArmorPaint. Phase 5's "
                                    "mesh-edit tools (decimate_mesh, etc.) need the scoped "
                                    "local patch built -- see ROADMAP.md's \"Patch policy\"."))
            else:
                checks.append(Check("mesh-edit patch", True,
                                    "all 7 mesh-edit functions registered"))
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append(Check("mesh-edit patch", False, str(exc)))
```

- [ ] **Step 10: Run to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_doctor.py tests/test_catalog.py -v`
Expected: all pass

- [ ] **Step 11: Real-binary sanity check (manual, not pytest)**

```powershell
Push-Location C:\Projects-local\Tool-ArmorPaintMCP
& .venv\Scripts\python.exe -m armorpaint_mcp.server --check
Pop-Location
```

Expected: `[PASS] mesh-edit patch: all 7 mesh-edit functions registered` (the
real rebuilt binary from Step 1, not a mock).

- [ ] **Step 12: Commit**

```powershell
git add src/armorpaint_mcp/catalog.py src/armorpaint_mcp/doctor.py tests/test_catalog.py tests/test_doctor.py
git commit -m "feat: detect the mesh-edit minic patch in --check preflight"
```

---

## Task 2: Shared `_run_mesh_edit` helper + `decimate_mesh`

**Files:**
- Modify: `src/armorpaint_mcp/server.py`
- Create: `tests/_mesh_edit_test_helpers.py`
- Create: `tests/test_decimate_mesh_integration.py`
- Modify: `tests/test_server.py` (add unit tests for `decimate_mesh` and `_run_mesh_edit`'s shared paths)

**Interfaces:**
- Produces: `server._run_mesh_edit(project: str, minic_call: str, output_project: str | None, in_place: bool, timeout_s: float) -> dict` — shape `{"ok": bool, "output_project": str | None, "error": str | None}`. Every later task's tool (`bevel_mesh`, `subdivide_mesh`, `smooth_mesh`, `duplicate_mesh`, `unwrap_mesh_uvs`, and `merge_mesh_geometry` after its own precondition check) calls this directly.
- Produces: `server.decimate_mesh(project: str, strength: float, output_project: str | None = None, in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict`
- Produces (test-only): `tests/_mesh_edit_test_helpers.py`'s `export_obj(project: str, out_path: str) -> str` and `count_obj_vertices_and_faces(text: str) -> tuple[int, int]` — reused by every later task's integration test.

- [ ] **Step 1: Write the shared test helpers module**

```python
# tests/_mesh_edit_test_helpers.py
"""Shared helpers for Phase 5's mesh-edit integration tests: verify a real
effect via an independent script_export_mesh OBJ export, never trust ok=True
alone (see this project's established minic-silent-failure history)."""

from armorpaint_mcp.server import run_script


def export_obj(project: str, out_path: str) -> str:
    """Export `project`'s current mesh to `out_path` (OBJ) via a fresh,
    edit-free run_script call, then return the file's text. Raises
    AssertionError with the tool's own error message if the export itself
    fails -- a failure here means the verification step is broken, not the
    thing under test, so it should fail loud rather than silently return
    empty text."""
    posix_out = out_path.replace("\\", "/")
    script = f'void main() {{\n\tscript_export_mesh("{posix_out}");\n}}\n'
    result = run_script(project=project, script=script)
    assert result["ok"], result["error"]
    with open(out_path, encoding="utf-8") as fh:
        return fh.read()


def count_obj_vertices_and_faces(text: str) -> tuple[int, int]:
    """(vertex count, face count) -- lines starting with 'v ' and 'f '
    specifically (not 'vn '/'vt ', which also start with 'v')."""
    vertices = sum(1 for line in text.splitlines() if line.startswith("v "))
    faces = sum(1 for line in text.splitlines() if line.startswith("f "))
    return vertices, faces


def obj_normal_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("vn ")]


def obj_uv_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("vt ")]
```

This has no tests of its own (it's test infrastructure, exercised by every
integration test that imports it starting with this task's own).

- [ ] **Step 2: Write the failing integration test for `decimate_mesh`**

```python
# tests/test_decimate_mesh_integration.py
"""Real ArmorPaint required (with the mesh-edit patch built -- see Task 1).
Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_decimate_mesh_integration.py -v -m integration
"""
import os
import shutil

import pytest

from armorpaint_mcp.server import decimate_mesh
from tests._mesh_edit_test_helpers import export_obj, count_obj_vertices_and_faces

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_decimate_mesh_reduces_vertex_and_face_count(tmp_path):
    output_project = str(tmp_path / "decimated.arm")

    result = decimate_mesh(project=FIXTURE, strength=0.5, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    assert result["output_project"] == output_project
    assert os.path.isfile(output_project)

    before_text = export_obj(FIXTURE, str(tmp_path / "before.obj"))
    after_text = export_obj(output_project, str(tmp_path / "after.obj"))
    before_v, before_f = count_obj_vertices_and_faces(before_text)
    after_v, after_f = count_obj_vertices_and_faces(after_text)

    assert after_v < before_v, (before_v, after_v)
    assert after_f < before_f, (before_f, after_f)


@pytest.mark.integration
def test_decimate_mesh_in_place_mutates_the_caller_s_own_file(tmp_path):
    project = str(tmp_path / "project.arm")
    shutil.copy2(FIXTURE, project)
    before_text = export_obj(project, str(tmp_path / "before.obj"))
    before_v, _ = count_obj_vertices_and_faces(before_text)

    result = decimate_mesh(project=project, strength=0.5, in_place=True)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    assert result["output_project"] == project

    after_text = export_obj(project, str(tmp_path / "after.obj"))
    after_v, _ = count_obj_vertices_and_faces(after_text)
    assert after_v < before_v
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_decimate_mesh_integration.py -v -m integration`
Expected: FAIL — `decimate_mesh` doesn't exist yet (`ImportError`)

- [ ] **Step 4: Write the failing unit tests**

Add to `tests/test_server.py` (mirroring the file's existing mock-based style
for `reexport_project`):

```python
from armorpaint_mcp.server import decimate_mesh  # add to the existing import block


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


def test_decimate_mesh_copies_then_edits_and_saves(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_run.return_value = ScriptResult(ok=True, stdout="", stderr="")

        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(output_project))

    assert result == {"ok": True, "output_project": str(output_project), "error": None}
    assert output_project.exists()  # shutil.copy2 actually ran
    script_arg = mock_run.call_args[0][2]
    assert "util_mesh_decimate(0.5);" in script_arg
    assert "project_save(0);" in script_arg


def test_decimate_mesh_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert "decimate_mesh" in by_name, sorted(by_name)
    tool = by_name["decimate_mesh"]
    assert set(tool.input_schema["properties"]) == {
        "project", "strength", "output_project", "in_place", "timeout_s"}
    assert set(tool.input_schema.get("required", [])) == {"project", "strength"}
```

- [ ] **Step 5: Run to verify the unit tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -k decimate_mesh -v`
Expected: FAIL — `decimate_mesh` doesn't exist yet

- [ ] **Step 6: Implement `_run_mesh_edit` and `decimate_mesh` in `server.py`**

Add `import shutil` to the top-of-file imports.

Add `_finite_float` to the existing script_gen import line:
```python
from armorpaint_mcp.script_gen import _finite_float, generate_script, NodeSpecError
```

Add after `_is_arm_project_file`:

```python
def _run_mesh_edit(project: str, minic_call: str, output_project: str | None,
                   in_place: bool, timeout_s: float) -> dict:
    """Shared plumbing for every mesh-edit tool: validate `project`, resolve
    the edit target (a copy at `output_project` by default -- never touching
    the caller's own file unless `in_place=True`), run `minic_call` followed
    by project_save(0) against that target, and report the outcome.

    ok=True proves only that the ArmorPaint process completed and
    project_save(0) ran -- same caveat as run_script and every other minic
    call in this project (see run_script's docstring). `minic_call` here is
    always one of this project's own, already-verified function calls
    (never caller-supplied text), so the practical risk is much narrower
    than run_script's arbitrary-script case, but the underlying guarantee
    is identical.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    cfg = _ensure_ready()

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "output_project")

    if not _is_arm_project_file(project):
        return _failure(f"'{project}' is not an existing .arm project file",
                        "output_project")

    if in_place:
        if output_project is not None:
            return _failure(
                "output_project must not be set when in_place=True (the "
                "caller's own project is mutated directly)", "output_project")
        target = project
    else:
        if not output_project:
            return _failure(
                "output_project is required unless in_place=True (mutating "
                "operations default to a copy, never the caller's own file)",
                "output_project")
        try:
            output_project = ensure_within_roots(output_project, cfg.allowed_roots)
        except PathNotAllowed as exc:
            return _failure(str(exc), "output_project")
        os.makedirs(os.path.dirname(output_project) or ".", exist_ok=True)
        shutil.copy2(project, output_project)
        target = output_project

    script = f"void main() {{\n\t{minic_call}\n\tproject_save(0);\n}}\n"
    result = run_minic_script(cfg.binary, target, script, timeout_s)
    if not result.ok:
        return _failure(result.error, "output_project")
    return {"ok": True, "output_project": target, "error": None}


def decimate_mesh(project: str, strength: float, output_project: str | None = None,
                  in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Reduce the project's mesh polycount via ArmorPaint's own decimate
    algorithm (util_mesh_decimate -- a real, working GUI tool as of
    ArmorPaint 1.0, exposed to --script by this project's scoped local
    patch; see ROADMAP.md's "Patch policy"). `strength` is 0.0-1.0-ish
    (ArmorPaint's own GUI default is 0.5); higher removes more geometry.
    Operates on a copy of `project` by default -- pass in_place=True to
    mutate `project` itself instead, in which case output_project must be
    omitted. Requires AP_BINARY to be a build carrying the mesh-edit patch
    (run `ap-mcp --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    ok=True proves the ArmorPaint process completed and saved -- not that
    the reduction looks good; inspect the result yourself for anything
    beyond "did geometry change" (verified by this tool's own test suite via
    real vertex/face counts, not asserted here at runtime).

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    try:
        strength = _finite_float("strength", strength)
    except NodeSpecError as exc:
        return _failure(str(exc), "output_project")
    return _run_mesh_edit(project, f"util_mesh_decimate({strength});",
                          output_project, in_place, timeout_s)


mcp.tool()(decimate_mesh)
```

- [ ] **Step 7: Run to verify the unit tests pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -k decimate_mesh -v`
Expected: 5 passed (need `from armorpaint_mcp.runner import ScriptResult` already
imported in test_server.py per its existing import line -- confirm, add if not)

- [ ] **Step 8: Run the real integration test**

Run: `.venv\Scripts\python.exe -m pytest tests/test_decimate_mesh_integration.py -v -m integration`
Expected: 2 passed (requires the Task 1 rebuild to be in place)

- [ ] **Step 9: Run the full unit suite to confirm no regressions**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all pass, count increased by the new unit tests

- [ ] **Step 10: Commit**

```powershell
git add src/armorpaint_mcp/server.py tests/_mesh_edit_test_helpers.py tests/test_decimate_mesh_integration.py tests/test_server.py
git commit -m "feat: add decimate_mesh + shared _run_mesh_edit helper"
```

---

## Task 3: `bevel_mesh` + `subdivide_mesh`

**Files:**
- Modify: `src/armorpaint_mcp/server.py`
- Modify: `tests/test_server.py`
- Create: `tests/test_bevel_mesh_integration.py`
- Create: `tests/test_subdivide_mesh_integration.py`

**Interfaces:**
- Consumes: `_run_mesh_edit` (Task 2), `_finite_float`/`NodeSpecError` (already imported in Task 2)
- Produces: `server.bevel_mesh(project, amount, output_project=None, in_place=False, timeout_s=DEFAULT_TIMEOUT_S) -> dict`
- Produces: `server.subdivide_mesh(project, output_project=None, in_place=False, timeout_s=DEFAULT_TIMEOUT_S) -> dict`

- [ ] **Step 1: Write the failing integration tests**

```python
# tests/test_bevel_mesh_integration.py
import os

import pytest

from armorpaint_mcp.server import bevel_mesh
from tests._mesh_edit_test_helpers import export_obj, count_obj_vertices_and_faces

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_bevel_mesh_adds_geometry(tmp_path):
    output_project = str(tmp_path / "beveled.arm")

    result = bevel_mesh(project=FIXTURE, amount=0.1, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    before_v, before_f = count_obj_vertices_and_faces(
        export_obj(FIXTURE, str(tmp_path / "before.obj")))
    after_v, after_f = count_obj_vertices_and_faces(
        export_obj(output_project, str(tmp_path / "after.obj")))

    assert after_v > before_v, (before_v, after_v)
    assert after_f > before_f, (before_f, after_f)
```

```python
# tests/test_subdivide_mesh_integration.py
import os

import pytest

from armorpaint_mcp.server import subdivide_mesh
from tests._mesh_edit_test_helpers import export_obj, count_obj_vertices_and_faces

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_subdivide_mesh_quadruples_face_count(tmp_path):
    """Confirmed empirically during this phase's own spike: subdivide is an
    exact 4x face-count operation (each triangle -> 4). Asserting the exact
    ratio here, not just an increase, since this one IS deterministic and a
    ratio check is a stronger proof than inequality alone."""
    output_project = str(tmp_path / "subdivided.arm")

    result = subdivide_mesh(project=FIXTURE, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    _, before_f = count_obj_vertices_and_faces(
        export_obj(FIXTURE, str(tmp_path / "before.obj")))
    _, after_f = count_obj_vertices_and_faces(
        export_obj(output_project, str(tmp_path / "after.obj")))

    assert after_f == before_f * 4, (before_f, after_f)
```

- [ ] **Step 2: Run to verify both fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_bevel_mesh_integration.py tests/test_subdivide_mesh_integration.py -v -m integration`
Expected: FAIL — neither tool exists yet

- [ ] **Step 3: Write the failing unit tests**

Add to `tests/test_server.py`:

```python
from armorpaint_mcp.server import bevel_mesh, subdivide_mesh  # extend the existing import


def test_bevel_mesh_calls_the_right_minic_function(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_run.return_value = ScriptResult(ok=True, stdout="", stderr="")

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
        mock_run.return_value = ScriptResult(ok=True, stdout="", stderr="")

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
```

- [ ] **Step 4: Run to verify the unit tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -k "bevel_mesh or subdivide_mesh" -v`
Expected: FAIL

- [ ] **Step 5: Implement both tools in `server.py`**

Add after `decimate_mesh`/`mcp.tool()(decimate_mesh)`:

```python
def bevel_mesh(project: str, amount: float, output_project: str | None = None,
               in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Bevel the project's mesh edges via ArmorPaint's own bevel algorithm
    (util_mesh_bevel -- exposed to --script by this project's scoped local
    patch; see ROADMAP.md's "Patch policy"). `amount` is the bevel distance
    (ArmorPaint's own GUI default is 0.1). Operates on a copy of `project`
    by default -- pass in_place=True to mutate `project` itself instead, in
    which case output_project must be omitted. Requires AP_BINARY to be a
    build carrying the mesh-edit patch (run `ap-mcp --check` to confirm).
    Bounded by AP_ALLOWED_ROOTS when set.

    ok=True proves the ArmorPaint process completed and saved -- not that
    the bevel looks good.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    try:
        amount = _finite_float("amount", amount)
    except NodeSpecError as exc:
        return _failure(str(exc), "output_project")
    return _run_mesh_edit(project, f"util_mesh_bevel({amount});",
                          output_project, in_place, timeout_s)


mcp.tool()(bevel_mesh)


def subdivide_mesh(project: str, output_project: str | None = None,
                   in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Subdivide the project's mesh via ArmorPaint's own subdivide algorithm
    (util_mesh_subdivide -- exposed to --script by this project's scoped
    local patch; see ROADMAP.md's "Patch policy"). Confirmed empirically to
    be an exact 4x face-count operation on this build. Operates on a copy of
    `project` by default -- pass in_place=True to mutate `project` itself
    instead, in which case output_project must be omitted. Requires
    AP_BINARY to be a build carrying the mesh-edit patch (run `ap-mcp
    --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    return _run_mesh_edit(project, "util_mesh_subdivide();",
                          output_project, in_place, timeout_s)


mcp.tool()(subdivide_mesh)
```

- [ ] **Step 6: Run to verify the unit tests pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -k "bevel_mesh or subdivide_mesh" -v`
Expected: 4 passed

- [ ] **Step 7: Run the integration tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_bevel_mesh_integration.py tests/test_subdivide_mesh_integration.py -v -m integration`
Expected: 2 passed

- [ ] **Step 8: Full unit suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all pass

- [ ] **Step 9: Commit**

```powershell
git add src/armorpaint_mcp/server.py tests/test_bevel_mesh_integration.py tests/test_subdivide_mesh_integration.py tests/test_server.py
git commit -m "feat: add bevel_mesh and subdivide_mesh"
```

---

## Task 4: `smooth_mesh` + `duplicate_mesh`

**Files:**
- Modify: `src/armorpaint_mcp/server.py`
- Modify: `tests/test_server.py`
- Create: `tests/test_smooth_mesh_integration.py`
- Create: `tests/test_duplicate_mesh_integration.py`

**Interfaces:**
- Consumes: `_run_mesh_edit` (Task 2)
- Produces: `server.smooth_mesh(project, output_project=None, in_place=False, timeout_s=DEFAULT_TIMEOUT_S) -> dict`
- Produces: `server.duplicate_mesh(project, output_project=None, in_place=False, timeout_s=DEFAULT_TIMEOUT_S) -> dict`

- [ ] **Step 1: Write the failing integration tests**

```python
# tests/test_smooth_mesh_integration.py
import os

import pytest

from armorpaint_mcp.server import smooth_mesh
from tests._mesh_edit_test_helpers import (export_obj, count_obj_vertices_and_faces,
                                           obj_normal_lines)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_smooth_mesh_preserves_topology_but_changes_normals(tmp_path):
    """Smoothing does not change vertex/face counts (it moves vertices and
    recomputes normals, it doesn't add or remove geometry). Confirmed
    empirically during this phase's own spike; asserted live here via
    before/after comparison rather than a hardcoded normal count, since the
    spike's own transcript had an internal inconsistency on the exact
    number -- the topology-preserved + normals-changed relationship is the
    robust, reproducible claim."""
    output_project = str(tmp_path / "smoothed.arm")

    result = smooth_mesh(project=FIXTURE, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    before_text = export_obj(FIXTURE, str(tmp_path / "before.obj"))
    after_text = export_obj(output_project, str(tmp_path / "after.obj"))

    before_v, before_f = count_obj_vertices_and_faces(before_text)
    after_v, after_f = count_obj_vertices_and_faces(after_text)
    assert (after_v, after_f) == (before_v, before_f), "smooth should not change topology"

    assert obj_normal_lines(after_text) != obj_normal_lines(before_text), (
        "smooth should change vertex normals even though topology is unchanged")
```

```python
# tests/test_duplicate_mesh_integration.py
import os

import pytest

from armorpaint_mcp.server import duplicate_mesh
from tests._mesh_edit_test_helpers import export_obj, count_obj_vertices_and_faces

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_duplicate_mesh_doubles_vertex_and_face_count(tmp_path):
    """Confirmed empirically during this phase's own spike: duplicate is an
    exact 2x operation, and it appends a second object (verified there via
    a new "o Tessellated.001" group). Asserting the exact ratio, the
    strongest available proof for this deterministic operation."""
    output_project = str(tmp_path / "duplicated.arm")

    result = duplicate_mesh(project=FIXTURE, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    _, before_f = count_obj_vertices_and_faces(
        export_obj(FIXTURE, str(tmp_path / "before.obj")))
    after_text = export_obj(output_project, str(tmp_path / "after.obj"))
    after_v, after_f = count_obj_vertices_and_faces(after_text)

    assert after_f == before_f * 2, (before_f, after_f)
    assert "o " in after_text  # a second named object group exists
```

- [ ] **Step 2: Run to verify both fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_smooth_mesh_integration.py tests/test_duplicate_mesh_integration.py -v -m integration`
Expected: FAIL

- [ ] **Step 3: Write the failing unit tests**

Add to `tests/test_server.py`:

```python
from armorpaint_mcp.server import smooth_mesh, duplicate_mesh  # extend the existing import


def test_smooth_mesh_calls_the_right_minic_function(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_run.return_value = ScriptResult(ok=True, stdout="", stderr="")

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
        mock_run.return_value = ScriptResult(ok=True, stdout="", stderr="")

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
```

- [ ] **Step 4: Run to verify the unit tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -k "smooth_mesh or duplicate_mesh" -v`
Expected: FAIL

- [ ] **Step 5: Implement both tools in `server.py`**

```python
def smooth_mesh(project: str, output_project: str | None = None,
                in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Smooth the project's mesh via ArmorPaint's own smoothing algorithm
    (util_mesh_smooth -- exposed to --script by this project's scoped local
    patch; see ROADMAP.md's "Patch policy"). Does not change vertex/face
    count (confirmed empirically), only vertex positions and normals.
    Operates on a copy of `project` by default -- pass in_place=True to
    mutate `project` itself instead, in which case output_project must be
    omitted. Requires AP_BINARY to be a build carrying the mesh-edit patch
    (run `ap-mcp --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    return _run_mesh_edit(project, "util_mesh_smooth();",
                          output_project, in_place, timeout_s)


mcp.tool()(smooth_mesh)


def duplicate_mesh(project: str, output_project: str | None = None,
                   in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Duplicate the project's mesh object via ArmorPaint's own duplicate
    function (util_mesh_duplicate -- exposed to --script by this project's
    scoped local patch; see ROADMAP.md's "Patch policy"). Confirmed
    empirically to be an exact 2x vertex/face-count operation, adding a
    second object to the scene. Operates on a copy of `project` by default
    -- pass in_place=True to mutate `project` itself instead, in which case
    output_project must be omitted. Requires AP_BINARY to be a build
    carrying the mesh-edit patch (run `ap-mcp --check` to confirm). Bounded
    by AP_ALLOWED_ROOTS when set.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    return _run_mesh_edit(project, "util_mesh_duplicate();",
                          output_project, in_place, timeout_s)


mcp.tool()(duplicate_mesh)
```

- [ ] **Step 6: Run to verify the unit tests pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -k "smooth_mesh or duplicate_mesh" -v`
Expected: 4 passed

- [ ] **Step 7: Run the integration tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_smooth_mesh_integration.py tests/test_duplicate_mesh_integration.py -v -m integration`
Expected: 2 passed

- [ ] **Step 8: Full unit suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all pass

- [ ] **Step 9: Commit**

```powershell
git add src/armorpaint_mcp/server.py tests/test_smooth_mesh_integration.py tests/test_duplicate_mesh_integration.py tests/test_server.py
git commit -m "feat: add smooth_mesh and duplicate_mesh"
```

---

## Task 5: `merge_mesh_geometry`

**Files:**
- Modify: `src/armorpaint_mcp/server.py`
- Modify: `tests/test_server.py`
- Create: `tests/test_merge_mesh_geometry_integration.py`

**Interfaces:**
- Consumes: `_run_mesh_edit` (Task 2), `run_api` (already imported), `scene_objects`/`CatalogError` (already imported from `catalog`), `duplicate_mesh` (Task 4, used by this task's own integration test to build a 2-object starting point -- no multi-object fixture exists yet, per ROADMAP.md's "Known gaps")
- Produces: `server.merge_mesh_geometry(project, output_project=None, in_place=False, timeout_s=DEFAULT_TIMEOUT_S) -> dict`

- [ ] **Step 1: Write the failing integration tests**

```python
# tests/test_merge_mesh_geometry_integration.py
import os

import pytest

from armorpaint_mcp.server import merge_mesh_geometry, duplicate_mesh, inspect_project

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_merge_mesh_geometry_rejects_a_single_object_project():
    """No multi-object fixture exists (ROADMAP.md's "Known gaps" -- ArmorPaint
    silently no-ops when fewer than 2 objects exist, per util_mesh_merge_geometry's
    own internal guard, confirmed during this phase's spike). This must surface
    as a clear, explicit failure -- never a false ok=True with zero visible
    effect."""
    result = merge_mesh_geometry(project=FIXTURE, output_project="unused.arm")

    assert result["ok"] is False
    assert "only 1 object" in result["error"]
    assert "merge_mesh_geometry" in result["error"]
    assert result["output_project"] is None


@pytest.mark.integration
def test_merge_mesh_geometry_collapses_two_objects_into_one(tmp_path):
    duplicated = str(tmp_path / "duplicated.arm")
    dup_result = duplicate_mesh(project=FIXTURE, output_project=duplicated)
    assert dup_result["ok"] is True, dup_result["error"]

    merged = str(tmp_path / "merged.arm")
    result = merge_mesh_geometry(project=duplicated, output_project=merged)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    inspected = inspect_project(project=merged)
    assert inspected["ok"] is True, inspected["error"]
    assert len(inspected["objects"]) == 1, inspected["objects"]
```

- [ ] **Step 2: Run to verify both fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_merge_mesh_geometry_integration.py -v -m integration`
Expected: FAIL — `merge_mesh_geometry` doesn't exist yet

- [ ] **Step 3: Write the failing unit tests**

Add to `tests/test_server.py`:

```python
from armorpaint_mcp.server import merge_mesh_geometry  # extend the existing import
from armorpaint_mcp.runner import ApiResult  # extend the existing runner import


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
        mock_run.return_value = ScriptResult(ok=True, stdout="", stderr="")

        result = merge_mesh_geometry(project=str(project), output_project=str(output_project))

    assert result["ok"] is True
    assert "util_mesh_merge_geometry();" in mock_run.call_args[0][2]


def test_merge_mesh_geometry_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert "merge_mesh_geometry" in by_name, sorted(by_name)
```

- [ ] **Step 4: Run to verify the unit tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -k merge_mesh_geometry -v`
Expected: FAIL

- [ ] **Step 5: Implement `merge_mesh_geometry` in `server.py`**

```python
def merge_mesh_geometry(project: str, output_project: str | None = None,
                        in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Merge every object in the project into one, via ArmorPaint's own
    util_mesh_merge_geometry (exposed to --script by this project's scoped
    local patch; see ROADMAP.md's "Patch policy").

    IMPORTANT: this merges ALL objects in the project, not a specific pair.
    ArmorPaint's GUI "merge with the object below" targeting
    (util_mesh_merge_geometry_down) needs a second minic accessor that does
    not exist -- see ROADMAP.md item 9. There is no way to merge only two
    of three-or-more objects with this tool.

    Requires at least 2 objects in the project -- util_mesh_merge_geometry
    silently no-ops (by its own internal guard) on a project with fewer,
    confirmed empirically. This tool checks the object count itself first
    (via inspect_project's same --api machinery) and returns a clear error
    rather than a false ok=True with zero visible effect.

    Operates on a copy of `project` by default -- pass in_place=True to
    mutate `project` itself instead, in which case output_project must be
    omitted. Requires AP_BINARY to be a build carrying the mesh-edit patch
    (run `ap-mcp --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    cfg = _ensure_ready()

    try:
        checked_project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "output_project")

    if not _is_arm_project_file(checked_project):
        return _failure(f"'{checked_project}' is not an existing .arm project file",
                        "output_project")

    api_result = run_api(cfg.binary, checked_project)
    if not api_result.ok:
        return _failure(api_result.error, "output_project")

    try:
        objects = scene_objects(api_result.text)
    except CatalogError as exc:
        return _failure(str(exc), "output_project")

    if len(objects) < 2:
        return _failure(
            f"project has only {len(objects)} object(s); merge_mesh_geometry "
            f"needs at least 2 (util_mesh_merge_geometry collapses ALL objects "
            f"in the project into one and silently does nothing with fewer -- "
            f"see this tool's docstring for why a specific-pair merge isn't "
            f"possible)", "output_project")

    return _run_mesh_edit(project, "util_mesh_merge_geometry();",
                          output_project, in_place, timeout_s)


mcp.tool()(merge_mesh_geometry)
```

- [ ] **Step 6: Run to verify the unit tests pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -k merge_mesh_geometry -v`
Expected: 3 passed

- [ ] **Step 7: Run the integration tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_merge_mesh_geometry_integration.py -v -m integration`
Expected: 2 passed

- [ ] **Step 8: Full unit suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all pass

- [ ] **Step 9: Commit**

```powershell
git add src/armorpaint_mcp/server.py tests/test_merge_mesh_geometry_integration.py tests/test_server.py
git commit -m "feat: add merge_mesh_geometry with a fewer-than-2-objects guard"
```

---

## Task 6: `unwrap_mesh_uvs`

**Files:**
- Modify: `src/armorpaint_mcp/server.py`
- Modify: `tests/test_server.py`
- Create: `tests/test_unwrap_mesh_uvs_integration.py`

**Interfaces:**
- Consumes: `_run_mesh_edit` (Task 2)
- Produces: `server.unwrap_mesh_uvs(project, output_project=None, in_place=False, timeout_s=DEFAULT_TIMEOUT_S) -> dict`

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_unwrap_mesh_uvs_integration.py
import os

import pytest

from armorpaint_mcp.server import unwrap_mesh_uvs
from tests._mesh_edit_test_helpers import export_obj, obj_uv_lines

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_unwrap_mesh_uvs_changes_the_uv_coordinates(tmp_path):
    """Confirmed empirically during this phase's own spike: real UV coords
    change (all 144 vt lines differed on the fixture), the topology does
    not (this is a UV operation, not a geometry operation)."""
    output_project = str(tmp_path / "unwrapped.arm")

    result = unwrap_mesh_uvs(project=FIXTURE, output_project=output_project)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    before_uvs = obj_uv_lines(export_obj(FIXTURE, str(tmp_path / "before.obj")))
    after_uvs = obj_uv_lines(export_obj(output_project, str(tmp_path / "after.obj")))

    assert len(after_uvs) == len(before_uvs)  # same vertex count, same UV count
    assert after_uvs != before_uvs, "unwrap should produce different UV coordinates"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_unwrap_mesh_uvs_integration.py -v -m integration`
Expected: FAIL — `unwrap_mesh_uvs` doesn't exist yet

- [ ] **Step 3: Write the failing unit tests**

Add to `tests/test_server.py`:

```python
from armorpaint_mcp.server import unwrap_mesh_uvs  # extend the existing import


def test_unwrap_mesh_uvs_calls_the_right_minic_function(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        mock_run.return_value = ScriptResult(ok=True, stdout="", stderr="")

        result = unwrap_mesh_uvs(project=str(project), output_project=str(output_project))

    assert result["ok"] is True
    assert "plugin_uv_unwrap_button();" in mock_run.call_args[0][2]


def test_unwrap_mesh_uvs_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert "unwrap_mesh_uvs" in by_name, sorted(by_name)
```

- [ ] **Step 4: Run to verify the unit tests fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -k unwrap_mesh_uvs -v`
Expected: FAIL

- [ ] **Step 5: Implement `unwrap_mesh_uvs` in `server.py`**

```python
def unwrap_mesh_uvs(project: str, output_project: str | None = None,
                    in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Re-unwrap the project's mesh UVs via ArmorPaint's own real, built-in
    unwrap algorithm (plugin_uv_unwrap_button -- calls proc_uv_unwrap()
    directly, NOT a loaded plugin despite the C function's name; exposed to
    --script by this project's scoped local patch; see ROADMAP.md's "Patch
    policy"). Confirmed empirically to genuinely change UV coordinates
    (unlike a no-op), unwrap quality/atlas-efficiency vs. xatlas
    (Tool-MeshTriage's unwrapper) has not been compared -- see ROADMAP.md's
    "Known gaps" before relying on this for production-quality UVs.

    Operates on a copy of `project` by default -- pass in_place=True to
    mutate `project` itself instead, in which case output_project must be
    omitted. Requires AP_BINARY to be a build carrying the mesh-edit patch
    (run `ap-mcp --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    return _run_mesh_edit(project, "plugin_uv_unwrap_button();",
                          output_project, in_place, timeout_s)


mcp.tool()(unwrap_mesh_uvs)
```

- [ ] **Step 6: Run to verify the unit tests pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -k unwrap_mesh_uvs -v`
Expected: 2 passed

- [ ] **Step 7: Run the integration test**

Run: `.venv\Scripts\python.exe -m pytest tests/test_unwrap_mesh_uvs_integration.py -v -m integration`
Expected: 1 passed

- [ ] **Step 8: Full unit suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all pass

- [ ] **Step 9: Commit**

```powershell
git add src/armorpaint_mcp/server.py tests/test_unwrap_mesh_uvs_integration.py tests/test_server.py
git commit -m "feat: add unwrap_mesh_uvs"
```

---

## Task 7: Final verification sweep + docs

**Files:**
- Modify: `smoke/smoke.ps1` — add a registration probe per new tool
- Modify: `STATUS.md` — new Phase 5 gate row + detail table
- Modify: `docs/PLAN.md` — new "Phase 5" section
- Modify: `ROADMAP.md` — flip items 1-7's status from 🔬 to ✅
- Modify: `README.md` — tool list

**Interfaces:**
- Consumes: everything from Tasks 1-6 (all 7 tools registered on `mcp`)

- [ ] **Step 1: Read `smoke/smoke.ps1`'s existing tool-registration probe pattern**

Find how it currently checks `run_script registered as an MCP tool` (Phase 4's
probe) and add one matching line per new tool name: `decimate_mesh`,
`bevel_mesh`, `subdivide_mesh`, `smooth_mesh`, `duplicate_mesh`,
`merge_mesh_geometry`, `unwrap_mesh_uvs` — mirror the exact existing probe's
shape (same PowerShell/Python invocation style already used for the other
five tools), don't invent a new probe mechanism.

- [ ] **Step 2: Run the smoke harness**

Run: `pwsh smoke/smoke.ps1`
Expected: FAIL initially if a probe references a tool before this task edits
the script correctly — iterate until all probes pass.

Run again: `pwsh smoke/smoke.ps1`
Expected: 13/13 passed, exit 0 (6 existing probes + 7 new ones)

- [ ] **Step 3: Run the complete verification sweep fresh**

```powershell
Push-Location C:\Projects-local\Tool-ArmorPaintMCP
& .venv\Scripts\python.exe -m pytest -q
& .venv\Scripts\python.exe -m pytest -q -m integration
pwsh smoke\smoke.ps1
Pop-Location
```

Record the exact pass counts from real output (not estimated) for STATUS.md.

- [ ] **Step 4: Update `STATUS.md`**

Add a new row to the Phase Gates table:

```
| 5 | 7 mesh/UV editing tools (decimate/bevel/subdivide/smooth/duplicate/merge/unwrap_mesh_uvs), via a scoped local minic patch (see ROADMAP.md) | ✅ 2026-09-16 | `smoke/smoke.ps1`: 13/13 passed, exit 0. `pytest -q`: <N> passed, 0 failed, <M> deselected. `-m integration`: <K> passed, 0 failed. All 7 tools verified against real geometry via independent script_export_mesh OBJ diffs (not just ok=True) -- see this row's phase detail table below. |
```

(Fill `<N>`/`<M>`/`<K>` with Step 3's real numbers.)

Add a new "Current Phase Detail (Phase 5)" section, one row per tool,
matching the existing per-phase table shape (see Phase 4's table for the
format) -- state `✅`, note what was verified for each (the specific
before/after relationship each integration test proved).

Update `Open phase` at the top from "none" to "none -- Phase 5 was the last
phase in docs/PLAN.md" (matching Phase 4's own closing convention) once
Step 4 lands, or leave it open if Grayson has more phases queued -- check
ROADMAP.md items 8-10 aren't silently implied as "done" by this line.

- [ ] **Step 5: Add the "Phase 5" section to `docs/PLAN.md`**

Follow the exact prose shape of the existing Phase 1-4 sections (scope
paragraph, empirical findings worth recording, then a **Gate:** line with
the real evidence). Pull the "why a scoped patch, why this isn't the
reference project's approach" framing from Amendment 3 rather than
re-explaining it from scratch — link to it.

- [ ] **Step 6: Update `ROADMAP.md`'s status column for items 1-7**

Change each `🔬 proven ... — not yet an MCP tool` line to
`✅ shipped (Phase 5)`.

- [ ] **Step 7: Update `README.md`'s tool list / Status section**

Follow Phase 4's own README update pattern (see git history for that
commit) -- add the 7 new tools to whatever list currently names
`reexport_project`/`create_procedural_material`/`inspect_project`/
`run_script`/`list_available_presets`, and update any "N tools shipped"
count if one exists.

- [ ] **Step 8: Commit**

```powershell
git add smoke/smoke.ps1 STATUS.md docs/PLAN.md ROADMAP.md README.md
git commit -m "docs: close out Phase 5 -- mesh/UV editing tools gate + verification sweep"
```

---

## Self-Review Notes

- **Spec coverage:** ROADMAP.md items 1-7 each have a dedicated tool + task
  (Tasks 2-6, decimate/bevel doubled up in Task 3 for their structural
  twinning, smooth/duplicate doubled up in Task 4 similarly). Item 8
  (mesh replace), item 9 (targeted merge), item 10 (UV validity check) are
  explicitly out of scope per the brainstorming session's own framing and
  are not touched by any task here. The Global Constraints section covers
  ROADMAP.md's "Patch policy" AP_BINARY dependency via Task 1's preflight
  check.
- **Placeholder scan:** every step has real code, real file paths, real
  commands. The one deliberately-approximate spot (Task 1 Step 1's MSBuild
  invocation) is flagged inline as needing the implementer to confirm
  against the spike's own real transcript rather than presented as
  authoritative -- an honest uncertainty, not a placeholder for effort not
  yet spent.
- **Type consistency:** every tool returns the same
  `{"ok": bool, "output_project": str | None, "error": str | None}` shape;
  `_run_mesh_edit`'s signature (`project, minic_call, output_project,
  in_place, timeout_s`) is used identically by every caller from Task 2
  onward. `_finite_float`/`NodeSpecError` (imported once in Task 2) are
  reused verbatim by `bevel_mesh` in Task 3, not redefined.
