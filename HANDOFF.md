# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-16 (wrap-up)_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

**v1's tool surface is complete AND its review debt is now closed.** All
five planned tools (`reexport_project`, `create_procedural_material` +
`list_available_presets`, `inspect_project`, `run_script`) are shipped,
tested, and gated — see Phase 4's entry below for that history. This
session additionally closed the 7 Minor findings parked at the end of
Phase 3's and Phase 4's final reviews (a cleanup pass, not a new phase —
`docs/PLAN.md` still has no Phase 5). Merged to `main` (`973a696`, real
`--no-ff` merge commit) and pushed — `origin/main` confirmed in sync.
Design spec: [docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md).
Implementation plan: [docs/PLAN.md](docs/PLAN.md). This session's own plan:
[docs/superpowers/plans/2026-09-16-minor-findings-cleanup.md](docs/superpowers/plans/2026-09-16-minor-findings-cleanup.md).

## 📌 Where we stopped

The Minor-findings cleanup pass is done, merged, and pushed. Nothing is
mid-flight. The project is at a clean, fully-verified stopping point —
there is no unfinished task to resume.

Executed as a 5-task plan
(`docs/superpowers/plans/2026-09-16-minor-findings-cleanup.md`) in an
isolated worktree (`worktree-minor-findings-cleanup`), each task committed
and reviewed before the next:

- **Task 1** (`d23fb6b`) — hardened `runner.run_api`'s stdout decode
  (`errors="replace"`) against non-ASCII object/material names that could
  otherwise raise `UnicodeDecodeError` and lose the whole `--api` result.
- **Task 2** (`2e75990`) — `catalog.scene_objects` now raises `CatalogError`
  when the "Scene objects in world space" marker is entirely absent from
  `--api` output, consistent with its sibling parsers (`extract_project_state`,
  `blend_modes`) — previously it silently returned `[]`, indistinguishable
  from a genuinely empty scene. `inspect_project`'s call site moved inside
  the existing `try/except CatalogError` block so the new exception can
  never escape uncaught.
- **Task 3** (`d4bc9b9`) — extracted two shared `server.py` helpers,
  `_failure(error, *null_fields)` and `_is_arm_project_file(path)`, and
  refactored all four tool functions to use them — pure refactor, no
  behavior change (verified: identical test pass count, no error-text
  changes).
- **Task 4** (`7401711`) — added a real-binary integration test for
  `run_script`'s timeout path (`timeout_s=0.01` against the real
  `ArmorPaint.exe`, forcing a genuine `subprocess.TimeoutExpired`) — only a
  mocked one existed before.
- **Task 5** (`d0c4f71`) — `STATUS.md` closeout: a Deviations entry for
  `run_script(project, script)` taking inline text instead of the
  originally-spec'd `script_path`, and two Known Issues entries closing
  findings confirmed **genuinely moot** via real `grep` verification (not
  just asserted) — `inspect_project` was found to no longer call the
  parsing `blend_modes()` at all (replaced by the hardcoded
  `layer_blend_modes()` back in Phase 3), and the "timeout discards partial
  output" concern is moot since stdout/stderr are already documented as
  structurally empty on this Windows build.

Final whole-branch review (opus, per this project's own established
convention) said "Ready to merge: Yes" — found 1 Important finding (an
unasserted `_failure()` null-field key-set invariant: nothing in the test
suite actually checked the exact key set at 6 of 10 call sites, so a future
typo like `_failure(msg, "file")` instead of `"files"` would silently ship)
plus several Minor findings. One fix wave (`37c9a76`) closed the Important
finding at 8 of 10 call sites plus 2 doc-accuracy Minors in `STATUS.md`. The
scoped re-review confirmed no new breakage but found the fix incomplete: 2
tests (`test_run_script_rejects_nonexistent_project_path` and
`test_run_script_rejects_path_outside_allowed_roots`) still assert only
`result["stdout"] is None`, missing the sibling `result["stderr"] is None`
for the same `_failure(msg, "stdout", "stderr")` call site. Per this
project's own subagent-driven-development convention, the final review gets
exactly one fix wave — no second round was spent. Adjudicated and parked:
the underlying code is already correct at both sites (verified
independently twice), so this is a real but non-load-bearing test-coverage
gap, not a live bug. Flagged below as a fine opportunistic pickup.

Verified fresh on the actual merged `main` tree (not just the pre-merge
branch): `.venv\Scripts\python.exe -m pytest -q` → **95 passed, 0 failed, 9
deselected**; `-m integration` (real `AP_BINARY`) → **9 passed, 0 failed**;
`pwsh smoke\smoke.ps1` → **6/6 passed, exit 0**.

---

### Earlier: Phase 4 (`run_script` escape hatch + v1 polish)

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
  checkout, since Phase 4's commits weren't merged to `main` yet at that
  point — cloning from there would have tested pre-Phase-4 code), fresh
  `python -m venv`, `pip install -e .` succeeded cleanly (built the
  editable wheel, all deps resolved), `ap-mcp --version` and `--help` both
  exit 0. `ap-mcp --check` correctly reported `[FAIL] AP_BINARY: not set`
  (exit 1) since the fresh clone has no `.env` — the honest, expected
  result for a config-less clone, not a defect in the check itself.
  Scratch dir removed after.

Then the **final whole-branch review** (opus, the most capable model, per
this project's established convention) found 1 Critical + 3 Important
findings none of the five per-task reviews caught, since each was scoped to
one task's diff:

- **Critical:** `run_script` can call minic's `project_save(0)` and
  silently overwrite the caller's `.arm` project in place — demonstrated
  empirically (fixture file size/md5 changed after a
  `script_fill_layer(); project_save(0);` script ran with `ok=True`, no
  warning). The plan's Global Constraints section had affirmatively (and
  wrongly) claimed `run_script` "never saves a project... no
  in-place-mutation risk." **Ruling:** fix is documentation-only, not an
  architecture change — no copy-by-default, no opt-in flag. The design
  spec explicitly says this tool must not be gated behind an extra flag,
  and a flag couldn't be enforced anyway since minic scripts can't be
  statically analyzed for whether they'll call `project_save()` before
  running them; forcing copy-by-default would also defeat the tool's
  actual purpose (acting on the real project) for exactly the cases it
  exists to serve.
- **Important:** `stdout`/`stderr` are structurally always empty on this
  Windows build — ArmorPaint's script-facing console functions
  (`console_log` etc.) write via `WriteConsoleW` directly to the console
  handle, which `subprocess.run(capture_output=True)`'s pipe redirection
  cannot capture (verified empirically; different from `run_api`, which
  uses plain `printf` and works fine).
- **Important:** the docstring's "Bounded by AP_ALLOWED_ROOTS when set"
  overclaimed — only the `project` path is bounded, not what the script
  body itself does.
- **Important:** no caller-facing `timeout_s` override existed, pinning an
  inherently unbounded, caller-defined workload to the 30s default.

One fix wave (`f764464`) closed all four, corrected the false claim
everywhere it appeared (plan, `server.py` docstring, `STATUS.md`,
double-checked `README.md` wasn't affirmatively claiming safety either),
added the honest `WARNING`/`NOTE` docstring language, fixed the
`AP_ALLOWED_ROOTS` sentence, and added `timeout_s: float = 30.0` as a real
parameter (forwarded to `run_minic_script`, covered by a new unit test).
Scoped re-review: all four ADDRESSED, no new breakage. 4 Minor findings
parked (see "Open questions" below) — none load-bearing.

Verification re-run fresh after the fix wave and again on the actual
**merged `main` tree** (never trust a pre-merge green): unit **88 passed, 0
failed, 6 deselected**; integration **6 passed, 0 failed**; smoke **6/6,
exit 0**.

**Merged and pushed.** `git merge --no-ff worktree-worktree-phase4-run-script`
into `main` (a real merge commit, `0c61b94`), worktree and branch removed,
pushed to `origin` on Grayson's explicit go-ahead — `origin/main` is
confirmed `0  0` against local `HEAD`.

## ▶️ Next concrete step

**Both `docs/PLAN.md`'s 4 phases AND their follow-up review debt are now
closed.** There is no Phase 5 and no more parked findings. The project is
at a genuine stopping point — the natural next work is whatever Grayson
picks up next, not something this codebase is waiting on:

- **The one parked test-coverage gap** (see this session's log entry below)
  — two tests missing a `result["stderr"] is None` assertion on an
  already-correct `run_script` code path. Trivial, non-urgent; fine to fix
  opportunistically next time `tests/test_server.py` is open for something
  else, or as its own 5-minute task.
- **Live mode** — deferred, not rejected, per the design spec's "Deferred:
  live mode" section (two options already named there, neither chosen).
  Revisit only once there's an actual concrete need for interactive
  GUI-attached control, not before.

## ❓ Open questions

- Live mode (deferred, not rejected) — two options named in the spec, neither
  chosen; revisit only once batch mode is solid and live mode is actually
  wanted.
- The parked `_failure()` key-set assertion gap (2 of 10 call sites) — worth
  its own tiny task, or picked up opportunistically? Not blocking anything.

## 🗂️ Changed this session

- Merged to `main` (`973a696`, real `--no-ff` merge commit) and pushed to
  `origin` — confirmed in sync. Worktree/branch
  (`worktree-minor-findings-cleanup`) removed after the merge.
- Files this session: `src/armorpaint_mcp/runner.py` (`run_api` decode
  hardening), `src/armorpaint_mcp/catalog.py` (`scene_objects` error
  convention), `src/armorpaint_mcp/server.py` (`_failure`/
  `_is_arm_project_file` shared helpers across all four tools),
  `tests/test_runner.py`, `tests/test_catalog.py`, `tests/test_server.py`,
  `tests/test_run_script_integration.py` (new real-timeout test),
  `STATUS.md` (Deviations entry + 2 Known Issues closures),
  `docs/superpowers/plans/2026-09-16-minor-findings-cleanup.md` (new),
  `HANDOFF.md`. Also logged this session to
  `_agent-commons\log\2026-09-16-claude-code-armorpaint-mcp-minor-findings-cleanup.md`
  (Skills-Core repo, committed and pushed separately via `Push-Repo.ps1`
  from inside `_agent-commons` — the shell's cwd resets between tool calls
  in this harness, so `Set-Location` and the script invocation had to be
  one single PowerShell call, not two).
- Decisions (+ why): confirmed via `grep` — not just asserted — that
  `inspect_project` no longer calls the parsing `blend_modes()` at all
  before writing STATUS.md's "moot" closure for that finding; ruled the
  final whole-branch review's one residual gap (2 tests missing a
  `stderr` assertion after the fix wave) as non-load-bearing and parked it
  rather than spending a second fix wave, since this project's
  subagent-driven-development convention grants the final review exactly
  one fix round.

---

## 🕓 Session log

### 2026-09-16 — Minor-findings cleanup pass (5 tasks, closes Phase 3+4 review debt)
- Picked up with v1's tool surface already shipped/merged/pushed from the
  prior session; `docs/PLAN.md` had no Phase 5, but HANDOFF's own "Next
  concrete step" named a consolidated Minor-findings cleanup pass as the
  natural follow-up. Grayson chose it, then to move on once done.
- Wrote a 5-task plan and executed it via `superpowers:subagent-driven-development`
  in an isolated worktree (`worktree-minor-findings-cleanup`, created via
  the native `EnterWorktree` tool), each task implemented and reviewed by a
  separate fresh subagent before the next task started. All 5 task reviews
  came back clean.
- Investigated (not assumed) two findings that turned out moot on closer
  reading: `blend_modes()`'s parse-failure risk no longer applies to
  `inspect_project` at all (Phase 3's own earlier fix had already replaced
  it with the hardcoded `layer_blend_modes()`), and the
  timeout-discards-partial-output concern is superseded by the already-documented
  stdout/stderr-empty fact. Verified both via `grep`/direct code reading
  before writing the closure into STATUS.md.
- Final whole-branch review (opus) found 1 Important + several Minor
  findings; one fix wave closed the Important finding and 2 doc-accuracy
  Minors. Scoped re-review found the fix wave introduced no new breakage
  but was itself incomplete at 2 of 10 call sites (a missing `stderr`
  assertion, not a code defect). Adjudicated and parked per this project's
  one-fix-wave convention for final reviews, surfaced to Grayson rather
  than silently dropped.
- Merged to `main` (`973a696`, real merge commit — an untracked duplicate
  plan-doc file left over from before the worktree was created had to be
  removed first, since it would otherwise have blocked the merge), re-verified
  green on the actual merged tree (95 unit / 9 integration / 6 smoke, all
  passing), removed the worktree and branch, pushed to `origin` on
  Grayson's explicit go-ahead.

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
- Final whole-branch review (opus) found 1 Critical + 3 Important findings
  the five per-task reviews missed: `run_script` can call minic's
  `project_save()` and silently overwrite the caller's project in place,
  contradicting the plan's false "never saves a project" claim; stdout/
  stderr are structurally always empty on this Windows build
  (`WriteConsoleW`, not pipe-capturable); an `AP_ALLOWED_ROOTS` docstring
  overclaim; and no caller-facing timeout override. Ruled the Critical fix
  should be documentation-only (no copy-by-default, no opt-in flag), per
  the design spec's explicit framing for this specific tool. One fix wave
  closed all four; scoped re-review came back clean, 4 Minor findings
  parked (see "Next concrete step").
- Merged to `main` (`0c61b94`, real merge commit), re-verified green on the
  merged tree (88 unit, 6 integration, 6/6 smoke), removed the worktree and
  branch, pushed to `origin` on Grayson's go-ahead, confirmed `0  0` sync.
  Logged the session to `_agent-commons\log\` (Skills-Core repo).

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
