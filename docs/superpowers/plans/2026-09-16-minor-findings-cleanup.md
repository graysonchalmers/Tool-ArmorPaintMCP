# Minor-Findings Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 7 Minor findings parked at the end of Phase 3's and Phase 4's
final whole-branch reviews (see `HANDOFF.md`'s "Next concrete step" / "Open
questions"), so nothing sits half-tracked between phase docs and code.

**Architecture:** Not a new phase — `docs/PLAN.md` has no Phase 5, and this
plan does not add one. Five small, independent tasks against existing files
(`runner.py`, `catalog.py`, `server.py`), executed and reviewed one at a time
in an isolated worktree, same convention as every prior phase in this
project.

**Tech Stack:** Python 3.13, pytest, the existing `armorpaint_mcp` package —
no new dependencies.

**Spec:** [docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](../specs/2026-09-15-armorpaint-mcp-design.md);
this cleanup implements no new spec surface, only closes review debt against
the already-shipped v1 tools it describes.

## Global Constraints

- No ArmorPaint source patching, no custom rebuild — nothing here touches
  the ArmorPaint checkout, only this package's own Python.
- Dynamic catalogs, not hardcoded enums — `layer_blend_modes()`'s hardcoded
  18-entry list is an already-documented, deliberate exception (see its own
  docstring); this plan does not touch it and must not add a new
  undocumented hardcode.
- Never mark a gate ✅ in `STATUS.md` without recorded evidence (real
  command output: test counts, exit codes).
- Every tool function's public return-dict *shape* (its key set) must not
  change for any existing caller — only the code that builds that dict may
  be refactored. Every existing test in `tests/test_server.py` and
  `tests/test_catalog.py` must keep passing unmodified except where a task
  below explicitly says a specific test changes.
- Secrets/paths come from env, never hardcoded (unaffected by this plan —
  no new config surface).

---

### Task 1: Harden `runner.run_api`'s stdout decode against non-ASCII names

**Files:**
- Modify: `src/armorpaint_mcp/runner.py:68-72` (the `subprocess.run` call inside `run_api`)
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: no signature change — `run_api(binary, project, timeout_s=DEFAULT_TIMEOUT_S) -> ApiResult` is unchanged.

Phase 3's final review flagged that `run_api`'s `subprocess.run(..., text=True, ...)`
call decodes the child process's stdout using Python's default locale
encoding with strict error handling — a project or material named with a
non-ASCII character that doesn't round-trip cleanly through that encoding
would raise `UnicodeDecodeError` deep inside `subprocess.run`, before this
function's own `try/except subprocess.TimeoutExpired` even has a chance to
turn it into a normal `ApiResult(ok=False, ...)`. Passing `errors="replace"`
degrades a decode hiccup to U+FFFD replacement characters in the offending
spot instead of blowing up the whole call.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_runner.py` (near the other `run_api` tests, e.g. after
`test_run_api_reports_timeout`):

```python
def test_run_api_tolerates_decode_errors_instead_of_raising(tmp_path):
    """A non-ASCII object/material name could round-trip through the OS's
    locale encoding in a way Python's default strict decode doesn't expect.
    errors='replace' means a decode hiccup degrades to U+FFFD replacement
    characters instead of raising UnicodeDecodeError and losing the whole
    --api result (Phase 3 final-review Minor finding)."""
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    project = tmp_path / "project.arm"
    project.write_text("")

    captured = {}

    def fake_run(args, **kwargs):
        captured.update(kwargs)
        return MagicMock(returncode=0, stdout="ok", stderr="")

    with patch("armorpaint_mcp.runner.subprocess.run", side_effect=fake_run):
        run_api(str(binary), str(project))

    assert captured["errors"] == "replace"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runner.py::test_run_api_tolerates_decode_errors_instead_of_raising -v`
Expected: FAIL with `KeyError: 'errors'` (the kwarg isn't passed yet).

- [ ] **Step 3: Add `errors="replace"` to the subprocess.run call**

In `src/armorpaint_mcp/runner.py`, change `run_api`'s `subprocess.run` call
(currently lines 69-72) from:

```python
        proc = subprocess.run(
            [binary, project, "--api"],
            capture_output=True, text=True, timeout=timeout_s,
        )
```

to:

```python
        proc = subprocess.run(
            [binary, project, "--api"],
            capture_output=True, text=True, timeout=timeout_s,
            errors="replace",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runner.py::test_run_api_tolerates_decode_errors_instead_of_raising -v`
Expected: PASS

- [ ] **Step 5: Run the full unit suite to confirm no regression**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all previously-passing tests still pass, plus this new one (one more than the prior total).

- [ ] **Step 6: Commit**

```bash
git add src/armorpaint_mcp/runner.py tests/test_runner.py
git commit -m "fix: harden run_api's stdout decode against non-ASCII names"
```

---

### Task 2: Fix `catalog.scene_objects`'s error convention to match its siblings

**Files:**
- Modify: `src/armorpaint_mcp/catalog.py` (the `scene_objects` function, currently lines 94-109)
- Modify: `src/armorpaint_mcp/server.py` (`inspect_project`, currently lines 139-194)
- Test: `tests/test_catalog.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `catalog.CatalogError` (already exists, defined in `catalog.py`).
- Produces: `scene_objects(api_text: str) -> list[dict]` keeps its signature
  and success behavior, but now **raises `CatalogError`** if the
  `"Scene objects in world space"` section marker is entirely absent from
  `api_text` (previously it silently returned `[]` for that case, the same
  as a section that's genuinely present-but-empty — the finding this task
  closes). It still returns `[]` when the marker IS present but no object
  lines follow it (a real empty scene is valid data, not a malformed read).

`extract_project_state` and `blend_modes` both raise `CatalogError` when
their own anchor text is missing from `api_text` — that's the "siblings"
convention `scene_objects` currently doesn't follow. Today it just
regex-searches the whole text for object-line patterns with no check that
the section itself exists, so a genuinely malformed/unexpected `--api`
output shape (no "Scene objects in world space" section at all) silently
reports `objects: []` instead of surfacing an error the way a missing
project-state block or a missing MIX_RGB enum already does.

`inspect_project` currently calls `scene_objects(result.text)` **unguarded**,
after the block that already catches `CatalogError` from
`extract_project_state`. Once `scene_objects` can raise, that call must move
inside the same `try/except CatalogError` block — otherwise a malformed
`--api` output would make `inspect_project` raise instead of returning its
usual `{"ok": False, ..., "error": str}` shape, breaking the tool's contract
that every failure is a returned dict, never an exception.

- [ ] **Step 1: Write the failing tests**

In `tests/test_catalog.py`, replace the existing
`test_scene_objects_empty_list_when_no_objects_section` test (delete it) with
these two:

```python
def test_scene_objects_raises_when_marker_missing():
    with pytest.raises(CatalogError, match="Scene objects in world space"):
        scene_objects("nothing here")


def test_scene_objects_empty_list_when_section_present_but_no_objects():
    text = (
        "Scene objects in world space, z axis up:\n"
        "\n"
        "script_shape_add() shapes:\n"
        '"cone"\n'
    )
    assert scene_objects(text) == []
```

In `tests/test_server.py`, add (near
`test_inspect_project_surfaces_catalog_parse_error`):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_catalog.py tests/test_server.py -v -k "scene_objects"`
Expected: `test_scene_objects_raises_when_marker_missing` FAILs (no exception
raised yet); `test_inspect_project_surfaces_scene_objects_parse_error` FAILs
(the mocked `CatalogError` from `scene_objects` currently propagates
uncaught out of `inspect_project`, so pytest reports an error, not the
expected returned dict).

- [ ] **Step 3: Fix `scene_objects` in `catalog.py`**

Replace the current `scene_objects` function (lines 94-109) with:

```python
_SCENE_OBJECTS_MARKER = "Scene objects in world space"


def scene_objects(api_text: str) -> list[dict]:
    """Every object in the 'Scene objects in world space' section: name,
    location, and size, already in world space (no matrix decoding needed --
    unlike mesh_transforms in the JSON state block, which is column-major
    4x4 and not worth parsing when this text section already has the
    answer).

    Raises CatalogError if the section marker itself is missing from
    api_text -- consistent with extract_project_state's and blend_modes()'s
    CatalogError convention for a missing anchor. Returns [] when the
    marker IS present but no object lines follow it: a genuinely empty
    scene is valid data, not a malformed read, and must not be confused
    with the marker being absent entirely."""
    if _SCENE_OBJECTS_MARKER not in api_text:
        raise CatalogError(
            "'--api' output has no 'Scene objects in world space' section -- "
            "was a project path passed to ArmorPaint.exe, not just --api?")
    pattern = re.compile(
        r'"([^"]+)": location \(([^)]+)\), size \(([^)]+)\)')
    return [
        {
            "name": name,
            "location": [float(v) for v in loc.split(", ")],
            "size": [float(v) for v in size.split(", ")],
        }
        for name, loc, size in pattern.findall(api_text)
    ]
```

- [ ] **Step 4: Move the `scene_objects` call inside `inspect_project`'s existing `try/except CatalogError` block**

In `src/armorpaint_mcp/server.py`, `inspect_project` currently has (lines
168-191):

```python
    try:
        state = extract_project_state(result.text)
    except CatalogError as exc:
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": str(exc)}

    modes = layer_blend_modes()
    materials = [
        {"name": m.get("name"), "node_count": len(m.get("nodes") or [])}
        for m in (state.get("material_nodes") or [])
    ]
    layers = [
        {
            "name": layer.get("name"),
            "resolution": layer.get("res"),
            "visible": layer.get("visible"),
            "blending": modes[layer["blending"]]
                        if isinstance(layer.get("blending"), int)
                        and 0 <= layer["blending"] < len(modes) else None,
        }
        for layer in (state.get("layer_datas") or [])
    ]
    return {"ok": True, "objects": scene_objects(result.text),
            "materials": materials, "layers": layers, "error": None}
```

Change it to fetch `objects` inside the guarded block, alongside `state`:

```python
    try:
        state = extract_project_state(result.text)
        objects = scene_objects(result.text)
    except CatalogError as exc:
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": str(exc)}

    modes = layer_blend_modes()
    materials = [
        {"name": m.get("name"), "node_count": len(m.get("nodes") or [])}
        for m in (state.get("material_nodes") or [])
    ]
    layers = [
        {
            "name": layer.get("name"),
            "resolution": layer.get("res"),
            "visible": layer.get("visible"),
            "blending": modes[layer["blending"]]
                        if isinstance(layer.get("blending"), int)
                        and 0 <= layer["blending"] < len(modes) else None,
        }
        for layer in (state.get("layer_datas") or [])
    ]
    return {"ok": True, "objects": objects,
            "materials": materials, "layers": layers, "error": None}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_catalog.py tests/test_server.py -v -k "scene_objects"`
Expected: both new/changed tests PASS.

- [ ] **Step 6: Run the full unit suite to confirm no regression**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all pass (one test removed, three added — net +2 from Task 1's baseline).

- [ ] **Step 7: Commit**

```bash
git add src/armorpaint_mcp/catalog.py src/armorpaint_mcp/server.py tests/test_catalog.py tests/test_server.py
git commit -m "fix: make scene_objects raise CatalogError on a missing section marker"
```

---

### Task 3: Shared helpers in `server.py` for the repeated failure-dict literal and the duplicated `.arm`-file guard

**Files:**
- Modify: `src/armorpaint_mcp/server.py` (all four tool functions)

**Interfaces:**
- Consumes: nothing new.
- Produces: two new private module-level helpers in `server.py`:
  - `_failure(error: str, *null_fields: str) -> dict` — returns
    `{"ok": False, "error": error, **{f: None for f in null_fields}}`.
  - `_is_arm_project_file(path: str) -> bool` — returns
    `os.path.isfile(path) and path.lower().endswith(".arm")`.
  Both are internal refactor helpers; no tool's public signature or return
  *shape* changes. Dict key **order** may change at some call sites, which
  is safe: every existing test compares these dicts with `==`, and Python
  dict equality ignores key order.

Every tool function currently repeats its own version of the same
early-exit failure-dict literal (`reexport_project` and
`create_procedural_material` each null out `"files"` at 2-4 call sites;
`inspect_project` nulls out `"objects"`, `"materials"`, `"layers"` at 4 call
sites; `run_script` nulls out `"stdout"`, `"stderr"` at 2 call sites) — a
pattern flagged by both Phase 3's and Phase 4's final reviews. `inspect_project`
and `run_script` also each hand-roll the identical
"does this path exist and end in `.arm`" phantom-default-project guard. This
task extracts one shared helper for each, mechanically, with no behavior
change.

- [ ] **Step 1: Add the two helpers**

In `src/armorpaint_mcp/server.py`, add immediately after `_ensure_ready`
(after line 34, before `def reexport_project`):

```python
def _failure(error: str, *null_fields: str) -> dict:
    """The common shape of every tool's early-exit failure: ok=False, the
    error message, and every OTHER field the tool's success shape declares
    explicitly nulled out (never omitted -- callers pattern-match on a
    stable key set regardless of which branch returned)."""
    return {"ok": False, "error": error, **{f: None for f in null_fields}}


def _is_arm_project_file(path: str) -> bool:
    """True only for an existing, real .arm file on disk. ArmorPaint
    silently ignores a bogus --script/project positional argument and opens
    its own empty default project instead of failing -- both
    inspect_project and run_script must reject a bad path themselves before
    launching ArmorPaint, or a typo'd path would report ok:True against
    that phantom default project's data instead of an error."""
    return os.path.isfile(path) and path.lower().endswith(".arm")
```

- [ ] **Step 2: Run the full unit suite to confirm it's still green before refactoring call sites**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: unchanged pass count from Task 2 (the helpers aren't used yet, so nothing can break).

- [ ] **Step 3: Refactor `reexport_project`**

Change (currently lines 51-60):

```python
    available = list_export_presets(cfg.binary)
    if preset not in available:
        return {"ok": False, "files": None,
                "error": f"unknown preset '{preset}'; available: {', '.join(available)}"}

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
        output_dir = ensure_within_roots(output_dir, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return {"ok": False, "files": None, "error": str(exc)}
```

to:

```python
    available = list_export_presets(cfg.binary)
    if preset not in available:
        return _failure(
            f"unknown preset '{preset}'; available: {', '.join(available)}", "files")

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
        output_dir = ensure_within_roots(output_dir, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "files")
```

- [ ] **Step 4: Refactor `create_procedural_material`**

Change (currently lines 90-116):

```python
    available = list_export_presets(cfg.binary)
    if preset not in available:
        return {"ok": False, "files": None,
                "error": f"unknown preset '{preset}'; available: {', '.join(available)}"}

    if preset != "generic":
        return {"ok": False, "files": None,
                "error": (f"create_procedural_material only supports the 'generic' "
                          f"preset: the single-process script flow calls "
                          f"export_texture_run(), which has no preset argument and "
                          f"no minic setter exists for it -- it always exports "
                          f"whatever preset last configured the export box, which "
                          f"in this headless flow is always ArmorPaint's own "
                          f"'generic' fallback. Requesting '{preset}' would either "
                          f"time out waiting for files that never arrive, or (for "
                          f"a preset whose files are a strict subset of generic's) "
                          f"silently report success for the wrong export.")}

    try:
        output_dir = ensure_within_roots(output_dir, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return {"ok": False, "files": None, "error": str(exc)}

    try:
        script_text = generate_script(node_spec, output_dir)
    except NodeSpecError as exc:
        return {"ok": False, "files": None, "error": str(exc)}
```

to:

```python
    available = list_export_presets(cfg.binary)
    if preset not in available:
        return _failure(
            f"unknown preset '{preset}'; available: {', '.join(available)}", "files")

    if preset != "generic":
        return _failure(
            (f"create_procedural_material only supports the 'generic' "
             f"preset: the single-process script flow calls "
             f"export_texture_run(), which has no preset argument and "
             f"no minic setter exists for it -- it always exports "
             f"whatever preset last configured the export box, which "
             f"in this headless flow is always ArmorPaint's own "
             f"'generic' fallback. Requesting '{preset}' would either "
             f"time out waiting for files that never arrive, or (for "
             f"a preset whose files are a strict subset of generic's) "
             f"silently report success for the wrong export."), "files")

    try:
        output_dir = ensure_within_roots(output_dir, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "files")

    try:
        script_text = generate_script(node_spec, output_dir)
    except NodeSpecError as exc:
        return _failure(str(exc), "files")
```

- [ ] **Step 5: Refactor `inspect_project`**

Change (currently lines 146-172, after Task 2's edit already merged the
`objects` fetch into the state try/except):

```python
    cfg = _ensure_ready()

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": str(exc)}

    # ArmorPaint silently ignores a bogus --script/project argument and opens
    # its own default empty project instead of failing -- without this check,
    # a typo'd or nonexistent path would report ok:True with that phantom
    # default project's data, which is worse than an error for a read-only
    # reporting tool.
    if not os.path.isfile(project) or not project.lower().endswith(".arm"):
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": f"'{project}' is not an existing .arm project file"}

    result = run_api(cfg.binary, project)
    if not result.ok:
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": result.error}

    try:
        state = extract_project_state(result.text)
        objects = scene_objects(result.text)
    except CatalogError as exc:
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": str(exc)}
```

to:

```python
    cfg = _ensure_ready()

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "objects", "materials", "layers")

    # ArmorPaint silently ignores a bogus --script/project argument and opens
    # its own default empty project instead of failing -- without this check,
    # a typo'd or nonexistent path would report ok:True with that phantom
    # default project's data, which is worse than an error for a read-only
    # reporting tool.
    if not _is_arm_project_file(project):
        return _failure(f"'{project}' is not an existing .arm project file",
                        "objects", "materials", "layers")

    result = run_api(cfg.binary, project)
    if not result.ok:
        return _failure(result.error, "objects", "materials", "layers")

    try:
        state = extract_project_state(result.text)
        objects = scene_objects(result.text)
    except CatalogError as exc:
        return _failure(str(exc), "objects", "materials", "layers")
```

- [ ] **Step 6: Refactor `run_script`**

Change (currently lines 240-254):

```python
    cfg = _ensure_ready()

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return {"ok": False, "stdout": None, "stderr": None, "error": str(exc)}

    # Same phantom-default-project trap inspect_project guards against
    # (Phase 3 Finding 2): a bogus/nonexistent project path makes ArmorPaint
    # silently open its own empty default project instead of failing, which
    # would let the caller's script run against nothing while still
    # reporting ok: True.
    if not os.path.isfile(project) or not project.lower().endswith(".arm"):
        return {"ok": False, "stdout": None, "stderr": None,
                "error": f"'{project}' is not an existing .arm project file"}
```

to:

```python
    cfg = _ensure_ready()

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "stdout", "stderr")

    # Same phantom-default-project trap inspect_project guards against
    # (Phase 3 Finding 2): a bogus/nonexistent project path makes ArmorPaint
    # silently open its own empty default project instead of failing, which
    # would let the caller's script run against nothing while still
    # reporting ok: True.
    if not _is_arm_project_file(project):
        return _failure(f"'{project}' is not an existing .arm project file",
                        "stdout", "stderr")
```

- [ ] **Step 7: Run the full unit suite to confirm no regression**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: identical pass count to Step 2 (Task 2's final count) — every
existing test's `assert result == {...}` still holds, since dict equality
ignores key order and no error string changed.

- [ ] **Step 8: Commit**

```bash
git add src/armorpaint_mcp/server.py
git commit -m "refactor: extract shared _failure/_is_arm_project_file helpers in server.py"
```

---

### Task 4: Real-binary integration test for `run_script`'s timeout path

**Files:**
- Test: `tests/test_run_script_integration.py`

**Interfaces:**
- Consumes: `server.run_script(project, script, timeout_s=DEFAULT_TIMEOUT_S) -> dict` (unchanged).
- Produces: nothing new — test-only addition.

Only a mocked `subprocess.TimeoutExpired` exists today
(`tests/test_runner.py::test_run_minic_script_reports_timeout`), which
proves the exception-handling code path works but not that a *real*
ArmorPaint process launch actually respects `timeout_s` end-to-end. This
adds a real-binary test using a `timeout_s` far too short for ArmorPaint to
even finish starting, forcing a genuine `subprocess.TimeoutExpired`.

- [ ] **Step 1: Add the test**

Append to `tests/test_run_script_integration.py`:

```python
@pytest.mark.integration
def test_run_script_reports_a_real_timeout():
    """Real-binary timeout path (Phase 4 final-review Minor finding: only a
    mocked TimeoutExpired existed for this before). timeout_s=0.01 is far
    too short for the real ArmorPaint.exe process to even finish starting,
    forcing subprocess.run's actual TimeoutExpired rather than a mocked
    one."""
    result = run_script(project=FIXTURE, script="void main() {}", timeout_s=0.01)

    assert result["ok"] is False
    assert "timed out after 0.01s" in result["error"]
```

- [ ] **Step 2: Run it against the real binary to verify it passes**

Run (needs `AP_BINARY` set to a working ArmorPaint build, see `.env.example`):
`.venv\Scripts\python.exe -m pytest tests/test_run_script_integration.py -v -m integration`
Expected: 3 passed (the 2 existing tests in this file plus this new one).

- [ ] **Step 3: Run the full integration suite to confirm no regression**

Run: `.venv\Scripts\python.exe -m pytest -q -m integration`
Expected: 7 passed, 0 failed (6 from Phase 4's last recorded count + this one).

- [ ] **Step 4: Commit**

```bash
git add tests/test_run_script_integration.py
git commit -m "test: add a real-binary integration test for run_script's timeout path"
```

---

### Task 5: Documentation closeout — Deviations entry, moot-finding closure, final verification sweep

**Files:**
- Modify: `STATUS.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing (documentation only) — this is the plan's final
  verification task, matching every prior phase's last-task convention.

Two of the seven original findings turn out to need no code once actually
checked against current state (do the checking for real, don't just take
this plan's word for it):

- The "`blend_modes()` parse failure aborts `inspect_project`'s whole read"
  finding predates Phase 3's own Critical-finding fix: `inspect_project`
  today calls `layer_blend_modes()` (a hardcoded list, takes no input, can
  never raise), not the text-parsing `blend_modes()`. Confirm this with
  `grep -n "blend_modes" src/armorpaint_mcp/server.py` — it should show only
  `layer_blend_modes` imported and used, never bare `blend_modes`. The
  out-of-range-index case that function's caller WOULD need to guard is
  already handled: the `layers` list comprehension in `inspect_project`
  already degrades an out-of-range `blending` index to `None` rather than
  raising. Nothing to fix.
- The "timeout discards partial output" concern is moot because
  `run_script`'s own docstring (and Phase 4's final review) already
  documents `stdout`/`stderr` as structurally empty on this Windows build
  regardless of timeout (`WriteConsoleW`, not pipe-capturable) — there is no
  partial output a timeout could discard in the first place.

The one finding that's genuinely a documentation gap (not code, not moot) is
the `run_script(project, script_path)` → `run_script(project, script)` spec
deviation: `docs/PLAN.md`'s Phase 4 sketch and the design spec's Components
table both originally named the parameter `script_path` (implying the
caller supplies a path to their own script file); the shipped tool instead
takes `script` as inline minic source text, which the server itself writes
to a temp file and cleans up. This was never logged in `STATUS.md`'s
Deviations table.

- [ ] **Step 1: Confirm the two moot findings for real**

Run: `grep -n "blend_modes" src/armorpaint_mcp/server.py`
Expected output: only lines mentioning `layer_blend_modes`, never a bare
`blend_modes` import or call. If a bare `blend_modes` call turns up instead,
STOP — that finding is not moot, and this task must be replaced with an
actual code fix (degrade to `blending: None` on `CatalogError` instead of
aborting the whole `inspect_project` read) before continuing.

- [ ] **Step 2: Add the Deviations table entry**

In `STATUS.md`, append a new row to the "Deviations from Plan" table (after
the existing 2026-09-16 row):

```markdown
| 2026-09-16 | `run_script(project, script)` takes inline minic source text as `script`, not a `script_path` naming a caller-supplied file, as `docs/PLAN.md`'s Phase 4 sketch and the design spec's Components table (`run_script(project, script_path)`) originally described. | An MCP tool caller composes script text conversationally; requiring it to first write that text to a file it can prove is reachable (and separately sandboxed, since `AP_ALLOWED_ROOTS` only bounds `project`) is a worse interface than accepting the text directly. The server owns the temp file's full lifecycle itself (write, pass to `--script`, delete in a `finally` block), so nothing is left behind regardless of outcome. |
```

- [ ] **Step 3: Add the two closed-as-moot findings to Known Issues**

In `STATUS.md`, append two new rows to the "Known Issues" table (after the
existing row #1), using its established strikethrough-and-bold-resolution
format:

```markdown
| 2 | ~~`blend_modes()`'s `CatalogError` (missing MIX_RGB anchor) could abort `inspect_project`'s entire read when only a blending label needed to degrade~~ -- **INVESTIGATED, MOOT (2026-09-16).** Confirmed via `grep`: `inspect_project` never calls `blend_modes()` -- Phase 3's Critical-finding fix already replaced it with the hardcoded `layer_blend_modes()` (see `catalog.py`'s own docstring on the enum mismatch), which takes no input and cannot raise. The out-of-range-index case it would have needed to guard is already handled: the `layers` list comprehension already degrades an out-of-range index to `blending: None`. | None -- finding predates the enum-mismatch fix and no longer describes reachable code. | Closed. No code change. |
| 3 | ~~`run_script`'s "timeout discards partial output" concern~~ -- **MOOT (2026-09-16).** `stdout`/`stderr` are already documented (Phase 4 final review) as structurally empty on this Windows build regardless of timeout (`WriteConsoleW`, not pipe-capturable) -- there is no partial output a timeout could discard. | None -- superseded by the stdout/stderr finding it was originally paired with. | Closed. No code change. |
```

- [ ] **Step 4: Update `STATUS.md`'s header line**

Change the `Last updated:` line at the top of `STATUS.md` from
`2026-09-16` (it already says today's date, so just confirm it's current --
no edit needed unless the date has rolled over since Phase 4's session).

- [ ] **Step 5: Run the full fresh verification sweep**

Run each of these and record the real output in this task's commit message
(not paraphrased -- copy the actual counts):

```bash
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pytest -q -m integration
pwsh smoke\smoke.ps1
```

Expected: unit suite passes with the cumulative count from Tasks 1-3 (started
at 88 passed/6 deselected; +1 Task 1, +2 net Task 2, +0 Task 3 = 91 passed, 0
failed, 6 deselected -- confirm the real number, don't assume this
arithmetic is exact); integration suite passes with 7 passed, 0 failed
(Task 4's addition); smoke passes 6/6, exit 0 (unchanged -- this plan adds
no new MCP tool, so no new smoke probe is needed).

- [ ] **Step 6: Commit**

```bash
git add STATUS.md
git commit -m "docs: close out Minor-findings cleanup -- Deviations entry, 2 moot findings, verification sweep"
```

---

## Self-Review Notes (for the plan author, not a task)

- **Spec coverage:** all 7 original findings from `HANDOFF.md`'s "Next
  concrete step" are covered: item 1 → Task 1; item 2 → Task 5 (moot,
  investigated not assumed); item 3 → Task 2; item 4 → Task 5 (Deviations
  entry); item 5 → Task 4; item 6 → Task 5 (moot); items 7+8 → Task 3.
- **No placeholders:** every step above has real, copy-pasteable code or an
  exact command with an expected result — no "add appropriate tests" or
  "similar to Task N" placeholders.
- **Type/name consistency:** `_failure` and `_is_arm_project_file` (Task 3)
  are used with identical names and signatures in Tasks 3's own steps for
  `reexport_project`, `create_procedural_material`, `inspect_project`, and
  `run_script`. Task 2's `objects` variable name matches what Task 3's
  Step 5 references when it re-shows the same `try/except` block.
