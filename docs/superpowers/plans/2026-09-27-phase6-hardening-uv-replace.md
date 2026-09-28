# Phase 6 — Hardening, UV Check, Mesh Replace — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every ArmorPaint script call fail loudly instead of returning a false `ok=True`, fix two shipped bugs, and add two tools: `check_mesh_uvs` (read-only UV validity report) and `replace_mesh` (swap one object's mesh while keeping layers, other objects, name, transform, parent, children and material).

**Architecture:** All ArmorPaint work stays subprocess-per-call through `runner.run_minic_script` / `runner.run_api`. Saving tools open the caller's original `.arm` directly (never writing it), save to a fresh sibling file in the target's directory as the script's last statement, verify, then `os.replace` onto the target. A new pure-stdlib `uv_analysis` module (ported from spike S3's prototype) rasterizes UV layouts for both new tools. A new `replace` module holds `replace_mesh`'s pure-Python pieces (pre-checks, minic script builder, `--api` state lookups).

**Tech Stack:** Python 3.13 stdlib only (numpy is NOT installed; add no dependencies), pytest, the MCP Python SDK already in use (`mcp.server.mcpserver.MCPServer`), ArmorPaint `AP_BINARY` built from `287e63f4` (has `WITH_PLUGINS` and pipe-capturable stdout).

**Spec:** `docs/PLAN.md` → "Phase 6 (APPROVED 2026-09-27)" → "Decisions applied" and the "Phase 6 gate". Spike evidence: `docs/superpowers/spikes/2026-09-27-phase6-spikes-S1-S2-S4-S5.md` and `docs/superpowers/spikes/2026-09-27-phase6-spike-S3.md`. Prototypes: `docs/superpowers/spikes/prototypes/`. Fixtures: `tests/fixtures/phase6/` (read its `README.md`).

## Global Constraints

- **Worktree:** all work happens in `C:\Projects-local\Tool-ArmorPaintMCP\.claude\worktrees\phase6` on branch `claude/phase6`. Never edit `C:\Projects-local\Tool-ArmorPaintMCP` (main) directly.
- **Python/env for every command** (PowerShell; the venv lives in main, the code under test in the worktree):
  ```powershell
  Push-Location C:\Projects-local\Tool-ArmorPaintMCP\.claude\worktrees\phase6; $env:PYTHONPATH = "$PWD\src"; $env:AP_DOTENV = 'C:\Projects-local\Tool-ArmorPaintMCP\.env'; $py = 'C:\Projects-local\Tool-ArmorPaintMCP\.venv\Scripts\python.exe'
  ```
  Before trusting any test run, confirm `& $py -c "import armorpaint_mcp; print(armorpaint_mcp.__file__)"` prints a path inside the worktree. Unit tests: `& $py -m pytest -q`. Integration: `& $py -m pytest -q -m integration <file>`. Smoke: `pwsh smoke/smoke.ps1` (run with the same `PYTHONPATH`). Never print `.env`.
- **ArmorPaint:** drive `ArmorPaint.exe` only through PowerShell or a Python subprocess (the project's own runner). NEVER through the Bash tool: it silently no-ops the binary. One ArmorPaint process at a time: never run integration tests in parallel (no `-n`, no two shells).
- **Flaky launches:** the machine is under memory pressure. If an integration test fails with exit code `3221225477` (0xC0000005) or a timeout on the *first* ArmorPaint call of the run, rerun that test once. If it fails again, report it. Retries belong in how you run tests, never in production code.
- **Do not touch** `C:\Projects-local\z-Git\ArmorPaint` (read-only source reference; ArmorPaint citations below are relative to its `paint/sources/` unless they start with `base/`).
- **Failure shape:** every tool returns `{"ok": False, "error": str, <every other declared field>: None}` via `server._failure(...)` on any failure. Never raise out of a tool.
- **No hardcoded magic numbers** except the ones this plan names with a citation (layer blend modes already; now `REPLACEMENT_FORMATS` and the UV-gate thresholds).
- **Commits:** one per task minimum, message prefix `feat:`/`fix:`/`test:`/`docs:`, ending with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. PowerShell 5.1 syntax (`;` not `&&`) in anything handed to Grayson.
- **Minic facts this plan relies on (all spike-verified):** script errors print `<script>:N: error: …` lines (stdout or stderr) while the process still exits 0; `project_save(0)` must be the script's LAST statement (an error after it still leaves the file); `script_append_mesh` needs a backslash path with each backslash doubled in the literal (forward slashes silently no-op); `project_filepath_set`/`script_export_mesh` accept forward slashes; minic string literals are not escaped by us, so a `"` (or, in names, a `\`) is rejected, never escaped.

## Review Focus

1. **A path with spaces or non-ASCII characters** (e.g. `C:\Users\Ø\Program Files (x86)\p.arm`): a reasonable person expects either a correct result or a clean `ok=False`, never `ok=True` without a verified output file. Pinned by Task 3's unicode/space-path unit test and the fresh-file verification (a false success is impossible when success requires the file).
2. **An object or material name containing `"` or `\`**: expect a clean `ok=False` before ArmorPaint launches, not a broken minic literal. Pinned in Task 7 (`minic_string_literal` tests) and Task 8 (tool-level test).
3. **A leftover `*.ap-mcp-*.tmp.arm` from a crashed earlier run in the target directory**: expect the new run to succeed and leave the stranger file alone. Pinned in Task 3.
4. **`output_project` in a directory that doesn't exist yet**: expect it to be created. Pinned in Task 3 (mesh edits) and Task 10 (replace).
5. **ArmorPaint crashes or times out after writing a complete fresh file**: expect `ok=False` and the fresh file removed (the spike saw exactly this hang). Pinned in Task 3's timeout-after-write unit test.

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `src/armorpaint_mcp/runner.py` | subprocess wrappers; now also script-error detection | 1 |
| `src/armorpaint_mcp/catalog.py` | `--api` parsing; backslash fix; minic name registry | 2, 4, 7 |
| `src/armorpaint_mcp/script_gen.py` | minic literal helpers (`minic_string_literal`, `minic_path_literal`) | 3 |
| `src/armorpaint_mcp/server.py` | tools; shared save/verify plumbing; `check_mesh_uvs`; `replace_mesh` | 3, 6, 8, 9 |
| `src/armorpaint_mcp/doctor.py` | `--check` "minic API" row | 4 |
| `src/armorpaint_mcp/uv_analysis.py` (new) | OBJ parse, UV raster, metrics, verdict, layout comparison | 5 |
| `src/armorpaint_mcp/replace.py` (new) | replace pre-checks, script builder, state lookups | 7 |
| `tests/test_runner.py`, `test_catalog.py`, `test_doctor.py`, `test_server.py` | unit tests (mocked ArmorPaint) | 1-9 |
| `tests/test_uv_analysis.py` (new), `tests/test_replace.py` (new) | pure-Python unit tests | 5, 7 |
| `tests/test_phase6_hardening_integration.py` (new) | real-ArmorPaint tests for Tasks 1-3 | 1-3 |
| `tests/test_check_mesh_uvs_integration.py` (new) | real-ArmorPaint | 6 |
| `tests/test_replace_mesh_integration.py` (new) | real-ArmorPaint | 8-10 |
| `scripts/calibrate_uv_gate.py` (new) | re-runnable real-ArmorPaint IoU/retention table | 10 |
| `smoke/smoke.ps1`, `README.md`, `STATUS.md`, `docs/PLAN.md`, `ROADMAP.md` | probes, docs, gate record | 11 |

---

### Task 1: Detect script errors from ArmorPaint's output

**Files:**
- Modify: `src/armorpaint_mcp/runner.py` (imports; `run_minic_script` at lines 93-143)
- Modify: `src/armorpaint_mcp/server.py` (`run_script` docstring, lines 515-557; `_run_mesh_edit` docstring lines 58-71)
- Test: `tests/test_runner.py`, `tests/test_phase6_hardening_integration.py` (new)

**Interfaces:**
- Produces: `runner.script_error_lines(*streams: str) -> list[str]`; `run_minic_script(...)` now returns `ScriptResult(ok=False, stdout=..., stderr=..., error="script error: <lines joined by '; '>")` when either stream contains an error line, even on exit code 0.

- [ ] **Step 1: Write the failing unit tests** (append to `tests/test_runner.py`; it already imports `patch`, `MagicMock`, `run_minic_script`)

```python
from armorpaint_mcp.runner import script_error_lines


def test_script_error_lines_finds_minic_errors_in_any_stream():
    out = "SPIKE_MARKER\n<script>:2: error: unknown function 'nope' (got '(')\n"
    err = "<script>:3: error: null pointer access on 'object_t->name' (got ';')\n"
    assert script_error_lines(out, err) == [
        "<script>:2: error: unknown function 'nope' (got '(')",
        "<script>:3: error: null pointer access on 'object_t->name' (got ';')",
    ]


def test_script_error_lines_ignores_ordinary_output():
    assert script_error_lines("Project saved\nerror: not at line start? no\n", "") == []


def test_run_minic_script_fails_on_a_script_error_despite_exit_0(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    project = tmp_path / "project.arm"
    project.write_text("")
    line = "<script>:2: error: unknown function 'this_is_undefined_q' (got '(')"

    with patch("armorpaint_mcp.runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=line + "\n", stderr="")
        result = run_minic_script(str(binary), str(project), "void main() {}")

    assert result.ok is False
    assert result.error == f"script error: {line}"
    assert result.stdout == line + "\n"


def test_run_minic_script_decodes_undecodable_output_without_raising(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    project = tmp_path / "project.arm"
    project.write_text("")

    with patch("armorpaint_mcp.runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_minic_script(str(binary), str(project), "void main() {}")

    assert mock_run.call_args.kwargs.get("errors") == "replace"
```

- [ ] **Step 2: Run to verify they fail**

Run: `& $py -m pytest -q tests/test_runner.py -k "script_error or undecodable"`
Expected: FAIL (`ImportError: cannot import name 'script_error_lines'`).

- [ ] **Step 3: Implement** in `runner.py`. Add `import re` to the imports, then above `run_minic_script`:

```python
# minic reports a runtime/compile error as "<script>:<line>: error: <msg>" and
# then carries on (an error only unwinds its own frame) -- the process still
# exits 0. Since upstream 3b77ab8c (2026-09-17) iron_log writes to a pipe via
# WriteFile, so these lines reach subprocess capture: INFO on stdout, errors
# possibly on stderr (base/sources/iron_system.c:44-54). Phase 6 spike S2.
_SCRIPT_ERROR_RE = re.compile(r"^<script>:\d+: error: .*$", re.MULTILINE)


def script_error_lines(*streams: str) -> list[str]:
    """Every minic error line in `streams`, in order."""
    return [m.group(0).rstrip("\r") for s in streams if s
            for m in _SCRIPT_ERROR_RE.finditer(s)]
```

In `run_minic_script`, add `errors="replace",` to the `subprocess.run(...)` keyword arguments, and replace the final `return ScriptResult(ok=True, ...)` with:

```python
    errors = script_error_lines(proc.stdout, proc.stderr)
    if errors:
        return ScriptResult(ok=False, stdout=proc.stdout, stderr=proc.stderr,
                            error="script error: " + "; ".join(errors))
    return ScriptResult(ok=True, stdout=proc.stdout, stderr=proc.stderr)
```

Replace the `IMPORTANT:` paragraph of `run_minic_script`'s docstring with:

```
    A minic script error (unknown function, missing struct field, null
    pointer, syntax error) does NOT change the exit code, but it does print
    "<script>:N: error: ..." -- this function turns any such line (stdout or
    stderr) into ok=False. ok=True therefore means "the process exited 0 and
    printed no script error", which still isn't proof the script did what
    its author wanted (an early `return` prints nothing): tools that save
    also verify their output file exists (see server._run_saving_script).
```

- [ ] **Step 4: Update the `server.py` docstrings.** In `run_script`'s docstring replace the `IMPORTANT:` paragraph and the `NOTE:` paragraph with:

```
    A minic script error (unknown function, bad field, null pointer, syntax
    error) returns ok=False with the "<script>:N: error: ..." line(s) in
    `error` -- the process itself exits 0 either way. ok=True means the
    process finished and printed no script error; it is still not proof the
    script did what you meant (a script that returns early prints nothing),
    so verify results yourself (e.g. call inspect_project afterward). The
    `project` path is bounded by AP_ALLOWED_ROOTS when set; the script body
    itself is not sandboxed and can read/write anywhere the ArmorPaint
    process has OS-level permission to.

    `stdout`/`stderr` carry the script's console_log()/printf output and
    ArmorPaint's own messages (e.g. "Project saved").
```

- [ ] **Step 5: Run unit tests**

Run: `& $py -m pytest -q`
Expected: all pass (122 + 4 new).

- [ ] **Step 6: Write the real-ArmorPaint test** — create `tests/test_phase6_hardening_integration.py`:

```python
"""Real ArmorPaint required. Phase 6.1 hardening (docs/PLAN.md).
Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_phase6_hardening_integration.py -v -m integration
"""
import os

import pytest

from armorpaint_mcp.server import run_script

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE = os.path.join(FIXTURES, "sample_project.arm")


@pytest.mark.integration
def test_run_script_reports_an_undefined_minic_call_as_a_failure():
    result = run_script(project=SAMPLE,
                        script="void main() {\n\tthis_is_undefined_q();\n}\n")

    assert result["ok"] is False
    assert "unknown function 'this_is_undefined_q'" in result["error"]


@pytest.mark.integration
def test_run_script_still_succeeds_for_a_clean_script():
    result = run_script(project=SAMPLE,
                        script='void main() {\n\tconsole_log("PHASE6_OK");\n}\n')

    assert result["error"] is None
    assert result["ok"] is True
    assert "PHASE6_OK" in result["stdout"]
```

- [ ] **Step 7: Run it**

Run: `& $py -m pytest -q -m integration tests/test_phase6_hardening_integration.py`
Expected: 2 passed.

- [ ] **Step 8: Commit**

```powershell
git add src/armorpaint_mcp/runner.py src/armorpaint_mcp/server.py tests/test_runner.py tests/test_phase6_hardening_integration.py; git commit -m "fix: treat minic script error lines as failures (stdout is capturable since 3b77ab8c)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `inspect_project` survives backslash paths (Known Issue #10)

**Files:**
- Modify: `src/armorpaint_mcp/catalog.py:25-44` (`extract_project_state`)
- Test: `tests/test_catalog.py`, `tests/test_phase6_hardening_integration.py`

**Interfaces:**
- Produces: `extract_project_state(api_text) -> dict` now accepts `--api` dumps containing Windows paths. Later tasks read `state["mesh_datas"]`, `state["mesh_transforms"]`, `state["mesh_parents[i32]"]`, `state["mesh_materials[i32]"]`, `state["material_nodes"]`, `state["layer_datas"]`, `state["mesh_assets"]` from it.

- [ ] **Step 1: Failing unit test** (append to `tests/test_catalog.py`; `extract_project_state` is already imported there — add it to the import if not)

```python
def test_extract_project_state_keeps_windows_backslash_paths_literal():
    """ArmorPaint's armpack_to_json_value writes strings with NO escaping
    (base/sources/iron_armpack.c:799-801), so every backslash in the dump is
    a literal character, never a JSON escape (Known Issue #10)."""
    api_text = ('/* Current project state:\n'
                '{"mesh_assets": ["C:\\Users\\x\\tmp\\new\\grid.obj"], "n": 1}'
                '\n\nScene objects in world space\n*/\n')

    state = extract_project_state(api_text)

    assert state["mesh_assets"] == ["C:\\Users\\x\\tmp\\new\\grid.obj"]
    assert state["n"] == 1
```

(The Python literal `"C:\\Users..."` puts single backslashes in `api_text`, exactly like ArmorPaint's output. `\n`, `\t` inside would otherwise be misread as JSON escapes; `\x` and `\U` would be invalid ones.)

- [ ] **Step 2: Run** `& $py -m pytest -q tests/test_catalog.py -k backslash` → FAIL (`CatalogError: ... Invalid \escape`).

- [ ] **Step 3: Implement.** In `extract_project_state`, replace `return json.loads(api_text[start:end])` with:

```python
        # armpack_to_json_value (base/sources/iron_armpack.c:799-801) writes
        # strings as "%s" with no escaping, so a backslash here is always a
        # literal character (a Windows path), never a JSON escape: double
        # every one. A '"' inside a name would still break the parse -- a
        # documented limitation (Known Issue #10), not fixable from here.
        return json.loads(api_text[start:end].replace("\\", "\\\\"))
```

- [ ] **Step 4: Run** `& $py -m pytest -q` → all pass.

- [ ] **Step 5: Real-ArmorPaint regression test** (append to `tests/test_phase6_hardening_integration.py`). This also adds the shared post-append project builder Task 3 reuses:

```python
import shutil

from armorpaint_mcp.server import inspect_project

PHASE6 = os.path.join(FIXTURES, "phase6")


def _bk(path: str) -> str:
    """Backslash path, each backslash doubled, for a minic string literal
    (script_append_mesh needs backslashes -- spike S5)."""
    return os.path.abspath(path).replace("/", "\\").replace("\\", "\\\\")


def build_post_append_project(directory) -> str:
    """A real project in `directory` whose mesh_assets holds a backslash path
    to an OBJ next to it: sample_project.arm + an appended ReplGrid mesh,
    saved as <directory>/appended.arm. Returns that path."""
    os.makedirs(directory, exist_ok=True)
    grid = os.path.join(directory, "repl_grid5.obj")
    shutil.copy2(os.path.join(PHASE6, "repl_grid5.obj"), grid)
    out = os.path.join(directory, "appended.arm")
    script = ("void main() {\n"
              f'\tscript_append_mesh("{_bk(grid)}");\n'
              f'\tproject_filepath_set("{os.path.abspath(out).replace(os.sep, "/")}");\n'
              "\tproject_save(0);\n}\n")
    result = run_script(project=SAMPLE, script=script)
    assert result["ok"], result["error"]
    assert os.path.isfile(out), "fixture build did not save"
    return out


@pytest.mark.integration
def test_inspect_project_reads_a_project_with_backslash_asset_paths(tmp_path):
    project = build_post_append_project(tmp_path / "a")

    result = inspect_project(project)

    assert result["error"] is None
    assert result["ok"] is True
    assert {o["name"] for o in result["objects"]} >= {"ReplGrid"}
```

- [ ] **Step 6: Run** `& $py -m pytest -q -m integration tests/test_phase6_hardening_integration.py` → 3 passed. (To see the red first: `git stash` the catalog change, run, see `Invalid \escape`, `git stash pop`.)

- [ ] **Step 7: Commit**

```powershell
git add src/armorpaint_mcp/catalog.py tests/test_catalog.py tests/test_phase6_hardening_integration.py; git commit -m "fix: parse --api state JSON with literal Windows backslashes (Known Issue #10)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Mesh edits open the original and save to a fresh sibling (Known Issue #11)

**Files:**
- Modify: `src/armorpaint_mcp/script_gen.py` (add two helpers after `NodeSpecError`)
- Modify: `src/armorpaint_mcp/server.py` (imports; replace `_run_mesh_edit` lines 56-137; add `_resolve_edit_target`, `_fresh_sibling`, `_save_script`, `_run_saving_script`, `_remove_quietly`; update the 7 mesh-edit docstrings' "ok=True proves" sentences and the "Operates on a copy" wording)
- Test: `tests/test_server.py`, `tests/test_script_gen.py`, `tests/test_phase6_hardening_integration.py`

**Interfaces:**
- Consumes: `build_post_append_project` (Task 2 test helper), `run_minic_script` error behavior (Task 1).
- Produces (later tasks call these exact names):
  - `script_gen.minic_string_literal(text: str, what: str) -> str` — `'"text"'`; raises `NodeSpecError` if `text` contains `"`, `\`, `\n` or `\r`.
  - `script_gen.minic_path_literal(path: str, what: str, *, backslashes: bool = False) -> str` — quoted absolute path; forward slashes by default, or backslashes each doubled; raises `NodeSpecError` on `"`, `\n`, `\r`.
  - `server._resolve_edit_target(project, output_project, in_place, cfg) -> tuple[str, str] | dict` — `(project, target)` both validated/absolute, target's directory created; or a `_failure(..., "output_project")` dict.
  - `server._fresh_sibling(target: str) -> str` — `<target_dir>\<stem>.ap-mcp-<12 hex>.tmp.arm` (never exists yet).
  - `server._save_script(body_lines: list[str], fresh: str) -> str` — `void main()` with `body_lines`, then `project_filepath_set(<fresh>)` and `project_save(0);` as the last two statements.
  - `server._run_saving_script(cfg, project: str, script: str, fresh: str, timeout_s: float) -> ScriptResult` — runs the script; returns the `ScriptResult`, but with `ok=False` and an explanatory error if the run succeeded yet `fresh` wasn't written.
  - `server._remove_quietly(path: str) -> None`.

- [ ] **Step 1: RED first — the real-ArmorPaint test for the bug** (append to `tests/test_phase6_hardening_integration.py`):

```python
import hashlib

from armorpaint_mcp.catalog import extract_project_state
from armorpaint_mcp.config import load_config
from armorpaint_mcp.runner import run_api
from armorpaint_mcp.server import subdivide_mesh


def _md5(path) -> str:
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


@pytest.mark.integration
def test_mesh_edit_into_another_directory_keeps_asset_paths_resolvable(tmp_path):
    """Known Issue #11: .arm files store asset paths relative to themselves
    (io/export_arm.c:70,90,110,130,288,453). A mesh edit written to a
    different directory must leave every mesh_assets entry pointing at a
    real file, and must not touch the caller's own project."""
    project = build_post_append_project(tmp_path / "a")
    before = _md5(project)
    output = str(tmp_path / "b" / "nested" / "out.arm")  # dirs don't exist yet

    result = subdivide_mesh(project=project, output_project=output)

    assert result["error"] is None
    assert result["ok"] is True
    assert _md5(project) == before
    state = extract_project_state(run_api(load_config().binary, output).text)
    assert state["mesh_assets"], state.get("mesh_assets")
    for asset in state["mesh_assets"]:
        assert os.path.isfile(asset), f"mesh_assets entry doesn't resolve: {asset}"
```

- [ ] **Step 2: Run it — expect RED.** `& $py -m pytest -q -m integration tests/test_phase6_hardening_integration.py -k asset_paths`. Expected: FAIL on the `os.path.isfile(asset)` assertion (the current `copy2`-then-open keeps paths relative to the old directory). **If it unexpectedly passes, stop and report**: the bug premise is wrong and the task needs re-planning.

- [ ] **Step 3: Failing unit tests for the literal helpers** (append to `tests/test_script_gen.py`):

```python
import os

from armorpaint_mcp.script_gen import (NodeSpecError, minic_path_literal,
                                       minic_string_literal)


def test_minic_string_literal_quotes_plain_text():
    assert minic_string_literal("Cone.001", "object name") == '"Cone.001"'


@pytest.mark.parametrize("bad", ['a"b', "a\\b", "a\nb", "a\rb"])
def test_minic_string_literal_rejects_characters_it_cannot_carry(bad):
    with pytest.raises(NodeSpecError, match="object name"):
        minic_string_literal(bad, "object name")


def test_minic_path_literal_defaults_to_forward_slashes(tmp_path):
    p = tmp_path / "Program Files (x86)" / "Ø" / "out.arm"
    assert minic_path_literal(str(p), "output path") == '"' + str(p).replace("\\", "/") + '"'


def test_minic_path_literal_doubles_backslashes_when_asked(tmp_path):
    p = tmp_path / "new mesh.obj"
    expected = '"' + str(p).replace("\\", "\\\\") + '"'
    assert minic_path_literal(str(p), "mesh path", backslashes=True) == expected


def test_minic_path_literal_rejects_a_double_quote(tmp_path):
    with pytest.raises(NodeSpecError, match="mesh path"):
        minic_path_literal(str(tmp_path / 'a"b.obj'), "mesh path")
```

- [ ] **Step 4: Run** `& $py -m pytest -q tests/test_script_gen.py` → FAIL (ImportError).

- [ ] **Step 5: Implement the helpers** in `script_gen.py` (add `import os` at the top; place after `class NodeSpecError`):

```python
def minic_string_literal(text: str, what: str) -> str:
    """`text` as a minic string literal. Nothing is escaped: a double quote,
    backslash or line break is rejected instead, so a caller-supplied name
    can never end the literal early or smuggle in a statement."""
    if any(ch in text for ch in '"\\\n\r'):
        raise NodeSpecError(
            f"{what} can't contain a double quote, backslash or line break: {text!r}")
    return f'"{text}"'


def minic_path_literal(path: str, what: str, *, backslashes: bool = False) -> str:
    """`path`, made absolute, as a minic string literal. Forward slashes by
    default (project_filepath_set, script_export_mesh and
    export_texture_run accept them). backslashes=True doubles each backslash
    instead: script_append_mesh REQUIRES that -- with forward slashes its
    iron_file_exists check fails and the append silently no-ops (Phase 6
    spike S5)."""
    full = os.path.abspath(path)
    if any(ch in full for ch in '"\n\r'):
        raise NodeSpecError(f"{what} can't contain a double quote or line break: {full!r}")
    if backslashes:
        return '"' + full.replace("/", "\\").replace("\\", "\\\\") + '"'
    return '"' + full.replace("\\", "/") + '"'
```

- [ ] **Step 6: Run** `& $py -m pytest -q tests/test_script_gen.py` → pass.

- [ ] **Step 7: Rewrite the mesh-edit unit tests.** In `tests/test_server.py`, delete `test_decimate_mesh_copies_then_edits_and_saves`, `test_decimate_mesh_converts_copy_failure_to_clean_error` and `test_decimate_mesh_removes_stale_copy_on_script_failure`, and add (the file already imports `patch`, `ScriptResult`, `decimate_mesh`; add `import os`, `import re`):

```python
def _fresh_path_in(script: str) -> str:
    """The path _save_script told ArmorPaint to save to."""
    return re.search(r'project_filepath_set\("([^"]+)"\);', script).group(1)


def _saving_run(stdout="", write=True):
    """A run_minic_script stand-in that 'saves' the fresh sibling the script
    names (as real ArmorPaint would) and returns ok."""
    def fake(binary, project, script, timeout_s):
        if write:
            with open(_fresh_path_in(script), "wb") as fh:
                fh.write(b"edited")
        return ScriptResult(ok=True, stdout=stdout, stderr="")
    return fake


def _cfg(mock_cfg):
    mock_cfg.return_value.binary = "ArmorPaint.exe"
    mock_cfg.return_value.allowed_roots = []


def test_decimate_mesh_edits_the_original_and_saves_to_a_fresh_sibling(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")
    output_project = tmp_path / "out" / "new" / "out.arm"  # dirs don't exist yet

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_saving_run()) as mock_run:
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(output_project))

    assert result == {"ok": True, "output_project": str(output_project), "error": None}
    assert output_project.read_bytes() == b"edited"
    assert project.read_bytes() == b"original"
    opened, script = mock_run.call_args[0][1], mock_run.call_args[0][2]
    assert opened == str(project)                      # the ORIGINAL is opened
    fresh = _fresh_path_in(script)
    assert os.path.dirname(fresh) == str(output_project.parent).replace("\\", "/")
    assert "util_mesh_decimate(0.5);" in script
    assert script.rstrip().endswith("project_save(0);\n}")         # save is last
    assert not os.path.exists(fresh)                   # moved, not copied
    assert os.listdir(output_project.parent) == ["out.arm"]


def test_decimate_mesh_fails_when_the_script_ran_but_never_saved(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_saving_run(write=False)):
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(output_project))

    assert result["ok"] is False
    assert "without saving" in result["error"]
    assert not output_project.exists()
    assert sorted(os.listdir(tmp_path)) == ["project.arm"]


def test_decimate_mesh_timeout_after_a_complete_write_is_a_failure(tmp_path):
    """Review Focus 5: the spike saw a run hang to its timeout after saving a
    complete file. The timeout wins; the fresh file must not survive."""
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")
    output_project = tmp_path / "out.arm"

    def wrote_then_timed_out(binary, project_, script, timeout_s):
        with open(_fresh_path_in(script), "wb") as fh:
            fh.write(b"complete")
        return ScriptResult(ok=False, stdout="", stderr="",
                            error="'--script' timed out after 30.0s")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=wrote_then_timed_out):
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(output_project))

    assert result["ok"] is False
    assert "timed out" in result["error"]
    assert sorted(os.listdir(tmp_path)) == ["project.arm"]


def test_decimate_mesh_in_place_replaces_the_project_only_after_success(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_saving_run()):
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5, in_place=True)

    assert result == {"ok": True, "output_project": str(project), "error": None}
    assert project.read_bytes() == b"edited"
    assert os.listdir(tmp_path) == ["project.arm"]


def test_decimate_mesh_ignores_a_leftover_fresh_sibling_from_a_crashed_run(tmp_path):
    """Review Focus 3."""
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")
    stranger = tmp_path / "out.ap-mcp-0123456789ab.tmp.arm"
    stranger.write_bytes(b"old crash")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_saving_run()):
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(output_project))

    assert result["ok"] is True
    assert stranger.read_bytes() == b"old crash"


def test_decimate_mesh_rejects_a_target_path_minic_cannot_carry(tmp_path):
    """A '"' can't reach minic: Windows refuses it in a directory name
    (makedirs fails) and minic_path_literal refuses it in the literal.
    Either way: a clean failure, and ArmorPaint never launches."""
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(tmp_path / 'we"ird' / "out.arm"))

    assert result["ok"] is False
    assert result["output_project"] is None
    mock_run.assert_not_called()


def test_decimate_mesh_converts_a_replace_failure_to_a_clean_error(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")
    output_project = tmp_path / "out.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_saving_run()), \
         patch("armorpaint_mcp.server.os.replace", side_effect=OSError("disk full")):
        _cfg(mock_cfg)
        result = decimate_mesh(project=str(project), strength=0.5,
                               output_project=str(output_project))

    assert result["ok"] is False
    assert "disk full" in result["error"]
    assert sorted(os.listdir(tmp_path)) == ["project.arm"]
```

Also update `test_decimate_mesh_in_place_failure_does_not_delete_project` to assert `project.read_bytes() == b"fake"` in addition to `project.exists()`. In `test_bevel_mesh_calls_the_right_minic_function`, `test_subdivide_mesh_calls_the_right_minic_function`, `test_smooth_mesh_calls_the_right_minic_function`, `test_duplicate_mesh_calls_the_right_minic_function`, `test_merge_mesh_geometry_calls_the_right_minic_function_when_enough_objects` and `test_unwrap_mesh_uvs_calls_the_right_minic_function`, replace the line `mock_run.return_value = ScriptResult(ok=True, stdout="", stderr="")` with `mock_run.side_effect = _saving_run()` (success now requires the fresh file to exist) and keep every other assertion.

- [ ] **Step 8: Run** `& $py -m pytest -q tests/test_server.py` → the new tests FAIL.

- [ ] **Step 9: Implement in `server.py`.** Imports: add `import uuid`; drop `import shutil`; import `ScriptResult` from runner; import `minic_path_literal` from script_gen. Replace `_run_mesh_edit` (lines 56-137) with:

```python
def _resolve_edit_target(project: str, output_project: str | None,
                         in_place: bool, cfg) -> tuple[str, str] | dict:
    """Validate a saving tool's inputs. Returns (project, target) -- both
    absolute and inside AP_ALLOWED_ROOTS, target's directory created -- or
    a _failure(..., "output_project") dict. Mutating tools default to a new
    output file; in_place=True targets the caller's own project."""
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
        return project, project
    if not output_project:
        return _failure(
            "output_project is required unless in_place=True (mutating "
            "operations default to a copy, never the caller's own file)",
            "output_project")
    try:
        output_project = ensure_within_roots(output_project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "output_project")
    if os.path.realpath(project) == os.path.realpath(output_project):
        return _failure(
            "output_project must not be the same file as project -- use "
            "in_place=True to edit project itself", "output_project")
    try:
        os.makedirs(os.path.dirname(output_project) or ".", exist_ok=True)
    except OSError as exc:
        return _failure(f"could not create output_project's directory: {exc}",
                        "output_project")
    return project, output_project


def _fresh_sibling(target: str) -> str:
    """A not-yet-existing save path next to `target`. Saving beside the final
    location matters: .arm files store asset paths relative to themselves
    (io/export_arm.c), so a file saved elsewhere and moved would break them
    (Known Issue #11). The random part keeps a crashed run's leftover from
    ever colliding with a new one."""
    stem = os.path.splitext(os.path.basename(target))[0]
    return os.path.join(os.path.dirname(os.path.abspath(target)),
                        f"{stem}.ap-mcp-{uuid.uuid4().hex[:12]}.tmp.arm")


def _save_script(body_lines: list[str], fresh: str) -> str:
    """`body_lines` wrapped in void main(), then save to `fresh`. The save is
    deliberately LAST: a minic error after project_save would still leave a
    saved file, so nothing may follow it (Phase 6 spike S2)."""
    save_to = minic_path_literal(fresh, "output path")
    lines = ["void main() {", *(f"\t{line}" for line in body_lines),
             f"\tproject_filepath_set({save_to});", "\tproject_save(0);", "}", ""]
    return "\n".join(lines)


def _run_saving_script(cfg, project: str, script: str, fresh: str,
                       timeout_s: float) -> ScriptResult:
    """Run a _save_script against the caller's ORIGINAL `project` (opened,
    never written). Success requires, in order: exit code 0 and no timeout,
    no minic error line (both run_minic_script), and `fresh` existing
    afterwards -- a script that returned early prints nothing, and only the
    file proves project_save ran."""
    result = run_minic_script(cfg.binary, project, script, timeout_s)
    if result.ok and not os.path.isfile(fresh):
        return ScriptResult(ok=False, stdout=result.stdout, stderr=result.stderr, error=(
            "ArmorPaint finished without saving: the script stopped before "
            "project_save and printed no error"))
    return result


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _run_mesh_edit(project: str, minic_call: str, output_project: str | None,
                   in_place: bool, timeout_s: float) -> dict:
    """Shared plumbing for every mesh-edit tool: open the caller's project
    (never writing it), run `minic_call`, save to a fresh sibling of the
    target, then move that over the target. A failure at any point leaves
    the target untouched and no temp file behind.

    ok=True means ArmorPaint exited cleanly, printed no minic error, and
    saved the edited project -- not that the edit looks good.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    cfg = _ensure_ready()
    resolved = _resolve_edit_target(project, output_project, in_place, cfg)
    if isinstance(resolved, dict):
        return resolved
    project, target = resolved
    fresh = _fresh_sibling(target)
    try:
        script = _save_script([minic_call], fresh)
    except NodeSpecError as exc:
        return _failure(str(exc), "output_project")
    try:
        result = _run_saving_script(cfg, project, script, fresh, timeout_s)
        error = result.error
        if result.ok:
            os.replace(fresh, target)
    except OSError as exc:
        error = f"could not write output_project: {exc}"
    finally:
        _remove_quietly(fresh)
    if error is not None:
        return _failure(error, "output_project")
    return {"ok": True, "output_project": target, "error": None}
```

In each of the 7 mesh-edit tools' docstrings: replace "Operates on a copy of `project` by default" with "Writes the result to `output_project` by default (the caller's `project` is never modified)", and replace the "ok=True proves (only) that the ArmorPaint process completed and saved(...)" sentence with "ok=True means ArmorPaint exited cleanly, printed no script error, and saved the result". Leave each tool's "not that the X looks good" clause.

- [ ] **Step 10: Run** `& $py -m pytest -q` → all pass.

- [ ] **Step 11: Run the RED test again — expect GREEN** plus the whole hardening file and the Phase 5 regressions:

Run: `& $py -m pytest -q -m integration tests/test_phase6_hardening_integration.py tests/test_decimate_mesh_integration.py tests/test_smooth_mesh_integration.py tests/test_bevel_mesh_integration.py tests/test_subdivide_mesh_integration.py tests/test_duplicate_mesh_integration.py tests/test_merge_mesh_geometry_integration.py tests/test_unwrap_mesh_uvs_integration.py`
Expected: all pass. **If `test_mesh_edit_into_another_directory_keeps_asset_paths_resolvable` is still red, STOP and report** (with the `mesh_assets` values it printed): it would mean ArmorPaint relativizes against the load path, not the save path, and the fix needs a different design.

- [ ] **Step 12: Commit**

```powershell
git add src/armorpaint_mcp/script_gen.py src/armorpaint_mcp/server.py tests/test_script_gen.py tests/test_server.py tests/test_phase6_hardening_integration.py; git commit -m "fix: mesh edits open the original and save to a fresh sibling (Known Issue #11)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Registry of every minic function the project emits; `--check` covers all of them (D1)

**Files:**
- Modify: `src/armorpaint_mcp/catalog.py:126-150` (replace `_MESH_EDIT_PATCH_FUNCTIONS` + `mesh_edit_patch_missing`)
- Modify: `src/armorpaint_mcp/doctor.py:13, 56-74`
- Test: `tests/test_catalog.py`, `tests/test_doctor.py`

**Interfaces:**
- Produces: `catalog.EMITTED_MINIC_FUNCTIONS: tuple[str, ...]`; `catalog.missing_minic_functions(api_text: str) -> list[str]`. Tasks 6 and 8 extend the tuple and the completeness test's script list.

- [ ] **Step 1: Failing tests.** In `tests/test_catalog.py` delete the three `test_mesh_edit_patch_missing_*` tests and the `mesh_edit_patch_missing` import; add:

```python
import re
from unittest.mock import patch

from armorpaint_mcp import server
from armorpaint_mcp.catalog import EMITTED_MINIC_FUNCTIONS, missing_minic_functions
from armorpaint_mcp.runner import ScriptResult
from armorpaint_mcp.script_gen import generate_script

_C_KEYWORDS = {"main", "if", "for", "while", "return", "sizeof"}


def _called_identifiers(script: str) -> set[str]:
    """Every `name(` in a minic script, ignoring string literals (a path like
    'Program Files (x86)' must not register 'Files' as a call)."""
    without_strings = re.sub(r'"(?:[^"\\]|\\.)*"', '""', script)
    return set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", without_strings)) - _C_KEYWORDS


def _captured_scripts(tmp_path) -> list[str]:
    """Scripts produced by the REAL builders: every create_procedural_material
    node type and every mesh-edit tool (run_minic_script patched to capture)."""
    scripts = [generate_script({"type": t}, str(tmp_path / "Program Files (x86)"))
               for t in ("checker", "solid", "noise", "voronoi")]
    project = tmp_path / "p.arm"
    project.write_bytes(b"x")
    captured = []

    def capture(binary, project_, script, timeout_s):
        captured.append(script)
        return ScriptResult(ok=False, stdout="", stderr="", error="captured")

    calls = [
        lambda: server.decimate_mesh(str(project), 0.5, str(tmp_path / "o.arm")),
        lambda: server.bevel_mesh(str(project), 0.1, str(tmp_path / "o.arm")),
        lambda: server.subdivide_mesh(str(project), str(tmp_path / "o.arm")),
        lambda: server.smooth_mesh(str(project), str(tmp_path / "o.arm")),
        lambda: server.duplicate_mesh(str(project), str(tmp_path / "o.arm")),
        lambda: server.unwrap_mesh_uvs(str(project), str(tmp_path / "o.arm")),
    ]
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=capture):
        mock_cfg.return_value.binary = "ArmorPaint.exe"
        mock_cfg.return_value.allowed_roots = []
        for call in calls:
            call()
    # merge_mesh_geometry runs run_api first; its minic call is the same shape
    scripts += captured + [server._save_script(["util_mesh_merge_geometry();"],
                                               str(tmp_path / "f.arm"))]
    return scripts


def test_every_emitted_minic_call_is_in_the_registry(tmp_path):
    called = set().union(*(_called_identifiers(s) for s in _captured_scripts(tmp_path)))
    assert called <= set(EMITTED_MINIC_FUNCTIONS), sorted(called - set(EMITTED_MINIC_FUNCTIONS))


def test_missing_minic_functions_matches_whole_names_only():
    api = "void util_mesh_merge_geometry_down(mesh_object_t *a);\nvoid project_save(i32 x);\n"
    missing = missing_minic_functions(api)
    assert "util_mesh_merge_geometry" in missing   # a longer name doesn't count
    assert "project_save" not in missing


def test_missing_minic_functions_empty_when_all_declared():
    api = "\n".join(f"void {n}();" for n in EMITTED_MINIC_FUNCTIONS)
    assert missing_minic_functions(api) == []
```

In `tests/test_doctor.py` replace both tests with:

```python
from armorpaint_mcp.catalog import EMITTED_MINIC_FUNCTIONS


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
```

- [ ] **Step 2: Run** `& $py -m pytest -q tests/test_catalog.py tests/test_doctor.py` → FAIL (ImportError).

- [ ] **Step 3: Implement.** In `catalog.py` replace lines 126-150 with:

```python
# Every minic function this project's generated scripts call. `ap-mcp
# --check` confirms each is registered on AP_BINARY: an unregistered one
# aborts the script with a "<script>:N: error: unknown function" line, and
# upstream renames them (01bae6c5 renamed plugin_uv_unwrap_button). The
# completeness test in tests/test_catalog.py extracts the calls from the
# real script builders, so this list can't silently fall behind them.
EMITTED_MINIC_FUNCTIONS = (
    # Phase 5 mesh edits
    "util_mesh_decimate", "util_mesh_smooth", "util_mesh_bevel",
    "util_mesh_subdivide", "util_mesh_merge_geometry", "util_mesh_duplicate",
    "util_mesh_uv_unwrap",
    # create_procedural_material (script_gen.generate_script)
    "script_project_new", "script_material_get_node",
    "script_material_create_node_at", "script_material_set_color",
    "script_material_set_float", "script_material_connect",
    "script_fill_layer", "export_texture_run",
    # saving tools (server._save_script)
    "project_filepath_set", "project_save",
)


def missing_minic_functions(api_text: str) -> list[str]:
    """Which EMITTED_MINIC_FUNCTIONS are not declared in `api_text`
    (ArmorPaint.exe --api, no project needed, which prints each registered
    function as `<type> name(<args>);`). Whole-name match: a registered
    util_mesh_merge_geometry_down does not count as util_mesh_merge_geometry."""
    return [name for name in EMITTED_MINIC_FUNCTIONS
            if not re.search(rf"\b{re.escape(name)}\s*\(", api_text)]
```

In `doctor.py` change the import to `from armorpaint_mcp.catalog import EMITTED_MINIC_FUNCTIONS, missing_minic_functions` and replace the `"mesh-edit patch"` block (lines 56-74) with:

```python
    if cfg.binary and os.path.isfile(cfg.binary):
        try:
            out = subprocess.run([cfg.binary, "--api"], capture_output=True,
                                  text=True, timeout=15, errors="replace")
            missing = missing_minic_functions(out.stdout) if out.returncode == 0 else None
            if missing is None:
                checks.append(Check("minic API", False,
                                    f"'--api' exited {out.returncode}, could not check"))
            elif missing:
                checks.append(Check("minic API", False,
                                    f"not registered on this build: {', '.join(missing)} "
                                    "-- tools that call them would fail. Rebuild AP_BINARY "
                                    "from current upstream main (see ROADMAP.md \"Patch "
                                    "policy\"), or update the renamed call."))
            else:
                checks.append(Check("minic API", True,
                                    f"all {len(EMITTED_MINIC_FUNCTIONS)} minic functions "
                                    "this project calls are registered"))
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append(Check("minic API", False, str(exc)))
```

- [ ] **Step 4: Run** `& $py -m pytest -q` → all pass. If `test_every_emitted_minic_call_is_in_the_registry` names a missing function, add it to the tuple under the right comment.

- [ ] **Step 5: Real check.** `& $py -m armorpaint_mcp.server --check` → exit 0, row `[PASS] minic API: all 17 minic functions this project calls are registered`.

- [ ] **Step 6: Commit**

```powershell
git add src/armorpaint_mcp/catalog.py src/armorpaint_mcp/doctor.py tests/test_catalog.py tests/test_doctor.py; git commit -m "feat: --check verifies every minic function the project emits (D1)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `uv_analysis` module (6.2 core)

**Files:**
- Create: `src/armorpaint_mcp/uv_analysis.py` (from `docs/superpowers/spikes/prototypes/uvraster.py`)
- Test: `tests/test_uv_analysis.py` (new)

**Interfaces:**
- Produces (used by Tasks 6-9):
  - `parse_obj(text: str) -> ObjData`; `ObjData(v, vt, groups)`; `ObjGroup(name, tri_v, tri_vt, faces, faces_without_uv, tris_without_uv, ngons)`.
  - `groups_by_name(obj: ObjData) -> dict[str, ObjGroup]` (only groups with at least one face).
  - `analyze(obj, g, n=256) -> dict` (keys as in the prototype, incl. `faces_without_uv`, `zero_area_tris_with_3d_area`, `zero_area_3d_share_pct`, `flipped_tris`, `flipped_pct`, `out_of_range_uvs`, `coverage_pct`, `overlap_pct`).
  - `verdict(metrics: dict, allow_udim: bool = False) -> dict` → `{"valid": bool, "errors": [str], "warnings": [str]}`.
  - `compare_layouts(old_obj, old_g, new_obj, new_g, n=256) -> dict` → `{"iou": float, "retention": float | None, "excluded_overlap_share": float | None, "size_ratio": float}`.
  - `group_signature(obj, g) -> tuple` (resolved, rounded triangles; equal for identical geometry regardless of global index offsets).
  - Constants: `RASTER_N = 256`, `ZERO_AREA_ERROR_PCT = 0.1`, `IOU_MIN = 0.95`, `RETENTION_MIN = 0.85`, `RETENTION_WARN = 0.98`, `RETENTION_TOL = 0.05`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_uv_analysis.py`:

```python
import os
import random

import pytest

from armorpaint_mcp import uv_analysis as ua

UV_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "phase6", "uv")

QUAD = """o Quad
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
f 1/1 2/2 3/3 4/4
"""


def _single(text):
    obj = ua.parse_obj(text)
    (g,) = ua.groups_by_name(obj).values()
    return obj, g


def test_unit_quad_covers_everything_once():
    obj, g = _single(QUAD)
    m = ua.analyze(obj, g)
    assert m["coverage_pct"] == 100.0
    assert m["overlap_pct"] == 0.0
    assert ua.verdict(m) == {"valid": True, "errors": [], "warnings": []}


def test_duplicated_triangle_is_an_overlap_warning_not_an_error():
    text = QUAD.replace("f 1/1 2/2 3/3 4/4", "f 1/1 2/2 3/3\nf 1/1 2/2 3/3")
    obj, g = _single(text)
    v = ua.verdict(ua.analyze(obj, g))
    assert v["valid"] is True
    assert any("overlapping" in w for w in v["warnings"])


def test_reversed_winding_counts_as_flipped_warning():
    text = QUAD.replace("f 1/1 2/2 3/3 4/4", "f 1/1 2/2 3/3\nf 1/1 4/4 3/3\nf 1/1 3/3 2/2")
    obj, g = _single(text)
    m = ua.analyze(obj, g)
    assert m["flipped_tris"] == 1
    assert any("flipped" in w for w in ua.verdict(m)["warnings"])


def test_out_of_range_uvs_are_an_error_unless_allow_udim():
    obj, g = _single(QUAD.replace("vt 1 1", "vt 1.5 1"))
    m = ua.analyze(obj, g)
    assert m["out_of_range_uvs"] == 1
    assert ua.verdict(m)["valid"] is False
    relaxed = ua.verdict(m, allow_udim=True)
    assert relaxed["valid"] is True
    assert any("outside [0,1]" in w for w in relaxed["warnings"])


def test_faces_without_uvs_are_an_error():
    obj, g = _single(QUAD.replace("f 1/1 2/2 3/3 4/4", "f 1 2 3 4"))
    v = ua.verdict(ua.analyze(obj, g))
    assert v["valid"] is False
    assert any("no UVs" in e for e in v["errors"])


def test_uv_degenerate_triangles_with_3d_area_error_only_above_the_share_limit():
    # big quad (UV fine) + one small triangle whose three UVs coincide
    small = QUAD + "v 0 0 1\nv 0.01 0 1\nv 0 0.01 1\nvt 0.5 0.5\nf 5/5 6/5 7/5\n"
    obj, g = _single(small)
    m = ua.analyze(obj, g)
    assert m["zero_area_tris_with_3d_area"] == 1
    assert 0 < m["zero_area_3d_share_pct"] <= ua.ZERO_AREA_ERROR_PCT
    assert ua.verdict(m)["valid"] is True
    big = QUAD + "v 0 0 1\nv 1 0 1\nv 0 1 1\nvt 0.5 0.5\nf 5/5 6/5 7/5\n"
    obj, g = _single(big)
    assert ua.verdict(ua.analyze(obj, g))["valid"] is False


def test_raster_matches_brute_force_on_random_triangles():
    """Prototype selftest check 7: a random soup (incl. out-of-range
    triangles) snapped to the rasterizer's fixed-point grid, so the float
    point-in-triangle test is exact."""
    rng = random.Random(3)
    n = 64
    soup = [tuple(rng.uniform(-0.2, 1.2) for _ in range(6)) for _ in range(25)]
    soup = [tuple(round(x * n * ua.SUB) / (n * ua.SUB) for x in t) for t in soup]
    counts = ua.rasterize(soup, n)

    expected = [0] * (n * n)
    for x0, y0, x1, y1, x2, y2 in soup:
        for j in range(n):
            py = (j + 0.5) / n
            for i in range(n):
                px = (i + 0.5) / n
                e0 = (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0)
                e1 = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
                e2 = (x0 - x2) * (py - y2) - (y0 - y2) * (px - x2)
                if (e0 > 1e-12 and e1 > 1e-12 and e2 > 1e-12) or \
                   (e0 < -1e-12 and e1 < -1e-12 and e2 < -1e-12):
                    expected[j * n + i] += 1
    assert sum(1 for a, b in zip(counts, expected) if a != b) == 0


def test_groups_are_keyed_by_name_and_faces_rebase_cleanly():
    two = QUAD + "o Other\nv 5 5 5\nv 6 5 5\nv 5 6 5\nvt 0 0\nvt 1 0\nvt 0 1\nf 5/5 6/6 7/7\n"
    obj = ua.parse_obj(two)
    by_name = ua.groups_by_name(obj)
    assert sorted(by_name) == ["Other", "Quad"]
    solo, g = _single("o Other\nv 5 5 5\nv 6 5 5\nv 5 6 5\nvt 0 0\nvt 1 0\nvt 0 1\nf 1/1 2/2 3/3\n")
    assert ua.group_signature(obj, by_name["Other"]) == ua.group_signature(solo, g)


def _fixture(name):
    with open(os.path.join(UV_DIR, f"{name}.obj"), encoding="utf-8") as fh:
        return _single(fh.read())


def _gate_passes(cmp):
    retention_ok = cmp["retention"] is None or cmp["retention"] >= ua.RETENTION_MIN
    return cmp["iou"] >= ua.IOU_MIN and retention_ok


@pytest.mark.parametrize("name", ["r1_noise", "r2_subdiv", "r3_bevel", "r4_extrude",
                                  "r5_decimate", "r5b_decimate_heavy",
                                  "r6b_subsurf_smoothall", "r7_bigmove", "r8_scaled"])
def test_round_trip_variants_pass_the_gate(name):
    cmp = ua.compare_layouts(*_fixture("base"), *_fixture(name))
    assert _gate_passes(cmp), cmp


@pytest.mark.parametrize("name", ["d1_smartuv45", "d2a_lightmap", "d2b_cube", "d3_repack",
                                  "d4_swap", "d5_rot180", "d6_repack_norot"])
def test_different_uv_variants_fail_the_gate(name):
    cmp = ua.compare_layouts(*_fixture("base"), *_fixture(name))
    assert not _gate_passes(cmp), cmp


@pytest.mark.parametrize("name,passes", [("sphere_r1_noise", True), ("sphere_d_mirror", False),
                                         ("sphere_d_rot180", False), ("sphere_d_smartuv", False)])
def test_sphere_set_including_iou_blind_mirror_and_rotation(name, passes):
    cmp = ua.compare_layouts(*_fixture("sphere"), *_fixture(name))
    assert _gate_passes(cmp) is passes, cmp


def test_size_ratio_reports_uniform_scale():
    cmp = ua.compare_layouts(*_fixture("base"), *_fixture("r8_scaled"))
    assert cmp["size_ratio"] == pytest.approx(1.25, rel=0.02)
```

- [ ] **Step 2: Run** `& $py -m pytest -q tests/test_uv_analysis.py` → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create the module.** `Copy-Item docs\superpowers\spikes\prototypes\uvraster.py src\armorpaint_mcp\uv_analysis.py`, then edit `src/armorpaint_mcp/uv_analysis.py`:
  1. Replace the module docstring with:
     ```python
     """UV-layout analysis for check_mesh_uvs and replace_mesh (Phase 6).

     Pure standard library (numpy is not a dependency). Ported from spike S3's
     prototype (docs/superpowers/spikes/prototypes/uvraster.py); calibration
     evidence in docs/superpowers/spikes/2026-09-27-phase6-spike-S3.md.
     OBJ faces are fan-triangulated; ArmorPaint ear-clips faces with more than
     4 corners (base/sources/iron_obj.c), so a concave n-gon in a *source* OBJ
     can rasterize slightly differently. ArmorPaint's own exports are all
     triangles.
     """
     ```
  2. Delete the spike-only ArmorPaint emulation: `import struct`, `_F32`, `_f32`, `_i16`, `_INV`, `ap_quantize_uv`, `ap_roundtrip_uv` (the whole "ArmorPaint emulation" section).
  3. Below the existing constants add:
     ```python
     RASTER_N = 256            # S3: IoU/retention stable across N; 128 undercounts tiny islands
     ZERO_AREA_ERROR_PCT = 0.1 # % of 3D surface in UV-degenerate triangles that errors (S3 F1)
     # replace_mesh round_trip gate, from S3's calibration (worst round trip
     # r7 retention 0.907 vs worst scramble d4 0.7385; IoU r5 0.9987 vs d3
     # 0.7651). Re-checked on real ArmorPaint exports by scripts/calibrate_uv_gate.py.
     IOU_MIN = 0.95
     RETENTION_MIN = 0.85
     RETENTION_WARN = 0.98
     RETENTION_TOL = 0.05      # fraction of the old bbox diagonal
     ```
  4. Add after `parse_obj`:
     ```python
     def groups_by_name(obj: ObjData) -> dict[str, ObjGroup]:
         """Face-bearing groups keyed by `o` name. ArmorPaint exports one
         uniquely named group per paint object (spike S1); key by name, never
         by position -- a replace moves the new object to the end."""
         return {g.name: g for g in obj.groups if g.faces}


     def group_signature(obj: ObjData, g: ObjGroup) -> tuple:
         """Resolved triangles (positions + UVs, rounded to 1e-6): equal for
         identical geometry however the global OBJ indices are offset. Raw `f`
         lines are NOT comparable across exports -- removing an object shifts
         every later group's indices (spike A, contradiction 1)."""
         v, vt = obj.v, obj.vt
         return tuple(
             tuple(tuple(round(c, 6) for c in v[i]) for i in tv)
             + tuple(tuple(round(c, 6) for c in vt[t]) for t in tt)
             for tv, tt in zip(g.tri_v, g.tri_vt))
     ```
  5. Add after `position_agreement`:
     ```python
     def verdict(metrics: dict, allow_udim: bool = False) -> dict:
         """Tiered judgement of one object's analyze() metrics (docs/PLAN.md
         6.2): errors make the UVs unusable for painting, warnings are often
         deliberate (mirrored/stacked islands)."""
         errors, warnings = [], []
         if metrics["faces_without_uv"]:
             errors.append(f"{metrics['faces_without_uv']} face(s) have no UVs")
         share = metrics["zero_area_3d_share_pct"]
         if share > ZERO_AREA_ERROR_PCT:
             errors.append(f"UV-degenerate triangles cover {share}% of the surface "
                           f"(limit {ZERO_AREA_ERROR_PCT}%): paint can't land there")
         elif metrics["zero_area_tris_with_3d_area"]:
             warnings.append(f"{metrics['zero_area_tris_with_3d_area']} UV-degenerate "
                             f"triangle(s) with 3D area ({share}% of the surface)")
         if metrics["out_of_range_uvs"]:
             msg = f"{metrics['out_of_range_uvs']} UV(s) outside [0,1]"
             if allow_udim:
                 warnings.append(msg)
             else:
                 errors.append(msg + " (pass allow_udim=True for a UDIM layout)")
         if metrics["overlap_pct"]:
             warnings.append(f"{metrics['overlap_pct']}% of covered texels are shared "
                             f"by overlapping UVs")
         if metrics["flipped_tris"]:
             warnings.append(f"{metrics['flipped_tris']} flipped UV triangle(s) "
                             f"({metrics['flipped_pct']}%)")
         return {"valid": not errors, "errors": errors, "warnings": warnings}


     def compare_layouts(old_obj: ObjData, old_g: ObjGroup, new_obj: ObjData,
                         new_g: ObjGroup, n: int = RASTER_N) -> dict:
         """replace_mesh's UV-match signals. `iou`: UV-coverage overlap. `retention`:
         share of the old layout's texels whose new 3D position lies within
         RETENTION_TOL of the old bbox diagonal after removing translation and
         uniform scale -- catches coverage-preserving scrambles IoU can't see
         (island swaps, mirrors). None when no texel is assessable (fully stacked
         layout). `size_ratio`: new bbox diagonal / old."""
         old_pos, new_pos = tri_positions(old_obj, old_g), tri_positions(new_obj, new_g)
         old_r = rasterize_positions(tri_uvs(old_obj, old_g), old_pos, n)
         new_r = rasterize_positions(tri_uvs(new_obj, new_g), new_pos, n)
         old_diag = bbox_diag([p for t in old_pos for p in t])
         new_diag = bbox_diag([p for t in new_pos for p in t])
         agree = position_agreement(old_r, new_r, old_diag, tols=(RETENTION_TOL,),
                                    normalize=True)
         return {"iou": round(iou(old_r[0], new_r[0]), 4),
                 "retention": agree[f"retained_{RETENTION_TOL}"],
                 "excluded_overlap_share": agree["excluded_overlap_share"],
                 "size_ratio": round(new_diag / old_diag, 4) if old_diag else None}
     ```
  6. Change the default of `analyze(..., n: int = 256, ...)` and `rasterize(..., n: int = 256)` to `RASTER_N` (define the constants block above the raster section so the names exist).

- [ ] **Step 4: Run** `& $py -m pytest -q tests/test_uv_analysis.py` → all pass. The fixture tests take a few seconds (pure Python). If a fixture test fails, print the `cmp` dict it shows and compare against the S3 table in `docs/superpowers/spikes/2026-09-27-phase6-spike-S3.md`; a mismatch there means the port broke something (re-diff against the prototype), not that the threshold is wrong.

- [ ] **Step 5: Run** `& $py -m pytest -q` → all pass.

- [ ] **Step 6: Commit**

```powershell
git add src/armorpaint_mcp/uv_analysis.py tests/test_uv_analysis.py; git commit -m "feat: uv_analysis module (raster, tiered verdict, IoU + texel retention)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `check_mesh_uvs` tool (6.2)

**Files:**
- Modify: `src/armorpaint_mcp/server.py` (add `_export_obj` helper and the tool after `inspect_project`), `src/armorpaint_mcp/catalog.py` (registry)
- Test: `tests/test_server.py`, `tests/test_catalog.py` (extend `_captured_scripts`), `tests/test_check_mesh_uvs_integration.py` (new)

**Interfaces:**
- Consumes: `uv_analysis.parse_obj/analyze/verdict`, `minic_path_literal`, `run_minic_script`.
- Produces: `server._export_obj(cfg, project: str, out_path: str, timeout_s: float) -> tuple[str | None, str | None]` → `(obj_text, None)` or `(None, error)`; tool `check_mesh_uvs(project, allow_udim=False, timeout_s=DEFAULT_TIMEOUT_S) -> {"ok", "valid", "objects", "error"}`, each object `{"name", "valid", "errors", "warnings", "metrics"}`.

- [ ] **Step 1: Failing unit tests** (append to `tests/test_server.py`, add `check_mesh_uvs` to the server import):

```python
QUAD_OBJ = ("o Quad\nv 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
            "vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nf 1/1 2/2 3/3\nf 1/1 3/3 4/4\n")


def _exporting_run(obj_text):
    def fake(binary, project, script, timeout_s):
        path = re.search(r'script_export_mesh\("([^"]+)"\);', script).group(1)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(obj_text)
        return ScriptResult(ok=True, stdout="", stderr="")
    return fake


def test_check_mesh_uvs_reports_per_object_verdicts(tmp_path):
    project = tmp_path / "p.arm"
    project.write_bytes(b"x")
    bad = QUAD_OBJ.replace("vt 1 1", "vt 1.5 1")
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=_exporting_run(bad)):
        _cfg(mock_cfg)
        result = check_mesh_uvs(str(project))
        relaxed = check_mesh_uvs(str(project), allow_udim=True)

    assert result["ok"] is True and result["error"] is None
    assert result["valid"] is False
    (obj,) = result["objects"]
    assert obj["name"] == "Quad" and obj["valid"] is False
    assert "coverage_pct" in obj["metrics"]
    assert relaxed["valid"] is True


def test_check_mesh_uvs_fails_cleanly_when_the_export_never_appears(tmp_path):
    project = tmp_path / "p.arm"
    project.write_bytes(b"x")
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script",
               return_value=ScriptResult(ok=True, stdout="", stderr="")):
        _cfg(mock_cfg)
        result = check_mesh_uvs(str(project))

    assert result == {"ok": False, "error": result["error"], "valid": None, "objects": None}
    assert "mesh export" in result["error"]


def test_check_mesh_uvs_rejects_a_non_arm_path(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        _cfg(mock_cfg)
        result = check_mesh_uvs(str(tmp_path / "nope.arm"))
    assert result["ok"] is False and result["objects"] is None


def test_check_mesh_uvs_is_registered_as_an_mcp_tool():
    by_name = {t.name: t for t in asyncio.run(mcp.list_tools())}
    tool = by_name["check_mesh_uvs"]
    assert set(tool.input_schema["properties"]) == {"project", "allow_udim", "timeout_s"}
    assert set(tool.input_schema.get("required", [])) == {"project"}
```

In `tests/test_catalog.py::_captured_scripts`, append to `calls`: `lambda: server.check_mesh_uvs(str(project)),`.

- [ ] **Step 2: Run** `& $py -m pytest -q tests/test_server.py tests/test_catalog.py` → FAIL.

- [ ] **Step 3: Implement.** Add `"script_export_mesh",` to `EMITTED_MINIC_FUNCTIONS` under a `# check_mesh_uvs / replace_mesh verification exports` comment. In `server.py` add `import tempfile` and `from armorpaint_mcp import uv_analysis`, then after `inspect_project`'s registration:

```python
def _export_obj(cfg, project: str, out_path: str,
                timeout_s: float) -> tuple[str | None, str | None]:
    """Export `project`'s meshes to `out_path` via script_export_mesh (one
    `o <name>` group per paint object, object-local coordinates -- spike S1)
    and return (text, None), or (None, error)."""
    try:
        target = minic_path_literal(out_path, "export path")
    except NodeSpecError as exc:
        return None, str(exc)
    script = f"void main() {{\n\tscript_export_mesh({target});\n}}\n"
    result = run_minic_script(cfg.binary, project, script, timeout_s)
    if not result.ok:
        return None, result.error
    if not os.path.isfile(out_path):
        return None, "ArmorPaint finished without writing the mesh export"
    with open(out_path, encoding="utf-8", errors="replace") as fh:
        return fh.read(), None


def check_mesh_uvs(project: str, allow_udim: bool = False,
                   timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Read-only UV validity report for every object in an existing .arm
    project. Exports the meshes through ArmorPaint and analyzes the UVs in
    Python (docs/PLAN.md 6.2); makes no changes to the project. Bounded by
    AP_ALLOWED_ROOTS when set.

    Per object, `errors` make `valid` false: faces without UVs, UV-degenerate
    triangles covering more than 0.1% of the 3D surface (paint can't land
    there), and UVs outside [0,1] (a warning instead with allow_udim=True).
    `warnings` are often deliberate: overlapping UVs (stacked/mirrored
    islands) and flipped UV triangles. `metrics` carries the numbers
    (coverage_pct, overlap_pct, flipped_pct, uv_islands, ...). ArmorPaint's
    importer folds UVs above 1 into [0,1] (base/sources/iron_obj.c), so an
    imported project rarely shows out-of-range UVs even if its source had
    them.

    Returns {"ok": bool, "valid": bool | None, "objects": [{"name", "valid",
    "errors", "warnings", "metrics"}] | None, "error": str | None}."""
    cfg = _ensure_ready()
    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "valid", "objects")
    if not _is_arm_project_file(project):
        return _failure(f"'{project}' is not an existing .arm project file",
                        "valid", "objects")
    with tempfile.TemporaryDirectory(prefix="ap-mcp-") as tmp:
        text, error = _export_obj(cfg, project, os.path.join(tmp, "mesh.obj"), timeout_s)
    if error is not None:
        return _failure(error, "valid", "objects")
    obj = uv_analysis.parse_obj(text)
    objects = []
    for name, group in uv_analysis.groups_by_name(obj).items():
        metrics = uv_analysis.analyze(obj, group)
        objects.append({"name": name, **uv_analysis.verdict(metrics, allow_udim),
                        "metrics": metrics})
    return {"ok": True, "valid": all(o["valid"] for o in objects),
            "objects": objects, "error": None}


mcp.tool()(check_mesh_uvs)
```

- [ ] **Step 4: Run** `& $py -m pytest -q` → all pass.

- [ ] **Step 5: Integration test** — create `tests/test_check_mesh_uvs_integration.py`:

```python
"""Real ArmorPaint required.
    .venv\\Scripts\\python.exe -m pytest tests/test_check_mesh_uvs_integration.py -v -m integration
"""
import os

import pytest

from armorpaint_mcp.server import check_mesh_uvs

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.mark.integration
def test_check_mesh_uvs_reports_the_sample_project():
    result = check_mesh_uvs(os.path.join(FIXTURES, "sample_project.arm"))

    assert result["error"] is None
    assert result["ok"] is True
    assert isinstance(result["valid"], bool)
    (obj,) = result["objects"]
    assert obj["name"] == "Tessellated"
    assert obj["metrics"]["coverage_pct"] > 0
    assert obj["metrics"]["faces_without_uv"] == 0


@pytest.mark.integration
def test_check_mesh_uvs_reports_every_object_by_name():
    result = check_mesh_uvs(os.path.join(FIXTURES, "phase6", "objects3.arm"))

    assert result["ok"] is True, result["error"]
    assert sorted(o["name"] for o in result["objects"]) == ["Cone", "Tessellated", "Torus"]
```

Run: `& $py -m pytest -q -m integration tests/test_check_mesh_uvs_integration.py` → 2 passed. Record each object's `valid`/`warnings` from the run in your task report (Task 11 quotes them).

- [ ] **Step 6: Commit**

```powershell
git add src/armorpaint_mcp/server.py src/armorpaint_mcp/catalog.py tests/test_server.py tests/test_catalog.py tests/test_check_mesh_uvs_integration.py; git commit -m "feat: check_mesh_uvs read-only UV validity tool (Phase 6.2)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `replace` module — pre-checks, script builder, state lookups

**Files:**
- Create: `src/armorpaint_mcp/replace.py`
- Modify: `src/armorpaint_mcp/catalog.py` (registry)
- Test: `tests/test_replace.py` (new)

**Interfaces:**
- Consumes: `uv_analysis.parse_obj/analyze/verdict`, `script_gen.minic_string_literal/minic_path_literal/NodeSpecError`.
- Produces (Task 8/9 use these exact names):
  - `REPLACEMENT_FORMATS = ("obj", "fbx", "glb", "gltf", "blend")`, `REPLACED_PLACEHOLDER = "__ap_mcp_replaced__"`, `ERROR_MARKER = "REPLACE_ERR"`.
  - `class ReplaceError(Exception)`.
  - `precheck_replacement(path: str, allow_udim: bool) -> None` (raises `ReplaceError`).
  - `object_names(state: dict) -> list[str]` (paint-object order, from `mesh_datas`).
  - `material_override_name(state: dict, object_name: str) -> str | None` (raises `ReplaceError`).
  - `local_transform(state, name) -> list[float]`; `parent_name(state, name) -> str | None`.
  - `build_replace_script(old_name: str, new_mesh: str, fresh: str, material_name: str | None) -> str` (raises `NodeSpecError` for unusable names/paths).
  - `marker_error(stdout: str) -> str | None` — first `REPLACE_ERR <reason>` line's reason, else None.

- [ ] **Step 1: Failing tests** — create `tests/test_replace.py`:

```python
import os

import pytest

from armorpaint_mcp import replace as rp
from armorpaint_mcp.script_gen import NodeSpecError

GOOD_OBJ = ("o ReplGrid\nv 0 0 0\nv 1 0 0\nv 1 1 0\n"
            "vt 0 0\nvt 1 0\nvt 1 1\nf 1/1 2/2 3/3\n")

STATE = {
    "mesh_datas": [{"name": "Tessellated"}, {"name": "Cone"}, {"name": "Torus"}],
    "mesh_transforms": [[1.0] * 16, [2.0] * 16, [3.0] * 16],
    "mesh_parents[i32]": [-1, 0, -1],
    "mesh_materials[i32]": [-1, 1, -1],
    "material_nodes": [{"name": "Material"}, {"name": "MatB"}],
}


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_precheck_accepts_a_single_object_obj_with_uvs(tmp_path):
    rp.precheck_replacement(_write(tmp_path, "g.obj", GOOD_OBJ), allow_udim=False)


@pytest.mark.parametrize("ext", ["fbx", "glb", "gltf", "blend"])
def test_precheck_accepts_other_native_formats_without_parsing(tmp_path, ext):
    rp.precheck_replacement(_write(tmp_path, f"m.{ext}", "binary"), allow_udim=False)


def test_precheck_rejects_an_unsupported_extension(tmp_path):
    with pytest.raises(rp.ReplaceError, match="stl"):
        rp.precheck_replacement(_write(tmp_path, "m.stl", "x"), allow_udim=False)


def test_precheck_rejects_an_obj_without_uvs(tmp_path):
    no_uv = "o G\nv 0 0 0\nv 1 0 0\nv 1 1 0\nf 1 2 3\n"
    with pytest.raises(rp.ReplaceError, match="no UVs"):
        rp.precheck_replacement(_write(tmp_path, "g.obj", no_uv), allow_udim=False)


def test_precheck_rejects_an_obj_with_two_objects(tmp_path):
    two = GOOD_OBJ + "o Second\nv 5 5 5\nv 6 5 5\nv 5 6 5\nvt 0 0\nvt 1 0\nvt 0 1\nf 4/4 5/5 6/6\n"
    with pytest.raises(rp.ReplaceError, match="2 objects"):
        rp.precheck_replacement(_write(tmp_path, "g.obj", two), allow_udim=False)


def test_precheck_rejects_out_of_range_uvs_unless_allow_udim(tmp_path):
    path = _write(tmp_path, "g.obj", GOOD_OBJ.replace("vt 1 1", "vt 1.5 1"))
    with pytest.raises(rp.ReplaceError, match=r"outside \[0,1\]"):
        rp.precheck_replacement(path, allow_udim=False)
    rp.precheck_replacement(path, allow_udim=True)


def test_state_lookups_follow_mesh_datas_order():
    assert rp.object_names(STATE) == ["Tessellated", "Cone", "Torus"]
    assert rp.local_transform(STATE, "Cone") == [2.0] * 16
    assert rp.parent_name(STATE, "Cone") == "Tessellated"
    assert rp.parent_name(STATE, "Torus") is None
    assert rp.material_override_name(STATE, "Cone") == "MatB"
    assert rp.material_override_name(STATE, "Torus") is None


def test_material_override_fails_closed_on_a_duplicate_material_name():
    dup = dict(STATE, material_nodes=[{"name": "MatB"}, {"name": "MatB"}])
    with pytest.raises(rp.ReplaceError, match="MatB"):
        rp.material_override_name(dup, "Cone")


def test_build_replace_script_shape(tmp_path):
    new_mesh = str(tmp_path / "Program Files (x86)" / "grid.obj")
    fresh = str(tmp_path / "out.ap-mcp-abc.tmp.arm")
    script = rp.build_replace_script("Cone", new_mesh, fresh, "MatB")

    assert script.startswith("void main() {\n")
    assert 'script_get_object("Cone");' in script
    assert f'script_object_set_name(old, "{rp.REPLACED_PLACEHOLDER}");' in script
    assert '"' + new_mesh.replace("\\", "\\\\") + '"' in script      # doubled backslashes
    assert 'script_get_material("MatB");' in script
    body = script.strip().splitlines()
    assert body[-3].strip().startswith("project_filepath_set(")
    assert body[-2].strip() == "project_save(0);"                     # save is last
    assert script.index("script_append_mesh(") < script.index("script_object_remove(old);")


def test_build_replace_script_without_an_override_clears_the_material(tmp_path):
    script = rp.build_replace_script("Torus", str(tmp_path / "g.obj"),
                                     str(tmp_path / "f.arm"), None)
    assert "script_object_set_material(nw, NULL);" in script
    assert "script_get_material" not in script


@pytest.mark.parametrize("bad", ['Co"ne', "Co\\ne"])
def test_build_replace_script_rejects_names_minic_cannot_carry(tmp_path, bad):
    with pytest.raises(NodeSpecError):
        rp.build_replace_script(bad, str(tmp_path / "g.obj"), str(tmp_path / "f.arm"), None)


def test_marker_error_reads_the_first_reason():
    assert rp.marker_error("x\nREPLACE_ERR old_not_found\nREPLACE_ERR other\n") == "old_not_found"
    assert rp.marker_error("Project saved\n") is None
```

- [ ] **Step 2: Run** `& $py -m pytest -q tests/test_replace.py` → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement** — create `src/armorpaint_mcp/replace.py`:

```python
"""Pure-Python pieces of replace_mesh (docs/PLAN.md 6.3): pre-checks, the
minic script, and lookups into ArmorPaint's --api project state. Every
minic statement here was verified against a real build in Phase 6 spikes
S4/S5 (docs/superpowers/spikes/2026-09-27-phase6-spikes-S1-S2-S4-S5.md)."""

import os
import re

from armorpaint_mcp import uv_analysis
from armorpaint_mcp.script_gen import minic_path_literal, minic_string_literal

# Mesh formats this build imports natively: path_mesh_formats() lists obj and
# blend (base/sources/iron_path.c:28-35) and WITH_PLUGINS (paint/project.c:14)
# registers gltf/glb/fbx (paint/plugins/plugins.c:167-172). Not exposed by
# --api, so hardcoded with this citation. Any other extension would reach an
# importer lookup that is called without a NULL check (io/import_mesh.c:39-42).
REPLACEMENT_FORMATS = ("obj", "fbx", "glb", "gltf", "blend")
REPLACED_PLACEHOLDER = "__ap_mcp_replaced__"
ERROR_MARKER = "REPLACE_ERR"


class ReplaceError(Exception):
    """The replacement can't be applied; the message is caller-facing."""


def precheck_replacement(path: str, allow_udim: bool) -> None:
    """Reject a replacement before ArmorPaint launches. Only OBJ can be read
    here: it must hold exactly one object (several `o` groups append several
    objects, io/import_mesh.c:49-57), every face must have UVs (missing ones
    come out as uninitialized memory, io/import_mesh.c:260-263), and UVs must
    stay in [0,1] unless allow_udim (the importer folds larger values,
    base/sources/iron_obj.c:628-638). Other formats are checked after the
    run by replace_mesh's post-verify."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext not in REPLACEMENT_FORMATS:
        raise ReplaceError(f"unsupported mesh format '.{ext}'; this ArmorPaint build "
                           f"imports: {', '.join(REPLACEMENT_FORMATS)}")
    if ext != "obj":
        return
    with open(path, encoding="utf-8", errors="replace") as fh:
        obj = uv_analysis.parse_obj(fh.read())
    groups = [g for g in obj.groups if g.faces]
    if len(groups) != 1:
        raise ReplaceError(f"the replacement OBJ has {len(groups)} objects; it must "
                           f"hold exactly one (each `o` group would become its own object)")
    metrics = uv_analysis.analyze(obj, groups[0])
    if metrics["faces_without_uv"]:
        raise ReplaceError(f"the replacement OBJ has no UVs on {metrics['faces_without_uv']} "
                           f"face(s); UV-unwrap it before replacing")
    if metrics["out_of_range_uvs"] and not allow_udim:
        raise ReplaceError(f"the replacement OBJ has {metrics['out_of_range_uvs']} UV(s) "
                           f"outside [0,1], which ArmorPaint's importer folds; pass "
                           f"allow_udim=True for a UDIM layout")


def object_names(state: dict) -> list[str]:
    """Paint-object names in paint_objects order. Index arrays
    (mesh_transforms, mesh_parents[i32], mesh_materials[i32]) follow this
    order; inspect_project's scene-text list does not once objects are
    parented (spike A, contradiction 6)."""
    return [m.get("name") for m in state.get("mesh_datas") or []]


def _index(state: dict, name: str) -> int:
    names = object_names(state)
    if name not in names:
        raise ReplaceError(f"no object named '{name}' (objects: {', '.join(names)})")
    return names.index(name)


def local_transform(state: dict, name: str) -> list[float]:
    return state["mesh_transforms"][_index(state, name)]


def parent_name(state: dict, name: str) -> str | None:
    parents = state.get("mesh_parents[i32]") or []
    i = _index(state, name)
    p = parents[i] if i < len(parents) else -1
    return None if p < 0 else object_names(state)[p]


def material_override_name(state: dict, object_name: str) -> str | None:
    """The name of `object_name`'s material override, or None if it uses the
    project default (-1). minic can't enumerate materials, so the script
    looks the material up by this name -- which only works if it's unique."""
    mats = state.get("mesh_materials[i32]") or []
    i = _index(state, object_name)
    idx = mats[i] if i < len(mats) else -1
    if idx < 0:
        return None
    nodes = state.get("material_nodes") or []
    name = nodes[idx].get("name")
    if [n.get("name") for n in nodes].count(name) > 1:
        raise ReplaceError(f"'{object_name}' uses material '{name}', but that name isn't "
                           f"unique in the project, so it can't be carried over; rename it")
    return name


def build_replace_script(old_name: str, new_mesh: str, fresh: str,
                         material_name: str | None) -> str:
    """The minic replace-with-carry-over script (spike A's verified snippet):
    rename the old object out of the way, append, move children, remove the
    old object, then restore name, parent, transform and material, and save
    to `fresh` as the LAST statement. Guards print a REPLACE_ERR marker and
    return early (so nothing is saved) if the old object is missing, the
    append silently did nothing (e.g. .blend without ArmorPaint's Blender
    path), or the material lookup doesn't match."""
    old = minic_string_literal(old_name, "old_object")
    placeholder = minic_string_literal(REPLACED_PLACEHOLDER, "placeholder")
    mesh = minic_path_literal(new_mesh, "new_mesh", backslashes=True)
    save_to = minic_path_literal(fresh, "output path")
    err = ERROR_MARKER
    lines = [
        f"object_t *old = script_get_object({old});",
        f'if (old == NULL) {{ console_log("{err} old_not_found"); return; }}',
        "char *oname = string_copy(old->name);",
        "transform_t *ot = old->transform;",
        "float lx = ot->loc.x; float ly = ot->loc.y; float lz = ot->loc.z;",
        "float rx = ot->rot.x; float ry = ot->rot.y; float rz = ot->rot.z; float rw = ot->rot.w;",
        "float sx = ot->scale.x; float sy = ot->scale.y; float sz = ot->scale.z;",
        "object_t *op = old->parent;",
    ]
    if material_name is not None:
        lines += ["mesh_object_t *omo = old->ext;",
                  "char *omat = string_copy(omo->material->name);"]
    lines += [
        f"script_object_set_name(old, {placeholder});",
        "context_t *cx = script_get_context();",
        "mesh_object_t *before = cx->paint_object;",
        f"script_append_mesh({mesh});",
        "mesh_object_t *nmo = cx->paint_object;",
        f'if (nmo == before) {{ console_log("{err} append_failed"); return; }}',
        "object_t *nw = nmo->base;",
        "int nc = old->children->length;",
        "for (int i = 0; i < nc; i++) { object_t *c = old->children->buffer[0]; object_set_parent(c, nw); }",
        "script_object_remove(old);",
        "script_object_set_name(nw, oname);",
        "object_set_parent(nw, op);",
        "transform_t *nt = nw->transform;",
        "nt->loc.x = lx; nt->loc.y = ly; nt->loc.z = lz;",
        "nt->rot.x = rx; nt->rot.y = ry; nt->rot.z = rz; nt->rot.w = rw;",
        "nt->scale.x = sx; nt->scale.y = sy; nt->scale.z = sz;",
        "transform_build_matrix(nt);",
    ]
    if material_name is not None:
        mat = minic_string_literal(material_name, "material name")
        lines += [
            f"slot_material_t *m = script_get_material({mat});",
            f'if (m == NULL) {{ console_log("{err} material_not_found"); return; }}',
            "string_array_t *mk = string_array_create(0);",
            'string_array_push(mk, "_material_"); string_array_push(mk, i32_to_string(m->id));',
            f'if (!string_equals(omat, string_array_join(mk, ""))) {{ console_log("{err} material_ambiguous"); return; }}',
            "script_object_set_material(nw, m);",
        ]
    else:
        lines.append("script_object_set_material(nw, NULL);")
    lines += [f"project_filepath_set({save_to});", "project_save(0);"]
    return "void main() {\n" + "".join(f"\t{line}\n" for line in lines) + "}\n"


_MARKER_RE = re.compile(rf"^{ERROR_MARKER} (\S+)", re.MULTILINE)


def marker_error(stdout: str) -> str | None:
    match = _MARKER_RE.search(stdout or "")
    return match.group(1) if match else None
```

Add to `EMITTED_MINIC_FUNCTIONS` under a `# replace_mesh (replace.build_replace_script)` comment: `"script_get_object", "string_copy", "script_object_set_name", "script_get_context", "script_append_mesh", "object_set_parent", "script_object_remove", "transform_build_matrix", "script_get_material", "string_array_create", "string_array_push", "i32_to_string", "string_equals", "string_array_join", "script_object_set_material", "console_log",`. In `tests/test_catalog.py::_captured_scripts`, before `return`, add:

```python
    from armorpaint_mcp import replace as rp
    scripts += [rp.build_replace_script("Cone", str(tmp_path / "g.obj"), str(tmp_path / "f.arm"), "MatB"),
                rp.build_replace_script("Cone", str(tmp_path / "g.obj"), str(tmp_path / "f.arm"), None)]
```

- [ ] **Step 4: Run** `& $py -m pytest -q` → all pass (the registry test proves the new names are listed).

- [ ] **Step 5: Commit**

```powershell
git add src/armorpaint_mcp/replace.py src/armorpaint_mcp/catalog.py tests/test_replace.py tests/test_catalog.py; git commit -m "feat: replace module (pre-checks, verified minic script, state lookups)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `replace_mesh` tool — run, structural post-verify, commit

**Files:**
- Modify: `src/armorpaint_mcp/server.py` (add `_project_state` helper and `replace_mesh` + registration after `check_mesh_uvs`)
- Test: `tests/test_server.py`, `tests/test_replace_mesh_integration.py` (new)

**Interfaces:**
- Consumes: Task 3 plumbing (`_resolve_edit_target`, `_fresh_sibling`, `_run_saving_script`, `_remove_quietly`), Task 6 `_export_obj`, Task 7 `replace` module, Task 5 `uv_analysis.parse_obj/groups_by_name/group_signature`.
- Produces: `server._project_state(cfg, project, timeout_s) -> tuple[dict | None, str | None]`; tool `replace_mesh(project, old_object, new_mesh, mode="round_trip", allow_udim=False, output_project=None, in_place=False, timeout_s=DEFAULT_TIMEOUT_S) -> {"ok", "output_project", "iou", "retention", "warnings", "error"}`. Task 9 inserts the UV gate at the `# UV gate (Task 9)` line and fills `iou`/`retention`.

- [ ] **Step 1: FIRST integration assertion (the riskiest assumption).** Create `tests/test_replace_mesh_integration.py`:

```python
"""Real ArmorPaint required.
    .venv\\Scripts\\python.exe -m pytest tests/test_replace_mesh_integration.py -v -m integration
"""
import hashlib
import os
import shutil

import pytest

from armorpaint_mcp import replace as rp
from armorpaint_mcp.catalog import extract_project_state
from armorpaint_mcp.config import load_config
from armorpaint_mcp.runner import run_api
from armorpaint_mcp.server import replace_mesh

PHASE6 = os.path.join(os.path.dirname(__file__), "fixtures", "phase6")


def _state(project):
    return extract_project_state(run_api(load_config().binary, project).text)


def _md5(path):
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


@pytest.mark.integration
def test_replace_keeps_name_parent_transform_and_material_with_a_differently_named_mesh(tmp_path):
    """The replacement's `o` name (ReplGrid) differs from the old object's
    (Cone), so this proves mesh_datas names follow script_object_set_name --
    every post-verify lookup is keyed on that."""
    project = os.path.join(PHASE6, "objects3_v4_parented.arm")
    before = _state(project)
    output = str(tmp_path / "out.arm")

    result = replace_mesh(project=project, old_object="Cone",
                          new_mesh=os.path.join(PHASE6, "repl_grid5.obj"),
                          mode="swap", output_project=output)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    after = _state(output)
    assert sorted(rp.object_names(after)) == ["Cone", "Tessellated", "Torus"]
    assert rp.parent_name(after, "Cone") == "Tessellated"
    assert rp.local_transform(after, "Cone") == pytest.approx(rp.local_transform(before, "Cone"), abs=1e-5)
    assert rp.material_override_name(after, "Cone") == "MatB"
    assert len(after["layer_datas"]) == len(before["layer_datas"])
```

- [ ] **Step 2: Failing unit tests** (append to `tests/test_server.py`; add `replace_mesh` to the server import):

```python
STATE_BEFORE = {"mesh_datas": [{"name": "Tessellated"}, {"name": "Cone"}],
                "mesh_transforms": [[1.0] * 16, [2.0] * 16], "mesh_parents[i32]": [-1, -1],
                "mesh_materials[i32]": [-1, -1], "material_nodes": [{"name": "Material"}],
                "layer_datas": [{"name": "Layer"}]}


def test_replace_mesh_rejects_an_unknown_mode(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        _cfg(mock_cfg)
        result = replace_mesh(str(tmp_path / "p.arm"), "Cone", str(tmp_path / "g.obj"),
                              mode="merge", output_project=str(tmp_path / "o.arm"))
    assert result["ok"] is False and "mode" in result["error"]
    assert set(result) == {"ok", "output_project", "iou", "retention", "warnings", "error"}


def test_replace_mesh_rejects_a_missing_old_object_before_launching_the_script(tmp_path):
    project = tmp_path / "p.arm"
    project.write_bytes(b"x")
    mesh = tmp_path / "g.obj"
    mesh.write_text("o G\nv 0 0 0\nv 1 0 0\nv 1 1 0\nvt 0 0\nvt 1 0\nvt 1 1\nf 1/1 2/2 3/3\n")
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server._project_state", return_value=(STATE_BEFORE, None)), \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        _cfg(mock_cfg)
        result = replace_mesh(str(project), "Nope", str(mesh), mode="swap",
                              output_project=str(tmp_path / "o.arm"))
    assert result["ok"] is False and "Nope" in result["error"]
    mock_run.assert_not_called()


def test_replace_mesh_rejects_an_old_object_name_minic_cannot_carry(tmp_path):
    """Review Focus 2."""
    project = tmp_path / "p.arm"
    project.write_bytes(b"x")
    mesh = tmp_path / "g.glb"
    mesh.write_bytes(b"glb")
    state = dict(STATE_BEFORE, mesh_datas=[{"name": "Tessellated"}, {"name": 'Co"ne'}])
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server._project_state", return_value=(state, None)), \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        _cfg(mock_cfg)
        result = replace_mesh(str(project), 'Co"ne', str(mesh), mode="swap",
                              output_project=str(tmp_path / "o.arm"))
    assert result["ok"] is False and "double quote" in result["error"]
    mock_run.assert_not_called()


def test_replace_mesh_turns_a_marker_into_a_readable_error_and_leaves_nothing(tmp_path):
    project = tmp_path / "p.arm"
    project.write_bytes(b"x")
    mesh = tmp_path / "g.blend"
    mesh.write_bytes(b"blend")
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server._project_state", return_value=(STATE_BEFORE, None)), \
         patch("armorpaint_mcp.server._export_obj", return_value=("o Cone\n", None)), \
         patch("armorpaint_mcp.server.run_minic_script",
               return_value=ScriptResult(ok=True, stdout="REPLACE_ERR append_failed\n",
                                         stderr="Blender executable path not set\n")):
        _cfg(mock_cfg)
        result = replace_mesh(str(project), "Cone", str(mesh), mode="swap",
                              output_project=str(tmp_path / "o.arm"))
    assert result["ok"] is False
    assert "append_failed" in result["error"] and "Blender executable path not set" in result["error"]
    assert sorted(os.listdir(tmp_path)) == ["g.blend", "p.arm"]


def test_replace_mesh_is_registered_as_an_mcp_tool():
    by_name = {t.name: t for t in asyncio.run(mcp.list_tools())}
    tool = by_name["replace_mesh"]
    assert set(tool.input_schema["properties"]) == {
        "project", "old_object", "new_mesh", "mode", "allow_udim",
        "output_project", "in_place", "timeout_s"}
    assert set(tool.input_schema.get("required", [])) == {"project", "old_object", "new_mesh"}
```

- [ ] **Step 3: Run** `& $py -m pytest -q tests/test_server.py -k replace_mesh` → FAIL.

- [ ] **Step 4: Implement** in `server.py` (add `from armorpaint_mcp import replace as rp`):

```python
def _project_state(cfg, project: str, timeout_s: float) -> tuple[dict | None, str | None]:
    """(--api project-state JSON, None) or (None, error)."""
    result = run_api(cfg.binary, project, timeout_s)
    if not result.ok:
        return None, result.error
    try:
        return extract_project_state(result.text), None
    except CatalogError as exc:
        return None, str(exc)


_REPLACE_FIELDS = ("output_project", "iou", "retention", "warnings")


def _replace_failure(error: str) -> dict:
    return _failure(error, *_REPLACE_FIELDS)


def replace_mesh(project: str, old_object: str, new_mesh: str, mode: str = "round_trip",
                 allow_udim: bool = False, output_project: str | None = None,
                 in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Replace one object's mesh with `new_mesh` (obj, fbx, glb, gltf, or
    blend -- the last needs ArmorPaint's own Blender path configured),
    keeping every layer, every other object, and the replaced object's name,
    transform, parent, children and material. ArmorPaint's own mesh import
    would clear every layer instead.

    Paint lives in UV space, so it carries over unchanged only if the new
    mesh keeps the old UV layout. mode="round_trip" (default) is for the same
    asset re-exported with edited geometry and UVs kept: it fails unless the
    UV layouts match (UV-coverage IoU >= 0.95 and >= 85% of painted texels
    landing where they were in 3D; warning below 98%). mode="swap" is for a
    different mesh: paint is expected to scramble, and the numbers are
    reported but not enforced. Either way the new mesh must have valid UVs.

    Writes to `output_project` by default (the caller's `project` is never
    modified); in_place=True replaces `project` itself, only after the
    result verifies. Warnings (not failures): a new mesh more than 2x off
    the old one's size (a Blender FBX lands at 100x), UV warnings from
    check_mesh_uvs, and -- on multi-object projects -- that ArmorPaint's
    Reimport Mesh would now reload only `new_mesh` and drop the other
    objects. Bounded by AP_ALLOWED_ROOTS when set.

    Returns {"ok": bool, "output_project": str | None, "iou": float | None,
    "retention": float | None, "warnings": [str] | None, "error": str | None}."""
    if mode not in ("round_trip", "swap"):
        return _replace_failure(f"mode must be 'round_trip' or 'swap', got {mode!r}")
    cfg = _ensure_ready()
    resolved = _resolve_edit_target(project, output_project, in_place, cfg)
    if isinstance(resolved, dict):
        return _replace_failure(resolved["error"])
    project, target = resolved
    try:
        new_mesh = ensure_within_roots(new_mesh, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _replace_failure(str(exc))
    if not os.path.isfile(new_mesh):
        return _replace_failure(f"new_mesh '{new_mesh}' does not exist")
    try:
        rp.precheck_replacement(new_mesh, allow_udim)
    except rp.ReplaceError as exc:
        return _replace_failure(str(exc))

    before, error = _project_state(cfg, project, timeout_s)
    if error is not None:
        return _replace_failure(error)
    fresh = _fresh_sibling(target)
    try:
        names_before = rp.object_names(before)
        material = rp.material_override_name(before, old_object)  # also checks it exists
        script = rp.build_replace_script(old_object, new_mesh, fresh, material)
    except (rp.ReplaceError, NodeSpecError) as exc:
        return _replace_failure(str(exc))

    warnings: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="ap-mcp-") as tmp:
            before_text, error = _export_obj(cfg, project, os.path.join(tmp, "before.obj"), timeout_s)
            if error is not None:
                return _replace_failure(error)
            result = _run_saving_script(cfg, project, script, fresh, timeout_s)
            marker = rp.marker_error(result.stdout)
            if marker is not None:
                detail = (result.stderr or "").strip()
                return _replace_failure(f"replace aborted: {marker}" + (f" ({detail})" if detail else ""))
            if not result.ok:
                return _replace_failure(result.error)
            after, error = _project_state(cfg, fresh, timeout_s)
            if error is not None:
                return _replace_failure(error)
            after_text, error = _export_obj(cfg, fresh, os.path.join(tmp, "after.obj"), timeout_s)
            if error is not None:
                return _replace_failure(error)

        problem = _verify_replace_structure(before, after, names_before, old_object,
                                            before_text, after_text, new_mesh)
        if problem is not None:
            return _replace_failure(f"replace did not verify: {problem}")
        # UV gate (Task 9)
        os.replace(fresh, target)
    except OSError as exc:
        return _replace_failure(f"could not write output_project: {exc}")
    finally:
        _remove_quietly(fresh)
    return {"ok": True, "output_project": target, "iou": None, "retention": None,
            "warnings": warnings, "error": None}


def _verify_replace_structure(before: dict, after: dict, names_before: list[str],
                              old_object: str, before_text: str, after_text: str,
                              new_mesh: str) -> str | None:
    """Everything that must hold after a replace, or a description of the
    first thing that doesn't (docs/PLAN.md 6.3 post-verify)."""
    names_after = rp.object_names(after)
    if rp.REPLACED_PLACEHOLDER in names_after:
        return "the old object is still present (hidden, not removed -- multi-stage project?)"
    if sorted(names_after) != sorted(names_before):
        return f"objects changed from {sorted(names_before)} to {sorted(names_after)}"
    if len(after.get("layer_datas") or []) != len(before.get("layer_datas") or []):
        return "the layer count changed"
    for name in names_before:
        if rp.parent_name(after, name) != rp.parent_name(before, name):
            return f"'{name}' changed parent"
        old_t, new_t = rp.local_transform(before, name), rp.local_transform(after, name)
        if any(abs(a - b) > 1e-4 for a, b in zip(old_t, new_t)):
            return f"'{name}' changed transform"
    if rp.material_override_name(after, old_object) != rp.material_override_name(before, old_object):
        return f"'{old_object}' lost its material"
    before_obj = uv_analysis.parse_obj(before_text)
    after_obj = uv_analysis.parse_obj(after_text)
    before_groups = uv_analysis.groups_by_name(before_obj)
    after_groups = uv_analysis.groups_by_name(after_obj)
    for name in names_before:
        if name == old_object:
            continue
        if (uv_analysis.group_signature(before_obj, before_groups[name])
                != uv_analysis.group_signature(after_obj, after_groups[name])):
            return f"untouched object '{name}' changed geometry"
    replaced = after_groups.get(old_object)
    if replaced is None or not replaced.tri_v:
        return f"'{old_object}' has no geometry after the replace"
    if new_mesh.lower().endswith(".obj"):
        with open(new_mesh, encoding="utf-8", errors="replace") as fh:
            source = uv_analysis.parse_obj(fh.read())
        expected = sum(len(g.tri_v) for g in source.groups)
        if len(replaced.tri_v) != expected:
            return (f"'{old_object}' has {len(replaced.tri_v)} triangles, but the "
                    f"replacement has {expected}")
    return None


mcp.tool()(replace_mesh)
```

- [ ] **Step 5: Run** `& $py -m pytest -q` → all pass.

- [ ] **Step 6: Run the Step 1 integration test.** `& $py -m pytest -q -m integration tests/test_replace_mesh_integration.py` → 1 passed. **If it fails on a name lookup** (e.g. `parent_name` raising "no object named 'Cone'"), stop and report the `mesh_datas` names you saw: it would mean mesh_datas doesn't follow `script_object_set_name`, and every state lookup needs a different key.

- [ ] **Step 7: Commit**

```powershell
git add src/armorpaint_mcp/server.py tests/test_server.py tests/test_replace_mesh_integration.py; git commit -m "feat: replace_mesh with carry-over and structural post-verify (Phase 6.3)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: `replace_mesh` UV gate and warnings

**Files:**
- Modify: `src/armorpaint_mcp/server.py` (`replace_mesh` at the `# UV gate (Task 9)` line; new `_replace_uv_gate`)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `uv_analysis.analyze/verdict/compare_layouts`, the constants `IOU_MIN`, `RETENTION_MIN`, `RETENTION_WARN`.
- Produces: `server._replace_uv_gate(before_text, after_text, old_object, mode, allow_udim, n_objects) -> tuple[dict, str | None]` where the dict is `{"iou", "retention", "warnings"}`; `replace_mesh` returns real `iou`/`retention`/`warnings`.

- [ ] **Step 1: Failing unit tests** (append to `tests/test_server.py`):

```python
from armorpaint_mcp import uv_analysis as ua

UV_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "phase6", "uv")


def _fixture_text(name):
    with open(os.path.join(UV_DIR, f"{name}.obj"), encoding="utf-8") as fh:
        return fh.read()


def test_uv_gate_passes_a_round_trip_and_reports_numbers():
    gate, error = server._replace_uv_gate(_fixture_text("base"), _fixture_text("r5_decimate"),
                                          "Base", "round_trip", False, 1)
    assert error is None
    assert gate["iou"] >= ua.IOU_MIN and gate["retention"] >= ua.RETENTION_MIN


def test_uv_gate_fails_a_re_unwrap_on_iou_in_round_trip_mode():
    gate, error = server._replace_uv_gate(_fixture_text("base"), _fixture_text("d1_smartuv45"),
                                          "Base", "round_trip", False, 1)
    assert error is not None and "IoU" in error


def test_uv_gate_fails_a_coverage_preserving_scramble_on_retention():
    gate, error = server._replace_uv_gate(_fixture_text("base"), _fixture_text("d4_swap"),
                                          "Base", "round_trip", False, 1)
    assert error is not None and "retention" in error


def test_uv_gate_swap_mode_reports_but_does_not_enforce():
    gate, error = server._replace_uv_gate(_fixture_text("base"), _fixture_text("d4_swap"),
                                          "Base", "swap", False, 1)
    assert error is None
    assert gate["retention"] < ua.RETENTION_MIN


def test_uv_gate_warns_about_size_and_reimport_on_multi_object_projects():
    gate, error = server._replace_uv_gate(_fixture_text("base"), _fixture_text("r8_scaled"),
                                          "Base", "swap", False, 3)
    assert error is None
    assert any("Reimport Mesh" in w for w in gate["warnings"])


def test_uv_gate_warns_when_the_replacement_is_far_off_the_old_size():
    scaled = "\n".join(
        ("v " + " ".join(str(float(c) * 100) for c in line.split()[1:4]))
        if line.startswith("v ") else line
        for line in _fixture_text("base").splitlines())
    gate, error = server._replace_uv_gate(_fixture_text("base"), scaled, "Base", "swap", False, 1)
    assert error is None
    assert any("100" in w and "size" in w for w in gate["warnings"])


def test_uv_gate_rejects_invalid_replacement_uvs_in_either_mode():
    no_uv = "o Base\nv 0 0 0\nv 1 0 0\nv 1 1 0\nf 1 2 3\n"
    for mode in ("round_trip", "swap"):
        _, error = server._replace_uv_gate(_fixture_text("base"), no_uv, "Base", mode, False, 1)
        assert error is not None and "no UVs" in error
```

- [ ] **Step 2: Run** `& $py -m pytest -q tests/test_server.py -k uv_gate` → FAIL.

- [ ] **Step 3: Implement.** Add to `server.py` (above `replace_mesh`):

```python
def _replace_uv_gate(before_text: str, after_text: str, old_object: str, mode: str,
                     allow_udim: bool, n_objects: int) -> tuple[dict, str | None]:
    """UV checks on the replaced object: its UVs must be valid (both modes);
    in round_trip mode its layout must match the old one (IoU and texel
    retention, thresholds in uv_analysis). Returns ({"iou", "retention",
    "warnings"}, error-or-None)."""
    before_obj, after_obj = uv_analysis.parse_obj(before_text), uv_analysis.parse_obj(after_text)
    old_g = uv_analysis.groups_by_name(before_obj)[old_object]
    new_g = uv_analysis.groups_by_name(after_obj)[old_object]
    check = uv_analysis.verdict(uv_analysis.analyze(after_obj, new_g), allow_udim)
    if not check["valid"]:
        # before compare_layouts: a UV-less mesh has no rasterizable triangles
        return ({"iou": None, "retention": None, "warnings": list(check["warnings"])},
                "the replacement's UVs are invalid: " + "; ".join(check["errors"]))
    cmp = uv_analysis.compare_layouts(before_obj, old_g, after_obj, new_g)
    gate = {"iou": cmp["iou"], "retention": cmp["retention"], "warnings": list(check["warnings"])}
    ratio = cmp["size_ratio"]
    if ratio and not 0.5 <= ratio <= 2.0:
        gate["warnings"].append(
            f"the new mesh is {ratio:.3g}x the old one's size (a Blender FBX lands at "
            f"100x: check the export's unit scale)")
    if n_objects > 1:
        gate["warnings"].append(
            "ArmorPaint's Reimport Mesh would now reload only the replacement file and "
            "remove the project's other objects")
    if mode == "round_trip":
        if cmp["iou"] < uv_analysis.IOU_MIN:
            return gate, (f"the UV layout changed (IoU {cmp['iou']} < {uv_analysis.IOU_MIN}); "
                          f"the paint would scramble -- use mode='swap' if that's expected")
        retention = cmp["retention"]
        if retention is not None and retention < uv_analysis.RETENTION_MIN:
            return gate, (f"only {retention:.0%} of painted texels would stay in place "
                          f"(retention {retention} < {uv_analysis.RETENTION_MIN}); use "
                          f"mode='swap' if the mesh really changed that much")
        if retention is not None and retention < uv_analysis.RETENTION_WARN:
            gate["warnings"].append(
                f"{1 - retention:.1%} of painted texels move by more than "
                f"{uv_analysis.RETENTION_TOL:.0%} of the object's size")
    return gate, None
```

In `replace_mesh`, replace the `# UV gate (Task 9)` line with:

```python
        gate, problem = _replace_uv_gate(before_text, after_text, old_object, mode,
                                         allow_udim, len(names_before))
        if problem is not None:
            return _replace_failure(f"{problem} (IoU {gate['iou']}, retention {gate['retention']})")
        warnings = gate["warnings"]
```

and change the success return to use `gate["iou"]`, `gate["retention"]`, `warnings`.

- [ ] **Step 4: Run** `& $py -m pytest -q` → all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/armorpaint_mcp/server.py tests/test_server.py; git commit -m "feat: replace_mesh UV gate (IoU + texel retention) and warnings" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Real-ArmorPaint calibration and the `replace_mesh` integration suite

**Files:**
- Create: `scripts/calibrate_uv_gate.py`
- Modify: `tests/test_replace_mesh_integration.py`, possibly `src/armorpaint_mcp/uv_analysis.py` (thresholds, only if calibration says so), `docs/PLAN.md` (record the table)

**Interfaces:**
- Consumes: `replace_mesh`, `run_script`, fixtures under `tests/fixtures/phase6/`.

- [ ] **Step 1: Write the calibration script** `scripts/calibrate_uv_gate.py`:

```python
"""Re-check replace_mesh's round_trip thresholds on REAL ArmorPaint exports
(the S3 spike emulated ArmorPaint's UV quantization; this runs the real
import/export path). Builds a one-object project per base mesh, replaces it
with every committed variant in swap mode, and prints IoU/retention.
Re-run after any AP_BINARY rebuild.

    .venv\\Scripts\\python.exe scripts\\calibrate_uv_gate.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from armorpaint_mcp import uv_analysis as ua  # noqa: E402
from armorpaint_mcp.server import replace_mesh, run_script  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
UV = os.path.join(ROOT, "phase6", "uv")
SETS = {
    "base": ["r1_noise", "r2_subdiv", "r3_bevel", "r4_extrude", "r5_decimate",
             "r5b_decimate_heavy", "r6b_subsurf_smoothall", "r7_bigmove", "r8_scaled",
             "d1_smartuv45", "d2a_lightmap", "d2b_cube", "d3_repack", "d4_swap",
             "d5_rot180", "d6_repack_norot", "d7_smartuv_rerun"],
    "sphere": ["sphere_r1_noise", "sphere_d_mirror", "sphere_d_rot180", "sphere_d_smartuv"],
}


def one_object_project(obj_name: str, out: str) -> str:
    """sample_project.arm + the base mesh appended, the default cube removed."""
    mesh = os.path.abspath(os.path.join(UV, f"{obj_name}.obj")).replace("\\", "\\\\")
    script = ("void main() {\n"
              f'\tscript_append_mesh("{mesh}");\n'
              '\tobject_t *t = script_get_object("Tessellated");\n'
              "\tscript_object_remove(t);\n"
              f'\tproject_filepath_set("{os.path.abspath(out).replace(os.sep, "/")}");\n'
              "\tproject_save(0);\n}\n")
    result = run_script(project=os.path.join(ROOT, "sample_project.arm"), script=script)
    if not result["ok"] or not os.path.isfile(out):
        raise SystemExit(f"could not build {out}: {result['error']}")
    return out


def main() -> int:
    print(f"{'variant':26} {'iou':>7} {'retention':>9}  gate(round_trip)")
    with tempfile.TemporaryDirectory(prefix="ap-mcp-cal-") as tmp:
        for base, variants in SETS.items():
            project = one_object_project(base, os.path.join(tmp, f"{base}.arm"))
            old = "Base" if base == "base" else "Sphere"
            for name in variants:
                r = replace_mesh(project=project, old_object=old,
                                 new_mesh=os.path.join(UV, f"{name}.obj"), mode="swap",
                                 output_project=os.path.join(tmp, f"{name}.arm"),
                                 timeout_s=120)
                if not r["ok"]:
                    print(f"{name:26} FAILED: {r['error']}")
                    continue
                ret = r["retention"]
                passes = r["iou"] >= ua.IOU_MIN and (ret is None or ret >= ua.RETENTION_MIN)
                print(f"{name:26} {r['iou']:7.4f} {ret if ret is None else f'{ret:9.4f}'}  "
                      f"{'pass' if passes else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it** (one ArmorPaint process at a time; it does ~25 replaces, several minutes):
`& $py scripts\calibrate_uv_gate.py`
Expected: every `r*`/`sphere_r1_noise` row `pass`; every `d1`-`d6`/`sphere_d_*` row `FAIL`; `d7` passes (known: a Smart UV rerun is below any texel statistic's resolution). **Specifically check** `sphere_d_mirror`/`sphere_d_rot180` (IoU 1.0, must fail on retention) and `r4_extrude`: with the zero-area rule, `r4_extrude` is expected to come back `FAILED: ... UV-degenerate triangles cover 4.1% ...` (the documented consequence in docs/PLAN.md 6.2). If any row disagrees with these expectations, stop and report the full table: do not move a threshold without Grayson.

- [ ] **Step 3: Record the table** in `docs/PLAN.md` → Phase 6 → "Empirical findings (summary)" as a new bullet `**Real-ArmorPaint calibration (Task 10, <date>)**:` followed by the printed table in a fenced block and one sentence on whether the S3 gap held.

- [ ] **Step 4: Extend the integration suite** (append to `tests/test_replace_mesh_integration.py`):

```python
from armorpaint_mcp.server import run_script

UV = os.path.join(PHASE6, "uv")
SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.fixture(scope="module")
def base_project(tmp_path_factory):
    """One-object project holding tests/fixtures/phase6/uv/base.obj as 'Base'."""
    out = str(tmp_path_factory.mktemp("uv") / "base.arm")
    mesh = os.path.abspath(os.path.join(UV, "base.obj")).replace("\\", "\\\\")
    script = ("void main() {\n"
              f'\tscript_append_mesh("{mesh}");\n'
              '\tobject_t *t = script_get_object("Tessellated");\n'
              "\tscript_object_remove(t);\n"
              f'\tproject_filepath_set("{os.path.abspath(out).replace(os.sep, "/")}");\n'
              "\tproject_save(0);\n}\n")
    result = run_script(project=SAMPLE, script=script)
    assert result["ok"] and os.path.isfile(out), result["error"]
    return out


@pytest.mark.integration
def test_round_trip_accepts_an_edited_mesh_with_kept_uvs(base_project, tmp_path):
    r = replace_mesh(base_project, "Base", os.path.join(UV, "r5_decimate.obj"),
                     output_project=str(tmp_path / "o.arm"))
    assert r["ok"] is True, r["error"]
    assert r["iou"] >= 0.95 and r["retention"] >= 0.85


@pytest.mark.integration
def test_round_trip_rejects_a_re_unwrap_and_writes_nothing(base_project, tmp_path):
    out = tmp_path / "o.arm"
    r = replace_mesh(base_project, "Base", os.path.join(UV, "d1_smartuv45.obj"),
                     output_project=str(out))
    assert r["ok"] is False and "IoU" in r["error"]
    assert not out.exists() and os.listdir(tmp_path) == []


@pytest.mark.integration
def test_round_trip_rejects_an_island_swap_that_iou_cannot_see(base_project, tmp_path):
    r = replace_mesh(base_project, "Base", os.path.join(UV, "d4_swap.obj"),
                     output_project=str(tmp_path / "o.arm"))
    assert r["ok"] is False and "retention" in r["error"]


@pytest.mark.integration
def test_swap_accepts_the_island_swap_and_reports_the_numbers(base_project, tmp_path):
    r = replace_mesh(base_project, "Base", os.path.join(UV, "d4_swap.obj"), mode="swap",
                     output_project=str(tmp_path / "o.arm"))
    assert r["ok"] is True, r["error"]
    assert r["retention"] < 0.85


@pytest.mark.integration
def test_in_place_failure_leaves_the_caller_s_project_byte_identical(base_project, tmp_path):
    project = str(tmp_path / "mine.arm")
    shutil.copy2(base_project, project)
    before = _md5(project)
    r = replace_mesh(project, "Base", os.path.join(UV, "d1_smartuv45.obj"), in_place=True)
    assert r["ok"] is False
    assert _md5(project) == before
    assert os.listdir(tmp_path) == ["mine.arm"]


@pytest.mark.integration
def test_replace_root_with_glb_on_a_multi_object_project_warns_about_reimport(tmp_path):
    r = replace_mesh(os.path.join(PHASE6, "objects3_v2.arm"), "Tessellated",
                     os.path.join(PHASE6, "repl_grid5.glb"), mode="swap",
                     output_project=str(tmp_path / "o.arm"))
    assert r["ok"] is True, r["error"]
    assert any("Reimport Mesh" in w for w in r["warnings"])


@pytest.mark.integration
def test_fbx_from_blender_is_accepted_with_a_size_warning(tmp_path):
    r = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "Cone",
                     os.path.join(PHASE6, "repl_grid5.fbx"), mode="swap",
                     output_project=str(tmp_path / "o.arm"))
    assert r["ok"] is True, r["error"]
    assert any("size" in w for w in r["warnings"])


@pytest.mark.integration
def test_blend_without_armorpaint_blender_path_fails_closed(tmp_path):
    out = tmp_path / "o.arm"
    r = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "Cone",
                     os.path.join(PHASE6, "repl_grid5.blend"), mode="swap",
                     output_project=str(out))
    if r["ok"]:
        pytest.skip("ArmorPaint's Blender path is configured on this machine")
    assert "append_failed" in r["error"]
    assert not out.exists()


@pytest.mark.integration
def test_obj_without_uvs_and_multi_object_obj_are_rejected_before_launch(tmp_path):
    no_uv = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "Cone",
                         os.path.join(PHASE6, "repl_grid5_nouv.obj"), mode="swap",
                         output_project=str(tmp_path / "a.arm"))
    assert no_uv["ok"] is False and "no UVs" in no_uv["error"]
    two = tmp_path / "two.obj"
    grid = open(os.path.join(PHASE6, "repl_grid5.obj"), encoding="utf-8").read()
    two.write_text(grid + "\no Second\nv 9 9 9\nv 10 9 9\nv 9 10 9\nvt 0 0\nvt 1 0\nvt 0 1\n"
                   "f -3/-3 -2/-2 -1/-1\n", encoding="utf-8")
    multi = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "Cone", str(two),
                         mode="swap", output_project=str(tmp_path / "b.arm"))
    assert multi["ok"] is False and "2 objects" in multi["error"]


@pytest.mark.integration
def test_wrong_old_name_fails_and_writes_nothing(tmp_path):
    out = tmp_path / "o.arm"
    r = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "NoSuchObject",
                     os.path.join(PHASE6, "repl_grid5.obj"), mode="swap",
                     output_project=str(out))
    assert r["ok"] is False and "NoSuchObject" in r["error"]
    assert not out.exists()


@pytest.mark.integration
def test_output_directory_is_created(tmp_path):
    out = tmp_path / "new" / "deeper" / "o.arm"
    r = replace_mesh(os.path.join(PHASE6, "objects3.arm"), "Cone",
                     os.path.join(PHASE6, "repl_grid5.obj"), mode="swap",
                     output_project=str(out))
    assert r["ok"] is True, r["error"]
    assert out.is_file()
```

- [ ] **Step 5: Run** `& $py -m pytest -q -m integration tests/test_replace_mesh_integration.py` → all pass (the `.blend` test may skip). Fix code, not tests, if a structural assertion fails — then rerun Task 8's unit tests.

- [ ] **Step 6: Commit**

```powershell
git add scripts/calibrate_uv_gate.py tests/test_replace_mesh_integration.py docs/PLAN.md src/armorpaint_mcp/uv_analysis.py; git commit -m "test: real-ArmorPaint UV-gate calibration and replace_mesh integration suite" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Smoke probes, docs, full regression, gate record

**Files:**
- Modify: `smoke/smoke.ps1`, `README.md`, `STATUS.md`, `ROADMAP.md`, `docs/PLAN.md`
- Test: full suite

- [ ] **Step 1: Smoke probes.** In `smoke/smoke.ps1`, after the Phase 5 block add:

```powershell
# Phase 6: UV check + mesh replace, registered on the MCP server object.
Probe "check_mesh_uvs registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'check_mesh_uvs' in names, names; print(names)" }
Probe "replace_mesh registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'replace_mesh' in names, names; print(names)" }
```

Run `pwsh smoke/smoke.ps1` (with `PYTHONPATH` set) → `15 passed, 0 failed`, exit 0.

- [ ] **Step 2: Full regression** (serially):
  - `& $py -m pytest -q` → record the pass count.
  - `& $py -m pytest -q -m integration` → record the pass/skip count.
  - `& $py -m armorpaint_mcp.server --check` → exit 0, `minic API` row PASS.

- [ ] **Step 3: README.** Add `check_mesh_uvs` and `replace_mesh` to the tool list (one paragraph each, paraphrasing their docstrings: purpose, modes, formats, the `.blend`/FBX caveats), and a line that script errors now fail tools instead of returning `ok=True`.

- [ ] **Step 4: STATUS.md.**
  - Phase Gates table: add row `| 6 | Rename hardening (stdout abort detection, --check over every emitted minic name), Known Issues #10/#11 fixed, check_mesh_uvs, replace_mesh | ✅ <date> | <pytest counts>; <integration counts>; smoke 15/15; --check green; calibration table in docs/PLAN.md |`.
  - Add a "Current Phase Detail (Phase 6)" table: one ✅ row per new/changed file with its test evidence.
  - Known Issues #10 and #11: strike the title and append `**FIXED <date>** in <commit>` with the evidence (the backslash integration test; the cross-directory asset test).
  - Update the "Open phase" line: Phase 6 gate green; Phase 7 (draft) next, not approved.

- [ ] **Step 5: ROADMAP.md.** Items 8 and 10: `✅ shipped (Phase 6)`. PLAN.md: change the Phase 6 heading to `## Phase 6 (APPROVED 2026-09-27, ✅ GATE GREEN <date>)`.

- [ ] **Step 6: Commit**

```powershell
git add smoke/smoke.ps1 README.md STATUS.md ROADMAP.md docs/PLAN.md; git commit -m "docs: record Phase 6 gate (smoke 15/15, full regression green)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
