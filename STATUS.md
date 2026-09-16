# 📊 STATUS — Tool-ArmorPaintMCP

> **Living truth.** Updated continuously; never let it flatter the project.
> States: ✅ verified (gate evidence exists) · 🔌 wired (code exists, no gate yet) · ⬜ not started.

**Last updated:** 2026-09-16
**Open phase:** none -- Phase 4 was the last phase in `docs/PLAN.md`

---

## Phase Gates

| Phase | Scope | Gate | Evidence |
|---|---|---|---|
| 0 | Scaffold + smoke harness | ✅ 2026-09-15 | `smoke/smoke.ps1`: 3 passed, 0 failed (package imports, `--version`, `--help`) |
| 1 | reexport_project tool (native export flags, no script) | ✅ 2026-09-15 | tests/test_reexport_integration.py: 1 passed, 5 real PNG files produced from tests/fixtures/sample_project.arm |
| 2 | `create_procedural_material` tool (single-process script build+fill+export) | ✅ 2026-09-15 | `.venv\Scripts\python.exe -m pytest -q`: 53 passed, 0 failed; `-m integration`: 2 passed (`test_checker_material_produces_a_genuinely_painted_texture` + Phase 1's `test_reexport_project_produces_real_files`, no regression); `smoke/smoke.ps1`: 4/4 passed, exit 0; gallery image `docs/images/gallery/procedural_checker_base.png` (61,764 bytes) visually confirmed by the controller as a genuine checker pattern, not flat gray |
| 3 | `inspect_project` + dynamic catalog (blend modes; bake types deliberately out of scope -- see Deviations) | ✅ 2026-09-16 | `smoke/smoke.ps1`: 5/5 passed, exit 0 (`inspect_project registered as an MCP tool` probe passing); `.venv\Scripts\python.exe -m pytest -q`: 76 passed, 0 failed, 4 deselected (72 from the initial gate sweep + 4 added by the final-review fix wave: `layer_blend_modes()` regression test, two bogus-path rejection tests, and the mocked blend-index-12 regression test); `-m integration`: 4 passed, 0 failed (`test_reexport_project_produces_real_files` [Phase 1], `test_checker_material_produces_a_genuinely_painted_texture` [Phase 2], `test_inspect_project_reports_real_object_from_the_fixture` [tightened to assert real fixture content, not just types] + `test_inspect_project_reports_all_materials_in_a_multi_material_project` [Phase 3], no regressions). Final whole-branch review (opus) found and a fix wave closed 2 Critical findings (layer blend-mode enum mismatch mislabeling 6/18 modes; a bogus project path returning a false `ok: True`) plus 2 Important test-coverage gaps -- see docs/superpowers/plans/2026-09-16-phase3-inspect-project.md's SDD ledger for the full writeup. |
| 4 | `run_script` escape hatch + docs/packaging polish | ✅ 2026-09-16 | `smoke/smoke.ps1`: 6/6 passed, exit 0 (`run_script registered as an MCP tool` probe passing); `.venv\Scripts\python.exe -m pytest -q`: 88 passed, 0 failed, 6 deselected (87 from the initial gate sweep + 1 added by the final-review fix wave: `test_run_script_passes_custom_timeout_s_through`); `-m integration`: 6 passed, 0 failed (all prior phases' integration tests plus the two new run_script tests, no regressions); clean-clone check (`git clone` to a scratch dir, `pip install -e .`, `ap-mcp --version`/`--help`/`--check`) all exit as expected with no undocumented manual steps -- `--version`/`--help` exit 0, `--check` correctly reports `[FAIL] AP_BINARY: not set` (exit 1) since a fresh clone has no `.env`, which is the honest expected result, not a defect. Final whole-branch review (opus) found and a fix wave closed 1 Critical finding (`run_script`'s docs falsely claimed it can never save/mutate the project, when minic's `project_save()` is reachable and demonstrated to overwrite it in place) plus 3 Important findings (stdout/stderr structurally empty on Windows -- `WriteConsoleW`, not pipe-capturable; `AP_ALLOWED_ROOTS` docstring overclaim -- only `project` is bounded, not the script body; no caller-facing `timeout_s` override) -- see docs/superpowers/plans/2026-09-16-phase4-run-script.md's SDD ledger (since deleted per convention; summarized in HANDOFF.md) for the full writeup. |

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

## Known Issues

| # | Issue | Impact | Workaround / Plan |
|---|---|---|---|
| 1 | ~~Minic script templates for rebake/texture-swap unverified against a real `.arm` project~~ — **RESOLVED 2026-09-15.** Investigated hands-on: mesh-detail baking is structurally unreachable from any script/API (`bake_texture_node_run` is only wired to a GUI button callback, no CLI/minic path); texture-set swapping into an existing project is blocked by minic's curated struct access (reading `assets->length` silently aborts script execution). Procedural material authoring — the one approach that worked — is what Phase 2 shipped instead (single-process build+fill+export; see `docs/PLAN.md` Phase 2 and `docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md` Amendment 2). | None — scope was adjusted to what's achievable, not left open | Closed. No further action; baking and texture-swap remain out of scope for this project. |
| 2 | ~~`blend_modes()`'s `CatalogError` (missing MIX_RGB anchor) could abort `inspect_project`'s entire read when only a blending label needed to degrade~~ -- **INVESTIGATED, MOOT (2026-09-16).** Confirmed via `grep`: `inspect_project` never calls `blend_modes()` -- Phase 3's Critical-finding fix already replaced it with the hardcoded `layer_blend_modes()` (see `catalog.py`'s own docstring on the enum mismatch), which takes no input and cannot raise. The out-of-range-index case it would have needed to guard is already handled: the `layers` list comprehension already degrades an out-of-range index to `blending: None`. | None -- finding predates the enum-mismatch fix and no longer describes reachable code. | Closed. No code change. |
| 3 | ~~`run_script`'s "timeout discards partial output" concern~~ -- **MOOT (2026-09-16).** `stdout`/`stderr` are already documented (Phase 4 final review) as structurally empty on this Windows build regardless of timeout (`WriteConsoleW`, not pipe-capturable) -- there is no partial output a timeout could discard. | None -- superseded by the stdout/stderr finding it was originally paired with. | Closed. No code change. |

---

## Deviations from Plan

| Date | Deviation | Rationale |
|---|---|---|
| 2026-09-15 | `list_export_presets` shipped in Phase 1/2 as a function in `runner.py`, not in `catalog.py` as the design spec's Components table originally described. | Phase 3's own plan (this file's history) chose not to relocate already-tested, working code for a cosmetic-only file-organization match -- see docs/superpowers/plans/2026-09-16-phase3-inspect-project.md's Global Constraints/rationale. |
| 2026-09-16 | `layer_blend_modes()` in `catalog.py` hardcodes the 18-name layer blend-type enum (`blend_type_t`, `paint/sources/enums.h` lines 135-154) instead of parsing it dynamically from `--api` output, breaking this project's "dynamic catalogs, no hardcoded magic numbers" convention. | Final Phase 3 review found `inspect_project` was mislabeling layer blend modes >= index 12 by reusing `blend_modes()` (MIX_RGB's 19-entry material-node ENUM, which has an extra "Exclusion" the layer enum lacks). No dynamic source exists for the layer enum -- `--api`'s text output never prints it; it's only ever built as a UI combo box (`paint/sources/ui/tab_layers.c`, `paint/sources/ui/ui_header.c`), never surfaced as text. Hardcoding from the verified source enum was the only option. |
| 2026-09-16 | `run_script(project, script)` takes inline minic source text as `script`, not a `script_path` naming a caller-supplied file, as `docs/PLAN.md`'s Phase 4 sketch and the design spec's Components table (`run_script(project, script_path)`) originally described. | An MCP tool caller composes script text conversationally; requiring it to first write that text to a file it can prove is reachable (and separately sandboxed, since `AP_ALLOWED_ROOTS` only bounds `project`) is a worse interface than accepting the text directly. The server owns the temp file's full lifecycle itself (write, pass to `--script`, delete in a `finally` block), so nothing is left behind regardless of outcome. |
