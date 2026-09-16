# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-15 23:58 CT_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

Phase 1 (`reexport_project`) and Phase 2 (`create_procedural_material` +
`list_available_presets`) are both shipped on `main`. Phase 2 lets an
assistant build a small procedural material (a checker pattern or a flat
color), render it into a fresh default ArmorPaint project's paint layer,
and export it — all inside one ArmorPaint process. Mesh-detail rebaking and
texture-set swapping (Phase 2's originally-planned scope) are **confirmed
structurally unreachable** on this build and are now permanently out of
scope — see `STATUS.md`'s Known Issues and the design spec's Amendment 2 for
the full empirical writeup. Design spec:
[docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md).
Implementation plan: [docs/PLAN.md](docs/PLAN.md).

## 📌 Where we stopped

Phase 2 rescoped twice this session after hands-on spiking (not just source
reading) against the real local ArmorPaint build: baking turned out to be a
GUI-button-only C function with no script/CLI path, and texture-set
swapping turned out to need reading `project_t->assets->length` from
minic — which silently aborts script execution (minic's struct access is
curated, not general C). What DID work: building a material node graph and
rendering+exporting it, but **only within a single ArmorPaint process** —
saving to `.arm` and re-exporting via a separate process (Phase 1's
`reexport_project` pattern) was empirically found to silently lose the
rendered pixels. `create_procedural_material` is a single-process
script-generator-and-runner built around that constraint.

All 7 tasks of the Phase 2 plan are complete and reviewed clean, executed on
feature branch `phase2-procedural-material`. The final whole-branch review
(opus) found 2 Important findings — fixed in one dispatch, re-reviewed
clean:
- `preset` was a silent no-op in the script-export path (`export_texture_run`
  has no preset argument and minic exposes no setter); worse, requesting
  `"base_color"` specifically returned `ok=True` for the WRONG export
  (its one file is a strict subset of `generic`'s five). Fixed:
  `create_procedural_material` now rejects any `preset != "generic"` with
  an honest capability-limit error.
  **Note if picking this up: this closes the bug but doesn't add
  preset support** — a future phase would need a real minic/CLI hook for
  choosing the export preset headlessly before this can be relaxed.
- `script_gen.py`'s numeric validation didn't guard against `OverflowError`
  (huge ints) or NaN/Infinity (both reachable via JSON), either escaping as
  an uncaught exception or breaking the generated minic script silently.
  Fixed via a `_finite_float` helper.

Plus 3 Minor doc-consistency fixes in the same wave (README's stale
rebake/texture-swap promise, `docs/PLAN.md`'s node-type list overstating
what shipped, `STATUS.md`'s Phase 3 row contradicting Phase 2's). One
residual parked, not fixed: `docs/PLAN.md`'s own Phase 3 *section heading*
still names `list_export_presets` (cosmetic — `STATUS.md`, the actual gate
ledger, is correct) — cheap to fix whenever that section is next touched.

Verification sweep is green:
- `pytest -q` → 58 passed, 2 deselected
- `pytest -q -m integration` (with `AP_BINARY` set) → 2 passed (Phase 1's
  `reexport_project` test + Phase 2's new checker-material content check,
  no regression)
- `pwsh smoke\smoke.ps1` → 4/4 passed, exit 0
- Gallery image (`docs/images/gallery/procedural_checker_base.png`)
  personally viewed this session — genuine red/dark-navy checker pattern,
  correctly UV-masked to the mesh's islands, not flat gray

**Merged to `main` and pushed** via `superpowers:finishing-a-development-branch`
(fast-forward, `aa5de5c..1ac4d47`). `phase2-procedural-material` (worktree
+ branch) has been removed — its history lives on in `main`'s git log.

## ▶️ Next concrete step

Phase 3 per `docs/PLAN.md`: `inspect_project` (a read-only `.arm` metadata
query — objects, materials, layers) + a dynamic catalog builder for
bake-types/blend-modes/export-presets from `--api` output and
`export_presets/*.json`. **Scope is narrower than `docs/PLAN.md`'s Phase 3
heading currently implies**: `list_export_presets` already shipped this
session (as the `list_available_presets` MCP tool) — don't re-build it, and
consider fixing that stale heading (the one parked finding from this
session) while in there. Hand off to `writing-plans` once the actual
remaining scope (`inspect_project` + catalog) is confirmed against the plan
text.

Alternatives:
- If `inspect_project`'s `.arm` metadata read turns out to need more than
  MessagePack-decoding the file directly (confirmed binary format from
  Phase 0 spiking), a quick spike on that specific question before writing
  the plan would avoid another mid-plan rescope like this session's.
- Phase 4 (`run_script` escape hatch + polish) could be pulled forward if
  Phase 3's catalog work turns out low-value on its own — worth a quick
  gut-check with Grayson before committing to plan order.

## ❓ Open questions

- Live mode (deferred, not rejected) — two options named in the spec, neither
  chosen; revisit only once batch mode is solid and live mode is actually
  wanted.
- Whether `inspect_project`'s read-only `.arm` parsing is worth building as
  real MessagePack decoding vs. something narrower — not yet scoped in
  detail (Phase 3 hasn't had its own brainstorm/plan pass yet).

## 🗂️ Changed this session

- Branch: `phase2-procedural-material`, merged to `main` and removed
  (worktree + branch, both local — no remote branch was pushed).
- Files: `script_gen.py` (new), `runner.py` (`_poll_and_terminate`
  extraction + `run_procedural_material`), `server.py`
  (`create_procedural_material` + `list_available_presets`), 3 new/extended
  test files, `docs/images/gallery/procedural_checker_base.png`, README/
  `docs/PLAN.md`/`STATUS.md`/the design spec (Amendment 2) all updated for
  the rescope, `HANDOFF.md` (this update).
- Decisions (+ why): rescoped Phase 2 twice based on empirical spiking, not
  assumption (baking blocked → confirmed structurally, not just untried;
  texture-swap blocked → minic's curated struct access, isolated via a
  3-step bisection ladder; procedural authoring works but single-process
  only → verified via two spikes that failed identically through a
  save/reload split and succeeded identically through one process); chose
  the "reject non-generic preset with an honest error" fix over silently
  dropping the parameter, to keep the door open for a future phase that
  finds a real preset-setting mechanism; parked the `docs/PLAN.md` Phase 3
  heading inconsistency rather than spending a second (disallowed) fix wave
  on a cosmetic doc mismatch.

---

## 🕓 Session log

### 2026-09-15 — Phase 2 rescope + `create_procedural_material` subagent-driven execution
- Picked up mid-Phase-2 with an already-blocked finding (baking unreachable)
  and a fresh AskUserQuestion pivot to "material-graph editing." Immediately
  found texture-swap ALSO blocked (minic struct-access limit, isolated via a
  3-step bisection spike) and pivoted again to "procedural material
  authoring" — the user confirmed both pivots via AskUserQuestion.
- Spiked the new scope directly: a checker-node-to-output connection,
  saved via `--script`, then exported via Phase 1's existing
  `reexport_project()` — produced flat gray, indistinguishable from an
  untouched default project. Root-caused via elimination (not guessing):
  confirmed `script_fill_layer()` + `export_texture_run()` both work when
  called in the SAME process as the graph-build, and confirmed the
  save/reload split is what loses the rendered pixels, via two spikes
  (solid RGB, then checker) that each failed through the split path and
  succeeded through the same-process path.
- Surfaced the finding to the user via AskUserQuestion (not a silent
  architecture swap) — confirmed proceeding with the single-process design.
- Updated `docs/PLAN.md`'s Phase 2 section and added a second spec
  amendment documenting all three findings (baking blocked, texture-swap
  blocked, procedural-authoring-single-process-only) before writing any
  implementation plan, so the "why this architecture" reasoning has a
  durable home independent of this conversation.
- Wrote and executed a 7-task implementation plan via subagent-driven-
  development: extracted a shared `_poll_and_terminate` helper (Task 1),
  built the minic script generator for a deliberately narrow v1 node-spec
  schema (checker/solid only — Task 2), added `run_procedural_material`
  (single-process launch, no `--background` — Task 3), wired the MCP tool
  plus a small bonus `list_available_presets` tool (Task 4), added a real
  integration test with genuine pixel-content verification (Task 5),
  generated and personally viewed real gallery output (Task 6), and ran a
  final verification sweep updating `STATUS.md` (Task 7). All 7 task
  reviews came back clean.
- Final whole-branch review (opus) caught a cross-task bug invisible to any
  single task's review: `preset` was a no-op in the script-export path, and
  `preset="base_color"` specifically returned a false `ok=True` for the
  wrong export. Also caught unguarded overflow/NaN/Infinity in numeric
  node-spec params. Fixed both plus 3 Minor doc-consistency issues in one
  fix wave; scoped re-review came back clean (one cosmetic finding parked,
  not fixed — see "Where we stopped").
- Merged `phase2-procedural-material` into `main` (fast-forward,
  `aa5de5c..1ac4d47`), re-verified green on the merged result, pushed to
  origin, removed the worktree and branch.

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
