# 📊 STATUS — Tool-ArmorPaintMCP

> **Living truth.** Updated continuously; never let it flatter the project.
> States: ✅ verified (gate evidence exists) · 🔌 wired (code exists, no gate yet) · ⬜ not started.

**Last updated:** 2026-09-15
**Open phase:** 3

---

## Phase Gates

| Phase | Scope | Gate | Evidence |
|---|---|---|---|
| 0 | Scaffold + smoke harness | ✅ 2026-09-15 | `smoke/smoke.ps1`: 3 passed, 0 failed (package imports, `--version`, `--help`) |
| 1 | reexport_project tool (native export flags, no script) | ✅ 2026-09-15 | tests/test_reexport_integration.py: 1 passed, 5 real PNG files produced from tests/fixtures/sample_project.arm |
| 2 | `create_procedural_material` tool (single-process script build+fill+export) | ✅ 2026-09-15 | `.venv\Scripts\python.exe -m pytest -q`: 53 passed, 0 failed; `-m integration`: 2 passed (`test_checker_material_produces_a_genuinely_painted_texture` + Phase 1's `test_reexport_project_produces_real_files`, no regression); `smoke/smoke.ps1`: 4/4 passed, exit 0; gallery image `docs/images/gallery/procedural_checker_base.png` (61,764 bytes) visually confirmed by the controller as a genuine checker pattern, not flat gray |
| 3 | `inspect_project` + dynamic catalog (`list_export_presets` already shipped in Phase 2 as `list_available_presets`) | ⬜ | |
| 4 | `run_script` escape hatch + docs/packaging polish | ⬜ | |

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
| `src/armorpaint_mcp/script_gen.py` (`generate_script`) | ✅ | builds a minic script from a whitelisted node-graph spec — exactly two node types shipped, `"checker"` (`TEX_CHECKER`) and `"solid"` (`RGB`); exercised by both unit tests and the real integration run |
| `src/armorpaint_mcp/runner.py` (`run_procedural_material`) | ✅ | single-process launch: `--script <file>` (no `--background`), reuses Phase 1's poll-and-terminate helper; real run produced a non-flat exported PNG |
| `src/armorpaint_mcp/server.py` (`create_procedural_material`) | ✅ | end-to-end real call verified via `test_checker_material_produces_a_genuinely_painted_texture`: exported base-color PNG samples multiple distinct colors (genuinely painted, not uniform) |
| `src/armorpaint_mcp/server.py` (`list_available_presets`) | ✅ | registered as an MCP tool this phase (written/tested in `runner.py` since Phase 1, previously unregistered); covered by unit tests |
| `docs/images/gallery/procedural_checker_base.png` | ✅ | 61,764 bytes, generated this session; controller visually confirmed genuine checker pattern (not flat gray) |

---

## Known Issues

| # | Issue | Impact | Workaround / Plan |
|---|---|---|---|
| 1 | ~~Minic script templates for rebake/texture-swap unverified against a real `.arm` project~~ — **RESOLVED 2026-09-15.** Investigated hands-on: mesh-detail baking is structurally unreachable from any script/API (`bake_texture_node_run` is only wired to a GUI button callback, no CLI/minic path); texture-set swapping into an existing project is blocked by minic's curated struct access (reading `assets->length` silently aborts script execution). Procedural material authoring — the one approach that worked — is what Phase 2 shipped instead (single-process build+fill+export; see `docs/PLAN.md` Phase 2 and `docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md` Amendment 2). | None — scope was adjusted to what's achievable, not left open | Closed. No further action; baking and texture-swap remain out of scope for this project. |

---

## Deviations from Plan

| Date | Deviation | Rationale |
|---|---|---|
| | | |
