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
node-graph spec (node type + params + connections — chosen from minic's
real registered node set: `TEX_CHECKER`, `RGB`, `TEX_NOISE`,
`TEX_VORONOI`, `TEX_GRADIENT`, `TEX_WAVE`, `MIX_RGB`, etc.), writes it to a
temp file, launches ArmorPaint with `--script <file>` (no `--background`,
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

## Phase 3 — `list_export_presets` + `inspect_project` + dynamic catalog

`catalog.py` builds bake-type/blend-mode/export-preset lists from `--api`
output and `export_presets/*.json` on disk — no hardcoded magic numbers.
`inspect_project` is a read-only `.arm` metadata query (objects, materials,
layers).

**Gate:** catalog build succeeds against the real local ArmorPaint
checkout/build and returns a non-empty, sane-looking list for each category.

## Phase 4 — `run_script` escape hatch + polish

The purpose-built escape-hatch tool for anything the above don't cover.
Documentation pass, packaging check (`pip install -e .` from a clean clone),
README accuracy pass.

**Gate:** a clean-clone install + `ap-mcp --check` + smoke test all pass with
no undocumented manual steps.

## Deferred (not scoped into any phase above)

- **Live mode** — interactive, GUI-attached control. See the design spec's
  "Deferred: live mode" section. Two architecture options are named there;
  neither is chosen. Only take this on once batch mode (Phases 0-4) is solid
  and live mode is actually wanted, per Grayson's "both, batch first"
  direction from the brainstorming session.
- **Material authoring from scratch** (node-graph generation from a
  text/style description) — the harder generative problem the reference
  project also attempts; explicitly out of v1 scope.
