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

## Phase 6 (APPROVED 2026-09-27) — rename hardening, UV check, mesh replace

> **Approved by Grayson 2026-09-27**, as written in "Decisions applied"
> below. Spikes S1-S5 run before any 6.2/6.3 tool code. Decisions recorded
> the same day (grill session). The grill answered D1-D5 plus seven design questions, and split
> the work in two: **Phase 6** needs no ArmorPaint C change, and **Phase 7**
> (below) holds all the C work plus item 9. Where "Decisions applied"
> disagrees with the research text further down, the decisions win; the
> research is kept for its citations.

### Decisions applied (2026-09-27; amended the same day from spikes S1-S5)

**Build order:** 6.0 (done) → 6.1 hardening → 6.2 item 10 → 6.3 item 8.
Item 8 reuses item 10's UV module and 6.1's save path, so both land first.

**6.1 — Hardening (D1, plus two shipped-bug fixes Grayson folded in).**
- Keep pinning to current-`main` names; no alias table. Widen `--check` to
  diff **every** minic name the project emits (`script_gen`, the mesh-edit
  tools, `create_procedural_material`, `run_script`'s wrapper) against
  `--api`'s registered list, not just the 7 mesh-edit names.
- **Abort detection via stdout (S2).** Stdout **is** capturable on this
  build (upstream `3b77ab8c`, `base/sources/iron_system.c:44-54`: pipe →
  `WriteFile`). Every tool returns `ok=False` on a nonzero exit, a timeout,
  or any `<script>:<line>: error:` line in stdout (unknown function,
  missing field, null pointer, syntax error). Exit codes and timeouts
  matter: ~5% of spike launches crashed (0xC0000005) under memory
  pressure, and one hung with a complete file.
- **Saving tools open the original and save to a fresh sibling (S2).** The
  script opens the caller's file directly (never written), and its **last
  statement** is `project_filepath_set(<fresh sibling in the target dir>)` +
  `project_save(0)`: an error *after* the save still leaves the file.
  Completion = that file exists after a normal exit. Python then verifies
  and `os.replace`s it onto `output_project` or the caller's file. This fixes
  **Known Issue #11** (the Phase 5 tools' `copy2`-then-open breaks the
  `.arm`'s relative asset paths when the output dir differs) and gives 6.3
  its verify-then-commit.
- **`inspect_project` backslash fix (Known Issue #10).** `--api`'s JSON
  leaves strings unescaped (`base/sources/iron_armpack.c:799-801`), so any
  backslash path (every project after an append; likely any Windows GUI
  import) breaks `json.loads` and the shipped tool returns `ok=False`.
  Escape backslashes before parsing. A quote inside a name remains a
  documented hazard (upstream fix: Phase 7 candidate).
- `run_script` and read-only tools: the stdout scan is the sentinel (no
  trailing file write; an early `return` would false-fail). Correct the
  stale "stdout isn't capturable" docstrings.
- Touches all 7 mesh-edit tools, `run_script` and `inspect_project`, so the
  gate includes a full regression rerun.

**6.2 — Item 10, `check_mesh_uvs` (tiered, strict default).**
- **Error:** UV-degenerate triangles that have real 3D area covering more
  than ~0.1% of the surface (below that: a warning; triangles degenerate in
  3D too are ignored). *Refined from S3 F1: a strict per-triangle rule
  rejected a legit round trip. Consequence: a Blender extrude (4.1% of
  surface in zero-UV-area side faces) errors; revisit at recalibration.*
  UVs outside [0,1] are an error too; `allow_udim=True` downgrades that to a
  warning. The importer folds UVs > 1 to their fraction
  (`base/sources/iron_obj.c:628-638`, S3 F2), so out-of-range is checked
  reliably only on a source OBJ before launch; in a project export it shows
  only as u < 0 or v > 1.
- **Warning:** overlap % and flipped-triangle %. **Info:** coverage %.
- `valid` = no errors. `replace_mesh`'s post-verify uses the same verdict.
- One shared pure-stdlib rasterizer (N=256 count raster), based on S3's
  prototype `uvraster.py`: coverage, overlap, IoU and retention.
- Per object: split the export on `o <name>` (S1: groups are contiguous,
  dedup is per object, face indices are global and safe to rebase). Key
  groups by name, never by position.

**6.3 — Item 8, `replace_mesh`.**
- **Modes, caller picks:** `mode="round_trip"` (same asset re-exported with
  UVs kept, so the paint carries over unchanged) or `mode="swap"` (a
  different mesh; paint loss expected, but layers and the other objects
  survive).
- **UV match = coverage IoU + texel retention** (S3: IoU alone passes
  coverage-preserving scrambles, e.g. swapped congruent islands 0.9963,
  mirrored sphere 1.0000). Retention = share of the old layout's texels
  whose new 3D position is within 5% of the old bbox diagonal, after
  normalizing translation + uniform scale. Both always reported. In
  `round_trip` mode: **error** if IoU < 0.95 or retention < 0.85,
  **warning** if retention < 0.98 (S3 gap: worst round trip 0.907 vs worst
  scramble 0.7385). Re-checked on real ArmorPaint round trips before they're
  fixed in code.
- **Formats: `obj`, `fbx`, `glb`, `gltf` natively, plus `blend`** (S5;
  this build has `WITH_PLUGINS`, `paint/plugins/plugins.c:167-172`,
  `paint/project.c:14`; corrects S3 F3's "no FBX").
  - Reject any other extension before launch: an unregistered extension's
    importer is called without a NULL check (`io/import_mesh.c:39-42`).
  - `.blend` shells out to the `blender` path in `data\config.json` next to
    `AP_BINARY` (`config.c:44-56`); it's empty on this machine and the append
    silently no-ops. Pre-check the key; reject with a clear error if unset.
  - Blender FBX lands at **100x** (unit scale); UVs are exact. Accepted:
    geometry and retention comparisons are scale-normalized, and the result
    **warns** when the replacement's bbox size is off from the old object's
    by more than 2x.
  - OBJ is rejected before launch if it has no `vt` lines or more than one
    `o` group; out-of-range UVs are checked here.
  - Non-OBJ has no pre-launch UV or object-count check. The post-verify
    count check catches multi-mesh files. A UV-less non-OBJ is caught only
    **probably** until Phase 7's `texa` zero-init lands; no gate test may
    expect its rejection until then.
- **No UVs = reject**, in both modes.
- **Carry-over (S4, all verified after reopen):** name; transform (then
  `transform_build_matrix`, or the write is lost on save); **parent**
  (`object_set_parent`; without it a parented object's world moves);
  **children** of the old object (moved onto the new one before removal);
  material (minic can't enumerate materials, so Python reads
  `mesh_materials[i32]` + `material_nodes[].name` from `--api` and passes the
  name; the script cross-checks `_material_<id>`, fails closed on a duplicate
  name, and maps -1 to `script_object_set_material(nw, NULL)`; Python
  pre-checks duplicates). Physics settings are not carried.
- **Script shape (S4/S5):** rename the old object to `__ap_mcp_replaced__`
  before the append (else the stage list keeps a duplicate); guard
  "old not found" and "append didn't change `paint_object`" with an early
  `return` + marker (the `.blend` no-op would otherwise rename the wrong
  object); append **before** remove (single-object guard); the append path
  must use **backslashes, doubled** in the literal (forward slashes make
  `iron_file_exists` fail and the append silently no-ops); `project_save`
  last. Working snippet:
  `docs/superpowers/spikes/2026-09-27-phase6-spikes-S1-S2-S4-S5.md`.
- **`mesh_assets` repoint: accepted**, with a warning on multi-object
  projects (Reimport Mesh would reload only the replacement,
  `project.c:379-381`).
- **Verify-then-commit** via 6.1's fresh-sibling save: a failure never
  touches the target, even with `in_place=True`.
- **Post-verify:**
  - object-name set and count unchanged, and `__ap_mcp_replaced__` absent
    (in multi-stage projects remove only hides);
  - the replaced object's resolved geometry matches the replacement's
    (scale-normalized);
  - untouched objects' resolved per-object data identical (v/vt/vn + faces
    rebased to local indices). **Not raw lines**: face indices shift for
    every group after the removed one;
  - transforms and parents via `--api` `mesh_transforms` /
    `mesh_parents[i32]`, mapped through `mesh_datas[].name` (scene-text order
    isn't `paint_objects` order once parented);
  - layer count unchanged; `check_mesh_uvs` `valid` on the replaced object;
    in `round_trip` mode, IoU and retention clear their thresholds.

**Spikes S1-S5: all done 2026-09-27.** Full write-ups, evidence and
fixtures: `docs/superpowers/spikes/2026-09-27-phase6-spikes-S1-S2-S4-S5.md` (S1, S2,
S4, S5) and `docs/superpowers/spikes/2026-09-27-phase6-spike-S3.md` (S3); spike scripts and fixture files stay in the session scratchpad `phase6-spikes\` until copied into `tests/fixtures` by the plan's tasks. Controller spot-checks:
S3 self-tests re-run (32/32); A's `WITH_PLUGINS`, stdout and JSON-escape
claims read in source; the `inspect_project` failure reproduced.

**Empirical findings (summary).**
- **S1:** per-object isolation holds; separate-process exports are
  byte-identical; an append doesn't disturb untouched groups' resolved data.
- **S2:** fresh-path save works (input never modified, 6 runs byte-identical);
  an undefined call before the save → no file; after it → file still written.
  Stdout carries errors, `console_log`, `Project saved`. Load + re-save does
  **not** reliably keep the `.arm` md5 (deterministic change on one fixture),
  so hash signals are out in both directions.
- **S3:** N=256; IoU gap 0.9987 vs 0.7651 for the requested families, but
  coverage-preserving scrambles defeat IoU → retention added. Pure stdlib:
  0.33 s at 12.9k tris, 1.63 s at 100k; numpy isn't in the venv. Blender
  5.1.1's Smart UV Project is nondeterministic: **commit fixtures, never
  regenerate them in CI.** Quantization was emulated, not run.
- **S4/S5:** see "Carry-over" and "Script shape" above. GLB appends natively
  (within 3.0e-5); FBX at 100x; `.blend` no-ops with the config unset.

**Fixtures:** an objects-fixture generator (`script_project_new` + cone +
torus, one object with a material override and a non-identity transform,
plus a parented variant); a replacement OBJ with UVs; the S3 round-trip,
re-unwrap and scramble variants (committed, never regenerated); a **GLB**
with UVs as the non-OBJ fixture (spike A's `repl_grid5.glb`). FBX and
`.blend` are covered by pre-check unit tests only. Every other format path
is untested; say so in the tool docstring.

**Known risks carried into Phase 6 (closed in Phase 7 where possible):**
- A UV-less non-OBJ replacement is caught probabilistically (`texa` not
  zeroed).
- Object-mask remap on delete (D5), made likelier by the replacement
  landing at the end of the object list (minic can't restore order). Not
  headless-testable.
- Reimport Mesh after a replace on a multi-object project collapses the
  scene (stock behavior; warned).
- A quote inside an object/material name still breaks `--api` JSON.
- Untested: multi-stage projects, multi-mesh GLB/FBX, non-uniformly scaled
  parents, paint pixel content (layer counts only), linked textures under
  the old staging hazard.

---

*Research text below is the pre-grill draft, kept for context.*

> **Draft for Grayson's review, not a scheduled phase.** Written 2026-09-27
> from source reading only: nothing was built or run (the ArmorPaint
> working tree was mid-rebuild), so every feasibility claim below is
> **source-read, not empirically verified**. ArmorPaint citations are
> against `origin/main` = `85f6cf1c` (2026-09-24) unless another SHA is
> named, with paths relative to `paint/sources/` unless they start with
> `base/` or `paint/`. `origin/main` is a moving ref, so re-pin before
> acting on a line number. Covers ROADMAP.md items 8-10 plus a prerequisite
> (6.0) the research turned up. Items are ordered by readiness, not by
> roadmap number.

**Scope:** 6.0 re-baselines on current upstream and blocks everything else.
Item 10 becomes a no-patch, Python-side check. Item 8 becomes a no-patch
minic composition. Item 9 starts with a zero-patch spike and needs a small
C change only after it. One gate at the end.

### 6.0 — Re-baseline on current upstream `main` (prerequisite) — ✅ DONE 2026-09-27

> **Done the same session this draft was written**, recorded as a Phase 5
> regression fix (STATUS.md Known Issue #6, closed; that settles D7 unless
> Grayson overrules it). `AP_BINARY` is now built from the ArmorPaint
> checkout's `fix/mesh-accumulator-zero-init` at `287e63f4`, which is
> `origin/main` `85f6cf1c` plus the zero-init fix. The zero-init fix was
> rebased, trimmed to 11 `memset` lines, and opened upstream as
> armory3d/armorpaint#2148. The project now pins `util_mesh_uv_unwrap`
> (D1, pin option). Evidence on that binary:
> - `pytest -q`: 122 passed.
> - `-m integration`: 18 passed, including the unwrap test and the
>   smooth/bevel near-zero scans.
> - `smoke/smoke.ps1`: 13/13.
> - `ap-mcp --check`: all green.
> - 10-run smooth/bevel repro: stock 3/10 and 9/10 corrupted, fixed 0/10 and
>   0/10.
>
> Both behavior changes flagged in task 3 below (`project_filepath_set`
> slash conversion, `--background --script` waiting on callbacks) are
> exercised by that green suite. The text below is the pre-rebuild research,
> kept for context.

**Why it blocks, part 1: upstream renamed one of Phase 5's seven
functions.** `01bae6c5` ("paint: uv unwrap cleanup", 2026-09-17, about 40
minutes after #2139 merged) replaced `X0(plugin_uv_unwrap_button, ...)`
with `X0(util_mesh_uv_unwrap, "v()", v)` (`minic_api_list.h:551`).
`plugin_uv_unwrap_button` no longer exists anywhere on `origin/main`. As
of `a27eb28`, this project still emits the old name at `src/armorpaint_mcp/server.py:351`
(the call) and `:332` (docstring), checks for it at
`src/armorpaint_mcp/catalog.py:129` (`--check`'s mesh-edit list), and
asserts it at `tests/test_catalog.py:122,134`, `tests/test_doctor.py:35`
and `tests/test_server.py:861`. Against a build of current `main`,
`ap-mcp --check` fails its "mesh-edit patch" row, and `unwrap_mesh_uvs`
calls an undefined minic function. That aborts the script before
`project_save(0)` while the process still exits 0, so the tool returns
`ok=True` pointing at an unedited copy: the silent-failure mode
`run_script`'s docstring already documents. The integration test would
catch it; a caller would not. Already logged as STATUS.md Known Issue #6
(`a27eb28`); this section adds the silent `ok=True` consequence.

Every other minic name this project emits is still registered on
`origin/main`: the six `util_mesh_*` (`minic_api_list.h:480-485`),
`project_save`, `project_filepath_set`, `script_project_new`,
`script_material_*`, `script_fill_layer`, `export_texture_run`,
`script_export_mesh`, `console_log`, and `printf` (a native builtin,
`minic_api.c:508`). `6c84667a` ("script api cleanup") renamed the
`plugin_*` registration family to `script_*`; this project calls none of
them.

The renamed function's body is a refactor, not a behavior change. It keeps
the same merge-all-objects-then-unwrap flow as the old `ui/tab_plugins.c`
version at `e246089d`. Position packing moved into
`util_mesh_pack_merged_positions` (`util/util_mesh.c:939`),
`proc_uv_unwrap` became `util_uv_unwrap_run` (now in
`util/util_uv_unwrap.c`), and the `WITH_PLUGINS` gate is gone. The Phase 5
unwrap test still has to re-prove it.

**Why it blocks, part 2: the local binary can't evaluate item 8.** The
local `AP_BINARY` is a 2026-09-17 build of `spike/minic-decimate` at
`e246089d`, 48 commits behind `origin/main`. That base predates
`4665266b` ("paint: append mesh fixes"), which added
`script_append_mesh_finish` (`minic_impl.c:413-418`) so a script-driven
append actually runs `import_mesh_finish_import`. Before it, the append
path never finished the import and left the global `import_mesh_append`
flag set. This likely explains why ROADMAP.md recorded item 8 as
"inconclusive".

**Tasks:**
1. Rebuild `AP_BINARY` from `origin/main` plus a cherry-pick of `e246089d`
   (the zero-init fix, STATUS.md Known Issues #4/#5). That fix is still
   needed upstream: `f32_array_create` and `i16_array_create` still don't
   zero (`base/sources/iron_array.c:399-406` and `:552-559`, both reaching
   `realloc` via e.g. `:103-106`), and `util/util_mesh.c:729` and
   `:1292-1295` still allocate the same accumulators. `git apply --check`
   of `e246089d` against `origin/main`'s `util_mesh.c` succeeds (hunks at
   offsets -33/+70/+68; checked on a scratch copy, not in the checkout).
2. Replace the unwrap name (see D1). Either pin to `util_mesh_uv_unwrap`
   and require a post-`01bae6c5` build, or resolve the name from `--api`,
   which the project's own "dynamic catalogs" convention favors: `--api`
   prints `minic_api_header_generate()`, which lists every registered
   function name (`minic_api.c:996`, `:1048`). Either way, update
   `catalog.py`'s `_MESH_EDIT_PATCH_FUNCTIONS`, the doctor message, and
   the four test sites. Pinning must land together with the rebuild. On
   the current pre-`01bae6c5` binary, the new name hits the same silent
   `ok=True` failure in reverse.
3. Re-run the full suite on the rebuilt binary. Two behavior changes
   landed in the same window and look benign here, but neither has been
   verified: `project_filepath_set` now converts `/` to `\` on Windows
   (`minic_impl.c:164-169`), and `--background --script` now waits for
   pending script callbacks before quitting (`args.c:117-123`).

### Research: item 10, UV validity check (now 6.2)

**What the "UV validity check" is in source.** The closest match found is
`b62fd323` ("Add basic uv map check", 2025-09-09): 8 lines inside the OBJ
parser (`base/sources/iron_obj.c:319-322`). If a face's first three UV
indices are all 0 (Blender's placeholder for un-unwrapped faces), it logs
`console_info("Warning: Mesh is not fully UV unwrapped")` once per parse.
The flag is file-`static` (`iron_obj.c:33`, reset at `:239`). The check
runs only for OBJ imports and isn't a function, and its only output is a
console line, which this project already knows is not pipe-capturable on
Windows (`WriteConsoleW`; see `run_script`'s docstring). **So it's not
reachable from minic, and it isn't a one-line registration.** Exposing it
would need new C that returns a result, not just a log line. An older
check also exists: a mesh imported with no UVs at all sets
`import_mesh_needs_unwrap` (`io/import_mesh.c:182`), which opens the
unwrap dialog (`:143-146`; `4582b27f`, 2021). It's GUI-only, runs only on
the replace path, and isn't minic-reachable either. Not verified: that
ArmorPaint 1.0's changelog entry refers to either commit.

**Proposed scope instead:** a read-only `check_mesh_uvs(project)` tool
built entirely in this project's Python layer. One `--script` run
calls `script_export_mesh` to a temp OBJ (the same export the Phase 5
tests already parse in `tests/_mesh_edit_test_helpers.py`), then pure
Python checks the result. This is this project's own UV check, not a port
of upstream's heuristic. OBJ export quantizes UVs to 16 bits, and the
vt-index-0 signal upstream keys on won't survive a re-export. Candidate
criteria, to settle at plan time:
- faces whose three UVs coincide (zero UV area);
- UVs outside [0,1];
- degenerate or flipped UV triangles;
- a UV-coverage figure.

Overlap detection is possible but naive O(n^2); defer it unless asked.

**Tasks:**
1. A pure-Python UV analysis module, with unit tests on synthetic OBJ
   text (clean, all-zero face, out-of-range, degenerate).
2. The MCP tool. It reuses `_run_mesh_edit`'s path validation but stays
   read-only: no copy, no `project_save`.
3. One integration test.

**Feasibility:** source-read only. Needs 6.0 only for a trustworthy
binary, not for any new registration.

### Research: item 8, non-destructive mesh replace (now 6.3)

**The roadmap's two paths, as they read on `origin/main`:**
- **`script_import_asset(path, hdr)` is destructive.** It
  (`minic_impl.c:397-407`) calls `import_asset_run(path, -1, -1, false, ...)`,
  which for a mesh calls `import_mesh_run(path, true, true, false)`, i.e.
  clear_layers=true and replace_existing=true (`io/import_asset.c:35-36`).
  `import_mesh_make_mesh` then:
  - deletes every other paint object (`io/import_mesh.c:201-208`);
  - swaps the main object's data;
  - pops and unloads **every layer**, creates one empty layer and resets
    history (`:241-249`);
  - nulls stages (`:251`).
- **`script_append_mesh(path)` is additive.** It
  (`minic_impl.c:420-432`) calls `import_mesh_run(path, false, false, true)`,
  so no layers are cleared and it runs in append mode. Each new object:
  - gets the *current* paint object's material and no parent
    (`io/import_mesh.c:271-272`);
  - gets a uniquified name (`:277-281`);
  - is pushed to the end of `paint_objects` (`:283`).

  Since `4665266b` the append then finishes the import synchronously
  (`minic_impl.c:413-418`).

**New since the roadmap:** `c0df922d` added
`X1(script_object_remove, "v(p:object_t o)", v, p)`
(`minic_api_list.h:500`, body at `minic_impl.c:819-838`). It no-ops
unless the object is a mesh object in `paint_objects` **and** the project
has at least 2 objects (`:823`). Otherwise it calls the GUI's own delete,
`tab_meshes_draw_context_menu_delete` (`ui/tab_meshes.c:443-477`). The
same commit commented out the raw `object_remove`/`mesh_object_remove`
registrations (`minic_api_list.h:18`, `:69`), so this is now the supported
removal path.

**So replace does compose on `origin/main`.** Four calls, in this order:
1. Look the old object up with `script_get_object(name)`
   (`minic_api_list.h:492`, `minic_impl.c:180-187`).
2. `script_append_mesh(new_path)`.
3. `script_object_remove(old)`.
4. `project_save(0)`.

Append must come before remove, or the `length < 2` guard makes remove a
no-op on a single-object project. Saving in the same script is safe, for
four reasons:
- the removal splices the object out of `paint_objects` synchronously
  (`ui/tab_meshes.c:464`) and defers only cleanup to the next frame
  (`:476`, `:413-424`);
- `project_save` itself also defers to the next frame (`project.c:59`);
- the next-frame queue is FIFO (`base/sources/iron_system.c:1171-1172`,
  drained in order at `:1138-1139`), so cleanup runs before the save;
- `export_arm_run_project` iterates `paint_objects` anyway
  (`io/export_arm.c:216`, `:308`).

**What happens to paint data (source-read).** Neither append nor remove
touches layers. Layers are UV-space textures shared by every object, so
the replacement shows the existing paint *through its own UV layout*.
That's correct only if its UVs match the old mesh's (e.g. a re-export of
the same asset with edited geometry); otherwise the paint comes out
scrambled. Nothing reprojects or transfers paint. The tool has to handle
these hazards:
- **A replacement without UVs gets garbage UVs.** `import_mesh_add_mesh`
  allocates `texa` with `i16_array_create` (`io/import_mesh.c:260-263`),
  which doesn't zero (see 6.0). The append path never triggers the unwrap
  prompt either: `import_mesh_needs_unwrap` is set only on the replace
  path (`:182`). Running `util_mesh_uv_unwrap()` afterwards is no fix,
  because it re-unwraps *all* objects into one atlas
  (`util/util_mesh.c:926-997`) and wrecks the kept objects' UVs.
- **Layer object masks aren't remapped on delete.** `object_mask` is a
  1-based index into `paint_objects` (`io/export_texture.c:233`). The
  delete path's only remap (`ui/tab_meshes.c:128-134`) handles re-sorting,
  and it's computed after the removal, so masks pointing past the removed
  index go stale. For a single-object swap this is accidentally right: the
  new object slides into index 0 and inherits mask 1. In a multi-object
  project, a masked layer can land on the wrong object. By contrast,
  `util_mesh_merge_geometry_down` remaps masks itself
  (`util/util_mesh.c:637-645`), which makes the delete path a small
  upstream fix candidate (D5).
- **Silent partial success.** A wrong old name makes `script_get_object`
  return NULL and turns remove into a no-op, but the appended mesh is
  still saved and the process exits 0. An OBJ with several `o` groups
  appends several objects. A mesh listed in another stage is only hidden,
  not removed (`ui/tab_meshes.c:447-462`).
- **Per-object state is lost.** The old object's material override,
  transform, name and physics settings don't carry over. Registered calls
  can restore some of them: `script_object_set_material`
  (`minic_api_list.h:528`), `script_object_set_name` (`:501`), and the
  `transform_t` fields reached through `object_t.transform`.

**Minimal tool signature (sketch):**
`replace_mesh(project, old_object: str, new_mesh: str, output_project=None, in_place=False, timeout_s=DEFAULT_TIMEOUT_S)`.
It reuses `_run_mesh_edit`'s copy/`in_place` plumbing.

Pre-checks, in Python:
- `old_object` exists, via `inspect_project`'s `scene_objects`.
- `new_mesh` exists, is inside `AP_ALLOWED_ROOTS`, has a supported
  extension, and has `vt` lines if it's an OBJ.
- Both strings pass the same double-quote rejection as
  `script_gen._output_dir_literal` before being embedded in minic.

Post-verification goes through `inspect_project`, not `ok=True`: the same
object count, the old name gone, exactly one new name. Keeping the old
name, copying the transform and restoring the material are open (D4).

**Test fixture (new; none exists yet):**
`tests/fixtures/sample_project_objects.arm`, generated headlessly by a new
`tests/fixtures/generate_objects_fixture.py`. The script calls
`script_project_new()`, then `script_shape_add("cone")` and
`script_shape_add("torus")` (`minic_impl.c:773-797`), then
`project_filepath_set` + `project_save(0)`. That gives three objects with
distinct geometry. Shape names come from `script_shape_list()`, i.e. the
`data/meshes/*.arm` files plus the built-in `plane`/`sphere`
(`ui/box_new_project.c:3-22`). Alongside it, commit a small replacement
OBJ with UVs and a known, distinct vertex count. The distinct fixture name
avoids confusion with `sample_project_multi.arm`, which is
multi-*material* and single-object. Limitation: minic registers no
`slot_layer_t` struct and no layer-mask setter, so a headless fixture
can't set an object-masked layer. The mask hazard above can only be
covered by a GUI-authored fixture (a host-only step) or stay a documented
risk.

**Tasks:**
1. The fixture generator and fixture.
2. A spike: the four-call composition via `run_script` on a copy,
   verified by `inspect_project` plus an OBJ export, before any tool code.
3. The `replace_mesh` tool and unit tests.
4. Integration tests (see Gate).

## Phase 7 (DRAFT, not approved) — ArmorPaint C changes + item 9

> Split out of Phase 6 on 2026-09-27 (grill Q12). Starts only after
> Phase 6's gate is green.

**Route (D3): upstream-first, bridged locally.**
- One small, single-purpose upstream PR per change. **Each PR is opened
  only on Grayson's explicit go**, and each change to the ArmorPaint
  checkout still needs his go (project CLAUDE.md). D3 is a default route,
  not standing approval.
- A local integration branch in the checkout = upstream `main` + every
  open PR (today: #2148). `AP_BINARY` builds from it. `--check` detects
  each dependency. When a PR merges, rebuild and drop it from the stack.
- ROADMAP.md's local-patch policy becomes the fallback for changes
  upstream declines.

**The three C changes:**
1. **`texa` zero-init** in `import_mesh_make_mesh` / `import_mesh_add_mesh`
   (`io/import_mesh.c:183-186`, `:260-263`), the same class as #2148. A
   UV-less mesh then comes out as deterministic all-(0,0) UVs, which
   `check_mesh_uvs` always flags, so Phase 6's non-OBJ risk closes. Add the
   gate test for a UV-less non-OBJ rejection only once this is in
   `AP_BINARY`.
2. **Object-mask remap on delete (D5: yes, upstream it).** The delete path
   (`ui/tab_meshes.c:128-134`) should remap the way
   `util_mesh_merge_geometry_down` already does (`util/util_mesh.c:637-645`).
3. **`script_object_merge(object_t *o, object_t *into)` (D2).** It goes in
   `minic_impl.c`, in the maintainer's `c0df922d` shape: take `object_t*`,
   check `ext_type`, and wrap the GPU state (~25 lines across 3 files).
   Scripts never touch `->ext`, so the zero-patch `->ext` spike (7.1 task
   1 below) is **dropped**.

Then item 9's `merge_mesh_pair` tool goes on top of change 3.

**Further upstream candidates found by the Phase 6 spikes** (same route,
each needs Grayson's go): escape strings in `armpack_to_json_value`
(`base/sources/iron_armpack.c:799-801`, Known Issue #10's root cause); a
NULL check for an unregistered mesh-importer extension
(`io/import_mesh.c:39-42`).

### 7.1 (was 6.3) — Item 9: targeted 2-object merge

> **Superseded in part by D2 (2026-09-27):** the wrapper, not the
> one-liner; no `->ext` spike. The text below is the pre-grill research.

**The Phase 5 and ROADMAP "no accessor" conclusion was wrong when it was
made.** `util_mesh_merge_geometry_down(mesh_object_t *main_object,
mesh_object_t *below)` (`util/util_mesh.c:609-652`) needs two mesh
objects, and minic can already reach both:
- `script_get_object(name)` returns any paint object's `object_t*`.
- minic registers `object_t` as a struct, including its `ext` pointer
  (`minic_api.c:767-780`, `ext` at `:778`). For a paint object, `ext` is
  the `mesh_object_t*`.
- Both were already present at `2b528475`, the #2139 commit itself.
- Upstream's own shipped dev script does exactly this:
  `object_t *proto = script_shape_add("cube"); mesh_object_t *proto_mo = proto->ext;`
  (`paint/assets/plugins/dev/blocks.c:195-196`).
- minic doesn't type-check pointer params: `minic_api_register` strips
  `:typename` from signatures before registering (`minic_api.c:356-372`).

**So the smallest change is a one-line registration, the same class as
#2139:**
`X2(util_mesh_merge_geometry_down, "v(p:mesh_object_t main_object,p:mesh_object_t below)", v, p, p)`.
The function is safe to expose headlessly as written. It checks that both
objects are in `paint_objects` and distinct (`util/util_mesh.c:611-615`),
remaps layer masks itself (`:637-645`), and doesn't require the two
objects to be adjacent. Only the GUI's `static tab_meshes_slot_below`
(`ui/tab_meshes.c:491-499`) limits it to "the one below".

**Alternative shape:** a `script_object_merge(object_t *o, object_t *into)`
wrapper in `minic_impl.c`. That matches the maintainer's own current
convention for object ops: `script_object_duplicate`, `_clone` and
`_remove` all take `object_t*`, check `ext_type`, and wrap GPU state
(`minic_impl.c:799-838`). `c0df922d` is exactly that shape: 25 added lines
across 3 files. Given the maintainer's warning that the script API "will
need a cleanup", the wrapper is likelier to survive it; the one-liner is
smaller (D2).

**Tasks:**
1. A zero-patch spike, runnable on any current build:
   `object_t *o = script_get_object("A"); mesh_object_t *m = o->ext;`,
   then prove `m` is usable. For example, `script_object_set_name(m->base, "A2")`
   + `project_save(0)`, and `inspect_project` shows the rename. This
   project has hit silent minic field-access aborts before (design spec
   Amendment 2), so `->ext` has to be proven empirically, one statement at
   a time.
2. The C change, upstream-first or local per D2.
3. A `merge_mesh_pair(project, keep: str, merge: str, ...)` tool on
   `_run_mesh_edit`, pre-checking both names and N >= 2.

**Not ready to schedule** until D2 is decided and the spike passes. If the
change goes upstream-first, the tool waits for the merge.

**Gates (split 2026-09-27, grill Q12).**

**Phase 6 gate:** headless-verifiable, recorded in STATUS.md with
evidence:
- 6.0: met (see its DONE note).
- **6.1 hardening:**
  - `--check` fails loudly when any emitted minic name is missing from
    `--api` (unit test on a mocked `--api` listing with one name removed).
  - A script with an injected undefined call returns `ok=False` (stdout
    error line), for a saving tool and for `run_script`.
  - `inspect_project` returns `ok=True` with correct objects on a project
    whose `--api` JSON contains backslash paths (Known Issue #10).
  - A mesh-edit tool writing `output_project` into a different directory
    leaves the result's relative asset paths resolvable, and the caller's
    file is byte-identical afterwards (Known Issue #11).
  - **Full regression rerun** on the same binary: `pytest -q`,
    `-m integration`, `smoke/smoke.ps1`, all exit 0.
- **6.2 item 10:** unit tests on synthetic OBJ text flag each defect class
  at its tier (and `allow_udim` downgrades out-of-range) and pass a clean
  mesh; an integration run on `sample_project.arm` returns a well-formed
  per-object report.
- **6.3 item 8** (on the new objects fixture):
  - The post-verify list in "Decisions applied" holds, for an OBJ and for
    the committed non-OBJ fixture.
  - Transform and material come back restored wherever S4 proved them
    reachable.
  - `round_trip` passes S3 round-trip variants, fails a re-unwrap (on
    IoU) and fails a coverage-preserving scramble such as d4's island swap
    (on retention). `swap` accepts both and reports their IoU and
    retention.
  - Negative tests: a bad old name gives `ok=False`; an OBJ without `vt`,
    and an OBJ with two `o` groups, are rejected before launch; with
    `in_place=True`, a failing post-verify leaves the caller's file
    byte-identical.
  - Multi-object projects get the `mesh_assets` warning.
  - Object-mask remapping is out of headless reach and recorded as a known
    risk, not gated.
- **Smoke:** one registration probe per new tool.

**Phase 7 gate:** item 9's list below, plus: a UV-less non-OBJ replacement
is rejected deterministically once the `texa` fix is in `AP_BINARY`, and
`--check` reports every open-PR dependency of the integration build.

*Pre-grill gate draft, kept for context:*
- **6.0** (✅ met 2026-09-27, evidence in 6.0's DONE note):
  - `ap-mcp --check` is all green.
  - `--api` output contains `util_mesh_uv_unwrap` and not
    `plugin_uv_unwrap_button`.
  - The full existing suite passes on the rebuilt binary: `pytest -q`,
    `-m integration`, and `smoke/smoke.ps1` exit 0. That includes the
    Phase 5 unwrap test and the near-zero-component scans for smooth and
    bevel.
- **Item 10:**
  - Unit tests on synthetic OBJ text flag each defect class and pass a
    clean mesh.
  - An integration run on `sample_project.arm` returns a well-formed
    report.
- **Item 8** (on the new objects fixture):
  - The object count is unchanged.
  - The old name is gone and exactly one new name exists
    (`inspect_project`).
  - The replaced object's exported vertex/face count equals the
    replacement mesh's.
  - Every untouched object's exported geometry is identical before and
    after.
  - The layer count is unchanged.
  - Negative tests: a bad old name returns `ok=False` and writes no file;
    an OBJ without `vt` lines is rejected before launch.
  - Object-mask remapping is out of headless reach (see the fixture note)
    and is recorded as a known risk, not gated.
- **Item 9** (only if scheduled):
  - N objects become N-1.
  - `keep`'s name survives and `merge`'s is gone.
  - The merged vertex count equals the sum of the two.
  - A third object's geometry is untouched.
- **Smoke:** one registration probe per new tool, as in Phase 5.

### Decisions for Grayson

All answered in the 2026-09-27 grill; see "Decisions applied" at the top
of Phase 6 and the Phase 7 block.
- ~~**D1 — Rename handling (6.0).**~~ **Pin + loud detection:** keep
  pinning; `--check` diffs every emitted name against `--api`; add a
  completion sentinel (6.1).
- ~~**D2 — Item 9's C change: upstream-first or local patch?**~~
  **Upstream-first (per D3), as a `script_object_merge` wrapper** in the
  `c0df922d` shape. No `->ext` spike.
- ~~**D3 — Default route for future minic registrations.**~~
  **Upstream-first with a local integration branch as the bridge.** Each
  PR and each checkout change still needs Grayson's explicit go.
- ~~**D4 — Item 8 semantics.**~~ **(a)** reject in both modes; **(b-d)**
  carry name, transform and material in both modes; **(e)** both
  meanings, caller picks via `mode`, and IoU gates `round_trip`; **(f)**
  accept the repoint and warn on multi-object projects. Original
  sub-questions:
  - (a) Reject replacement meshes without UVs, or accept them with a
    warning?
  - (b) Does the replacement keep the old object's name?
  - (c) Does it inherit the old object's transform?
  - (d) Should the tool restore the old object's material via
    `script_object_set_material`?
  - (e) Is "the paint shows through the new UVs, unchanged" what
    "non-destructive" should mean? Or does it mean paint reprojection,
    which ArmorPaint doesn't offer headlessly?
  - (f) Is it acceptable that `import_mesh_run` also repoints the
    project's `mesh_assets` at the replacement file
    (`io/import_mesh.c:60-64`)? After a replace, "reimport mesh" reloads
    the new file, not the original.
- ~~**D5 — Upstream the `object_mask`-on-delete remap?**~~ **Yes**, as
  Phase 7 change 2 (per D3).
- ~~**D6 — Upstream the zero-init fix now?**~~ Done 2026-09-27 on
  Grayson's go-ahead: armory3d/armorpaint#2148.
- ~~**D7 — Bookkeeping for 6.0.**~~ Recorded as a Phase 5 regression fix
  (STATUS.md Known Issue #6).
