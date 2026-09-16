# Phase 4 — `run_script` escape hatch + docs/packaging polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `run_script(project, script)` — the last tool in the v1 scope
(an escape hatch for anything `reexport_project`/`create_procedural_material`/
`inspect_project` don't cover) — and close out the project's v1 docs/packaging
polish, per `docs/PLAN.md`'s Phase 4.

**Architecture:** `runner.run_minic_script(binary, project, script_text,
timeout_s)` writes `script_text` to a temp `.c` file and launches
`ArmorPaint.exe <project> --background --script <file>` via
`subprocess.run(..., timeout=timeout_s)` — **no poll-and-terminate loop**,
unlike every other tool in this project. This is a deliberate, empirically
confirmed departure from the established pattern (see "Empirical findings"
below). `server.run_script` wraps it with the same `AP_ALLOWED_ROOTS`
sandboxing and phantom-default-project guard `inspect_project` already uses.

**Tech Stack:** Python 3.13, `subprocess`, `tempfile`, `pytest` (unit +
`-m integration`), PowerShell (clean-clone check), matches every prior phase.

**Spec:** [docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](../../superpowers/specs/2026-09-15-armorpaint-mcp-design.md)
(`run_script` tool description, "Error handling" timeout convention).
Phase scope: [docs/PLAN.md](../../PLAN.md) Phase 4 section.

## Empirical findings (2026-09-16, this planning session)

Confirmed hands-on against the real local ArmorPaint build (`z-Git\ArmorPaint`,
`paint\build\out\ArmorPaint.exe`) before writing this plan, not assumed from
source reading alone — matching this project's established convention:

1. **`--background` + `--script <path>` against a REAL opened project (a
   project path passed positionally, not `script_project_new()`) self-exits
   cleanly and correctly runs the script.** Spiked with
   `tests/fixtures/sample_project.arm` + a script that calls
   `script_fill_layer(); export_texture_run(<dir>, 0);` directly against the
   already-open project (no `script_project_new()`): `returncode == 0`,
   elapsed ~1.2s, and all 5 expected `sample_project_*.png` files landed on
   disk. This is a **materially different result** from Amendment 1's finding
   that `--background` + `--export-textures` is broken: reading
   `paint/sources/args.c`, `args_run_script`'s `minic_eval()` call is
   synchronous within the frame it runs on, and only *after* it returns does
   `args_run_script_stop` (which calls `iron_stop()`) get scheduled for the
   *next* frame — so by the time the process is told to stop, the script has
   already fully executed. `args_run_export_queue`'s export, by contrast, is
   itself deferred to the next frame, so `iron_stop()` (scheduled from the
   *same* callback that scheduled the export) can race ahead of it. Different
   mechanism, different outcome.
2. **Consequence: `run_script` needs no poll-and-terminate loop.** Every
   other tool in this project launches without `--background`, polls an
   output directory for expected files, then terminates the still-running GUI
   process — because either the operation's own async/broken timing needs it
   (`export_textures`) or because a fresh `script_project_new()` project has
   nothing to open first, so the same-process poll pattern was simplest
   (`run_procedural_material`). `run_script`'s job is exactly one already-open
   project plus one script; `subprocess.run(..., timeout=...)` is the whole
   implementation — closer to `run_api`'s shape than to the export tools'.
3. **minic gives no diagnostic signal for a script runtime error.** A script
   that calls a nonexistent function (`this_function_does_not_exist();`)
   exits with the exact same `returncode == 0`, empty stdout, empty stderr as
   a script that runs perfectly. This matches the silent-failure behavior
   Phase 2's spiking already found for minic's curated struct access (design
   spec Amendment 2) — it's a property of minic generally, not something new
   to work around, but it means `run_script`'s `ok: True` can only ever mean
   "the ArmorPaint process completed," never "the script did what the caller
   intended." The docstring and this plan's tests make that limitation
   explicit rather than letting the return shape imply more than it can
   promise.

## Global Constraints

- No source patching, no custom ArmorPaint rebuild (CLAUDE.md, design spec).
- Dynamic catalogs, not hardcoded enums, for anything that needs one — not
  applicable to this phase (`run_script` has no catalog surface).
- Mutating operations default to a copy of the source project unless the
  caller opts in — not applicable here: `run_script` never saves a project
  (the opened project's in-memory state is discarded when the process exits;
  nothing this tool does persists back to the `.arm` file on disk), so there
  is no in-place-mutation risk to guard against the way `rebake_and_export`
  would have needed to (that tool was dropped from scope entirely — see
  `docs/PLAN.md` Phase 2's rescoping history).
- Secrets/paths come from env, never hardcoded.
- `AP_ALLOWED_ROOTS` enforced on every path before it reaches the subprocess
  (design spec "Safety").
- Gate rule: this is the last phase in `docs/PLAN.md` — no Phase 5 to defer
  to; the final task's gate must leave the project's v1 scope genuinely done.

---

### Task 1: `runner.run_minic_script`

**Files:**
- Modify: `src/armorpaint_mcp/runner.py` (add `ScriptResult` dataclass +
  `run_minic_script` function, after `run_api` and before `_presets_dir`)
- Test: `tests/test_runner.py` (add tests after the existing `run_api` tests)

**Interfaces:**
- Consumes: nothing new from earlier tasks (module already has
  `subprocess`, `tempfile`, `os`, `DEFAULT_TIMEOUT_S`).
- Produces: `ScriptResult(ok: bool, stdout: str, stderr: str, error: str |
  None = None)` and `run_minic_script(binary: str, project: str, script_text:
  str, timeout_s: float = DEFAULT_TIMEOUT_S) -> ScriptResult` — Task 2's
  `server.run_script` imports and calls both.

- [ ] **Step 1: Commit the plan document**

This plan was written before any implementation — commit it now so it isn't
lost the way Phase 3's plan doc almost was (see `docs/PLAN.md`'s Phase 3
history / HANDOFF.md's "loose, uncommitted working copy" lesson).

```bash
git add docs/superpowers/plans/2026-09-16-phase4-run-script.md
git commit -m "docs: add Phase 4 implementation plan (run_script + polish)"
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_runner.py`, after the existing `test_run_api_reports_timeout`
function (around line 563) and adjust the top-of-file import line to also
import `run_minic_script`:

```python
from armorpaint_mcp.runner import (
    expected_output_files,
    export_textures,
    list_export_presets,
    preset_texture_names,
    run_api,
    run_minic_script,
    run_procedural_material,
)
```

```python
def test_run_minic_script_returns_stdout_on_success(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    project = tmp_path / "project.arm"
    project.write_text("")

    with patch("armorpaint_mcp.runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = run_minic_script(str(binary), str(project), "void main() {}")

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == str(binary)
    assert args[1] == str(project)
    assert "--background" in args
    assert "--script" in args
    assert result.ok is True
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.error is None


def test_run_minic_script_writes_the_given_script_text(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    project = tmp_path / "project.arm"
    project.write_text("")
    written = {}

    def fake_run(args, **kwargs):
        script_path = args[args.index("--script") + 1]
        with open(script_path, encoding="utf-8") as fh:
            written["content"] = fh.read()
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("armorpaint_mcp.runner.subprocess.run", side_effect=fake_run):
        run_minic_script(str(binary), str(project), "void main() { /* marker */ }")

    assert written["content"] == "void main() { /* marker */ }"


def test_run_minic_script_cleans_up_tempfile_even_on_failure(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    project = tmp_path / "project.arm"
    project.write_text("")
    captured = {}

    def fake_run(args, **kwargs):
        captured["script_path"] = args[args.index("--script") + 1]
        return MagicMock(returncode=1, stdout="", stderr="boom")

    with patch("armorpaint_mcp.runner.subprocess.run", side_effect=fake_run):
        run_minic_script(str(binary), str(project), "void main() {}")

    assert not os.path.exists(captured["script_path"])


def test_run_minic_script_reports_nonzero_exit(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    project = tmp_path / "project.arm"
    project.write_text("")

    with patch("armorpaint_mcp.runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
        result = run_minic_script(str(binary), str(project), "void main() {}")

    assert result.ok is False
    assert result.stdout == ""
    assert result.stderr == "boom"
    assert "boom" in result.error


def test_run_minic_script_reports_timeout(tmp_path):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_text("")
    project = tmp_path / "project.arm"
    project.write_text("")

    with patch("armorpaint_mcp.runner.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="x", timeout=5.0)):
        result = run_minic_script(str(binary), str(project), "void main() {}",
                                  timeout_s=5.0)

    assert result.ok is False
    assert "timed out after 5.0s" in result.error
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest -q tests/test_runner.py -k run_minic_script -v`
Expected: FAIL with `ImportError: cannot import name 'run_minic_script'`

- [ ] **Step 4: Implement `run_minic_script`**

In `src/armorpaint_mcp/runner.py`, add after the `run_api` function (after
line 81, before the `_presets_dir` function at line 84):

```python
@dataclass
class ScriptResult:
    ok: bool
    stdout: str
    stderr: str
    error: str | None = None


def run_minic_script(binary: str, project: str, script_text: str,
                     timeout_s: float = DEFAULT_TIMEOUT_S) -> ScriptResult:
    """Run `script_text` (minic/.c source) against `project` via ArmorPaint's
    `--script` flag, then let the process exit on its own.

    Unlike export_textures/run_procedural_material, this launches WITH
    --background and needs no poll-and-terminate: confirmed empirically
    (2026-09-16) that --background + --script against a REAL opened project
    self-exits cleanly (~1-2s) and runs the script correctly (a
    script_fill_layer()+export_texture_run() script produced real output
    files). This is NOT the same combination Amendment 1 found broken --
    that was --background + --export-textures, where iron_stop() could race
    ahead of a deferred export. Here, args_run_script's minic_eval() runs
    synchronously in the same frame callback, and iron_stop() is only
    scheduled a full frame after minic_eval() has already returned -- see
    paint/sources/args.c's args_run_script/args_run_script_stop.

    IMPORTANT: minic gives no diagnostic signal for a script runtime error --
    confirmed empirically that calling an undefined function exits 0 with
    empty stdout/stderr, identical to a script that ran perfectly (the same
    kind of minic silent-failure Phase 2's spiking found for curated struct
    access -- see the design spec's Amendment 2). So ok=True here means only
    "the ArmorPaint process completed" -- it is NOT proof the script did what
    it was supposed to do. Callers should verify results independently (e.g.
    check that expected output files appeared, or call inspect_project
    afterward).

    Never raises for a normal script-didn't-work failure -- that's
    ScriptResult(ok=False, ...)."""
    fd, script_path = tempfile.mkstemp(suffix=".c")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(script_text)

        try:
            proc = subprocess.run(
                [binary, project, "--background", "--script", script_path],
                capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return ScriptResult(ok=False, stdout="", stderr="", error=(
                f"'--script' timed out after {timeout_s}s -- outcome "
                f"uncertain, inspect the project directly"))
    finally:
        os.unlink(script_path)

    if proc.returncode != 0:
        detail = f": {proc.stderr.strip()}" if proc.stderr and proc.stderr.strip() else ""
        return ScriptResult(ok=False, stdout=proc.stdout, stderr=proc.stderr,
                            error=f"'--script' exited {proc.returncode}{detail}")
    return ScriptResult(ok=True, stdout=proc.stdout, stderr=proc.stderr)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest -q tests/test_runner.py -v`
Expected: PASS (all existing + 5 new tests)

- [ ] **Step 6: Commit**

```bash
git add src/armorpaint_mcp/runner.py tests/test_runner.py
git commit -m "feat: add runner.run_minic_script (Phase 4 foundation)"
```

---

### Task 2: `server.run_script` MCP tool

**Files:**
- Modify: `src/armorpaint_mcp/server.py` (import `run_minic_script`, add
  `run_script` tool function after `inspect_project`, register it)
- Modify: `smoke/smoke.ps1` (add registration probe)
- Test: `tests/test_server.py` (add tests after the existing `inspect_project`
  tests)

**Interfaces:**
- Consumes: `run_minic_script(binary, project, script_text, timeout_s) ->
  ScriptResult` (Task 1), `ensure_within_roots`/`PathNotAllowed` (existing,
  from `armorpaint_mcp.paths`), `_ensure_ready()` (existing module-level
  helper).
- Produces: `run_script(project: str, script: str) -> dict` registered as an
  MCP tool named `"run_script"`, returning `{"ok": bool, "stdout": str |
  None, "stderr": str | None, "error": str | None}`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_server.py`, after `test_inspect_project_registered_as_mcp_tool`
(the last function, currently ending the file), and update the top-of-file
import to also pull in `run_script`:

```python
from armorpaint_mcp.server import (mcp, reexport_project, create_procedural_material,
                                   list_available_presets, inspect_project, run_script)
```

Also add `ScriptResult` to the existing `from armorpaint_mcp.runner import
ExportResult, ApiResult` line, making it `ExportResult, ApiResult, ScriptResult`.

```python
def test_run_script_rejects_path_outside_allowed_roots(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside_project = tmp_path / "elsewhere" / "project.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = [str(root)]
        result = run_script(project=str(outside_project), script="void main() {}")

    assert result["ok"] is False
    assert result["stdout"] is None
    assert "allowed" in result["error"]


def test_run_script_rejects_nonexistent_project_path(tmp_path):
    """Same phantom-default-project trap inspect_project guards against
    (Phase 3 Finding 2): a bogus project path would otherwise make
    ArmorPaint silently run the caller's script against its own empty
    default project instead of failing."""
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = run_script(project=str(tmp_path / "does_not_exist.arm"),
                            script="void main() {}")

    assert result["ok"] is False
    assert result["stdout"] is None
    assert "not an existing .arm project file" in result["error"]


def test_run_script_rejects_existing_file_with_wrong_extension(tmp_path):
    not_arm = tmp_path / "README.md"
    not_arm.write_text("not a project")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = run_script(project=str(not_arm), script="void main() {}")

    assert result["ok"] is False
    assert "not an existing .arm project file" in result["error"]


def test_run_script_calls_runner_and_returns_result(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run.return_value = ScriptResult(ok=True, stdout="out", stderr="")

        result = run_script(project=str(project), script="void main() {}")

    assert result == {"ok": True, "stdout": "out", "stderr": "", "error": None}
    mock_run.assert_called_once_with(
        mock_cfg.return_value.binary, str(project), "void main() {}")


def test_run_script_nulls_stdout_stderr_on_runner_failure(tmp_path):
    project = tmp_path / "project.arm"
    project.write_bytes(b"fake")

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_minic_script") as mock_run:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run.return_value = ScriptResult(ok=False, stdout="partial",
                                             stderr="err", error="'--script' exited 1: err")

        result = run_script(project=str(project), script="void main() {}")

    assert result == {"ok": False, "stdout": None, "stderr": None,
                       "error": "'--script' exited 1: err"}


def test_run_script_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())

    by_name = {t.name: t for t in tools}
    assert "run_script" in by_name, sorted(by_name)
    tool = by_name["run_script"]
    assert set(tool.input_schema["properties"]) == {"project", "script"}
    assert set(tool.input_schema.get("required", [])) == {"project", "script"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest -q tests/test_server.py -k run_script -v`
Expected: FAIL with `ImportError: cannot import name 'run_script'`

- [ ] **Step 3: Implement the tool**

In `src/armorpaint_mcp/server.py`, change the runner import line (line 12)
from:

```python
from armorpaint_mcp.runner import export_textures, list_export_presets, run_api, run_procedural_material
```

to:

```python
from armorpaint_mcp.runner import (export_textures, list_export_presets, run_api,
                                   run_minic_script, run_procedural_material)
```

Then add, after the `inspect_project` function and its `mcp.tool()(inspect_project)`
line (after line 187), before the `_USAGE` block:

```python
def run_script(project: str, script: str) -> dict:
    """Escape hatch: run an arbitrary minic script against an existing .arm
    project via ArmorPaint's own --script flag, for anything the
    purpose-built tools (reexport_project, create_procedural_material,
    inspect_project) don't cover yet. `script` is minic (.c) source text --
    written to a temp file and passed via --script, never executed as
    arbitrary OS-level code (minic is ArmorPaint's own curated scripting
    surface registered in minic_api_list.h, not a general-purpose language).
    Same trust level as this project's other tools -- not gated behind an
    extra opt-in flag.

    IMPORTANT: ArmorPaint gives no diagnostic signal for a script runtime
    error (confirmed empirically -- calling an undefined function exits 0
    with empty output, identical to success). ok=True here means only "the
    ArmorPaint process completed", not "the script did what you expected" --
    verify results yourself (e.g. check that expected output files appeared,
    or call inspect_project afterward). Bounded by AP_ALLOWED_ROOTS when set.
    Returns {"ok": bool, "stdout": str | None, "stderr": str | None,
    "error": str | None}."""
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

    result = run_minic_script(cfg.binary, project, script)
    return {"ok": result.ok,
            "stdout": result.stdout if result.ok else None,
            "stderr": result.stderr if result.ok else None,
            "error": result.error}


mcp.tool()(run_script)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest -q tests/test_server.py -v`
Expected: PASS (all existing + 6 new tests)

- [ ] **Step 5: Add the smoke probe**

In `smoke/smoke.ps1`, after the `inspect_project` probe line (line 49), add:

```powershell
Probe "run_script registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'run_script' in names, names; print(names)" }
```

- [ ] **Step 6: Run the smoke harness**

Run: `pwsh smoke/smoke.ps1`
Expected: exit 0, all probes `[PASS]` including the new one.

- [ ] **Step 7: Commit**

```bash
git add src/armorpaint_mcp/server.py tests/test_server.py smoke/smoke.ps1
git commit -m "feat: register run_script as an MCP tool"
```

---

### Task 3: Real integration test

**Files:**
- Test: `tests/test_run_script_integration.py` (new)

**Interfaces:**
- Consumes: `run_script(project, script) -> dict` (Task 2), the existing
  `tests/fixtures/sample_project.arm` fixture (Phase 1).
- Produces: nothing new for later tasks — this is the phase's real-binary
  gate evidence.

- [ ] **Step 1: Write the integration test**

Create `tests/test_run_script_integration.py`:

```python
"""Real ArmorPaint required. Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_run_script_integration.py -v
(needs AP_BINARY set to a working build -- see .env.example)
"""
import os

import pytest

from armorpaint_mcp.server import run_script

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_run_script_fills_and_exports_the_already_open_project(tmp_path):
    """Confirmed empirically during Phase 4 planning (2026-09-16): a script
    that calls script_fill_layer() + export_texture_run() directly (no
    script_project_new()) against a project opened via the positional CLI
    argument produces real output files named after that project, not
    ArmorPaint's 'untitled' fallback -- proof --script genuinely operates on
    the caller's own project, not a fresh throwaway one."""
    out_dir = str(tmp_path).replace("\\", "/")
    script = (
        "void main() {\n"
        "\tscript_fill_layer();\n"
        f'\texport_texture_run("{out_dir}", 0);\n'
        "}\n"
    )

    result = run_script(project=FIXTURE, script=script)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True

    exported = sorted(os.listdir(tmp_path))
    expected = sorted(f"sample_project_{n}.png"
                      for n in ["base", "metal", "nor", "occ", "rough"])
    assert exported == expected


@pytest.mark.integration
def test_run_script_ok_true_does_not_prove_the_script_succeeded(tmp_path):
    """Documents the real, confirmed minic limitation this tool's docstring
    warns about: a script calling an undefined function exits 0 with no
    error, indistinguishable from success by return value alone."""
    result = run_script(project=FIXTURE,
                        script="void main() {\n\tthis_function_does_not_exist();\n}\n")

    assert result["ok"] is True
    assert result["error"] is None
```

- [ ] **Step 2: Run the integration test against the real binary**

Run (with `AP_BINARY` set to the real local build):
```
$env:AP_BINARY = "C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe"
.venv\Scripts\python.exe -m pytest -q -m integration tests/test_run_script_integration.py -v
```
Expected: 2 passed. If the first test fails on file names, the real
`generic` preset's texture-name list may differ from `["base", "metal",
"nor", "occ", "rough"]` on this install -- reconcile the assertion against
what actually lands on disk (matching `GENERIC_NAMES` in `tests/test_runner.py`)
rather than forcing the test to pass.

- [ ] **Step 3: Run the full test suite to confirm no regressions**

Run: `.venv\Scripts\python.exe -m pytest -q -m integration`
Expected: PASS, including Phase 1/2/3's existing integration tests.

- [ ] **Step 4: Commit**

```bash
git add tests/test_run_script_integration.py
git commit -m "test: add real-binary integration coverage for run_script"
```

---

### Task 4: Docs/packaging polish

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nothing code-level from earlier tasks — describes what they
  shipped.
- Produces: nothing later tasks import; Task 5's clean-clone check exercises
  the `pyproject.toml` change.

- [ ] **Step 1: Update `README.md`'s intro paragraph**

In `README.md`, replace the intro paragraph (lines 3-12) to mention
`run_script`:

```markdown
An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant
batch-drive [ArmorPaint](https://armorpaint.org) — re-export existing
projects at different presets, build small procedural materials
(checker/solid node graphs built, rendered, and exported in a single pass),
inspect an existing project's objects, materials, and layers, and run
arbitrary minic scripts against a project for anything the purpose-built
tools don't cover — without opening the GUI for each pass. Mesh-detail
rebaking and swapping texture sets into an existing project are structurally
unreachable on this ArmorPaint build (no CLI or scripting path exists for
either) and are permanently out of scope — see [STATUS.md](STATUS.md)'s
Known Issues for the specifics.
```

- [ ] **Step 2: Update the `## Status` line**

Replace line 20-21:

```markdown
**Pre-alpha, Phase 3 (inspect_project shipped).** See [docs/PLAN.md](docs/PLAN.md)
for the phase plan and [STATUS.md](STATUS.md) for the gate ledger.
```

with:

```markdown
**Alpha — v1 tool surface complete (Phase 4: `run_script` shipped).** All
five planned tools (`reexport_project`, `create_procedural_material`,
`list_available_presets`, `inspect_project`, `run_script`) are implemented,
tested, and gated. See [docs/PLAN.md](docs/PLAN.md) for the phase plan and
[STATUS.md](STATUS.md) for the gate ledger. Live/interactive "live mode" is
deferred, not shipped — see the design spec's "Deferred: live mode" section.
```

- [ ] **Step 3: Add a `run_script` mention to "How it works"**

Append one sentence to the end of the "## How it works" section (after line
62):

```markdown
The escape-hatch tool, `run_script`, hands the caller's own minic source
straight to `--script` against an already-open project — for the cases the
four purpose-built tools above don't cover.
```

- [ ] **Step 4: Bump the packaging classifier**

In `pyproject.toml`, change:

```toml
    "Development Status :: 2 - Pre-Alpha",
```

to:

```toml
    "Development Status :: 3 - Alpha",
```

(v1's full planned tool surface is now implemented and gate-verified — still
pre-1.0 and not yet broadly used outside this machine, so "Alpha" is
accurate; "Beta" would overclaim before any use beyond this project's own
verification.)

- [ ] **Step 5: Commit**

```bash
git add README.md pyproject.toml
git commit -m "docs: README/packaging polish for Phase 4 (run_script, v1 complete)"
```

---

### Task 5: Final verification sweep + STATUS.md/HANDOFF.md

**Files:**
- Modify: `STATUS.md`
- Modify: `HANDOFF.md`

**Interfaces:**
- Consumes: everything from Tasks 1-4.
- Produces: the phase's recorded gate evidence — nothing downstream in code.

- [ ] **Step 1: Run the full unit + integration suite**

Run:
```
.venv\Scripts\python.exe -m pytest -q
$env:AP_BINARY = "C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe"
.venv\Scripts\python.exe -m pytest -q -m integration
```
Expected: both green, no regressions in Phase 0-3's existing tests. Record
the exact pass counts for `STATUS.md`.

- [ ] **Step 2: Run the smoke harness**

Run: `pwsh smoke/smoke.ps1`
Expected: exit 0, every probe `[PASS]` including `run_script registered as an
MCP tool`.

- [ ] **Step 3: Clean-clone install check**

This is Phase 4's own gate requirement from `docs/PLAN.md` ("a clean-clone
install + `ap-mcp --check` + smoke test all pass with no undocumented manual
steps") — run it against the actually-committed tree, after Tasks 1-4 have
landed:

```powershell
$CleanDir = Join-Path $env:TEMP "ap-mcp-clean-clone-check"
Remove-Item -Recurse -Force $CleanDir -ErrorAction SilentlyContinue
git clone C:\Projects-local\Tool-ArmorPaintMCP $CleanDir
Push-Location $CleanDir
python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install -e .
& ".venv\Scripts\ap-mcp.exe" --version
& ".venv\Scripts\ap-mcp.exe" --help
& ".venv\Scripts\ap-mcp.exe" --check
Pop-Location
```

Expected: `pip install -e .` succeeds with no errors, `--version`/`--help`
exit 0, `--check` runs and prints its red/green checklist (it will report
red for `AP_BINARY` since the clean clone has no `.env` — that is a correct,
honest result for a fresh clone with no config, not a failure of this check;
the check confirms `ap-mcp --check` runs and reports clearly, not that
config happens to be present). Record the transcript in `STATUS.md`. Clean
up: `Remove-Item -Recurse -Force $CleanDir`.

- [ ] **Step 4: Update STATUS.md**

Add a Phase 4 row to the Phase Gates table (after the Phase 3 row, replacing
the current `⬜` placeholder):

```markdown
| 4 | `run_script` escape hatch + docs/packaging polish | ✅ 2026-09-16 | `smoke/smoke.ps1`: 6/6 passed, exit 0 (`run_script registered as an MCP tool` probe passing); `.venv\Scripts\python.exe -m pytest -q`: <N> passed, 0 failed, <M> deselected; `-m integration`: <K> passed, 0 failed (all prior phases' integration tests plus the two new run_script tests, no regressions); clean-clone check (`git clone` to a scratch dir, `pip install -e .`, `ap-mcp --version`/`--help`/`--check`) all exit as expected with no undocumented manual steps. |
```

(Fill in the exact `<N>`/`<M>`/`<K>` counts from Step 1's real output before
committing -- never write placeholder numbers into STATUS.md.)

Add a "Current Phase Detail (Phase 4)" section (mirroring the existing Phase
1-3 sections' shape) after the Phase 3 detail table:

```markdown
## Current Phase Detail (Phase 4)

| Item / File | State | Notes |
|---|---|---|
| `src/armorpaint_mcp/runner.py` (`run_minic_script`) | ✅ | subprocess.run with --background + --script against an already-open project; confirmed empirically to self-exit cleanly and run correctly, no poll-and-terminate needed (see docs/superpowers/plans/2026-09-16-phase4-run-script.md's "Empirical findings") |
| `src/armorpaint_mcp/server.py` (`run_script`) | ✅ | registered as an MCP tool (smoke probe passing); same AP_ALLOWED_ROOTS sandboxing and phantom-default-project guard as inspect_project; end-to-end real calls verified by tests/test_run_script_integration.py |
```

- [ ] **Step 5: Update HANDOFF.md**

Rewrite the "🎯 Current state", "📌 Where we stopped", "▶️ Next concrete
step", and "🕓 Session log" sections to reflect Phase 4 shipping (mirroring
the structure of the existing 2026-09-16 entry). The "Next concrete step"
section should note that Phase 4 was the last phase in `docs/PLAN.md`, so
the natural next steps are either the deferred cleanup items (the four
Minor findings noted in the prior HANDOFF entry, if still unaddressed) or
live mode (deferred, not rejected, per the design spec) -- not a further
numbered phase, since none remain.

- [ ] **Step 6: Commit**

```bash
git add STATUS.md HANDOFF.md
git commit -m "docs: close out Phase 4 gate evidence -- run_script shipped, v1 tool surface complete"
```
