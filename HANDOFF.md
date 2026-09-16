# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-16_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

**Phase 4 (`run_script`) is shipped — v1's tool surface is now complete.**
All five planned tools are implemented, tested, and gated:
`reexport_project`, `create_procedural_material` + `list_available_presets`,
`inspect_project`, and now `run_script` — an escape-hatch tool that hands
the caller's own minic (.c) source straight to ArmorPaint's `--script` flag
against an already-open project, for anything the four purpose-built tools
don't cover. `pyproject.toml`'s classifier moved from Pre-Alpha to Alpha and
the README got a pass reflecting the complete v1 surface. Design spec:
[docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md).
Implementation plan: [docs/PLAN.md](docs/PLAN.md). Phase 4's own plan is
recorded at [docs/superpowers/plans/2026-09-16-phase4-run-script.md](docs/superpowers/plans/2026-09-16-phase4-run-script.md).

## 📌 Where we stopped

Phase 4 (`run_script` + docs/packaging polish) executed as a 5-task plan
(`docs/superpowers/plans/2026-09-16-phase4-run-script.md`) in an isolated
worktree (`worktree-worktree-phase4-run-script`), each task committed and
reviewed before the next:

- **Task 1** (`c09bff0`) — `runner.run_minic_script`: launches ArmorPaint
  **with** `--background` this time (a confirmed departure from Phases 1-2's
  no-`--background` pattern — see the plan's "Empirical findings"),
  `subprocess.run([binary, project, "--background", "--script", path])`
  against an already-open project. Empirically confirmed the process
  self-exits cleanly in ~1-2s and runs the script correctly, so **no
  poll-and-terminate dance is needed** here (unlike `--export-textures`,
  where Amendment 1 found `--background` races ahead of a deferred export —
  this is a different code path: `args_run_script`'s `minic_eval()` runs
  synchronously before `iron_stop()` is scheduled). Also reconfirmed minic's
  known silent-failure mode: a script calling an undefined function exits 0
  with empty stdout/stderr, identical to success — `ok=True` proves only
  that the ArmorPaint process completed, never that the script did what was
  asked. Documented prominently in the docstring so callers don't
  over-trust the return value.
- **Task 2** (`e29614c`) — registered `run_script` as the server's fifth MCP
  tool, mirroring `inspect_project`'s exact pattern: same
  `AP_ALLOWED_ROOTS` sandboxing via `ensure_within_roots`, and the same
  phantom-default-project guard (file-exists + `.arm`-extension check
  before launching ArmorPaint, so a bogus path can't silently make
  ArmorPaint open its own empty default project and report a false
  `ok: True` — the Phase 3 Critical-finding pattern, applied proactively
  here instead of needing a second review cycle to catch it).
- **Task 3** (`8fbcdb4`) — `tests/test_run_script_integration.py`: two real
  end-to-end tests against the actual local `ArmorPaint.exe`, filling a
  layer and exporting textures via `--script` against the fixture project.
  Both passed first run; full suites green with no regressions (87/87 unit,
  6/6 integration at that point in the branch).
- **Task 4** — Phase 4 plan doc itself, committed (`698080c`) before
  implementation started, continuing Phase 1-3's precedent of the plan
  living in git history, not just the worktree.
- **Task 5 (this task)** — final verification sweep + `README.md` /
  `pyproject.toml` polish (`8735118`): `Development Status` classifier
  moved Pre-Alpha → Alpha, README's Status section now states all five v1
  tools are shipped, and a short escape-hatch blurb for `run_script` was
  added to the tools section.

Verification run fresh on the fully-assembled branch (all counts real,
this session):
- `.venv\Scripts\python.exe -m pytest -q` → **87 passed, 0 failed, 6
  deselected**
- `.venv\Scripts\python.exe -m pytest -q -m integration` (with `AP_BINARY`
  set to the real local `ArmorPaint.exe`) → **6 passed, 0 failed** (every
  prior phase's integration test plus both new `run_script` tests, no
  regressions)
- `pwsh smoke\smoke.ps1` → **6/6 passed, exit 0**, including the new
  `run_script registered as an MCP tool` probe
- **Clean-clone install check** (this phase's own stated gate from
  `docs/PLAN.md`): cloned the worktree's committed tree to a scratch temp
  dir (not the `main`-tracking `C:\Projects-local\Tool-ArmorPaintMCP`
  checkout, since Phase 4's commits aren't merged to `main` yet — cloning
  from there would have tested pre-Phase-4 code), fresh `python -m venv`,
  `pip install -e .` succeeded cleanly (built the editable wheel, all deps
  resolved), `ap-mcp --version` and `--help` both exit 0. `ap-mcp --check`
  correctly reported `[FAIL] AP_BINARY: not set` (exit 1) since the fresh
  clone has no `.env` — the honest, expected result for a config-less clone,
  not a defect in the check itself. Scratch dir removed after.

## ▶️ Next concrete step

**Phase 4 was the last phase in `docs/PLAN.md` — there is no Phase 5.**
This worktree/branch still needs to be finished (merged into `main` and
pushed, following the same `superpowers:finishing-a-development-branch`
path Phases 1-3 used) as the immediate mechanical step. After that lands,
the natural next work is one of:

- **The 4 deferred Minor findings from Phase 3's final review**, still open
  and not yet re-ledgered anywhere durable: stdout encoding in
  `runner.run_api` (locale-encoding decode could raise
  `UnicodeDecodeError` on non-ASCII object/material names), `blend_modes()`
  parse failure currently aborts the whole `inspect_project` read
  (degrading to `blending: None` would be kinder), `catalog.scene_objects`'s
  error convention differs from its two siblings (returns `[]` silently
  instead of raising `CatalogError`), and a repeated 4-key failure-dict
  literal in `server.py` that could drift. None are urgent — a cheap
  cleanup pass, not a new phase.
- **Live mode** — deferred, not rejected, per the design spec's "Deferred:
  live mode" section (two options already named there, neither chosen).
  Revisit only once there's an actual concrete need for interactive
  GUI-attached control, not before.

## ❓ Open questions

- Live mode (deferred, not rejected) — two options named in the spec, neither
  chosen; revisit only once batch mode is solid and live mode is actually
  wanted.
- The 4 deferred Minor findings above — worth their own small cleanup task,
  or picked up opportunistically the next time one of those files is
  touched for an unrelated reason?

## 🗂️ Changed this session

- Still on the isolated worktree/branch `worktree-worktree-phase4-run-script`
  — **not yet merged to `main`**. Merging is the immediate next mechanical
  step (see "Next concrete step" above), not done as part of this task.
- Files this session: `src/armorpaint_mcp/runner.py` (`run_minic_script`),
  `src/armorpaint_mcp/server.py` (`run_script` tool registration),
  `tests/test_runner.py`, `tests/test_server.py`,
  `tests/test_run_script_integration.py` (new), `smoke/smoke.ps1` (new
  probe), `docs/superpowers/plans/2026-09-16-phase4-run-script.md` (new),
  `README.md`, `pyproject.toml`, `STATUS.md`, `HANDOFF.md`.
- Decisions (+ why): launched `run_minic_script` **with** `--background`
  (a departure from Phase 1-2's runner functions, which deliberately omit
  it) after confirming empirically that `--background` + `--script` against
  an already-open project self-exits cleanly with no poll-and-terminate
  needed — a different code path from the `--background` + `--export-textures`
  combination Amendment 1 found racy; applied `inspect_project`'s
  phantom-default-project guard to `run_script` proactively at
  implementation time (Task 2) instead of waiting for a review cycle to
  catch it, since Phase 3's final review had already established the
  pattern; for the clean-clone check (this task), cloned from the worktree
  itself rather than the brief's literal `C:\Projects-local\Tool-ArmorPaintMCP`
  path, since Phase 4's commits live only on this unmerged branch and
  cloning the `main`-tracking checkout would have silently tested
  pre-Phase-4 code.

---

## 🕓 Session log

### 2026-09-16 — Phase 4 (`run_script` escape hatch + v1 polish)
- Picked up with Phases 1-3 shipped and pushed to `main`; `docs/PLAN.md`
  named Phase 4 (`run_script` + docs/packaging polish) as the final planned
  phase.
- Wrote a 5-task plan (`docs/superpowers/plans/2026-09-16-phase4-run-script.md`)
  and executed it task-by-task in an isolated worktree
  (`worktree-worktree-phase4-run-script`), each task committed and reviewed
  before the next: `runner.run_minic_script` (Task 1, `c09bff0`), the
  `run_script` MCP tool registration mirroring `inspect_project`'s
  sandboxing + phantom-project guard (Task 2, `e29614c`), a real-binary
  integration test (Task 3, `8fbcdb4`), the plan doc itself (Task 4,
  `698080c`), and this final verification sweep + docs update (Task 5).
- Confirmed empirically (not assumed from source-reading) that
  `--background` + `--script` against an already-open project behaves
  differently from `--background` + `--export-textures`: the former
  self-exits cleanly with no race, letting Phase 4 skip the
  poll-and-terminate dance every earlier phase needed. Also reconfirmed
  minic's silent-failure mode (an undefined-function call exits 0 with
  empty output, same as success) and documented it prominently so
  `run_script` callers don't over-trust `ok: True`.
- Ran the full verification sweep fresh on the assembled branch: unit
  (87 passed, 6 deselected), integration with the real local
  `ArmorPaint.exe` (6 passed, no regressions), smoke harness (6/6, exit 0,
  new `run_script` probe passing), and the clean-clone install check
  specified as this phase's own gate in `docs/PLAN.md` (`git clone` to a
  scratch temp dir, fresh venv, `pip install -e .`, `--version`/`--help`
  exit 0, `--check` correctly red on missing `AP_BINARY` for a
  config-less clone — the expected, honest result).
- Updated `STATUS.md` (Phase 4 gate row + detail table, `Open phase` set to
  "none") and this file to reflect v1's tool surface being complete, and
  that Phase 4 was the last phase in the plan — no Phase 5 exists.

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
