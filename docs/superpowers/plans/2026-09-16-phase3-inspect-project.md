# Phase 3: `inspect_project` + dynamic catalog — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `inspect_project` — a read-only MCP tool that reports a `.arm`
project's objects, materials, and layers — backed by a dynamic catalog
module that turns ArmorPaint's own `--api` output into a blend-mode lookup,
with zero hardcoded magic numbers.

**Architecture:** `ArmorPaint.exe <project.arm> --api` is a *third*,
previously-unused automation path, distinct from Phase 1's
`--export-textures` and Phase 2's `--script`. It is a single, clean
subprocess call — no `--background`/export polling dance, no GUI process to
terminate: `args_api` sets `args_background = true` internally and the
process exits on its own once it has printed. Its stdout contains (in
order) the minic API reference, the material node-type reference (as C
comments, including every node's input/output socket names and any ENUM
button's option list), a `/* Current project state: <JSON> ... */` block
(a JSON dump of the live project — objects, materials, layers, with large
pixel/vertex arrays replaced by `"<N values omitted>"` placeholders), and a
trailing LLM-prompt guide (ignored). `catalog.py` parses that text;
`inspect_project` composes the parse into a clean result shape.

**Tech Stack:** Python 3.13, stdlib `subprocess`/`json`/`re`, pytest. No new
dependencies.

**Spec:** [docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](../specs/2026-09-15-armorpaint-mcp-design.md)
(Amendments 1 and 2 record the prior phases' empirical corrections this plan
builds on). Phase scope: [docs/PLAN.md](../../PLAN.md) Phase 3.

## Global Constraints

- Windows only, Python 3.10+, no new dependencies (stdlib only for this
  phase's new code).
- No source patching of ArmorPaint — this phase only reads a third
  already-existing CLI flag (`--api`), same non-invasive posture as Phases
  1–2.
- `AP_ALLOWED_ROOTS` path sandboxing (`ensure_within_roots`) applies to
  `inspect_project`'s `project` argument, same as every existing tool.
- Never mark a STATUS.md gate ✅ without recorded evidence (real command
  output), per project convention.
- Dynamic catalogs only, never hardcoded enums — this phase's central
  finding changes what "dynamic catalog" means in practice (see Task 5).

## Empirical findings this plan is built on (verified 2026-09-16)

Confirmed by hands-on spiking against the real local ArmorPaint build
(`tests/fixtures/sample_project.arm` and a script-authored project with a
real checker material), not just source reading:

1. **`ArmorPaint.exe <project> --api` works as a single, simple subprocess
   call.** Exit 0, no GUI window persists, no poll-and-terminate needed —
   this is structurally *simpler* than `reexport_project` or
   `create_procedural_material`'s runner code.
2. **The project-state JSON is real and rich.** For a project with an
   actual material (built the same way `create_procedural_material` builds
   one — `script_material_create_node_at`/`connect`/`set_color`/`set_float`,
   `script_fill_layer()`, then `project_filepath_set()` + `project_save(0)`
   — confirmed this round-trip **does** preserve the material graph, layer
   metadata, and mesh info even though Phase 2 found the *painted pixel
   buffer* doesn't survive a save/reopen; those are different claims and
   this phase only needs the former), `--api`'s JSON includes populated
   `material_nodes` (full node graph: names, types, sockets, links),
   `material_datas` (per-material paint-channel flags), `layer_datas`
   (name, resolution, bit depth, blend mode index, visibility, opacity,
   fill material, parent — large pixel buffers correctly omitted), and
   `mesh_datas`/`mesh_transforms`. A separate, simpler
   "Scene objects in world space" text section gives each object's name,
   location, size, and bounds already in world space — no matrix math
   needed for the `objects` half of `inspect_project`.
3. **Blend modes ARE dynamically extractable, from the `MIX_RGB` node's
   `blend_type` ENUM button** in the material node-type reference section
   (`//     button 0 blend_type ENUM: 0 Mix, 1 Darken, 2 Multiply, ...` —
   19 named modes). `layer_datas[].blending` is an integer index into this
   same list.
4. **Bake types are NOT meaningfully catalogable, and this phase drops them
   from scope.** The only bake-adjacent node types in the reference are
   `TEX_BAKE` (its type selector is a `CUSTOM` button widget, not an ENUM —
   no text-exposed option list) and `BAKE_CURVATURE` (a genuine, separate
   procedural node, unrelated to the GUI "Bake Texture" mesh-detail
   operation). Since Known Issue #1 already closed mesh-detail baking as
   structurally unreachable from any script/CLI path, a "bake type"
   catalog would have zero consumers — see Task 5 for the doc update
   recording this as a deliberate descope, not an oversight.
5. **Export presets are unaffected** — already shipped in Phase 2 as
   `list_available_presets` (`runner.list_export_presets`), staying exactly
   where it is (see Task 5's Deviations-from-Plan note on why this phase
   does not relocate it into `catalog.py`).

## Task 1: `runner.run_api` — subprocess wrapper for `--api`

**Files:**
- Modify: `src/armorpaint_mcp/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Produces: `ApiResult` (dataclass: `ok: bool`, `text: str`, `error: str | None`)
  and `run_api(binary: str, project: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> ApiResult`
  in `armorpaint_mcp.runner`.

- [ ] **Step 1: Write the failing unit test**

Append to `tests/test_runner.py`:

```python
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
```

Add `from unittest.mock import patch, MagicMock` and `import subprocess` to
`tests/test_runner.py`'s existing imports if not already present (`patch`/
`MagicMock` already are; `subprocess` is not — add it), and add `run_api` to
the `from armorpaint_mcp.runner import (...)` block.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runner.py -k run_api -v`
Expected: FAIL with `ImportError` (`run_api` doesn't exist yet).

- [ ] **Step 3: Implement `run_api`**

Add to `src/armorpaint_mcp/runner.py` (near the top, after the existing
`ExportResult` dataclass, before `export_textures`):

```python
@dataclass
class ApiResult:
    ok: bool
    text: str
    error: str | None = None


def run_api(binary: str, project: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> ApiResult:
    """Run `binary <project> --api` and return its stdout. Unlike
    export_textures/run_procedural_material, this needs no poll-and-terminate:
    args_api (paint/sources/args.c) sets args_background = true internally
    and the process exits on its own once it has printed -- confirmed
    empirically (2026-09-16), a genuinely simpler path than the export
    flows. Never raises for a normal failure -- that's ApiResult(ok=False, ...)."""
    try:
        proc = subprocess.run(
            [binary, project, "--api"],
            capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return ApiResult(ok=False, text="",
                          error=f"'--api' timed out after {timeout_s}s")

    if proc.returncode != 0:
        detail = f": {proc.stderr.strip()}" if proc.stderr and proc.stderr.strip() else ""
        return ApiResult(ok=False, text="",
                          error=f"'--api' exited {proc.returncode}{detail}")
    return ApiResult(ok=True, text=proc.stdout)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runner.py -k run_api -v`
Expected: 3 passed.

- [ ] **Step 5: Run the full unit suite to check for regressions**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all pass (58 existing + 3 new = 61).

- [ ] **Step 6: Commit**

```bash
git add src/armorpaint_mcp/runner.py tests/test_runner.py
git commit -m "feat: add runner.run_api, a subprocess wrapper for ArmorPaint's --api flag"
```

## Task 2: `catalog.py` — parse `--api` output

**Files:**
- Create: `src/armorpaint_mcp/catalog.py`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: nothing from other tasks (pure text/JSON parsing over a string).
- Produces (in `armorpaint_mcp.catalog`, used by Task 3):
  - `class CatalogError(Exception)`
  - `blend_modes(api_text: str) -> list[str]`
  - `extract_project_state(api_text: str) -> dict`
  - `scene_objects(api_text: str) -> list[dict]` (each dict:
    `{"name": str, "location": [float, float, float], "size": [float, float, float]}`)

- [ ] **Step 1: Write the failing unit tests**

Create `tests/test_catalog.py`:

```python
"""Unit tests for catalog.py's --api output parsing. The sample text below
is a trimmed, hand-built excerpt matching the real structure captured from
`ArmorPaint.exe <project> --api` on 2026-09-16 (see docs/PLAN.md Phase 3) --
real field names and real ENUM option text, shortened for a fast, offline
unit test. The real end-to-end shape is checked separately by
tests/test_inspect_project_integration.py against actual ArmorPaint output.
"""
import pytest

from armorpaint_mcp.catalog import (
    CatalogError,
    blend_modes,
    extract_project_state,
    scene_objects,
)

SAMPLE_API_TEXT = '''\
// Material nodes reference:
// TEX_CHECKER | in: 0 Vector, 1 Color 1, 2 Color 2, 3 Scale | out: 0 Color, 1 Factor
// MIX_RGB | in: 0 Factor, 1 Color 1, 2 Color 2 | out: 0 Color
//     button 0 blend_type ENUM: 0 Mix, 1 Darken, 2 Multiply, 3 Burn, 4 Lighten, 5 Screen, 6 Dodge, 7 Add, 8 Overlay, 9 Soft Light, 10 Linear Light, 11 Difference, 12 Exclusion, 13 Subtract, 14 Divide, 15 Hue, 16 Saturation, 17 Color, 18 Value
//     button 1 Clamp Factor BOOL
// MIX_NORMAL_MAP | in: 0 Normal Map 1, 1 Normal Map 2 | out: 0 Normal Map
//     button 0 blend_type ENUM: 0 Partial Derivative, 1 Whiteout, 2 Reoriented
//
// Pre-created material output node:
// OUTPUT_MATERIAL_PBR | in: 0 Base Color | out:

/* Current project state:
{"version":"16","material_nodes":[{"name":"Material 1","nodes":[],"links":[]}],"layer_datas":[{"name":"Layer 1","res":2048,"bpp":8,"blending":0,"visible":true,"opacity_mask":1.0,"fill_material":-1,"parent":-1}],"mesh_datas":[{"name":"Tessellated"}]}

Scene objects in world space, z axis up:
"Tessellated": location (0.000, 0.000, 0.000), size (1.039, 1.039, 1.039), bounds min (-0.520, -0.520, -0.520) max (0.520, 0.520, 0.520)

script_shape_add() shapes:
"cone"
"cube"
*/

Reply with C code only wrapped in a ```c markdown fence.
'''


def test_blend_modes_reads_mix_rgb_enum_not_mix_normal_map():
    modes = blend_modes(SAMPLE_API_TEXT)

    assert modes[0] == "Mix"
    assert modes[1] == "Darken"
    assert modes[-1] == "Value"
    assert len(modes) == 19
    assert "Partial Derivative" not in modes  # that's MIX_NORMAL_MAP's list, not MIX_RGB's


def test_blend_modes_raises_when_mix_rgb_not_found():
    with pytest.raises(CatalogError, match="MIX_RGB"):
        blend_modes("no material node reference here")


def test_extract_project_state_parses_the_json_block():
    state = extract_project_state(SAMPLE_API_TEXT)

    assert state["version"] == "16"
    assert state["material_nodes"][0]["name"] == "Material 1"
    assert state["layer_datas"][0]["name"] == "Layer 1"
    assert state["mesh_datas"][0]["name"] == "Tessellated"


def test_extract_project_state_raises_when_marker_missing():
    with pytest.raises(CatalogError, match="Current project state"):
        extract_project_state("no state block here")


def test_scene_objects_parses_name_location_size():
    objects = scene_objects(SAMPLE_API_TEXT)

    assert objects == [{
        "name": "Tessellated",
        "location": [0.0, 0.0, 0.0],
        "size": [1.039, 1.039, 1.039],
    }]


def test_scene_objects_empty_list_when_no_objects_section():
    assert scene_objects("nothing here") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError` (`armorpaint_mcp.catalog` doesn't exist yet).

- [ ] **Step 3: Implement `catalog.py`**

Create `src/armorpaint_mcp/catalog.py`:

```python
"""Parses ArmorPaint's own `--api` output (paint/sources/args.c's args_api,
paint/sources/nodes_neural/text_to_text_node.c's text_to_text_node_reference)
into structured data. No hardcoded bake-type/blend-mode magic numbers --
everything here is read from the app's own text output, confirmed
empirically against the real local build (2026-09-16, see
docs/PLAN.md Phase 3). Bake types are deliberately NOT parsed here: the only
bake-adjacent node type, TEX_BAKE, exposes its bake-type selector as a
CUSTOM button widget (not an ENUM), so no option list is text-exposed --
and since mesh-detail baking is already confirmed structurally unreachable
from any script/CLI path (STATUS.md Known Issue #1), a bake-type catalog
would have no consumer anyway.
"""

import json
import re

_STATE_START = "/* Current project state:\n"
_STATE_END = "\n\nScene objects in world space"


class CatalogError(Exception):
    """`api_text` doesn't contain the section being parsed, or it's malformed."""


def extract_project_state(api_text: str) -> dict:
    """The `/* Current project state: <JSON> ... */` block's JSON, decoded.
    Anchored on the literal marker text and the following section header
    (rather than searching for a bare '*/', which the JSON payload could in
    principle contain inside a string value)."""
    start = api_text.find(_STATE_START)
    if start == -1:
        raise CatalogError(
            "'--api' output has no 'Current project state' block -- "
            "was a project path passed to ArmorPaint.exe, not just --api?")
    start += len(_STATE_START)
    end = api_text.find(_STATE_END, start)
    if end == -1:
        raise CatalogError(
            "'--api' output's project state block has no terminating "
            "'Scene objects in world space' section -- unexpected output shape")
    try:
        return json.loads(api_text[start:end])
    except json.JSONDecodeError as exc:
        raise CatalogError(f"project state block is not valid JSON: {exc}") from exc


def blend_modes(api_text: str) -> list[str]:
    """Blend mode names, in index order, from the MIX_RGB node's blend_type
    ENUM button in the material node-type reference. layer_datas[].blending
    is an integer index into this same list. Specifically anchored to
    MIX_RGB (not just any 'blend_type' button) because MIX_NORMAL_MAP has
    its own, differently-sized blend_type ENUM."""
    match = re.search(
        r'// MIX_RGB \|.*?\n//\s+button \d+ blend_type ENUM: (.+)',
        api_text)
    if match is None:
        raise CatalogError(
            "'--api' output has no MIX_RGB blend_type ENUM button -- "
            "unexpected material node reference shape")
    options = match.group(1).split(", ")
    # Each option is "<index> <name>"; keep the name, drop the index (the
    # list's own position is the index).
    return [re.sub(r'^\d+\s+', '', opt) for opt in options]


def scene_objects(api_text: str) -> list[dict]:
    """Every object in the 'Scene objects in world space' section: name,
    location, and size, already in world space (no matrix decoding needed --
    unlike mesh_transforms in the JSON state block, which is column-major
    4x4 and not worth parsing when this text section already has the
    answer)."""
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_catalog.py -v`
Expected: 6 passed.

- [ ] **Step 5: Run the full unit suite to check for regressions**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all pass (61 + 6 = 67).

- [ ] **Step 6: Commit**

```bash
git add src/armorpaint_mcp/catalog.py tests/test_catalog.py
git commit -m "feat: add catalog.py to parse ArmorPaint's --api output"
```

## Task 3: `inspect_project` MCP tool

**Files:**
- Modify: `src/armorpaint_mcp/server.py`
- Modify: `tests/test_server.py`
- Test: `tests/test_inspect_project_integration.py` (new)

**Interfaces:**
- Consumes: `runner.run_api` (Task 1), `catalog.extract_project_state` /
  `catalog.blend_modes` / `catalog.scene_objects` / `catalog.CatalogError`
  (Task 2).
- Produces: `inspect_project(project: str) -> dict` registered as an MCP
  tool in `armorpaint_mcp.server`. Return shape:
  `{"ok": bool, "objects": [{"name": str, "location": [f,f,f], "size": [f,f,f]}] | None,`
  `"materials": [{"name": str, "node_count": int}] | None,`
  `"layers": [{"name": str, "resolution": int, "visible": bool, "blending": str | None}] | None,`
  `"error": str | None}`.

- [ ] **Step 1: Write the failing unit tests**

Append to `tests/test_server.py` (add `inspect_project` to the existing
`from armorpaint_mcp.server import (...)` block, and `from armorpaint_mcp.runner import ApiResult`
alongside the existing `ExportResult` import):

```python
def test_inspect_project_rejects_path_outside_allowed_roots(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside_project = tmp_path / "elsewhere" / "project.arm"

    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = [str(root)]
        result = inspect_project(project=str(outside_project))

    assert result["ok"] is False
    assert result["objects"] is None
    assert "allowed" in result["error"]


def test_inspect_project_surfaces_run_api_failure(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_api") as mock_run_api:
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run_api.return_value = ApiResult(ok=False, text="", error="'--api' exited 1")

        result = inspect_project(project=str(tmp_path / "project.arm"))

    assert result["ok"] is False
    assert result["error"] == "'--api' exited 1"


def test_inspect_project_composes_catalog_parses_into_result(tmp_path):
    fake_api_text = "fake api text"
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_api") as mock_run_api, \
         patch("armorpaint_mcp.server.extract_project_state") as mock_state, \
         patch("armorpaint_mcp.server.blend_modes", return_value=["Mix", "Darken"]), \
         patch("armorpaint_mcp.server.scene_objects",
               return_value=[{"name": "Tessellated", "location": [0.0, 0.0, 0.0],
                              "size": [1.0, 1.0, 1.0]}]):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run_api.return_value = ApiResult(ok=True, text=fake_api_text)
        mock_state.return_value = {
            "material_nodes": [{"name": "Material 1", "nodes": [1, 2, 3]}],
            "layer_datas": [{"name": "Layer 1", "res": 2048, "visible": True,
                             "blending": 1}],
        }

        result = inspect_project(project=str(tmp_path / "project.arm"))

    assert result["ok"] is True
    assert result["error"] is None
    assert result["objects"] == [{"name": "Tessellated", "location": [0.0, 0.0, 0.0],
                                  "size": [1.0, 1.0, 1.0]}]
    assert result["materials"] == [{"name": "Material 1", "node_count": 3}]
    assert result["layers"] == [{"name": "Layer 1", "resolution": 2048,
                                 "visible": True, "blending": "Darken"}]


def test_inspect_project_surfaces_catalog_parse_error(tmp_path):
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_api") as mock_run_api, \
         patch("armorpaint_mcp.server.extract_project_state",
               side_effect=CatalogError("no state block")):
        mock_cfg.return_value.binary = str(tmp_path / "ArmorPaint.exe")
        mock_cfg.return_value.allowed_roots = []
        mock_run_api.return_value = ApiResult(ok=True, text="text")

        result = inspect_project(project=str(tmp_path / "project.arm"))

    assert result["ok"] is False
    assert "no state block" in result["error"]


def test_inspect_project_registered_as_mcp_tool():
    names = [t.name for t in asyncio.run(mcp.list_tools())]
    assert "inspect_project" in names
```

Add `from armorpaint_mcp.catalog import CatalogError` to `tests/test_server.py`'s imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -k inspect_project -v`
Expected: FAIL with `ImportError` (`inspect_project` doesn't exist in `armorpaint_mcp.server` yet).

- [ ] **Step 3: Implement `inspect_project`**

Add to `src/armorpaint_mcp/server.py`:

```python
from armorpaint_mcp.catalog import CatalogError, blend_modes, extract_project_state, scene_objects
from armorpaint_mcp.runner import export_textures, list_export_presets, run_api, run_procedural_material
```

(replace the existing `from armorpaint_mcp.runner import ...` line with the
one above, adding `run_api`; add the new `catalog` import line above it.)

Then, after `list_available_presets` and its `mcp.tool()(list_available_presets)`
line:

```python
def inspect_project(project: str) -> dict:
    """Read-only metadata for an existing .arm project -- objects,
    materials, and layers -- via ArmorPaint's own `--api` flag (a project
    path plus --api prints a full project-state dump, not just static API
    docs). Makes no changes to the project. Bounded by AP_ALLOWED_ROOTS
    when set. Returns {"ok": bool, "objects": [...] | None,
    "materials": [...] | None, "layers": [...] | None, "error": str | None}."""
    cfg = _ensure_ready()

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": str(exc)}

    result = run_api(cfg.binary, project)
    if not result.ok:
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": result.error}

    try:
        state = extract_project_state(result.text)
        modes = blend_modes(result.text)
    except CatalogError as exc:
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": str(exc)}

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


mcp.tool()(inspect_project)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_server.py -v`
Expected: all pass (existing `test_server.py` tests + 5 new).

- [ ] **Step 5: Write the real integration test**

Create `tests/test_inspect_project_integration.py`:

```python
"""Real ArmorPaint required. Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_inspect_project_integration.py -v
(needs AP_BINARY set to a working build -- see .env.example)
"""
import os

import pytest

from armorpaint_mcp.server import inspect_project

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project.arm")


@pytest.mark.integration
def test_inspect_project_reports_real_object_from_the_fixture():
    result = inspect_project(project=FIXTURE)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    assert len(result["objects"]) == 1
    assert result["objects"][0]["name"]  # a real, non-empty object name
    assert isinstance(result["materials"], list)
    assert isinstance(result["layers"], list)
```

- [ ] **Step 6: Run the integration test against real ArmorPaint**

Run: `.venv\Scripts\python.exe -m pytest tests/test_inspect_project_integration.py -v -m integration`
Expected: 1 passed. Record the real output in the task's review notes (this
is the gate evidence Task 6 will cite in STATUS.md).

- [ ] **Step 7: Run the full unit suite to check for regressions**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all pass (67 + 5 = 72, integration tests still deselected by default).

- [ ] **Step 8: Commit**

```bash
git add src/armorpaint_mcp/server.py tests/test_server.py tests/test_inspect_project_integration.py
git commit -m "feat: register inspect_project as an MCP tool"
```

## Task 4: Multi-entity fixture — verify array-index correlation holds

**Why this task exists:** every finding so far comes from a project with
exactly one object, one material, one layer. `material_datas[]` correlating
positionally with `material_nodes[]` (rather than some other key) is an
assumption, not yet a confirmed fact — this task builds a real project with
two materials and two layers and checks it before anything downstream
trusts that assumption.

**Files:**
- Create: `tests/fixtures/generate_multi_fixture.py`
- Create (generated by the script above, then committed): `tests/fixtures/sample_project_multi.arm`
- Test: `tests/test_inspect_project_integration.py` (extend)

**Interfaces:**
- Consumes: the same `script_material_*`/`script_fill_layer`/
  `project_filepath_set`/`project_save` minic calls Phase 2 and this
  phase's own findings section already confirmed working.
- Produces: a committed binary fixture at
  `tests/fixtures/sample_project_multi.arm`, mirroring how
  `tests/fixtures/sample_project.arm` was produced by
  `tests/fixtures/generate_fixture.py`.

- [ ] **Step 1: Write the fixture generator**

Create `tests/fixtures/generate_multi_fixture.py`:

```python
# tests/fixtures/generate_multi_fixture.py
"""Regenerates tests/fixtures/sample_project_multi.arm -- a project with two
materials and two layers, used to verify inspect_project's array-index
correlation assumptions (material_datas[i] describes material_nodes[i],
etc.) against a real multi-entity project, not just the single-entity
sample_project.arm.

Run manually whenever the fixture needs to change:
    .venv\\Scripts\\python.exe tests\\fixtures\\generate_multi_fixture.py

Requires AP_BINARY set (env var or .env) to a working ArmorPaint.exe.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from armorpaint_mcp.config import load_config  # noqa: E402

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "sample_project_multi.arm")

SCRIPT_TEMPLATE = """\
void main() {{
	script_project_new();
	ui_node_t *out = script_material_get_node("OUTPUT_MATERIAL_PBR");
	ui_node_t *src = script_material_create_node_at("TEX_CHECKER", -400.0, 0.0);
	script_material_set_color(src, 1, 1, 0.9, 0.1, 0.1, 1.0);
	script_material_set_color(src, 1, 2, 0.1, 0.1, 0.9, 1.0);
	script_material_set_float(src, 1, 3, 8.0);
	script_material_connect(src, 0, out, 0);
	script_fill_layer();

	slot_material_t *mat2 = script_material_create("Second Material");
	script_material_set(mat2);
	ui_node_t *out2 = script_material_get_node("OUTPUT_MATERIAL_PBR");
	ui_node_t *src2 = script_material_create_node_at("RGB", -400.0, 0.0);
	script_material_set_color(src2, 0, 0, 0.2, 0.8, 0.2, 1.0);
	script_material_connect(src2, 0, out2, 0);

	project_filepath_set("{path}");
	project_save(0);
	printf("multi fixture created\\n");
}}
"""


def main() -> int:
    cfg = load_config()
    if not cfg.binary or not os.path.isfile(cfg.binary):
        print(f"AP_BINARY not set to a valid ArmorPaint.exe (got '{cfg.binary}')",
              file=sys.stderr)
        return 1

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

Note for the implementing agent: `script_material_create`/`script_material_set`
(switching the active material before adding the second node graph) are
registered minic functions (`minic_api_list.h` lines 513-514) but were not
exercised by any prior phase — if `script_material_create("Second Material")`
does not actually produce a second entry in the saved project's
`material_nodes` array (i.e. it's a "rename the current material" call
rather than "add a new material"), fall back to two separate objects each
with their own single material instead: `script_shape_add("cube")` for a
second mesh, then build/connect/fill for it. Either shape (two materials on
one object, or two objects each with one material) equally exercises the
array-correlation question this task exists to answer -- adjust the
template and this task's assertions to match whichever actually produces
two entries, and note which one it was in the task's review notes.

- [ ] **Step 2: Generate the fixture and inspect the raw `--api` output by hand**

Run:
```
.venv\Scripts\python.exe tests\fixtures\generate_multi_fixture.py
& "$env:AP_BINARY" tests\fixtures\sample_project_multi.arm --api
```
Confirm by eye: does `material_nodes` have 2 entries? Does `material_datas`
also have 2 entries, in the same order? This is the fact Step 3's test
locks in — if the array lengths don't match 2 and 2, the fixture template
needs adjusting per the note in Step 1 before writing the test against it.

- [ ] **Step 3: Write the correlation test**

Append to `tests/test_inspect_project_integration.py`:

```python
FIXTURE_MULTI = os.path.join(os.path.dirname(__file__), "fixtures",
                             "sample_project_multi.arm")


@pytest.mark.integration
def test_inspect_project_reports_all_materials_in_a_multi_material_project():
    result = inspect_project(project=FIXTURE_MULTI)

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    assert len(result["materials"]) == 2
    names = [m["name"] for m in result["materials"]]
    assert len(set(names)) == 2  # two distinct materials, not the same one twice
```

- [ ] **Step 4: Run the integration tests against real ArmorPaint**

Run: `.venv\Scripts\python.exe -m pytest tests/test_inspect_project_integration.py -v -m integration`
Expected: 2 passed. Record the real output (gate evidence for Task 6).

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/generate_multi_fixture.py tests/fixtures/sample_project_multi.arm tests/test_inspect_project_integration.py
git commit -m "test: verify inspect_project against a real multi-material project"
```

## Task 5: Docs — scope decision, cosmetic residual, README

**Files:**
- Modify: `docs/PLAN.md`
- Modify: `STATUS.md`
- Modify: `README.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Fix `docs/PLAN.md`'s Phase 3 heading (the parked cosmetic residual)**

In `docs/PLAN.md`, change:
```
## Phase 3 — `list_export_presets` + `inspect_project` + dynamic catalog
```
to:
```
## Phase 3 — `inspect_project` + dynamic catalog
```
(`list_export_presets` shipped in Phase 2 as `list_available_presets` --
HANDOFF.md's session log has flagged this heading as stale since then.)

- [ ] **Step 2: Record the bake-type descope and blend-mode source in `docs/PLAN.md`**

In `docs/PLAN.md`'s Phase 3 section, after the existing paragraph starting
"`catalog.py` builds bake-type/blend-mode/export-preset lists...", replace
that sentence with:

```
`catalog.py` builds a blend-mode list from ArmorPaint's own `--api` output
(the MIX_RGB node's `blend_type` ENUM button) -- no hardcoded magic
numbers. Bake types are deliberately NOT catalogued: the only bake-adjacent
node type, TEX_BAKE, exposes its type selector as a CUSTOM button widget
with no text-exposed option list, and since mesh-detail baking is already
confirmed structurally unreachable from any script/CLI path (see Known
Issue #1 in STATUS.md), a bake-type catalog would have no consumer.
`inspect_project` is a read-only `.arm` metadata query (objects, materials,
layers) via `ArmorPaint.exe <project> --api` -- a third, previously-unused
automation path distinct from `--export-textures` and `--script`, and
structurally simpler than either (no poll-and-terminate needed).
```

- [ ] **Step 3: Add the Deviations-from-Plan row for `list_export_presets`'s location**

In `docs/PLAN.md`... actually this belongs in `STATUS.md`'s "Deviations
from Plan" table (currently empty). Add a row:

```markdown
| 2026-09-15 | `list_export_presets` shipped in Phase 1/2 as a function in `runner.py`, not in `catalog.py` as the design spec's Components table originally described. | Phase 3's own plan (this file's history) chose not to relocate already-tested, working code for a cosmetic-only file-organization match -- see docs/superpowers/plans/2026-09-16-phase3-inspect-project.md's Global Constraints/rationale. |
```

- [ ] **Step 4: Update `STATUS.md`'s Phase 3 gate row and add a Current Phase Detail table**

Change the Phase 3 row in the Phase Gates table from:
```
| 3 | `inspect_project` + dynamic catalog (`list_export_presets` already shipped in Phase 2 as `list_available_presets`) | ⬜ | |
```
to (evidence filled in by Task 6 once the real integration tests have run):
```
| 3 | `inspect_project` + dynamic catalog (blend modes; bake types deliberately out of scope -- see Deviations) | ⬜ | |
```

Add a new "Current Phase Detail (Phase 3)" section (mirroring the existing
Phase 1/Phase 2 sections) with empty/🔌 rows for `catalog.py`,
`runner.run_api`, and `server.py` (`inspect_project`) -- Task 6 fills in ✅
and real evidence once the full suite is green.

- [ ] **Step 5: Add `inspect_project` to README**

In `README.md`'s first paragraph, change:

> ...and build small procedural materials (checker/solid node graphs built,
> rendered, and exported in a single pass) — without opening the GUI for
> each pass.

to:

> ...build small procedural materials (checker/solid node graphs built,
> rendered, and exported in a single pass), and inspect an existing
> project's objects, materials, and layers — without opening the GUI for
> each pass.

Also update the `## Status` line from `Pre-alpha, Phase 2` to
`Pre-alpha, Phase 3` once Task 6 confirms the gate is green (do this edit
in Task 6, not here, so it doesn't get committed prematurely if Task 6
finds something that needs fixing first).

- [ ] **Step 6: Commit**

```bash
git add docs/PLAN.md STATUS.md README.md
git commit -m "docs: record Phase 3 scope decisions (blend-mode-only catalog, --api discovery)"
```

## Task 6: Final verification sweep

**Files:**
- Modify: `smoke/smoke.ps1`
- Modify: `STATUS.md`
- Modify: `README.md`

**Interfaces:** none (verification + gate recording).

- [ ] **Step 1: Add an `inspect_project` probe to `smoke/smoke.ps1`**

After the existing `reexport_project registered as an MCP tool` probe, add:

```powershell
Probe "inspect_project registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'inspect_project' in names, names; print(names)" }
```

- [ ] **Step 2: Run the smoke test**

Run: `pwsh smoke/smoke.ps1`
Expected: exit 0, all probes `[PASS]` including the new one.

- [ ] **Step 3: Run the full unit suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all pass (72 total from Tasks 1-4), integration tests deselected.

- [ ] **Step 4: Run every integration test against real ArmorPaint**

Run: `.venv\Scripts\python.exe -m pytest -q -m integration`
Expected: all pass (Phase 1's `test_reexport_project_produces_real_files`,
Phase 2's `test_checker_material_produces_a_genuinely_painted_texture`, and
this phase's `test_inspect_project_reports_real_object_from_the_fixture` +
`test_inspect_project_reports_all_materials_in_a_multi_material_project`),
with no regression in the pre-existing two.

- [ ] **Step 5: Record the gate in `STATUS.md`**

Fill in the Phase 3 row's Evidence column with the real command output
summary (pass counts + exit codes) from Steps 2-4, changing `⬜` to `✅
2026-09-16` (or the actual date this task runs). Fill in the Phase 3
"Current Phase Detail" table's rows (added in Task 5 Step 4) with ✅ and
one-line evidence each, matching the style of the existing Phase 1/Phase 2
detail tables.

- [ ] **Step 6: Update `README.md`'s status line**

Change `## Status` from `Pre-alpha, Phase 2 (...)` to
`Pre-alpha, Phase 3 (inspect_project shipped)`.

- [ ] **Step 7: Commit**

```bash
git add smoke/smoke.ps1 STATUS.md README.md
git commit -m "test: verify Phase 3 gate -- inspect_project smoke probe + full suite green"
```

---

## Self-review notes (for the plan author, not a task to execute)

- **Spec coverage:** `docs/PLAN.md` Phase 3 names two deliverables --
  `catalog.py`'s dynamic catalog (Task 2, scope narrowed to blend-modes-only
  per the empirical findings section, with the narrowing itself documented
  in Task 5) and `inspect_project` (Tasks 1, 3, 4). The gate ("catalog
  build succeeds ... returns a non-empty, sane-looking list for each
  category") is satisfied by Task 2's `blend_modes()` (one category, since
  bake types are out and export presets already shipped) plus Task 3's
  real integration test.
- **Placeholder scan:** every step has real, complete code -- no "add
  appropriate handling" language. Task 4's Step 1 has one explicit
  documented fallback (a genuine unresolved API question -- whether
  `script_material_create` adds vs. renames -- flagged as something the
  implementing agent must check empirically in Step 2, not a placeholder
  for missing design work).
- **Type consistency:** `ApiResult` (Task 1) is consumed identically in
  Tasks 2 (via its `.text` attribute) and 3 (via `run_api(...).ok`/`.text`/
  `.error`). `CatalogError` (Task 2) is caught by name in Task 3. Return
  dict shape for `inspect_project` is defined once in Task 3's Interfaces
  block and used consistently in every subsequent test and doc reference.
