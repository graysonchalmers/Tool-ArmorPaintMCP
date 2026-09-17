# 📊 STATUS — Tool-ArmorPaintMCP

> **Living truth.** Updated continuously; never let it flatter the project.
> States: ✅ verified (gate evidence exists) · 🔌 wired (code exists, no gate yet) · ⬜ not started.

**Last updated:** 2026-09-16
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
| 5 | 7 mesh/UV editing tools (decimate/bevel/subdivide/smooth/duplicate/merge/unwrap_mesh_uvs), via a scoped local minic patch (see ROADMAP.md) | ✅ 2026-09-16 | `smoke/smoke.ps1`: 13/13 passed, exit 0. `pytest -q`: 118 passed, 0 failed, 18 deselected. `-m integration`: 18 passed, 0 failed. All 7 tools verified against real geometry via independent script_export_mesh OBJ diffs (not just ok=True) -- see this row's phase detail table below. |

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
| 4 | **OPEN (2026-09-17).** `smooth_mesh` is genuinely flaky, worse than previously recorded. 5 repeated calls against the identical fixture returned vertex counts 91/96/92/96/96 (only 3/5 preserved the count Phase 5's own integration test asserts as invariant). More seriously, even count-preserving runs had 9-23 of 96 vertices with a near-zero coordinate component -- i.e. individual vertices landing at or near the mesh's own center, not a normals-only change. Found while building the mesh/UV visual gallery (a real wireframe render surfaced this; the existing test only asserts vertex *count*, never position sanity, which is why it was never caught). Supersedes the lighter `armorpaint-smooth-mesh-flaky-vertex-count` memory entry ("94 vs 96 once... root cause unconfirmed") with stronger, repeatable evidence. | Phase 5's ✅ gate for `smooth_mesh` overstates reliability -- the tool can silently return degenerate geometry on `ok=True`. The gallery uses a retry-until-clean sample (see README's mesh/UV gallery caption) as a stopgap, not a fix. | Open. Root cause not yet investigated (likely in ArmorPaint's own `util_mesh_smooth`, or in how this project's patch calls it -- not eliminated as a candidate). Needs its own investigation, separate from this gallery work. |

---

## Deviations from Plan

| Date | Deviation | Rationale |
|---|---|---|
| 2026-09-15 | `list_export_presets` shipped in Phase 1/2 as a function in `runner.py`, not in `catalog.py` as the design spec's Components table originally described. | Phase 3's own plan (this file's history) chose not to relocate already-tested, working code for a cosmetic-only file-organization match -- see docs/superpowers/plans/2026-09-16-phase3-inspect-project.md's Global Constraints/rationale. |
| 2026-09-16 | `layer_blend_modes()` in `catalog.py` hardcodes the 18-name layer blend-type enum (`blend_type_t`, `paint/sources/enums.h` lines 135-154) instead of parsing it dynamically from `--api` output, breaking this project's "dynamic catalogs, no hardcoded magic numbers" convention. | Final Phase 3 review found `inspect_project` was mislabeling layer blend modes >= index 12 by reusing `blend_modes()` (MIX_RGB's 19-entry material-node ENUM, which has an extra "Exclusion" the layer enum lacks). No dynamic source exists for the layer enum -- `--api`'s text output never prints it; it's only ever built as a UI combo box (`paint/sources/ui/tab_layers.c`, `paint/sources/ui/ui_header.c`), never surfaced as text. Hardcoding from the verified source enum was the only option. |
| 2026-09-16 | `run_script(project, script)` takes inline minic source text as `script`, not a `script_path` naming a caller-supplied file, as the design spec's Components table (`run_script(project, script_path)`, `docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md:165`) originally described. `docs/PLAN.md`'s Phase 4 section names no parameters at all, so it isn't a source of this deviation. | An MCP tool caller composes script text conversationally; requiring it to first write that text to a file it can prove is reachable (and separately sandboxed, since `AP_ALLOWED_ROOTS` only bounds `project`) is a worse interface than accepting the text directly. The server owns the temp file's full lifecycle itself (write, pass to `--script`, delete in a `finally` block), so nothing is left behind regardless of outcome. |
