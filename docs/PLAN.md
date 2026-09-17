# Phase plan — Tool-ArmorPaintMCP

Full design: [superpowers/specs/2026-09-15-armorpaint-mcp-design.md](superpowers/specs/2026-09-15-armorpaint-mcp-design.md).

Gate rule: never start Phase N+1 until Phase N's gate is green and recorded
in [STATUS.md](../STATUS.md) with evidence.

## Phase 0 — Scaffold + smoke harness

Standard kit (README, CLAUDE.md, HANDOFF.md, STATUS.md, this file,
`.gitignore`, `.env.example`, build stamp), package skeleton
(`config.py`/`doctor.py`/`server.py`) with **zero MCP tools yet**, git repo,
GitHub repo.

**Gate:** `smoke/smoke.ps1` exits 0. `ap-mcp --version` and `ap-mcp --help`
both exit 0. (`pytest -q` collects zero tests at this phase — pytest's own
exit 5 for that case is expected, not a failure; the first real tests land
in Phase 1.)

## Phase 1 — `reexport_project`

The first real tool: re-export an existing `.arm` project at a different
export preset, using ArmorPaint's native `--export-textures <type> <preset>
<path>` flag. **Confirmed empirically (2026-09-15), not just from source
reading:** `--background` combined with `--export-textures` is silently
broken on this build — `iron_stop()` fires in the same frame that merely
*schedules* the export for the next frame, so the process exits with code 0
having produced nothing. Without `--background` the same export works
correctly (verified: 5 real PNGs for the "generic" preset), but the GUI
process doesn't self-exit afterward — `runner.py` launches it, polls the
output dir for the expected files with a timeout, then terminates the
process itself. **Resolution is dropped from this phase's tool signature**:
no CLI flag and no confirmed minic setter exist for it (it reads from a
static app config, `config_get_texture_res_x/y`); only `preset` is
controllable per call. Includes `runner.py` (the process wrapper: build
args, spawn without `--background`, poll for output, terminate, capture
exit code/stdout/stderr) and `paths.py` (AP_ALLOWED_ROOTS enforcement,
path-traversal rejection).

**Gate:** an integration smoke test shells out to the real local ArmorPaint
build against a small sample `.arm` project (created headlessly via
`--background --script`, calling minic's `script_project_new()` +
`project_filepath_set()` + `project_save()` — confirmed working) and asserts
the expected texture files land on disk. Unit tests for arg-building pass
without ArmorPaint running.

## Phase 2 — `create_procedural_material`

Rescoped twice during hands-on spiking (2026-09-15) after the original
`rebake_and_export` scope turned out to rest on capabilities that don't
exist in this build. In order:

1. **Mesh-detail baking (AO/curvature/normal-from-highpoly) is unreachable
   from any script or API.** `bake_texture_node_run` is a `static` C
   function invoked only from `bake_texture_node_button`, which is
   registered solely in a GUI-only button-callback map
   (`ui_nodes_custom_buttons`). No CLI flag, no minic function, no
   workaround — confirmed by reading the call chain, not just grepping for
   an entry point.
2. **Texture-set swapping into an existing project is also unreachable.**
   It needs the newly-imported asset's combo-index, which requires reading
   `project_t->assets->length` from minic — and minic's struct access is
   curated, not general C: `int n = p->assets->length;` silently aborts
   script execution with no error. Isolated with a 3-step spike ladder
   (baseline → +1 line → +1 more line) to the exact breaking statement.
3. **Procedural material authoring (build a node graph, render it into the
   paint layer, export) is real and confirmed working** — but only as a
   **single-process** operation. `script_fill_layer()` and
   `export_texture_run(path, bake_material)` are both minic-registered and
   both work correctly when called in the same `--script` invocation that
   built the graph. Saving to `.arm` and re-exporting via a *separate*
   process (i.e. reusing Phase 1's `reexport_project` on a
   script-authored project) silently loses the rendered pixels — verified
   with two spikes (solid-color fill and a checker-pattern fill) that
   produced flat, unpainted output through the save/reload path and
   correct output through the same-process path. Root cause not
   pinned down further than "the `.arm` round-trip doesn't preserve the
   rendered `texpaint` buffer the way project save/reload of a
   GUI-authored project does" — not worth chasing further since the
   single-process path is fully sufficient.

**Scope:** one new tool generates a minic script from a small, whitelisted
node-graph spec (node type + params + connections). **Scope is deliberately
narrow (YAGNI): v1 supports exactly two node types, `"checker"`
(`TEX_CHECKER`) and `"solid"` (`RGB`)** — a general multi-node graph DSL is
future scope, not this phase's job. minic's real registered node set is
much broader (`TEX_NOISE`, `TEX_VORONOI`, `TEX_GRADIENT`, `TEX_WAVE`,
`MIX_RGB`, etc.) and is a possible future expansion, not something v1
exposes. The tool writes the generated script to a temp file, launches
ArmorPaint with `--script <file>` (no `--background`,
per Phase 1's established GUI-process-plus-poll pattern), and the script
itself does project setup → build graph → `script_fill_layer()` →
`export_texture_run()` in one process before exiting. Also exposes
`list_export_presets` (already written and tested in `runner.py` from
Phase 1, never registered as a tool) since it's a one-line addition once
this phase touches `server.py` again.

**Gate:** integration smoke test runs the tool with a small procedural
graph (e.g. checker or noise) against the default primitive mesh and
asserts the exported base-color PNG is *not* uniform (i.e. genuinely
painted, not the flat default) — a real content check, not just
file-exists.

## Phase 3 — `inspect_project` + dynamic catalog

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

**Gate:** catalog build succeeds against the real local ArmorPaint
checkout/build and returns a non-empty, sane-looking list for each category.

## Phase 4 — `run_script` escape hatch + polish

The purpose-built escape-hatch tool for anything the above don't cover.
Documentation pass, packaging check (`pip install -e .` from a clean clone),
README accuracy pass.

**Gate:** a clean-clone install + `ap-mcp --check` + smoke test all pass with
no undocumented manual steps.

## Phase 5 — Mesh/UV editing tools

7 new tools (`decimate_mesh`, `bevel_mesh`, `subdivide_mesh`, `smooth_mesh`,
`duplicate_mesh`, `merge_mesh_geometry`, `unwrap_mesh_uvs`), all wired to
ArmorPaint's own real, working mesh-edit algorithms via a small, scoped
local patch to `paint\sources\minic_api_list.h` in the ArmorPaint checkout.
Why a patch is the accepted path here — and why this doesn't reopen
source-patching for anything else (rebake/texture-swap remain exactly as
out-of-scope as Phase 2 found them) — is covered in
[ROADMAP.md's "Patch policy"](../ROADMAP.md#patch-policy) and
[the design spec's Amendment 3](superpowers/specs/2026-09-15-armorpaint-mcp-design.md#amendment-3-scoped-patch-policy-for-meshuv-2026-09-16);
not re-explained here.

**Scope:** every tool shares one helper, `_run_mesh_edit`, which resolves the
edit target (a copy at `output_project` by default -- never the caller's own
file unless `in_place=True`), runs the tool-specific minic call followed by
`project_save(0)` in a single `--script` process, and reports the outcome.
`merge_mesh_geometry` additionally checks the project's object count via
`inspect_project`'s own `--api` machinery before running, since
`util_mesh_merge_geometry` silently no-ops (by its own internal guard) on a
project with fewer than 2 objects -- confirmed empirically during this
phase's spike, and worth a clear error instead of a false `ok=True` with no
visible effect.

**Empirical findings worth recording:**
- `subdivide_mesh` is an exact 4x face-count operation on this build;
  `duplicate_mesh` is an exact 2x vertex/face-count operation. Both confirmed
  via real OBJ export diffs, not just "changed."
- `smooth_mesh` preserves vertex/face count exactly (topology unchanged) but
  does change vertex normals -- the reverse assertion direction from every
  other tool in this phase, and the one real correctness risk task review
  flagged and confirmed.
- `merge_mesh_geometry` merges ALL objects in the project, not a targeted
  pair -- ArmorPaint's GUI "merge with the object below"
  (`util_mesh_merge_geometry_down`) needs a second minic accessor for "the
  other object" that doesn't exist yet (ROADMAP.md item 9, out of scope for
  this phase).
- `unwrap_mesh_uvs`'s underlying call (`plugin_uv_unwrap_button`) is real,
  built-in ArmorPaint code calling `proc_uv_unwrap()` directly -- not a
  loaded plugin despite the C function's name. Confirmed to genuinely change
  UV coordinates (all 144 `vt` lines differed on the fixture); unwrap
  quality/atlas-efficiency vs. `xatlas` (Tool-MeshTriage's unwrapper) has not
  been compared -- see ROADMAP.md's "Known gaps."
- No multi-object test fixture exists yet, so `merge_mesh_geometry`'s
  2-object integration test builds its own starting point by calling
  `duplicate_mesh` first, rather than a dedicated fixture file.

**Gate:** `smoke/smoke.ps1`: 13/13 passed, exit 0 (6 prior probes + 1 new
registration probe per tool). `.venv\Scripts\python.exe -m pytest -q`: 118
passed, 0 failed, 18 deselected. `-m integration`: 18 passed, 0 failed. All 7
tools verified against real geometry via independent `script_export_mesh`
OBJ diffs (never just `ok=True`) -- see STATUS.md's Phase 5 gate row and
"Current Phase Detail (Phase 5)" table for the specific before/after
relationship each tool's integration test proved.

## Deferred (not scoped into any phase above)

- **Live mode** — interactive, GUI-attached control. See the design spec's
  "Deferred: live mode" section. Two architecture options are named there;
  neither is chosen. Only take this on once batch mode (Phases 0-4) is solid
  and live mode is actually wanted, per Grayson's "both, batch first"
  direction from the brainstorming session.
- **Material authoring from scratch** (node-graph generation from a
  text/style description) — the harder generative problem the reference
  project also attempts; explicitly out of v1 scope.
