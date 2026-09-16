# 📊 STATUS — Tool-ArmorPaintMCP

> **Living truth.** Updated continuously; never let it flatter the project.
> States: ✅ verified (gate evidence exists) · 🔌 wired (code exists, no gate yet) · ⬜ not started.

**Last updated:** 2026-09-15
**Open phase:** 1

---

## Phase Gates

| Phase | Scope | Gate | Evidence |
|---|---|---|---|
| 0 | Scaffold + smoke harness | ✅ 2026-09-15 | `smoke/smoke.ps1`: 3 passed, 0 failed (package imports, `--version`, `--help`) |
| 1 | `reexport_project` tool (native export flags, no script) | ⬜ | |
| 2 | `rebake_and_export` tool + minic script templates | ⬜ | |
| 3 | `list_export_presets` + `inspect_project` + dynamic catalog | ⬜ | |
| 4 | `run_script` escape hatch + docs/packaging polish | ⬜ | |

---

## Current Phase Detail (Phase 0)

| Item / File | State | Notes |
|---|---|---|
| `src/armorpaint_mcp/config.py` | 🔌 | loads `AP_*` env/`.env`, `require_valid` |
| `src/armorpaint_mcp/doctor.py` | 🔌 | `--check` preflight checklist |
| `src/armorpaint_mcp/server.py` | 🔌 | `--check`/`--version`/`--help` + empty `MCPServer`, zero tools |
| `smoke/smoke.ps1` | ✅ | run 2026-09-15, 3/3 passed |
| build stamp (`scripts/build_stamp.py`) | 🔌 | vendored, baked at first commit |
| git repo | 🔌 | initialized this session |

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
