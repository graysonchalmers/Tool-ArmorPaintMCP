# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-16_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

Phases 1-3 are all shipped on `main` and pushed: `reexport_project`,
`create_procedural_material` + `list_available_presets`, and now
`inspect_project` (a read-only `.arm` metadata query — objects, materials,
layers) + `catalog.py`'s dynamic blend-mode extraction. The gallery also
got a real upgrade this session — noise and Voronoi procedural-material
renders replace the old flat checker/solid swatches as the visual
centerpiece. Design spec:
[docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md).
Implementation plan: [docs/PLAN.md](docs/PLAN.md). Phase 3's own plan is
recorded at [docs/superpowers/plans/2026-09-16-phase3-inspect-project.md](docs/superpowers/plans/2026-09-16-phase3-inspect-project.md).

## 📌 Where we stopped

Session had two threads, both closed out:

**1. Better gallery screenshots** (the ask that opened the session). Spiked
whether ArmorPaint's minic engine supports node types beyond the two
`create_procedural_material` ships, and multiple build/fill/export cycles
in one `--script` process — both confirmed working against the real local
build in one shot (checker/noise/Voronoi, 3 cycles, 1 process, all 15
expected files landed). `scripts/generate_gallery.py` (hand-written minic,
deliberately outside the shipped tool surface, same convention as
`tests/fixtures/generate_fixture.py`) renders noise (~791K distinct
colors) and Voronoi (cellular, ~771 colors) — both dramatically richer than
the old checker's 3-color swatches. Committed straight to `main` first
(`03735eb`), ahead of the Phase 3 merge, since it touched `README.md` and
needed to land before a clean merge was possible.

**2. Phase 3: `inspect_project` + dynamic catalog.** Key discovery:
`ArmorPaint.exe <project> --api` is a third, previously-unused automation
path — pass it a project and it dumps the *entire* project state as JSON
(objects, materials, layers, large arrays omitted) plus a text node-type
reference, in one clean subprocess call with **no poll-and-terminate
dance** (unlike the existing `--export-textures`/`--script` flows — `--api`
sets `args_background = true` internally and self-exits). Ran the full
`writing-plans` → `subagent-driven-development` lifecycle in an isolated
worktree (6 tasks, each independently reviewed clean). The **final
whole-branch review (opus) caught two real Critical bugs** the per-task
reviews missed:
- Layer blend-mode names were silently wrong for 6 of 18 modes (index ≥
  12): the code indexed `layer_datas[].blending` into the wrong enum — the
  MIX_RGB *material node's* 19-entry blend-type ENUM (parseable from
  `--api` text) instead of ArmorPaint's actual 18-entry layer `blend_type_t`
  C enum (`paint/sources/enums.h:135-154`, confirmed by reading the source
  directly — **never exposed as text anywhere**, so this one field is a
  deliberate, documented exception to "dynamic catalogs only," hardcoded
  and cited). Fixed via a new `catalog.layer_blend_modes()`.
- `inspect_project` returned `ok: True` describing ArmorPaint's *phantom
  default project* for a nonexistent or non-`.arm` path — confirmed against
  the real binary that a typo'd path silently opens nothing and reports a
  confident, wrong answer. Fixed with a file-exists + `.arm`-extension
  guard before launching ArmorPaint.
- Plus 2 Important test-coverage gaps closed in the same fix wave: the
  real-fixture integration test was tightened (it previously asserted only
  types/truthiness — a shape the phantom-project bug also satisfied), and a
  regression test for the blend-index-≥-12 case was added (unit-level,
  since an exhaustive search of all ~55 minic `script_*` functions found no
  way to set a layer's blend mode from a script for a real end-to-end
  fixture).

One controller ruling got **partially reversed** by that final review: I'd
earlier accepted Task 4's multi-material fixture as sufficient even though
it never got a second layer or exercised `material_datas` correlation,
reasoning `inspect_project` doesn't consume `material_datas` anyway. That
reasoning held for `material_datas` — but the **layers half of the gap was
load-bearing**: it's exactly what hid the blend-mode bug above. Lesson
banked in the plan's ledger, not just this doc.

Verification sweep, run twice (once pre-merge on the branch, once again on
the actual merged `main` tree — never trust a pre-merge green):
- `pytest -q` → 76 passed, 4 deselected
- `pytest -q -m integration` (with `AP_BINARY` set) → 4 passed (Phase 1 +
  Phase 2's existing tests unregressed, plus both new Phase 3 tests)
- `pwsh smoke\smoke.ps1` → 5/5 passed, exit 0 (new `inspect_project`
  probe passing)

**Merged to `main` locally, then pushed** via
`superpowers:finishing-a-development-branch` (a real merge commit, not
fast-forward, since `main` had the gallery commit ahead of the branch
point). One extra fix during cleanup: the Phase 3 plan doc had only ever
existed as a loose, uncommitted working copy in the worktree (never
actually committed by any of that branch's own tasks) — caught this because
`git worktree remove` refused over it, copied it onto `main`, and committed
it for the historical record, matching Phase 1/2's own committed-plan
precedent. `origin/main` is now at `9540526`, confirmed `0  0` against
local `HEAD`.

## ▶️ Next concrete step

Phase 4 per `docs/PLAN.md`: `run_script` escape hatch (the purpose-built
tool for anything the earlier purpose-built tools don't cover) +
documentation/packaging polish (clean-clone `pip install -e .` check,
README accuracy pass). This is the last phase in the current plan.

Alternatives:
- The final review's 4 deferred Minor findings are still open in the
  Phase 3 branch's history (not re-ledgered anywhere durable yet): stdout
  encoding in `runner.run_api` (locale-encoding decode could raise
  `UnicodeDecodeError` on non-ASCII object/material names — the one stdout
  path that decodes user-supplied names, unlike the export flows which only
  decode stderr), `blend_modes()` parse failure currently aborts the whole
  `inspect_project` read (degrading to `blending: None` would be kinder),
  `catalog.scene_objects`'s error convention differs from its two siblings
  (returns `[]` silently instead of raising `CatalogError`), and a repeated
  4-key failure-dict literal in `server.py` that could drift. None are
  urgent; worth a cheap cleanup pass before Phase 4 if picking this up soon
  while the context is fresh.
- If Phase 4's `run_script` escape hatch feels premature without a concrete
  need for it yet, a quick gut-check with Grayson on whether it's still
  wanted before writing that plan would avoid over-building.

## ❓ Open questions

- Live mode (deferred, not rejected) — two options named in the spec, neither
  chosen; revisit only once batch mode is solid and live mode is actually
  wanted.
- The 4 deferred Minor findings above — worth their own small cleanup task,
  or fold into Phase 4's "polish" scope when that plan gets written?

## 🗂️ Changed this session

- No branch left behind: `worktree-phase3-inspect-project` was merged and
  deleted (worktree + branch, both local), gallery work landed directly on
  `main`. `origin/main` is in sync (`9540526`).
- Files: `scripts/generate_gallery.py` (new) + 2 new gallery PNGs +
  `README.md` (gallery section) for the screenshots work;
  `src/armorpaint_mcp/{runner.py,catalog.py,server.py}`,
  `tests/{test_runner.py,test_catalog.py,test_server.py,test_inspect_project_integration.py,fixtures/generate_multi_fixture.py,fixtures/sample_project_multi.arm}`,
  `smoke/smoke.ps1`, `docs/PLAN.md`, `STATUS.md`, `README.md`,
  `docs/superpowers/plans/2026-09-16-phase3-inspect-project.md` for Phase 3.
- Decisions (+ why): dropped bake-type cataloging from Phase 3 entirely —
  ArmorPaint's `--api` never exposes the bake-type option list as text
  (`TEX_BAKE`'s selector is a `CUSTOM` widget, not an `ENUM`), and no tool
  can invoke baking anyway (already closed as structurally unreachable,
  `STATUS.md` Known Issue #1), so a bake-type catalog would have zero
  consumers; hardcoded `layer_blend_modes()` as a documented, cited
  exception to "dynamic catalogs only" rather than silently reusing the
  wrong (but text-available) MIX_RGB enum, once the final review proved
  they're genuinely different lists; ruled Task 4's shipped scope
  acceptable against its own literal steps even though its "why this task
  exists" prose promised more — then let the final review's evidence
  override that ruling on the one point (layers) where it turned out to
  matter, rather than defending the earlier call past the point it held up.

---

## 🕓 Session log

### 2026-09-16 — better gallery screenshots + Phase 3 (`inspect_project`)
- Grayson opened the session asking for better debug/smoke examples so the
  GitHub gallery had stronger screenshots than the existing flat swatches.
  Spiked multi-cycle/multi-node-type minic scripting directly against the
  real ArmorPaint build (not source-reading alone) before committing to a
  design — confirmed both worked in one process. Shipped
  `scripts/generate_gallery.py` and real noise/Voronoi gallery images,
  committed to `main`.
- Grayson also chose to start Phase 3 in the same session. Research into
  `inspect_project`'s actual data source (what can ArmorPaint's `.arm`
  format/scripting surface actually expose about objects/materials/layers?)
  turned up the `--api`-with-a-project-path project-state-JSON-dump
  discovery — genuinely new information not assumed in the original design
  spec's Phase 3 sketch.
- Wrote a 6-task plan (`superpowers:writing-plans`), pre-flight-scanned it
  for cross-task conflicts (clean), and executed via
  `superpowers:subagent-driven-development` in an isolated worktree — each
  task implemented by a fresh subagent (haiku for pure-transcription tasks,
  sonnet for judgment/integration tasks) and reviewed by a second, separate
  subagent before moving on.
- Final whole-branch review (opus, the most capable model, per this
  project's own established convention) found 2 Critical + 2 Important
  findings the six per-task reviews had each individually missed — a real
  demonstration of why the final broad pass exists even after every task
  passed its own gate. One fix-dispatch closed all four; scoped re-review
  confirmed clean with no new breakage.
- Merged locally (a genuine merge commit, since `main` had moved ahead with
  the gallery commit), re-verified green on the actual merged tree (not
  just the pre-merge branch), caught and fixed one more loose end during
  worktree cleanup (the plan doc itself had never been committed by any
  task), then pushed to `origin` on Grayson's explicit go-ahead.

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
