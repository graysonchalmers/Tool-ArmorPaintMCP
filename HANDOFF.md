# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-15_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

Project scaffolded today (2026-09-15) after a `superpowers:brainstorming`
session settled the architecture: a Python MCP server that batch-drives
ArmorPaint via its native CLI flags and minic scripting engine, deliberately
**not** patching ArmorPaint's source the way the reference implementation
does. Design spec is written and approved
([docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md)).
Phase 0 (scaffold + smoke harness) is in progress via `project-setup`: git,
package skeleton (`config.py`/`doctor.py`/`server.py`, zero tools yet),
build stamp, and standard docs are being created now.

## 📌 Where we stopped

`project-setup` complete: smoke gate green (3/3), scaffold committed (2
commits on `main`), build stamp baked, GitHub repo created and pushed
(`graysonchalmers/Tool-ArmorPaintMCP`, private,
https://github.com/graysonchalmers/Tool-ArmorPaintMCP).

## ▶️ Next concrete step

Hand off to `writing-plans` for Phase 1 (`reexport_project` tool — the first
real MCP tool, pure native `--export-textures` flags, no minic script
needed; see [docs/PLAN.md](docs/PLAN.md)).

Alternatives:
- Skip the GitHub repo creation and stay local-only a while longer — lower
  priority than actually writing Phase 1's tool.
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

- Branch: (git not yet initialized as of this write)
- Files: whole scaffold — see git first commit once made.
- Decisions (+ why): no source patching (ArmorPaint's native CLI/scripting
  already covers the batch-mode scope — see spec); Python + official `mcp`
  SDK (matches local sibling Tool-MaterialMaker-MCP's proven pattern);
  coarse pipeline tools, not one-tool-per-operation (subprocess-per-call
  model means fine-grained tools would each pay a full process launch);
  first real workflow target is batch re-export/rebake of *existing*
  projects, not from-scratch material authoring (narrower, lower-risk v1).

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
