# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-16 (wrap-up)_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

**Major pivot session: mesh/UV editing is now a first-class part of this
project, shipped as Phase 5, alongside v1's still-intact texture/material
tools.** Grayson redirected priority from batch texture/material export
toward automating mesh fixes (decimate/subdivide/bevel/smooth/duplicate/
merge/UV-unwrap) and eventually non-destructive mesh replace. A same-session
spike proved ArmorPaint 1.0's real GUI-only mesh-edit tools can be exposed to
`--script` via a scoped one-line-per-function patch to `minic_api_list.h` —
6 of 7 functions patched and empirically verified against real geometry in
the spike, the 7th (`merge_geometry_down`, targeted 2-object merge) a
confirmed dead end needing a new accessor. That became [ROADMAP.md](ROADMAP.md)
(the project's new North Star doc) plus Amendment 3 in the design spec
(revises, doesn't reverse, the original "no source patching" decision —
narrowly scoped to register-an-already-working-function patches). A 7-task
implementation plan
([docs/superpowers/plans/2026-09-16-phase5-mesh-uv-editing.md](docs/superpowers/plans/2026-09-16-phase5-mesh-uv-editing.md))
shipped all 7 tools (`decimate_mesh`, `bevel_mesh`, `subdivide_mesh`,
`smooth_mesh`, `duplicate_mesh`, `merge_mesh_geometry`, `unwrap_mesh_uvs`)
via subagent-driven-development — every task reviewed clean, a final
whole-branch review (opus) found 4 cross-task Important findings, one fix
wave closed all of them, a scoped re-review confirmed clean. **Merged to
`main` (`b461ff7`, real `--no-ff` merge commit) and pushed** — `origin/main`
confirmed in sync. v1's five original tools (`reexport_project`,
`create_procedural_material` + `list_available_presets`, `inspect_project`,
`run_script`) are unchanged, still shipped and gated (Phase 4's history
below). Design spec:
[docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md)
(now with Amendment 3). Implementation plan: [docs/PLAN.md](docs/PLAN.md)
(now with a Phase 5 section).

## 📌 Where we stopped

Phase 5 is done, merged, and pushed. Nothing is mid-flight — a clean,
fully-verified stopping point. Full detail on both the pivot (brainstorm →
spike → ROADMAP.md → plan) and the build (7-task SDD execution → final
review → fix wave → merge) is in this session's log entry below; the short
version: Grayson redirected priority to mesh/UV automation, a spike proved
ArmorPaint's GUI-only mesh-edit tools patch cleanly into `--script`, and all
7 tools shipped through this project's normal brainstorm→plan→SDD→review
pipeline with nothing skipped.

Verified fresh on the actual merged `main` tree (twice — once right after
merge, once more after adding a `.env` at the repo root since none existed
there before): `.venv\Scripts\python.exe -m pytest -q` → **122 passed, 0
failed, 18 deselected**; `-m integration` (real patched `AP_BINARY`) →
**18 passed, 0 failed** (one flaky failure on the very first post-merge run,
`smooth_mesh`'s vertex-count assertion — reran clean twice after; root-caused
to ArmorPaint's own algorithm, not a merge regression — see project memory
`armorpaint-smooth-mesh-flaky-vertex-count`, not yet run through
`smoke\smoke.ps1` this exact session but was 13/13 as part of Phase 5's
own Task 7 closeout).

## ▶️ Next concrete step

No open phase — `docs/PLAN.md`'s Phase 5 is the last one, and ROADMAP.md
items 1-7 are all shipped. Real options for next session, none urgent:

- **Upstream the mesh-edit patch as a PR to `armory3d/armorpaint`** —
  Grayson's stated ambition (his first open-source contribution). The patch
  (branch `spike/minic-decimate` in `C:\Projects-local\z-Git\ArmorPaint`,
  unpushed, one file, 7 functions, every line empirically proven) is a
  strong candidate. Not yet done: read the project's actual contribution
  guidelines, decide whether to mention the rejected `merge_geometry_down`
  attempt in the same PR or a follow-up.
- **ROADMAP.md items 8-10** — non-destructive mesh replace (needs its own
  bisection + a real multi-object fixture), targeted 2-object merge (needs
  a new minic accessor, bigger patch), UV validity check (reachability
  unchecked). None scoped into a phase yet.
- **Two small parked doc/docstring gaps** from the final review (see
  "Open questions") — trivial whenever `server.py` or the design spec is
  next open for something else.

## ❓ Open questions

- Live mode (deferred, not rejected) — two options named in the spec, neither
  chosen; revisit only once batch mode is solid and live mode is actually
  wanted. (Carried over, unchanged this session.)
- The parked `_failure()` key-set assertion gap (2 of 10 call sites, from the
  Minor-findings cleanup session) — still open, unrelated to Phase 5. Worth
  its own tiny task, or picked up opportunistically.
- Design spec's own Amendment 3 prose still says "6 of 7 functions patched" —
  ROADMAP.md's copy was corrected during Phase 5's final-review fix wave, the
  spec's own historical text wasn't (out of that fix's scope). Cosmetic.
- `merge_mesh_geometry`'s docstring has no general "ok=True proves only
  completion" caveat (only its precondition-guard-specific one) — a real but
  non-load-bearing gap, one sentence to fix whenever `server.py` is next open.
- `smooth_mesh`'s flaky vertex count (94 vs 96, once) — needs more data
  points before it's worth a real investigation; see project memory.

## 🗂️ Changed this session

- **Pivot:** [ROADMAP.md](ROADMAP.md) (new — the project's North Star:
  revised purpose, MeshTriage boundary, stack-ranked roadmap, patch policy,
  known gaps), Amendment 3 in the design spec (revises, doesn't reverse,
  "no source patching" — narrowly scoped to register-an-already-working-
  function patches), `docs/superpowers/plans/2026-09-16-phase5-mesh-uv-editing.md`
  (new, 7-task plan).
- **Build (Phase 5, via subagent-driven-development in worktree
  `worktree-phase5-mesh-uv-editing`):** `src/armorpaint_mcp/server.py` (7
  new tools + shared `_run_mesh_edit` helper), `src/armorpaint_mcp/catalog.py`
  (`mesh_edit_patch_missing`), `src/armorpaint_mcp/doctor.py` (new
  `--check` preflight item), 9 new integration test files, `tests/test_server.py`
  and `tests/test_catalog.py`/`tests/test_doctor.py` (new) extended,
  `tests/_mesh_edit_test_helpers.py` (new shared OBJ-diffing helpers),
  `smoke/smoke.ps1` (7 new probes), `STATUS.md`/`docs/PLAN.md`/`ROADMAP.md`/
  `README.md`/`CLAUDE.md` doc closeout.
- **Sibling repo:** `C:\Projects-local\z-Git\ArmorPaint` fast-forwarded
  16 commits, then switched to branch `spike/minic-decimate` (local commit
  `fbef46e7`, the mesh-edit patch — unpushed) — `paint\build\out\ArmorPaint.exe`
  (this project's `AP_BINARY` target) rebuilt from that branch. **This is a
  deliberate, flagged state change**, not an accident — `CLAUDE.md` now
  documents it. The checkout is no longer plain stock `main`.
- **Merged to `main` (`b461ff7`, real `--no-ff` merge commit) and pushed**
  — `origin/main` confirmed in sync. Worktree/branch removed after merge.
  `.env` created at both the worktree root (during the build) and the main
  repo root (during wrap-up verification) — neither existed before this
  session; past sessions must have set `AP_BINARY` as a raw process env var.
- **Decisions (+ why):** full detail in this session's log entry below —
  the MeshTriage-boundary call (triage vs. edit, not delegation), the
  scoped-patch-policy revision (narrow, not a blanket reopening of
  "no source patching"), and every ruling made during the SDD execution
  (worktree base, `.env` setup, the two parked final-review residuals).
- Memory: 4 new entries this session (`armorpaint-minic-mesh-edit-patching`,
  `armorpaint-bash-tool-silently-no-ops`, `armorpaint-smooth-mesh-flaky-vertex-count`,
  plus an update to the mesh-edit-patching entry with the full 7-function
  batch results).
- Commons log:
  `_agent-commons\log\2026-09-16-claude-code-armorpaint-mcp-meshuv-pivot.md`
  (written mid-session, before the Phase 5 build — covers the pivot/spike
  half only, not the full implementation; a future session reading it
  should also read this HANDOFF for the build half).

---

## 🕓 Session log

### 2026-09-16 — Phase 5: mesh/UV editing pivot, patch spike, 7-task build, merge + push
- Picked up with v1 + Minor-findings cleanup already shipped/merged/pushed.
  Grayson opened the session redirecting the project's priority: he's
  probably not using v1 as originally intended, and actually wants to
  automate mesh/UV fixes (fixing UVs, remeshing/decimating, non-destructive
  mesh updates) with materials/blockouts as a secondary want. Asked for a
  gap analysis, a stack-ranked roadmap, and a North Star doc.
- Surfaced (not silently assumed) that `Tool-MeshTriage` already does
  non-destructive poly reduction + UV auto-unwrap on Blender, but as an
  assessment/triage tool, not a live-project editor. Grayson clarified: he
  wants to actually EDIT inside ArmorPaint once a problem's identified, not
  delegate to MeshTriage — the two are complementary, not competing.
- Two background-agent spikes (real ArmorPaint checkout, PowerShell only —
  the Bash tool silently no-ops `ArmorPaint.exe` on this machine, cost ~8
  tool calls to diagnose once, saved to memory) confirmed: UV unwrap and
  remesh/decimate/etc. are GUI-button-only, not minic-registered — but
  ArmorPaint 1.0 genuinely shipped real mesh-editing tools that don't exist
  in older versions Grayson may have been thinking of.
- Grayson asked about ArmorPaint 1.0's forum release notes; investigating
  corrected an earlier false negative (my own and an agent's initial
  `decimat` grep both missed `util_mesh_decimate` — re-ran and found it).
  Fast-forwarded the ArmorPaint checkout 16 commits to current.
- Grayson approved a scoped local source patch (revising, not reversing,
  the project's "no source patching" decision) plus an eventual upstream
  PR to `armory3d/armorpaint` — his first open-source contribution.
  Classified as `superpowers:brainstorming`'s architectural path.
- Spiked the patch mechanism on `util_mesh_decimate` first (cheapest to
  verify: exact triangle-count diff): one-line `minic_api_list.h`
  registration, 16.4s incremental rebuild, genuinely mutated the mesh
  (96/188 → 56/108 → 20/36 vert/face across strength 0.1/0.5/0.9). Then
  batched the remaining 6: `smooth`/`bevel`/`subdivide`/`merge_geometry`/
  `duplicate`/UV-unwrap — all 6 patched and empirically verified (UV-unwrap
  turned out to be a real built-in algorithm, `proc_uv_unwrap`, not
  plugin-dependent despite its C function's misleading name); only
  `merge_geometry_down` (targeted 2-object merge) was a genuine dead end.
- Wrote [ROADMAP.md](ROADMAP.md) (North Star: revised purpose, MeshTriage
  boundary, 15-item stack-ranked roadmap, patch policy, known gaps) and
  Amendment 3 in the design spec, both reviewed and approved by Grayson
  before proceeding.
- Wrote a 7-task implementation plan
  (`docs/superpowers/plans/2026-09-16-phase5-mesh-uv-editing.md`) and
  executed it via `superpowers:subagent-driven-development` in worktree
  `worktree-phase5-mesh-uv-editing`: Task 1 rebuilt the real `AP_BINARY`
  target from the patch branch + added a `--check` preflight
  (`mesh_edit_patch_missing` in `catalog.py`, wired into `doctor.py`) so a
  stock binary fails loud instead of silently no-opping; Task 2 built the
  shared `_run_mesh_edit` helper (copy-by-default, `in_place` opt-out) +
  `decimate_mesh`; Tasks 3-4 added `bevel_mesh`/`subdivide_mesh` and
  `smooth_mesh`/`duplicate_mesh`; Task 5 added `merge_mesh_geometry` with a
  precondition guard (ArmorPaint silently no-ops merging <2 objects — this
  surfaces as a clear failure instead); Task 6 added `unwrap_mesh_uvs`;
  Task 7 closed out docs with a real fresh verification sweep. Every task
  reviewed clean (0 Critical/Important across all 7).
- **Controller error, self-caught:** the Task 1 dispatch omitted the
  patch-branch-already-committed premise's actual state (it was uncommitted
  working-tree state, not a real commit) — the implementer discovered and
  fixed it themselves, flagged clearly, no harm done. **Second controller
  error:** the final-review fix-wave dispatch omitted a "commit your work"
  instruction — implementer correctly did what was asked (no commit),
  caught by re-reading its report, resumed the same agent to commit rather
  than losing the fix or re-deriving context in a fresh dispatch.
- Final whole-branch review (opus) found 0 Critical, 4 cross-task Important
  findings invisible to any single task's review: `_run_mesh_edit` raised
  an uncaught `OSError` instead of the standard failure shape when
  `output_project` resolved to the same file as `project`; a stale
  *unedited* copy was left on disk when the minic script failed; the
  `ok=True`-proves-only-completion caveat was missing from 4 of 7
  docstrings; `CLAUDE.md`/`README.md` misstated the patched-binary
  situation (claimed stock `main`, didn't mention the unpushed patch
  dependency). One fix wave closed all four plus a 3-item doc-accuracy
  sweep; a scoped re-review confirmed every finding addressed, no new
  breakage, 2 non-load-bearing residuals parked with rulings (spec's own
  stale "6 of 7" count, `merge_mesh_geometry`'s missing general caveat).
- Merged to `main` (`b461ff7`, real `--no-ff` merge commit), re-verified on
  the actual merged tree (hit one flaky `smooth_mesh` integration-test
  failure on the first post-merge run, reran clean twice, root-caused to
  ArmorPaint's own algorithm rather than the merge — saved to memory),
  worktree and branch removed, pushed to `origin` on Grayson's explicit
  go-ahead (standing approval from earlier in the session, per this
  project's own wrap-up convention).

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
