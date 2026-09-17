# 2026-09-16 — Phase 4 (`run_script` escape hatch + v1 polish)

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
  "none") and HANDOFF.md to reflect v1's tool surface being complete, and
  that Phase 4 was the last phase in the plan — no Phase 5 exists (yet).
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
  parked.
- Merged to `main` (`0c61b94`, real merge commit), re-verified green on the
  merged tree (88 unit, 6 integration, 6/6 smoke), removed the worktree and
  branch, pushed to `origin` on Grayson's go-ahead, confirmed `0  0` sync.
  Logged the session to `_agent-commons\log\` (Skills-Core repo).
