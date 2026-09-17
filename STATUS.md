# 📊 STATUS — Tool-ArmorPaintMCP

> **Living truth.** Updated continuously; never let it flatter the project.
> States: ✅ verified (gate evidence exists) · 🔌 wired (code exists, no gate yet) · ⬜ not started.

**Last updated:** 2026-09-17
**Open phase:** none -- Phase 5 was the last phase in `docs/PLAN.md` (ROADMAP.md
items 8-10 -- non-destructive mesh replace, targeted 2-object merge, UV
validity check -- remain open on the roadmap but were never scoped into a
`docs/PLAN.md` phase; not implied done by this line)

---

## Phase Gates

| Phase | Scope | Gate | Evidence |
|---|---|---|---|
| 0 | Scaffold + smoke harness | ✅ 2026-09-15 | `smoke/smoke.ps1`: 3 passed, 0 failed (package imports, `--version`, `--help`) |
| 1 | reexport_project tool (native export flags, no script) | ✅ 2026-09-15 | tests/test_reexport_integration.py: 1 passed, 5 real PNG files produced from tests/fixtures/sample_project.arm |
| 2 | `create_procedural_material` tool (single-process script build+fill+export) | ✅ 2026-09-15 | `.venv\Scripts\python.exe -m pytest -q`: 53 passed, 0 failed; `-m integration`: 2 passed (`test_checker_material_produces_a_genuinely_painted_texture` + Phase 1's `test_reexport_project_produces_real_files`, no regression); `smoke/smoke.ps1`: 4/4 passed, exit 0; gallery image `docs/images/gallery/procedural_checker_base.png` (61,764 bytes) visually confirmed by the controller as a genuine checker pattern, not flat gray |
| 3 | `inspect_project` + dynamic catalog (blend modes; bake types deliberately out of scope -- see Deviations) | ✅ 2026-09-16 | `smoke/smoke.ps1`: 5/5 passed, exit 0 (`inspect_project registered as an MCP tool` probe passing); `.venv\Scripts\python.exe -m pytest -q`: 76 passed, 0 failed, 4 deselected (72 from the initial gate sweep + 4 added by the final-review fix wave: `layer_blend_modes()` regression test, two bogus-path rejection tests, and the mocked blend-index-12 regression test); `-m integration`: 4 passed, 0 failed (`test_reexport_project_produces_real_files` [Phase 1], `test_checker_material_produces_a_genuinely_painted_texture` [Phase 2], `test_inspect_project_reports_real_object_from_the_fixture` [tightened to assert real fixture content, not just types] + `test_inspect_project_reports_all_materials_in_a_multi_material_project` [Phase 3], no regressions). Final whole-branch review (opus) found and a fix wave closed 2 Critical findings (layer blend-mode enum mismatch mislabeling 6/18 modes; a bogus project path returning a false `ok: True`) plus 2 Important test-coverage gaps -- see docs/superpowers/plans/2026-09-16-phase3-inspect-project.md's SDD ledger for the full writeup. |
| 4 | `run_script` escape hatch + docs/packaging polish | ✅ 2026-09-16 | `smoke/smoke.ps1`: 6/6 passed, exit 0 (`run_script registered as an MCP tool` probe passing); `.venv\Scripts\python.exe -m pytest -q`: 88 passed, 0 failed, 6 deselected (87 from the initial gate sweep + 1 added by the final-review fix wave: `test_run_script_passes_custom_timeout_s_through`); `-m integration`: 6 passed, 0 failed (all prior phases' integration tests plus the two new run_script tests, no regressions); clean-clone check (`git clone` to a scratch dir, `pip install -e .`, `ap-mcp --version`/`--help`/`--check`) all exit as expected with no undocumented manual steps -- `--version`/`--help` exit 0, `--check` correctly reports `[FAIL] AP_BINARY: not set` (exit 1) since a fresh clone has no `.env`, which is the honest expected result, not a defect. Final whole-branch review (opus) found and a fix wave closed 1 Critical finding (`run_script`'s docs falsely claimed it can never save/mutate the project, when minic's `project_save()` is reachable and demonstrated to overwrite it in place) plus 3 Important findings (stdout/stderr structurally empty on Windows -- `WriteConsoleW`, not pipe-capturable; `AP_ALLOWED_ROOTS` docstring overclaim -- only `project` is bounded, not the script body; no caller-facing `timeout_s` override) -- see docs/superpowers/plans/2026-09-16-phase4-run-script.md's SDD ledger (since deleted per convention; summarized in HANDOFF.md) for the full writeup. |
| Cleanup | Minor-findings cleanup pass (post-Phase-4, 5 tasks: `_failure`/`_is_arm_project_file` shared helpers, `scene_objects` `CatalogError` on a missing section marker, `run_api` stdout decode hardened against non-ASCII names, a real-binary integration test for `run_script`'s timeout path, docs sweep) | ✅ 2026-09-16 | Final whole-branch review's fresh verification sweep: `.venv\Scripts\python.exe -m pytest -q`: 95 passed, 0 failed, 9 deselected; `-m integration`: 9 passed, 0 failed; `smoke/smoke.ps1`: 6/6 passed, exit 0. |
| 5 | 7 mesh/UV editing tools (decimate/bevel/subdivide/smooth/duplicate/merge/unwrap_mesh_uvs), via a scoped local minic patch (see ROADMAP.md) | ✅ 2026-09-16 | `smoke/smoke.ps1`: 13/13 passed, exit 0. `pytest -q`: 118 passed, 0 failed, 18 deselected. `-m integration`: 18 passed, 0 failed. All 7 tools verified against real geometry via independent script_export_mesh OBJ diffs (not just ok=True) -- see this row's phase detail table below. **Note (2026-09-17):** see Known Issue #4 -- `smooth_mesh`'s reliability is now known to be worse than this row implies. |

---

## Current Phase Detail (Phase 0)

| Item / File | State | Notes |
|---|---|---|
| `src/armorpaint_mcp/config.py` | 🔌 | loads `AP_*` env/`.env`, `require_valid` |
| `src/armorpaint_mcp/doctor.py` | 🔌 | `--check` preflight checklist |
| `src/armorpaint_mcp/server.py` | 🔌 | `--check`/`--version`/`--help` + the `MCPServer` (empty at Phase 0; `reexport_project` registered on it in Phase 1) |
| `smoke/smoke.ps1` | ✅ | run 2026-09-15, 3/3 passed |
| build stamp (`scripts/build_stamp.py`) | 🔌 | vendored, baked at first commit |
| git repo | 🔌 | initialized this session |

---

## Current Phase Detail (Phase 1)

| Item / File | State | Notes |
|---|---|---|
| `src/armorpaint_mcp/paths.py` | ✅ | `ensure_within_roots` / `reject_path_fragment`; exercised live via `reexport_project`'s real run (empty `AP_ALLOWED_ROOTS` passthrough) |
| `src/armorpaint_mcp/runner.py` | ✅ | real subprocess launch of `ArmorPaint.exe` (no `--background`), polled output dir, terminated process; 5/5 expected PNGs produced in 2.33s |
| `src/armorpaint_mcp/server.py` (`reexport_project`) | ✅ | end-to-end real call verified: `ok=True`, `error=None`, 5 files, all non-empty on disk |
| `tests/fixtures/sample_project.arm` | ✅ | 217,931 bytes, generated headlessly by `tests/fixtures/generate_fixture.py`; consumed successfully by the real integration test |

---

## Current Phase Detail (Phase 2)

| Item / File | State | Notes |
|---|---|---|
| `src/armorpaint_mcp/script_gen.py` (`generate_script`) | ✅ | builds a minic script from a whitelisted node-graph spec — four node types shipped: `"checker"` (`TEX_CHECKER`), `"solid"` (`RGB`), `"noise"` (`TEX_NOISE`), `"voronoi"` (`TEX_VORONOI`, both added 2026-09-16, promoted from `scripts/generate_gallery.py`'s demo-only minic once proven); exercised by unit tests (`tests/test_script_gen.py`, 92 passed total) and real integration runs (`tests/test_create_procedural_material_integration.py`, 8 passed with `AP_BINARY` set, incl. parametrized noise/voronoi pixel-content checks) |
| `src/armorpaint_mcp/runner.py` (`run_procedural_material`) | ✅ | single-process launch: `--script <file>` (no `--background`), reuses Phase 1's poll-and-terminate helper; real run produced a non-flat exported PNG |
| `src/armorpaint_mcp/server.py` (`create_procedural_material`) | ✅ | end-to-end real call verified via `test_checker_material_produces_a_genuinely_painted_texture`: exported base-color PNG samples multiple distinct colors (genuinely painted, not uniform) |
| `src/armorpaint_mcp/server.py` (`list_available_presets`) | ✅ | registered as an MCP tool this phase (written/tested in `runner.py` since Phase 1, previously unregistered); covered by unit tests |
| `docs/images/gallery/procedural_checker_base.png` | ✅ | 61,764 bytes, generated this session; controller visually confirmed genuine checker pattern (not flat gray) |

---

## Current Phase Detail (Phase 3)

| Item / File | State | Notes |
|---|---|---|
| `src/armorpaint_mcp/catalog.py` | ✅ | builds blend-mode list from `--api` output; bake types deliberately out of scope; covered by unit tests, real `--api` output parsed successfully in integration runs |
| `src/armorpaint_mcp/runner.py` (`run_api`) | ✅ | subprocess wrapper for ArmorPaint's `--api` flag; exercised for real by both `inspect_project` integration tests (2 passed) |
| `src/armorpaint_mcp/server.py` (`inspect_project`) | ✅ | registered as an MCP tool (smoke probe passing), reads `.arm` metadata via `ArmorPaint.exe <project> --api`; end-to-end real calls verified by `test_inspect_project_reports_real_object_from_the_fixture` and `test_inspect_project_reports_all_materials_in_a_multi_material_project` |

---

## Current Phase Detail (Phase 4)

| Item / File | State | Notes |
|---|---|---|
| `src/armorpaint_mcp/runner.py` (`run_minic_script`) | ✅ | subprocess.run with --background + --script against an already-open project; confirmed empirically to self-exit cleanly and run correctly, no poll-and-terminate needed (see docs/superpowers/plans/2026-09-16-phase4-run-script.md's "Empirical findings") |
| `src/armorpaint_mcp/server.py` (`run_script`) | ✅ | registered as an MCP tool (smoke probe passing); AP_ALLOWED_ROOTS sandboxing and phantom-default-project guard cover the `project` path only, not the script body; end-to-end real calls verified by tests/test_run_script_integration.py. ⚠️ Not read-only/non-mutating: a script can call minic's `project_save()` and overwrite the caller's `.arm` file in place (confirmed empirically) -- intentional escape-hatch behavior, documented in the tool's docstring, not a gap. `timeout_s` (default 30s) is caller-overridable. |

---

## Current Phase Detail (Phase 5)

| Item / File | State | Notes |
|---|---|---|
| `src/armorpaint_mcp/server.py` (`_run_mesh_edit`) | ✅ | shared plumbing for all 7 tools: validates `project`, resolves the edit target (a copy at `output_project` by default, never the caller's own file unless `in_place=True`), runs the tool-specific `minic_call` + `project_save(0)` in one `--script` process; every integration test below verifies the effect independently via a fresh `script_export_mesh` OBJ export, never trusting `ok=True` alone (`tests/_mesh_edit_test_helpers.py`) |
| `decimate_mesh` | ✅ | end-to-end real call verified: `test_decimate_mesh_reduces_vertex_and_face_count` confirms real vertex AND face count both strictly decrease vs. an independent before/after OBJ export; `test_decimate_mesh_in_place_mutates_the_caller_s_own_file` confirms `in_place=True` mutates the caller's own file (vertex count drops on the same path passed in) |
| `bevel_mesh` | ✅ | `test_bevel_mesh_adds_geometry` confirms real geometry is added (vertex/face count increases) vs. an independent before/after OBJ export |
| `subdivide_mesh` | ✅ | `test_subdivide_mesh_quadruples_face_count` confirms an exact 4x face-count relationship (not just "more faces") vs. an independent before/after OBJ export |
| `smooth_mesh` | ✅ | `test_smooth_mesh_preserves_topology_but_changes_normals` confirms the reversed direction correctly: vertex/face COUNT unchanged (topology preserved), normals DO change -- this is a smoothing op, not a decimation/subdivision op |
| `duplicate_mesh` | ✅ | `test_duplicate_mesh_doubles_vertex_and_face_count` confirms an exact 2x vertex AND face-count relationship, adding a second object to the scene |
| `merge_mesh_geometry` | ✅ | `test_merge_mesh_geometry_rejects_a_single_object_project` confirms the precondition guard fires a clear `ok=False` error (not a silent no-op false-positive) on a project with fewer than 2 objects; `test_merge_mesh_geometry_collapses_two_objects_into_one` builds a real 2-object project via `duplicate_mesh` (no multi-object fixture exists yet -- see ROADMAP.md's "Known gaps"), merges it, and confirms via `inspect_project` that exactly 1 object remains |
| `unwrap_mesh_uvs` | ✅ | `test_unwrap_mesh_uvs_changes_the_uv_coordinates` confirms real UV coordinates change (all 144 `vt` lines differed on the fixture during this phase's spike) while vertex/UV count stays the same (a UV operation, not a geometry operation) |
| `src/armorpaint_mcp/doctor.py` (`--check` mesh-edit-patch detection) | ✅ | Task 1: `--check` detects whether `AP_BINARY` carries the mesh-edit minic patch and fails clearly (not a confusing "function not found" minic error) when it doesn't; covered by `test_doctor.py` |
| `smoke/smoke.ps1` | ✅ | run 2026-09-16, 13/13 passed (6 prior probes + 1 new probe per tool for all 7 new tools) |

---

## Known Issues

| # | Issue | Impact | Workaround / Plan |
|---|---|---|---|
| 1 | ~~Minic script templates for rebake/texture-swap unverified against a real `.arm` project~~ — **RESOLVED 2026-09-15.** Investigated hands-on: mesh-detail baking is structurally unreachable from any script/API (`bake_texture_node_run` is only wired to a GUI button callback, no CLI/minic path); texture-set swapping into an existing project is blocked by minic's curated struct access (reading `assets->length` silently aborts script execution). Procedural material authoring — the one approach that worked — is what Phase 2 shipped instead (single-process build+fill+export; see `docs/PLAN.md` Phase 2 and `docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md` Amendment 2). | None — scope was adjusted to what's achievable, not left open | Closed. No further action; baking and texture-swap remain out of scope for this project. |
| 2 | ~~`blend_modes()`'s `CatalogError` (missing MIX_RGB anchor) could abort `inspect_project`'s entire read when only a blending label needed to degrade~~ -- **INVESTIGATED, MOOT (2026-09-16).** Confirmed via `grep`: `inspect_project` never calls `blend_modes()` -- Phase 3's Critical-finding fix already replaced it with the hardcoded `layer_blend_modes()` (see `catalog.py`'s own docstring on the enum mismatch), which takes no input and cannot raise. The out-of-range-index case it would have needed to guard is already handled: the `layers` list comprehension already degrades an out-of-range index to `blending: None`. | None -- finding predates the enum-mismatch fix and no longer describes reachable code. | Closed. No code change. |
| 3 | ~~`run_script`'s "timeout discards partial output" concern~~ -- **MOOT (2026-09-16).** `stdout`/`stderr` are already documented (Phase 4 final review) as structurally empty on this Windows build regardless of timeout (`WriteConsoleW`, not pipe-capturable) -- there is no partial output a timeout could discard. | None -- superseded by the stdout/stderr finding it was originally paired with. | Closed. No code change. |
| 4 | `smooth_mesh`'s flaky vertex count / degenerate positions -- **ROOT-CAUSED 2026-09-17 (upstream ArmorPaint bug, not this project's patch or plumbing).** `util_mesh_smooth()` (`paint/sources/util/util_mesh.c:1222-1248`) accumulates each vertex's Loop-smoothing neighbor sum/count into `vsum`/`vbsum`/`vn`/`vbn` via `+=`/`++`, but those four arrays are allocated with `f32_array_create`/`i32_array_create`, whose buffer comes from `realloc(NULL, size)` (`base/sources/iron_array.c` — confirmed no zero-filling override exists anywhere in the codebase) -- i.e. raw, uninitialized heap memory, never zeroed. Every OTHER array `util_mesh_smooth` allocates is fully covered by plain assignment before use (so garbage never surfaces); only these four accumulator arrays are missing an initial zero-fill. The final smoothed position is therefore `garbage_from_process's_prior_heap_state + real_neighbor_sum`, not just the real sum. Confirmed empirically, not just from source reading: (a) reran the original 5-call repro at 10 calls -- 6/10 clean (vcount=96, 0 near-zero verts), 4/10 corrupted (vcount as low as 91, up to 29/96 near-zero-component vertices), same fixture, same binary, zero code changes between runs; (b) many corrupted x/y/z components print as an exact `0` in the OBJ export (`f32_to_string`), the signature of a NaN-poisoned computation truncating through `(i16)math_floor(np * 32767.0f)`, with the rest landing as small-but-nonzero wrapped values -- both are hallmarks of uninitialized-float arithmetic, not a legitimate smoothing result; (c) whether a given run comes back clean or corrupted tracks whether `realloc` happened to hand back fresh, kernel-zeroed OS pages (clean) vs. recycled, still-dirty heap memory from earlier in that same process's life (corrupted) -- this is why the earlier working theory of "timing/process-state dependency" was on the right track: the dependency is real, but on heap-allocator state at process-launch time, not frame-scheduling/render-loop timing (`--script` was independently confirmed to run a full frame after `import_arm_run_project()` completes synchronously, ruling out a project-load race). **Blast radius wider than originally scoped:** the identical accumulate-into-uninitialized-buffer pattern also exists in `util_mesh_bevel()`'s cap-vertex averaging (`cap_sx`/`cap_sy`/`cap_sz`/`cap_su`/`cap_sv`/`cap_cnt`, `util_mesh.c:1369-1374`) and in `util_mesh_calc_normals(true)`'s `smooth_vals` (`util_mesh.c:762`, accumulated at `802-813`) -- the latter is the "compute smooth normals" path called by `util_mesh_smooth` itself plus 3 other call sites (`util_mesh.c:1100`, `1503`, `1633`), so it may silently corrupt NORMALS (not positions) in other patched tools too, invisible to their existing count-only tests. Reran the exact same 10-call repro against `bevel_mesh` on the unmodified current binary (no rebuild) as a discriminator: it shows the same signature (vertex counts 601-660 out of a max 660, near-zero-component vertices ranging 0-43 per run) -- this is not something specific to `smooth_mesh`'s call site, it's the shared allocator/accumulator pattern. `decimate_mesh` shows a related but not-yet-confirmed-same symptom, found in the same gallery session that first flagged this issue: decimating a subdivided fixture (378v/752f -> 50v/96f, a real and large numeric reduction) produced no visually obvious change in a wireframe render from the gallery's camera angle -- possibly the same class of numeric-claim-vs-observable-geometry mismatch, but `decimate_mesh` doesn't call any of the three functions named above, so it needs its own separate investigation, not assumed to share this root cause. See project memory `armorpaint-smooth-mesh-flaky-vertex-count` (updated) for the full repro data and code citations. **Not this project's patch's fault**: the minic patch on `spike/minic-decimate` only *registers* `util_mesh_smooth`/`util_mesh_bevel` to minic (`X0(util_mesh_smooth, "v()", v)` / `X1(util_mesh_bevel, ...)`, one line each in `minic_api_list.h`) -- it does not touch either function's body. | `smooth_mesh`'s ✅ gate (Phase 5) and `bevel_mesh`'s ✅ gate both overstate reliability: `ok=True` does not prove sane output for either tool, and neither tool's own test would have caught this (count-only assertions, or "normals changed" without checking they changed *correctly*). | Open -- root cause identified and confirmed, but no fix has been written, built, or upstreamed. An actual fix (zero-initializing the four/six/one accumulator arrays before their `+=`/`++` loops) is a real algorithm patch to ArmorPaint's own C source, a different and bigger category of change than this project's existing registration-only patch policy (see ROADMAP.md's "Patch policy") -- needs Grayson's explicit call before writing, rebuilding, or upstreaming it (upstream PR #2139 is already open for the registration-only patch; an algorithm fix would be a separate PR). |
| 5 | `bevel_mesh`'s ✅ gate is likely overstated -- **DISCOVERED 2026-09-17 as a corollary of investigating #4**, not yet its own investigation. `test_bevel_mesh_adds_geometry` only asserts vertex/face count *increases*, which the corrupted accumulator (#4) doesn't necessarily prevent (a garbage-corrupted cap vertex is still a vertex). A 10-call repro on the current binary shows the same flaky-count + near-zero-component-vertex signature as `smooth_mesh`. | `ok=True` from `bevel_mesh` does not prove the added geometry is sane; downstream consumers should independently verify (per this tool's own docstring caveat) rather than trust the count check alone. | Open, same root cause and same fix category as #4 -- tracked separately since it's a distinct tool with its own test gate that should eventually get its own position-sanity assertion, not just a vertex-count one. |

---

## Deviations from Plan

| Date | Deviation | Rationale |
|---|---|---|
| 2026-09-15 | `list_export_presets` shipped in Phase 1/2 as a function in `runner.py`, not in `catalog.py` as the design spec's Components table originally described. | Phase 3's own plan (this file's history) chose not to relocate already-tested, working code for a cosmetic-only file-organization match -- see docs/superpowers/plans/2026-09-16-phase3-inspect-project.md's Global Constraints/rationale. |
| 2026-09-16 | `layer_blend_modes()` in `catalog.py` hardcodes the 18-name layer blend-type enum (`blend_type_t`, `paint/sources/enums.h` lines 135-154) instead of parsing it dynamically from `--api` output, breaking this project's "dynamic catalogs, no hardcoded magic numbers" convention. | Final Phase 3 review found `inspect_project` was mislabeling layer blend modes >= index 12 by reusing `blend_modes()` (MIX_RGB's 19-entry material-node ENUM, which has an extra "Exclusion" the layer enum lacks). No dynamic source exists for the layer enum -- `--api`'s text output never prints it; it's only ever built as a UI combo box (`paint/sources/ui/tab_layers.c`, `paint/sources/ui/ui_header.c`), never surfaced as text. Hardcoding from the verified source enum was the only option. |
| 2026-09-16 | `run_script(project, script)` takes inline minic source text as `script`, not a `script_path` naming a caller-supplied file, as the design spec's Components table (`run_script(project, script_path)`, `docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md:165`) originally described. `docs/PLAN.md`'s Phase 4 section names no parameters at all, so it isn't a source of this deviation. | An MCP tool caller composes script text conversationally; requiring it to first write that text to a file it can prove is reachable (and separately sandboxed, since `AP_ALLOWED_ROOTS` only bounds `project`) is a worse interface than accepting the text directly. The server owns the temp file's full lifecycle itself (write, pass to `--script`, delete in a `finally` block), so nothing is left behind regardless of outcome. |
