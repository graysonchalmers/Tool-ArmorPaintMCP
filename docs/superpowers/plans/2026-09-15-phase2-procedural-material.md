# Phase 2 — `create_procedural_material` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `create_procedural_material` MCP tool that builds a small
procedural material (a checker pattern or a flat color) on a fresh default
ArmorPaint project and exports the result — proving Phase 2's rescoped
"procedural material authoring" capability end to end.

**Architecture:** A new `script_gen.py` module turns a small, whitelisted
`node_spec` dict into a complete minic script (build one node → connect it
to the material output → `script_fill_layer()` → `export_texture_run()`).
A new `runner.py` function, `run_procedural_material`, writes that script
to a temp file, launches `ArmorPaint.exe --script <file>` (no
`--background` — untested with real GPU rendering in that mode, and Phase
1's convention is to avoid it for anything that renders or exports),
reuses Phase 1's proven fingerprint-and-poll completion detection, and
terminates the process once every expected file has been freshly written.
`server.py` wires this up as `create_procedural_material`, plus a small
bonus tool, `list_available_presets`, exposing Phase 1's already-tested
`list_export_presets` helper that was never registered.

**Tech Stack:** Python 3.13, official `mcp` SDK, pytest (`integration`
marker for real-ArmorPaint tests), Pillow (new dev-only dependency, for the
integration test's pixel-content check).

---

## Why this phase looks like this (read before starting)

Phase 2 was originally scoped as `rebake_and_export`. Hands-on spiking
against the real local ArmorPaint build (2026-09-15) found that scope
rests on capabilities that don't exist here — full writeup in
`docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md`'s "Amendment
2" and `docs/PLAN.md`'s Phase 2 section. Two short version:

1. Mesh-detail baking is a GUI-button-only `static` C function — no
   script/CLI path exists.
2. Reading `project_t->assets->length` (needed to know which combo-index a
   newly-imported texture-set asset occupies) silently aborts minic script
   execution — minic's struct access is curated, not general C.
3. **What does work:** building a material node graph via
   `script_material_create_node_at`/`connect`/`set_float`/`set_color`,
   rendering it into the paint layer via `script_fill_layer()`, and
   exporting via `export_texture_run(path, bake_material)` — all
   minic-registered, all confirmed with real spikes producing a correct,
   UV-masked checker-pattern PNG. **The catch:** this only works within a
   single ArmorPaint process. Building the graph, saving to `.arm`, and
   exporting via a *second* process (Phase 1's `reexport_project` pattern)
   silently produces flat, unpainted output — verified with two separate
   spikes that both failed through the save/reload path and both
   succeeded through the same-process path.

That's why this phase's tool is a single `--script` invocation that does
graph-build + fill + export together, not a two-step
"author-then-reexport" pipeline.

**v1 scope is deliberately narrow (YAGNI):** exactly two node types,
`"checker"` and `"solid"`, each a single node wired straight to
`OUTPUT_MATERIAL_PBR`'s Base Color input. This is not a general node-graph
DSL — that's future scope, tracked as an open item, not this phase's job.

---

## Task 1: Extract the shared poll-and-terminate helper in `runner.py`

Pure refactor, no behavior change. `export_textures` and the new
`run_procedural_material` (Task 4) both need to: poll until every expected
file has been freshly (re)written, terminate the ArmorPaint process no
matter what, and build the same `ExportResult` shape either way. Right now
that logic lives inline inside `export_textures`. Extracting it first
means Task 4 doesn't duplicate ~30 lines of subtle polling logic.

**Files:**
- Modify: `src/armorpaint_mcp/runner.py:152-204`

- [ ] **Step 1: Confirm the full existing test suite passes before touching anything**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runner.py -v`
Expected: all tests in the file PASS (this is the baseline the refactor
must not break).

- [ ] **Step 2: Extract `_poll_and_terminate` and rewrite `export_textures` to use it**

Replace lines 152-204 of `src/armorpaint_mcp/runner.py` (the current
`export_textures` function) with:

```python
def _poll_and_terminate(proc: subprocess.Popen, expected: list[str],
                        before: dict[str, tuple[int, int]], timeout_s: float,
                        preset: str, output_dir: str) -> ExportResult:
    """Poll `expected` until every file has been freshly (re)written since
    `before`, or `timeout_s` elapses -- then terminate `proc` unconditionally
    (it does not self-exit) and report the outcome. Shared by every caller
    that launches an ArmorPaint process and waits for preset-defined files to
    land: the completion rule (fingerprint-before, require-change,
    confirm-stable) and the uncertain-outcome error message are identical
    regardless of how the process was launched."""
    deadline = time.monotonic() + timeout_s
    complete = False
    try:
        while time.monotonic() < deadline:
            fresh = _written_by_this_run(expected, before)
            if fresh is None:
                time.sleep(POLL_INTERVAL_S)
                continue
            # Every expected file has been (re)written and is non-empty.
            # Confirm the last writes have landed by re-reading once.
            time.sleep(POLL_INTERVAL_S)
            if _written_by_this_run(expected, before) == fresh:
                complete = True
                break
    finally:
        stderr = _terminate(proc)

    if not complete:
        written = [p for p in expected
                   if _fingerprint(p) not in (None, before.get(p))]
        unwritten = [p for p in expected if p not in written]
        detail = f": {stderr.strip()}" if stderr and stderr.strip() else ""
        return ExportResult(ok=False, files=written, error=(
            f"export outcome uncertain: after {timeout_s}s, "
            f"{len(unwritten)} of {len(expected)} file(s) preset '{preset}' should "
            f"write were not written by this run (missing, empty, or unchanged) "
            f"in '{output_dir}': "
            f"{', '.join(os.path.basename(p) for p in unwritten) or 'none'}"
            f"{detail}"))
    return ExportResult(ok=True, files=expected)


def export_textures(binary: str, project: str, texture_type: str, preset: str,
                     output_dir: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> ExportResult:
    """Launch ArmorPaint against `project` and export textures at `preset`.
    Returns ExportResult(ok, files, error). Never raises for a normal
    export-didn't-happen failure -- that's ExportResult(ok=False, ...)."""
    os.makedirs(output_dir, exist_ok=True)

    try:
        expected = expected_output_files(binary, project, texture_type, preset,
                                          output_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Fail before spawning a GUI process we'd have no way to judge.
        return ExportResult(ok=False, files=[], error=(
            f"could not determine which files preset '{preset}' exports: {exc}"))

    before = _snapshot(expected)
    proc = subprocess.Popen(
        [binary, project, "--export-textures", texture_type, preset, output_dir],
        # stdout is never read during the poll; an unread PIPE could fill the
        # OS buffer and deadlock a long export. stderr IS read and reported.
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    return _poll_and_terminate(proc, expected, before, timeout_s, preset, output_dir)
```

This is a pure extraction: `_poll_and_terminate`'s body is exactly what
used to be inline in `export_textures` (same variable names, same logic,
same error message), so behavior is identical.

- [ ] **Step 3: Confirm the full existing test suite still passes, unchanged**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runner.py -v`
Expected: the exact same tests PASS as in Step 1 — no new tests were
added or removed in this task, and none should have changed outcome.

- [ ] **Step 4: Commit**

```bash
git add src/armorpaint_mcp/runner.py
git commit -m "refactor: extract shared poll-and-terminate helper in runner.py"
```

---

## Task 2: `script_gen.py` — minic script generation from a node spec

**Files:**
- Create: `src/armorpaint_mcp/script_gen.py`
- Test: `tests/test_script_gen.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_script_gen.py`:

```python
import pytest

from armorpaint_mcp.script_gen import generate_script, NodeSpecError


def test_generate_script_checker_includes_expected_calls():
    script = generate_script(
        {"type": "checker", "params": {"scale": 8.0,
                                        "color1": [1.0, 0.0, 0.0],
                                        "color2": [0.0, 0.0, 1.0]}},
        "C:/out/dir",
    )

    assert "void main() {" in script
    assert script.rstrip().endswith("}")
    assert 'script_material_create_node_at("TEX_CHECKER", -400.0, 0.0)' in script
    assert 'script_material_get_node("OUTPUT_MATERIAL_PBR")' in script
    assert "script_material_set_color(src, 1, 1, 1.0, 0.0, 0.0, 1.0);" in script
    assert "script_material_set_color(src, 1, 2, 0.0, 0.0, 1.0, 1.0);" in script
    assert "script_material_set_float(src, 1, 3, 8.0);" in script
    assert "script_material_connect(src, 0, out, 0);" in script
    assert "script_fill_layer();" in script
    assert 'export_texture_run("C:/out/dir", 0);' in script
    # fill must happen before export, and node setup before the connect
    assert script.index("script_fill_layer();") < script.index("export_texture_run")
    assert script.index("script_material_connect") < script.index("script_fill_layer();")


def test_generate_script_checker_uses_defaults_when_params_omitted():
    script = generate_script({"type": "checker"}, "C:/out")

    assert "script_material_set_float(src, 1, 3, 5.0);" in script
    assert "script_material_set_color(src, 1, 1, 0.8, 0.8, 0.8, 1.0);" in script
    assert "script_material_set_color(src, 1, 2, 0.2, 0.2, 0.2, 1.0);" in script


def test_generate_script_solid_includes_expected_calls():
    script = generate_script(
        {"type": "solid", "params": {"color": [0.1, 0.2, 0.3]}}, "C:/out")

    assert 'script_material_create_node_at("RGB", -400.0, 0.0)' in script
    assert "script_material_set_color(src, 0, 0, 0.1, 0.2, 0.3, 1.0);" in script
    assert "script_material_connect(src, 0, out, 0);" in script
    assert "script_fill_layer();" in script
    assert 'export_texture_run("C:/out", 0);' in script


def test_generate_script_solid_uses_default_color_when_omitted():
    script = generate_script({"type": "solid"}, "C:/out")

    assert "script_material_set_color(src, 0, 0, 0.8, 0.8, 0.8, 1.0);" in script


def test_generate_script_rejects_unknown_node_type():
    with pytest.raises(NodeSpecError, match="unsupported node_spec type 'glow'"):
        generate_script({"type": "glow"}, "C:/out")


def test_generate_script_rejects_missing_type_key():
    with pytest.raises(NodeSpecError, match="must be a dict with a 'type' key"):
        generate_script({"params": {}}, "C:/out")


def test_generate_script_rejects_non_dict_node_spec():
    with pytest.raises(NodeSpecError, match="must be a dict"):
        generate_script("checker", "C:/out")


def test_generate_script_rejects_bad_color_shape():
    with pytest.raises(NodeSpecError, match="color1.*3 numbers"):
        generate_script({"type": "checker", "params": {"color1": [1.0, 0.0]}},
                         "C:/out")


def test_generate_script_rejects_non_numeric_scale():
    with pytest.raises(NodeSpecError, match="scale must be a number"):
        generate_script({"type": "checker", "params": {"scale": "big"}}, "C:/out")


def test_generate_script_normalizes_windows_backslashes():
    script = generate_script({"type": "solid"}, r"C:\out\dir")

    assert 'export_texture_run("C:/out/dir", 0);' in script
    assert "\\o" not in script  # no literal backslash made it into the script


def test_generate_script_rejects_path_containing_double_quote():
    with pytest.raises(NodeSpecError, match="double-quote"):
        generate_script({"type": "solid"}, 'C:/out/"; system("evil"); //')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_script_gen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'armorpaint_mcp.script_gen'`

- [ ] **Step 3: Write the implementation**

Create `src/armorpaint_mcp/script_gen.py`:

```python
"""Generates minic scripts for procedural material authoring.

v1 supports exactly two node types -- "checker" and "solid" -- each a
single node wired straight to OUTPUT_MATERIAL_PBR's Base Color input
(socket 0). This is deliberately narrow (YAGNI): a general multi-node
graph DSL is future scope, not this phase's job -- see docs/PLAN.md's
Phase 2 section for why the scope stops here.

Every generated script does the same four things in order: create a fresh
default project, build the one node the spec asks for and connect it to
the output, render it into the paint layer (script_fill_layer), and export
(export_texture_run) -- all inside a single ArmorPaint process. That
ordering is load-bearing: see the design spec's Amendment 2 for why a
save-then-reexport split silently loses the rendered pixels.
"""


class NodeSpecError(Exception):
    """`node_spec` is malformed or requests an unsupported node type."""


def _number(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NodeSpecError(f"{name} must be a number, got {value!r}")
    return float(value)


def _color3(name: str, value) -> tuple[float, float, float]:
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(isinstance(c, bool) or not isinstance(c, (int, float)) for c in value)):
        raise NodeSpecError(f"{name} must be a [r, g, b] list of 3 numbers, got {value!r}")
    return tuple(float(c) for c in value)


def _checker_node_lines(params: dict) -> list[str]:
    scale = _number("scale", params.get("scale", 5.0))
    r1, g1, b1 = _color3("color1", params.get("color1", [0.8, 0.8, 0.8]))
    r2, g2, b2 = _color3("color2", params.get("color2", [0.2, 0.2, 0.2]))
    return [
        '\tui_node_t *src = script_material_create_node_at("TEX_CHECKER", -400.0, 0.0);',
        f'\tscript_material_set_color(src, 1, 1, {r1}, {g1}, {b1}, 1.0);',
        f'\tscript_material_set_color(src, 1, 2, {r2}, {g2}, {b2}, 1.0);',
        f'\tscript_material_set_float(src, 1, 3, {scale});',
        '\tscript_material_connect(src, 0, out, 0);',
    ]


def _solid_node_lines(params: dict) -> list[str]:
    r, g, b = _color3("color", params.get("color", [0.8, 0.8, 0.8]))
    return [
        '\tui_node_t *src = script_material_create_node_at("RGB", -400.0, 0.0);',
        f'\tscript_material_set_color(src, 0, 0, {r}, {g}, {b}, 1.0);',
        '\tscript_material_connect(src, 0, out, 0);',
    ]


_NODE_BUILDERS = {
    "checker": _checker_node_lines,
    "solid": _solid_node_lines,
}


def _output_dir_literal(output_dir: str) -> str:
    """Render `output_dir` as a minic double-quoted string literal. minic
    (matching the rest of ArmorPaint's own path handling) wants forward
    slashes even on Windows, so backslashes are normalized first -- that is
    the normal, expected transformation for every real Windows path this
    receives, not something to reject. A literal double-quote is rejected
    outright rather than escaped: it is the one character that could break
    out of the string literal into the surrounding script, and no real
    filesystem path legitimately contains one."""
    normalized = output_dir.replace("\\", "/")
    if '"' in normalized:
        raise NodeSpecError(
            f"output_dir cannot be safely embedded in a minic script "
            f"(contains a double-quote): {output_dir!r}")
    return f'"{normalized}"'


def generate_script(node_spec: dict, output_dir: str) -> str:
    """Build the complete minic script text for `node_spec`, which exports
    to `output_dir` when run. Raises NodeSpecError for a malformed or
    unsupported node_spec, or an output_dir that can't be safely embedded
    in the generated script."""
    if not isinstance(node_spec, dict) or "type" not in node_spec:
        raise NodeSpecError(
            f"node_spec must be a dict with a 'type' key, got {node_spec!r}")
    node_type = node_spec["type"]
    builder = _NODE_BUILDERS.get(node_type)
    if builder is None:
        raise NodeSpecError(
            f"unsupported node_spec type '{node_type}'; supported: "
            f"{', '.join(sorted(_NODE_BUILDERS))}")
    node_lines = builder(node_spec.get("params", {}))

    lines = [
        "void main() {",
        "\tscript_project_new();",
        '\tui_node_t *out = script_material_get_node("OUTPUT_MATERIAL_PBR");',
        *node_lines,
        "\tscript_fill_layer();",
        f"\texport_texture_run({_output_dir_literal(output_dir)}, 0);",
        "}",
        "",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_script_gen.py -v`
Expected: all 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/armorpaint_mcp/script_gen.py tests/test_script_gen.py
git commit -m "feat: add minic script generator for procedural materials"
```

---

## Task 3: `run_procedural_material` in `runner.py`

**Files:**
- Modify: `src/armorpaint_mcp/runner.py`
- Test: `tests/test_runner.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_runner.py` (add this import at the top alongside the
existing `from armorpaint_mcp.runner import (...)` block — extend that
same import statement rather than adding a second one):

```python
from armorpaint_mcp.runner import (
    expected_output_files,
    export_textures,
    list_export_presets,
    preset_texture_names,
    run_procedural_material,
)
```

Then append these tests to the end of the file:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runner.py -v -k procedural`
Expected: FAIL with `ImportError: cannot import name 'run_procedural_material'`

- [ ] **Step 3: Write the implementation**

Add `import tempfile` to the top of `src/armorpaint_mcp/runner.py`'s
import block (alongside the existing `glob`, `json`, `os`, `subprocess`,
`time`, `dataclasses` imports), then append this function at the end of
the file, after `export_textures`:

```python
def run_procedural_material(binary: str, script_text: str, output_dir: str,
                            preset: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> ExportResult:
    """Launch ArmorPaint with `script_text` as a --script file (no
    --background: untested with real GPU rendering in that mode, and this
    project's convention is to avoid it for anything that renders or
    exports -- see the module docstring) and export at `preset`.

    This flow never saves a project, so ArmorPaint names every file after
    "untitled" (export_texture.c falls back to that name when
    ui_files_filename is empty) -- expected_output_files is called with a
    synthetic "untitled.arm" project name so the derived filenames match
    exactly what ArmorPaint will actually write.

    Returns ExportResult(ok, files, error). Never raises for a normal
    export-didn't-happen failure."""
    os.makedirs(output_dir, exist_ok=True)

    try:
        expected = expected_output_files(binary, "untitled.arm", "png", preset,
                                          output_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ExportResult(ok=False, files=[], error=(
            f"could not determine which files preset '{preset}' exports: {exc}"))

    before = _snapshot(expected)

    fd, script_path = tempfile.mkstemp(suffix=".c")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(script_text)

        proc = subprocess.Popen(
            [binary, "--script", script_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        return _poll_and_terminate(proc, expected, before, timeout_s, preset,
                                   output_dir)
    finally:
        os.unlink(script_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runner.py -v`
Expected: all tests PASS (both the pre-existing ones and the 6 new
`run_procedural_material` tests)

- [ ] **Step 5: Commit**

```bash
git add src/armorpaint_mcp/runner.py tests/test_runner.py
git commit -m "feat: add run_procedural_material to launch a script and export in one process"
```

---

## Task 4: Wire `create_procedural_material` and `list_available_presets` into `server.py`

**Files:**
- Modify: `src/armorpaint_mcp/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server.py` (add `create_procedural_material` and
`list_available_presets` to the existing
`from armorpaint_mcp.server import mcp, reexport_project` line so it
reads `from armorpaint_mcp.server import (mcp, reexport_project, create_procedural_material, list_available_presets)`):

```python
def test_create_procedural_material_returns_error_for_unknown_preset(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets", return_value=["generic"]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = create_procedural_material(
            node_spec={"type": "checker"},
            output_dir=str(tmp_path / "out"),
            preset="not_a_real_preset",
        )

    assert result["ok"] is False
    assert "not_a_real_preset" in result["error"]
    assert "generic" in result["error"]


def test_create_procedural_material_rejects_path_outside_allowed_roots(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside_dir = tmp_path / "elsewhere" / "out"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets", return_value=["generic"]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = [str(root)]
        result = create_procedural_material(
            node_spec={"type": "checker"},
            output_dir=str(outside_dir),
            preset="generic",
        )

    assert result["ok"] is False
    assert "allowed roots" in result["error"]


def test_create_procedural_material_rejects_invalid_node_spec(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets", return_value=["generic"]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        result = create_procedural_material(
            node_spec={"type": "not_a_real_type"},
            output_dir=str(tmp_path / "out"),
            preset="generic",
        )

    assert result["ok"] is False
    assert "unsupported node_spec type" in result["error"]


def test_create_procedural_material_calls_runner_and_returns_files(tmp_path):
    output_dir = tmp_path / "out"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets", return_value=["generic"]), \
         patch("armorpaint_mcp.server.run_procedural_material") as mock_run:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run.return_value = ExportResult(
            ok=True, files=[str(output_dir / "untitled_base.png")])

        result = create_procedural_material(
            node_spec={"type": "solid", "params": {"color": [1.0, 0.0, 0.0]}},
            output_dir=str(output_dir), preset="generic")

    assert result == {"ok": True, "files": [str(output_dir / "untitled_base.png")],
                       "error": None}
    mock_run.assert_called_once()
    call_args = mock_run.call_args.args
    assert call_args[0] == mock_cfg.return_value.binary
    assert "script_material_create_node_at(\"RGB\"" in call_args[1]
    assert call_args[2] == str(output_dir)
    assert call_args[3] == "generic"


def test_create_procedural_material_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())

    by_name = {t.name: t for t in tools}
    assert "create_procedural_material" in by_name, sorted(by_name)
    tool = by_name["create_procedural_material"]
    assert set(tool.input_schema["properties"]) == {"node_spec", "output_dir", "preset"}
    assert set(tool.input_schema.get("required", [])) == {"node_spec", "output_dir"}


def test_list_available_presets_returns_presets_dict(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.list_export_presets",
               return_value=["generic", "unity"]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")

        result = list_available_presets()

    assert result == {"presets": ["generic", "unity"]}


def test_list_available_presets_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())

    by_name = {t.name: t for t in tools}
    assert "list_available_presets" in by_name, sorted(by_name)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -v -k "procedural or available_presets"`
Expected: FAIL with `ImportError: cannot import name 'create_procedural_material'`

- [ ] **Step 3: Write the implementation**

In `src/armorpaint_mcp/server.py`, change the runner import line (line 9)
from:

```python
from armorpaint_mcp.runner import export_textures, list_export_presets
```

to:

```python
from armorpaint_mcp.runner import export_textures, list_export_presets, run_procedural_material
from armorpaint_mcp.script_gen import generate_script, NodeSpecError
```

Then, after the `mcp.tool()(reexport_project)` line (line 62), add:

```python
def create_procedural_material(node_spec: dict, output_dir: str,
                               preset: str = "generic") -> dict:
    """Build a small procedural material -- {"type": "checker", "params":
    {"scale": float, "color1": [r,g,b], "color2": [r,g,b]}} or {"type":
    "solid", "params": {"color": [r,g,b]}}, all params optional -- on a
    fresh default project and export it at `preset`. Everything happens in
    one ArmorPaint process (build the graph, render it into the paint
    layer, export): saving to .arm and exporting separately does not
    preserve the rendered pixels on this build -- see docs/PLAN.md's
    Phase 2 section. Bounded by AP_ALLOWED_ROOTS when set. Returns
    {"ok": bool, "files": [str] | None, "error": str | None}."""
    cfg = _ensure_ready()

    available = list_export_presets(cfg.binary)
    if preset not in available:
        return {"ok": False, "files": None,
                "error": f"unknown preset '{preset}'; available: {', '.join(available)}"}

    try:
        output_dir = ensure_within_roots(output_dir, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return {"ok": False, "files": None, "error": str(exc)}

    try:
        script_text = generate_script(node_spec, output_dir)
    except NodeSpecError as exc:
        return {"ok": False, "files": None, "error": str(exc)}

    result = run_procedural_material(cfg.binary, script_text, output_dir, preset)
    return {"ok": result.ok, "files": result.files if result.ok else None,
            "error": result.error}


mcp.tool()(create_procedural_material)


def list_available_presets() -> dict:
    """List the export preset names available from the connected
    ArmorPaint install (<binary_dir>/data/export_presets/*.json) -- for
    picking a `preset` value for reexport_project or
    create_procedural_material without guessing. Returns
    {"presets": [str]}."""
    cfg = _ensure_ready()
    return {"presets": list_export_presets(cfg.binary)}


mcp.tool()(list_available_presets)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -v`
Expected: all tests PASS (pre-existing `reexport_project` tests plus the
7 new tests)

- [ ] **Step 5: Run the full unit suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all tests PASS, 0 failures (still excludes `integration`-marked
tests per `pyproject.toml`'s `addopts`)

- [ ] **Step 6: Commit**

```bash
git add src/armorpaint_mcp/server.py tests/test_server.py
git commit -m "feat: register create_procedural_material and list_available_presets MCP tools"
```

---

## Task 5: Real integration test against the actual ArmorPaint build

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/test_create_procedural_material_integration.py`

- [ ] **Step 1: Add Pillow as a dev dependency**

Pillow is needed to decode the exported PNG and check it's genuinely
painted (not a flat single color) — a real content check, not just
file-existence, matching Phase 1's own integration test rigor. It's a
test-only need, not a runtime dependency of the MCP server itself, so it
goes in the `dev` extra.

In `pyproject.toml`, change:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0.0"]
```

to:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pillow>=10.0.0"]
```

Then install it:

Run: `.venv\Scripts\python.exe -m pip install "pillow>=10.0.0"`
Expected: installs successfully (it's already present transitively in
this `.venv`, so this should be near-instant)

- [ ] **Step 2: Write the integration test**

Create `tests/test_create_procedural_material_integration.py`:

```python
# tests/test_create_procedural_material_integration.py
"""Real ArmorPaint required. Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_create_procedural_material_integration.py -v
(needs AP_BINARY set to a working build -- see .env.example)
"""
import pytest
from PIL import Image

from armorpaint_mcp.server import create_procedural_material


@pytest.mark.integration
def test_checker_material_produces_a_genuinely_painted_texture(tmp_path):
    output_dir = tmp_path / "out"

    result = create_procedural_material(
        node_spec={"type": "checker", "params": {"scale": 8.0}},
        output_dir=str(output_dir),
        preset="generic",
    )

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    assert len(result["files"]) == 5  # base, nor, occ, rough, metal

    base_color_file = next(f for f in result["files"] if f.endswith("_base.png"))
    image = Image.open(base_color_file).convert("RGB")
    sampled_colors = {
        image.getpixel((x, y))
        for x in (0, image.width // 4, image.width // 2, image.width - 1)
        for y in (0, image.height // 4, image.height // 2, image.height - 1)
    }
    # A checker pattern samples to at least two distinct colors across the
    # image (some sample points may land on transparent/unpainted UV gaps,
    # which is expected -- the point is proving it's not a single flat
    # color everywhere, the exact failure mode this phase spent a session
    # debugging).
    assert len(sampled_colors) > 1, (
        f"expected a genuinely painted checker pattern, got a single "
        f"uniform color across all sample points: {sampled_colors}")
```

- [ ] **Step 3: Run the integration test**

Run: `.venv\Scripts\python.exe -m pytest tests/test_create_procedural_material_integration.py -v`
Expected: PASS (this launches the real ArmorPaint binary — allow ~15-20
seconds)

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml tests/test_create_procedural_material_integration.py
git commit -m "test: add real-ArmorPaint integration test for create_procedural_material"
```

---

## Task 6: Gallery update — real procedural output on GitHub

The user explicitly wants visible proof of new capabilities landing on
GitHub, not just passing tests (same requirement Phase 1's gallery task
satisfied). This task runs the new tool for real, captures a visually
distinct example, and updates the README to match.

**Files:**
- Create: `docs/images/gallery/procedural_checker_base.png` (binary, copied
  from a real run — see Step 1)
- Modify: `README.md`

- [ ] **Step 1: Generate the example image**

Run this from the project root (adjust the output path only if
`AP_ALLOWED_ROOTS` in your `.env` restricts where output can land):

```bash
.venv\Scripts\python.exe -c "from armorpaint_mcp.server import create_procedural_material; import json; print(json.dumps(create_procedural_material(node_spec={'type': 'checker', 'params': {'scale': 8.0, 'color1': [0.85, 0.2, 0.2], 'color2': [0.1, 0.1, 0.15]}}, output_dir='docs/images/gallery/_tmp_procedural', preset='generic')))"
```

Expected: prints a JSON object with `"ok": true` and 5 file paths under
`docs/images/gallery/_tmp_procedural/`.

- [ ] **Step 2: Copy the base-color output into the gallery and remove the scratch directory**

```powershell
Copy-Item docs\images\gallery\_tmp_procedural\untitled_base.png docs\images\gallery\procedural_checker_base.png
Remove-Item -Recurse -Force docs\images\gallery\_tmp_procedural
```

- [ ] **Step 3: Open the image and confirm it looks right**

Visually confirm `docs/images/gallery/procedural_checker_base.png` shows a
real red/dark checker pattern across the UV-mapped faces of the default
cube-bevel mesh (not flat gray — flat gray means something regressed;
stop and investigate rather than committing it if so).

- [ ] **Step 4: Update the README Gallery section**

In `README.md`, after the existing Gallery table (the one comparing
`generic`/`unreal` presets, right before the `## How it works` heading),
add:

```markdown

Real procedural output from `create_procedural_material` (Phase 2) — a
checker-pattern node graph built, rendered, and exported in a single
ArmorPaint process, on the default cube-bevel primitive:

![procedural checker material, base color export](docs/images/gallery/procedural_checker_base.png)
```

Also update the `## Status` line near the top of `README.md` from:

```markdown
**Pre-alpha, Phase 1 (`reexport_project` shipped).** See [docs/PLAN.md](docs/PLAN.md)
```

to:

```markdown
**Pre-alpha, Phase 2 (`create_procedural_material` shipped).** See [docs/PLAN.md](docs/PLAN.md)
```

- [ ] **Step 5: Commit**

```bash
git add docs/images/gallery/procedural_checker_base.png README.md
git commit -m "docs: add real procedural-material output to the gallery"
```

---

## Task 7: Final verification pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full unit suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all PASS, 0 failures

- [ ] **Step 2: Run the full integration suite**

Run: `.venv\Scripts\python.exe -m pytest -q -m integration`
Expected: all PASS, 0 failures (this includes both Phase 1's
`test_reexport_project_produces_real_files` and this phase's new checker
test — confirms Phase 2 didn't regress Phase 1)

- [ ] **Step 3: Run the existing smoke script**

Run: `powershell -File smoke\smoke.ps1`
Expected: exits 0

- [ ] **Step 4: Update `STATUS.md`**

Add a Phase 2 entry to `STATUS.md` following the same shape as the
existing Phase 0/Phase 1 entries (read the file first to match its exact
format), recording: ✅ verified, the gate from `docs/PLAN.md`'s Phase 2
section, and the evidence (unit + integration test names, the gallery
image path).

- [ ] **Step 5: Commit**

```bash
git add STATUS.md
git commit -m "docs: record Phase 2 gate as verified in STATUS.md"
```

---

## Self-review notes (writer's own pass)

- **Spec coverage:** Amendment 2's three findings are all reflected —
  baking/texture-swap are documented as out of scope (not re-attempted),
  and the single-process procedural authoring finding drives every
  architectural choice in Tasks 1-4 (no save/reload split, `--script`
  without `--background`, reusing `expected_output_files`/fingerprinting
  rather than reinventing completion detection).
- **Placeholder scan:** no TBD/TODO/"add error handling" markers; every
  code step is complete, runnable code matching the target files' actual
  current contents (verified by reading `runner.py`, `server.py`,
  `paths.py`, `test_runner.py`, `test_server.py`, `generate_fixture.py`,
  `pyproject.toml`, and `README.md` before writing this plan).
- **Type/name consistency:** `generate_script(node_spec, output_dir) -> str`
  (Task 2) is called identically in Task 4's `create_procedural_material`;
  `run_procedural_material(binary, script_text, output_dir, preset, timeout_s=...) -> ExportResult`
  (Task 3) matches its Task 4 call site's positional args exactly;
  `NodeSpecError` is raised in Task 2 and caught by name in Task 4 (import
  added in the same task). `_poll_and_terminate`'s signature (Task 1) is
  used identically by both `export_textures` (existing) and
  `run_procedural_material` (Task 3).
