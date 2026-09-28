# 2026-09-27 — Phase 6 executed and merged; Phase 7 approved and planned

## What happened
- **Pickup.** Resumed Phase 6 SDD at Task 1 fix round 1. The original review text hadn't been saved, so I reconstructed the findings from the ledger's rulings.
- **Tasks 1-11.** Ran them subagent-driven: sonnet implementers and sonnet/opus reviewers, each task reviewed before the next. Fix rounds:
  - Task 1: stdout/stderr kept on failure; stale test rewritten.
  - Task 8: post-verify exceptions could escape the tool.
  - Task 9: bare size-band literal became the `SIZE_RATIO_WARN` constant.
- **Task 10 calibration on real ArmorPaint.** Every row matched the S3 expectations, including `r4_extrude` rejected on the zero-area rule at 4.14%. No threshold moved.
- **Final whole-branch review (opus).** It found a Critical bug by tracing ArmorPaint source:
  - ArmorPaint reads its command-line arguments as ANSI on Windows (`windows_system.c:860`).
  - A non-ASCII project path therefore fails to open (`import_arm.c:538-542`), and ArmorPaint keeps its default scene loaded.
  - Our script's UTF-8 `project_filepath_set` still saves, so mesh edits returned `ok=True` holding the default scene. With `in_place=True`, that overwrote the user's project.
  - This was a regression against the pre-Phase-6 copy-then-save flow.
  - **Reproduced on the real binary before the fix:** `ok=True`, 1 object where there should have been 3.
- **Final fix wave:**
  - `24dded1`: pre-launch ASCII guard on every path ArmorPaint receives on its command line, including `reexport_project`.
  - `2436495`: malformed OBJs never raise; `check_mesh_uvs` fails on an empty export; retention-None warning.
  - `c13d438`: docs.
  - `be2b447`: Known Issue #12 rewritten as mitigated.
  - A scoped re-review addressed all findings.
- **Merge.** Grayson chose "both, merge first". `claude/phase6` merged into `main` as `c23f437`. The one conflict, in STATUS.md's header, went to the newer text. Unit 230 and smoke 15/15 pass on the merged result.
- **Phase 7.** Marked approved (`36262e1`), with `__wargv` logged as an upstream candidate. An opus subagent drafted the 16-task plan, which I reviewed and committed (`ce03241`). I verified its claim that PLAN.md's change-2 citation was wrong and corrected PLAN.md.
- **Phase 7 setup.** Created worktree `phase7`, the SDD ledger and the global-constraints file. Started a background preflight scan. No tasks dispatched; Grayson's Task 5-8 go-aheads were requested, not given.

## Decisions (+ why)
- **Keep stdout/stderr on `run_script` failures.** The error lines exist so callers can read them.
- **`replace_mesh` fails closed on duplicate object names and on malformed state.** The binding rule is that a tool never raises and never mis-restores data.
- **A guard, not log detection, for non-ASCII paths.** YAGNI: the guard removes the trigger.
- **Reproduce a source-traced Critical before fixing it.** STATUS.md records only evidenced claims.
- **Phase 6 scratch workspace moved to `_to_delete\` rather than deleted.** Rule 1 of the root CLAUDE.md is never delete.

## Ruled out
- Detecting ArmorPaint's "Could not open file" log line (see above).
- Deleting the `phase6` worktree before the push. `Clear-MergedWorktrees` requires the branch to be merged into `origin/main` first.

## Files touched
`src/armorpaint_mcp/{server,runner,catalog,doctor,script_gen,uv_analysis,replace}.py`, many `tests/*`, `tests/fixtures/phase6/*`, `scripts/calibrate_uv_gate.py`, `smoke/smoke.ps1`, `README.md`, `STATUS.md`, `ROADMAP.md`, `docs/PLAN.md`, the Phase 7 plan, and `HANDOFF.md`.
