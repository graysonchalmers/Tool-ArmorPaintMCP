# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-27 (late night CDT, wrap-up: Phase 6 executed + merged, Phase 7 approved + planned)_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

**Phase 6 is ✅ gate green and merged into `main` (`c23f437`, pushed).**
- It shipped `check_mesh_uvs` and `replace_mesh`, fixed Known Issues #10 and #11, made script errors fail tools, and made `--check` cover all 34 emitted minic names.
- Evidence on `main`: unit tests 230 passed; integration 38/38 across 15 files (two first-run flakes passed on rerun); smoke 15/15; `--check` green.
- Known Issue #12 (non-ASCII paths on ArmorPaint's command line) is mitigated with a pre-launch ASCII guard.

**Phase 7 is approved (`36262e1`), and its 16-task plan is committed (`ce03241`):** `docs/superpowers/plans/2026-09-27-phase7-c-changes-merge-pair.md`.
- Execution has started in worktree `.claude\worktrees\phase7` (branch `claude/phase7`, still equal to `main`).
- `AP_BINARY` is still built from `287e63f4` (#2148, not yet reviewed upstream).

## 📌 Where we stopped

Phase 7 SDD is at setup:
- The ledger and global constraints are in `.claude\worktrees\phase7\.superpowers\sdd\2026-09-27-phase7-c-changes-merge-pair\`.
- A background agent was writing the preflight conflict scan to `preflight-scan.md` in that folder. Check that it exists and is complete. If it doesn't exist, rerun the scan.
- No task has been dispatched.
- Grayson has **not yet given his go** for Tasks 5-8. Those are the ArmorPaint checkout branches for the 3 C changes, plus the `integration/ap-mcp` build of `AP_BINARY`.

## ▶️ Next concrete step

Resume SDD on the Phase 7 plan:
1. Rule on each preflight-scan finding and record the rulings in the ledger.
2. Dispatch Tasks 1-4. These are pure Python with no gate: the dependency registry and `--check` rows, the build-manifest writer, `merge_mesh_pair` tested against a mocked runner, and a GLB fixture with no UVs.
3. Ask Grayson for the Task 5-8 go-aheads in one message, quoting each task's HUMAN GATE line. Each yes covers only the action it names.

Alternatives:
- **Get the Task 5-8 go first, then run everything in order.** Waiting costs no work. Tasks 1-4 don't depend on the gates, so running them in the meantime is free.
- **Rebase the plan onto current upstream before any C work.** Upstream `main` is `eec04adf`, while the checkout's `origin/main` is stale at `85f6cf1c`. Task 5 already re-pins, so this is only needed if Grayson wants to review the drift first.

## ❓ Open questions

- **Task 5-8 go-aheads.** All four are pending with Grayson. The PR go-aheads (Tasks 14-16) come after Task 13 writes the PR texts.
- **#2148** is still open with no review.
- **Change 2 may have code-reading evidence only.** Setting a layer mask needs a fixture made in the GUI (optional Task 11).
- **Unproven until Task 9 runs:**
  - whether minic accepts `!=`;
  - whether merge-down keeps the kept object's material;
  - whether a child keeps its world pose when its parent is merged in.
- **Parked for later, not Phase 7 scope:**
  - `__wargv` (the real fix for Known Issue #12);
  - a non-ASCII `%TEMP%` breaks every script tool;
  - `armpack` string escaping;
  - splicing `atlas_objects` on delete;
  - Known Issue #8 (mesh edits re-unwrap every object's UVs);
  - Known Issue #9 (cold-start timeout).
- **Phase 6 deferred minors** (test naming, error-text polish, docstring history) are in `_to_delete\ArmorPaintMCP-sdd-phase6-2026-09-27\` → `progress.md`, if anyone wants them.

## 🗂️ Changed this session

- **Branches:**
  - `claude/phase6` (17 commits, `9070a14`..`be2b447`) merged into `main` as `c23f437`.
  - `main` also gained `36262e1` (Phase 7 approved) and `ce03241` (Phase 7 plan).
  - All pushed at wrap-up.
- **Decisions (+ why):**
  - Duplicate object names make `replace_mesh` fail closed. `script_get_object` and the Python lookup could otherwise pick different objects.
  - The size-ratio band became the named constant `SIZE_RATIO_WARN`, per the rule against uncited magic numbers.
  - The non-ASCII fix is a pre-launch guard only, with no log-line detection. The guard removes the trigger. The residual case, an ASCII path that fails to open mid-run, is recorded under Known Issue #12.
  - Phase 7 route (D3): one small upstream PR per C change, plus a local `integration/ap-mcp` build. `--check` trusts a git-derived build manifest bound to the binary's SHA-256, because changes 1 and 2 add no `--api` name.
- **Corrections:** PLAN.md had change 2's delete-path site wrong. `tab_meshes.c:128-134` is the reorder remap; the delete path is `:443-476`. Fixed in `ce03241`.

---
📜 Full session history: `handoff-log/` (one dated file per session, oldest to newest)
