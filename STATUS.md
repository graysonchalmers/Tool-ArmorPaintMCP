# 📊 STATUS — Tool-ArmorPaintMCP

> **Living truth.** Updated continuously; never let it flatter the project.
> States: ✅ verified (gate evidence exists) · 🔌 wired (code exists, no gate yet) · ⬜ not started.

**Last updated:** 2026-09-15
**Open phase:** 2

---

## Phase Gates

| Phase | Scope | Gate | Evidence |
|---|---|---|---|
| 0 | Scaffold + smoke harness | ✅ 2026-09-15 | `smoke/smoke.ps1`: 3 passed, 0 failed (package imports, `--version`, `--help`) |
| 1 | reexport_project tool (native export flags, no script) | ✅ 2026-09-15 | tests/test_reexport_integration.py: 1 passed, 5 real PNG files produced from tests/fixtures/sample_project.arm |
| 2 | `rebake_and_export` tool + minic script templates | ⬜ | |
| 3 | `list_export_presets` + `inspect_project` + dynamic catalog | ⬜ | |
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

## Known Issues

| # | Issue | Impact | Workaround / Plan |
|---|---|---|---|
| 1 | Minic script templates for rebake/texture-swap unverified against a real `.arm` project | Phase 2 scope assumes `minic_api_list.h` covers what's needed | Hands-on verify with `--api` + a throwaway project before writing `catalog.py`/`templates/` |

---

## Deviations from Plan

| Date | Deviation | Rationale |
|---|---|---|
| | | |
