# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-15_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

Phase 1 shipped: a Python MCP server that batch-drives ArmorPaint via its
native CLI flags — `--export-textures` **without** `--background`, since
that combination is confirmed broken on this build (it exits 0 having
written nothing; see `runner.py`'s docstring) — with a real
`reexport_project` MCP tool, path sandboxing, a subprocess runner, a real
binary `.arm` fixture, a passing integration test against real ArmorPaint on
this machine, and a gallery of two real example output images with an
honest caption. Deliberately **not** patching ArmorPaint's source the way
the reference implementation does. Design spec:
[docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md).
Implementation plan: [docs/PLAN.md](docs/PLAN.md).

## 📌 Where we stopped

All 8 tasks of the Phase 1 plan are complete and reviewed clean, executed
on feature branch `phase1-reexport-project` (a controller decision made
before Task 1, for safety — work did not proceed directly on `main`). The
final whole-branch review's one Critical and six Important findings were
fixed on the same branch (the SDD execution ledger with the full writeup
was scratch workspace, deleted per process once the branch merged cleanly —
see this file's session log below and the git history for the record); the
headline of that wave is that export completion is now decided against the
files the chosen preset says it writes, not against "filenames that are new
since we started". Verification sweep is green:

- `pytest -q` → 29 passed, 1 deselected (unit-only is now the default,
  via `addopts` in `pyproject.toml`)
- `pytest -q -m integration` (with `AP_BINARY` set) → 1 passed, 29 deselected
- `pwsh smoke\smoke.ps1` → `SMOKE OK` (4/4)
- `python -m armorpaint_mcp.server --check` (with `AP_BINARY` set) → all
  checks passed, exit 0

**Merged to `main` and pushed** via `superpowers:finishing-a-development-branch`
(fast-forward, `0447c03..46f6b37`, tests re-verified green on the merged
result). `phase1-reexport-project` (local and remote) has been deleted —
its history lives on in `main`'s git log now.

## ▶️ Next concrete step

Phase 2 is `rebake_and_export` — the first tool that needs a minic script
template (not just native CLI flags like Phase 1's `reexport_project`).
Hand off to `writing-plans` for that.

Alternatives:
- Jump straight to hand-verifying the minic scripting API actually covers
  rebake/texture-swap operations (open item flagged in the design spec)
  before committing to Phase 2's scope — worth doing before too much of
  `catalog.py`/`templates/` gets built against an unverified assumption.

## ❓ Open questions

- Design spec's "Open items": minic script templates for rebake/texture-swap
  need hands-on verification against a real `.arm` sample project — not yet
  confirmed the registered API (`minic_api_list.h`) actually covers what's
  needed.
- Live mode (deferred, not rejected) — two options named in the spec, neither
  chosen; revisit only once batch mode is solid and live mode is actually
  wanted.

## 🗂️ Changed this session

- Branch: `phase1-reexport-project`, merged to `main` and deleted.
- Files: `paths.py`, `runner.py`, `reexport_project` MCP tool, integration
  test + real binary `.arm` fixture, `docs/images/` gallery + caption,
  `HANDOFF.md` (this update).
- Decisions (+ why): no source patching (ArmorPaint's native CLI/scripting
  already covers the batch-mode scope — see spec); Python + official `mcp`
  SDK (matches local sibling Tool-MaterialMaker-MCP's proven pattern);
  coarse pipeline tools, not one-tool-per-operation (subprocess-per-call
  model means fine-grained tools would each pay a full process launch);
  first real workflow target is batch re-export/rebake of *existing*
  projects, not from-scratch material authoring (narrower, lower-risk v1);
  Phase 1 executed on a feature branch rather than `main` (controller
  safety decision, predating Task 1) — merge is a deliberately separate
  next step, not skipped.

---

## 🕓 Session log

### 2026-09-15 — brainstorm + scaffold
- Surveyed the reference implementation (`z-Git\armorpaint-mcp`) in depth via
  a research subagent: patch-and-rebuild architecture, ~40-struct native
  coupling, silent-no-op patch fragility, zero tests, Windows unverified.
- Read ArmorPaint's own source directly and found it already ships native
  CLI automation (`--background`, `--export-*`, `--script`, `--api`) and a
  real scripting engine (`minic`, `minic_api_list.h`) — the reference's core
  "no plugin SDK exists" premise doesn't hold for the batch-mode scope.
- Ran `superpowers:brainstorming` (architectural path) to converge on scope
  and architecture; wrote and got approval on the design spec.
- Started `project-setup` to scaffold git/docs/build-stamp/package skeleton.

### 2026-09-15 — Phase 1 (`reexport_project`) subagent-driven execution
- Executed the 8-task Phase 1 plan on feature branch
  `phase1-reexport-project` (controller decision: not on `main`, for
  safety, made before Task 1).
- Built `paths.py` (sandboxing), `runner.py` (subprocess runner for native
  `--export-textures`, deliberately **without** `--background`), and the
  `reexport_project` MCP tool.
- Added a real binary `.arm` fixture, unit tests, and one passing
  integration test run against real ArmorPaint on this machine.
- Added a docs gallery with two real (if visually flat/deliberately-blank
  fixture) example output images and an honest caption.
- Task 8 final verification sweep all green (unit, integration, smoke,
  `--check`); pushed `phase1-reexport-project` to origin.

### 2026-09-15 — final whole-branch review fix wave
- Fixed the review's Critical finding: `runner.py` decided success by
  diffing output-directory filenames, but ArmorPaint overwrites rather than
  creating uniquely-named files — so a re-export reported a false failure
  and a second preset into the same directory reported a partial file list
  as `ok=True`. Completion is now derived from the preset's own JSON
  definition (`data/export_presets/<preset>.json`) and each expected file
  must be (re)written by this run.
- Fixed six Important findings: config validation in `reexport_project`
  (`_ensure_ready`, not bare `load_config`), HANDOFF stating the
  `--background` fact backwards, no MCP-registration coverage (test +
  smoke probe), `pytest -q` silently running the integration test,
  `try/finally` around the poll loop so the GUI process can't be leaked,
  and `AP_OUTPUT_DIR` documented as live when nothing reads it.
- Scoped re-review: all findings addressed, no new Critical/Important
  breakage. Three items parked (not load-bearing): a stale docstring in
  `tests/test_reexport_integration.py` still naming the pre-`addopts`
  invocation; a theoretical uncaught `AttributeError` in `runner.py` if a
  preset JSON's `textures` entries were ever malformed (unreachable against
  every real preset in this install); and a narrow case where a config
  failure's actionable message gets masked by the MCP SDK's generic error
  wrapping (matches this project's pre-existing `main()` convention, not a
  regression).
- Merged `phase1-reexport-project` into `main` (fast-forward,
  `0447c03..46f6b37`), re-verified green, deleted the branch locally and on
  origin.
