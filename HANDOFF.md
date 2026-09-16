# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-15_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

Phase 1 shipped: a Python MCP server that batch-drives ArmorPaint via its
native CLI flags (`--background`/`--export-textures`), with a real
`reexport_project` MCP tool, path sandboxing, a subprocess runner, a real
binary `.arm` fixture, a passing integration test against real ArmorPaint on
this machine, and a gallery of two real example output images with an
honest caption. Deliberately **not** patching ArmorPaint's source the way
the reference implementation does. Design spec:
[docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md).
Implementation plan: [docs/PLAN.md](docs/PLAN.md).

## 📌 Where we stopped

All 8 tasks of the Phase 1 plan
(`.superpowers/sdd/2026-09-15-phase1-reexport-project/`) are complete and
reviewed clean, executed on feature branch **`phase1-reexport-project`**
(a controller decision made before Task 1, for safety — work did not
proceed directly on `main`). Final verification sweep (Task 8) is green:

- `pytest -q -m "not integration"` → 14 passed, 1 deselected
- `pytest -q -m integration` (with `AP_BINARY` set) → 1 passed, 14 deselected
- `pwsh smoke\smoke.ps1` → `SMOKE OK` (3/3)
- `python -m armorpaint_mcp.server --check` (with `AP_BINARY` set) → all
  checks passed, exit 0

Branch is **pushed to origin** (`phase1-reexport-project`,
https://github.com/graysonchalmers/Tool-ArmorPaintMCP/tree/phase1-reexport-project)
but **not yet merged to `main`** — that merge/integration decision belongs
to a separate controller-level step (`superpowers:finishing-a-development-branch`),
not to this task.

## ▶️ Next concrete step

Run `superpowers:finishing-a-development-branch` to decide how
`phase1-reexport-project` integrates into `main` (merge, PR, or otherwise).

After that's settled, Phase 2 is `rebake_and_export` — the first tool that
needs a minic script template (not just native CLI flags like Phase 1's
`reexport_project`). Hand off to `writing-plans` for that once the branch
question is resolved.

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

- Branch: `phase1-reexport-project` (pushed to origin, not merged to `main`).
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
  `--background --export-textures`), and the `reexport_project` MCP tool.
- Added a real binary `.arm` fixture, unit tests, and one passing
  integration test run against real ArmorPaint on this machine.
- Added a docs gallery with two real (if visually flat/deliberately-blank
  fixture) example output images and an honest caption.
- Task 8 final verification sweep all green (unit, integration, smoke,
  `--check`); pushed `phase1-reexport-project` to origin (not merged to
  `main` — that's next, via `superpowers:finishing-a-development-branch`).
