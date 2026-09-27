# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-27 (late evening CDT, wrap-up: Phase 6 grill → spikes → plan → Task 1)_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

v1 (5 tools) and Phase 5 (7 mesh/UV tools) are green on `AP_BINARY` @ `287e63f4`
(upstream `85f6cf1c` + the zero-init fix, open upstream as armory3d/armorpaint#2148,
still unreviewed). **Phase 6 is approved and in execution** on branch
`claude/phase6` in worktree `.claude\worktrees\phase6`:
- Scope: rename hardening (stdout abort detection, `--check` covering every emitted
  minic name) + Known Issues #10/#11 fixes, then `check_mesh_uvs` and `replace_mesh`.
- Design: `docs/PLAN.md` "Phase 6 → Decisions applied", amended from spikes S1-S5.
- Implementation plan: `docs/superpowers/plans/2026-09-27-phase6-hardening-uv-replace.md`
  (11 tasks, on the branch).
- Spike evidence: `docs/superpowers/spikes/`. Fixtures: `tests/fixtures/phase6/`
  (MD5-pinned; the `uv/` set can't be regenerated).
- Phase 7 (3 upstream C changes + targeted merge) is drafted, not approved.

## 📌 Where we stopped

Subagent-driven execution, **Task 1 of 11**:
- Implemented and committed: `9070a14`. Minic `<script>:N: error:` lines now fail
  `run_minic_script`.
- Review approved it with 2 Important findings.
- Fix round 1 was dispatched, then interrupted when the session ended. No changes
  landed; the worktree is clean.
- The SDD ledger (git-ignored) is at
  `.claude\worktrees\phase6\.superpowers\sdd\2026-09-27-phase6-hardening-uv-replace\progress.md`.
  It holds the preflight scan, 5 rulings, 2 deferred minors, and the fix-round note.

## ▶️ Next concrete step

Resume SDD at **Task 1 fix round 1**. Dispatch a fresh implementer with the brief
`task-1-brief.md`, the report `task-1-report.md`, and the two findings from the ledger:
1. `run_script` keeps stdout/stderr on runner failures.
2. Rewrite the stale `test_run_script_ok_true_does_not_prove_the_script_succeeded`
   so it pins the early-`return` caveat.

Then run the scoped re-review and continue with Task 2. The env recipe is in the
plan's Global Constraints (`PYTHONPATH=<worktree>\src`, `AP_DOTENV` → main's `.env`).

Alternatives:
- **Free memory first.** The machine was at 2.6 GB free commit with 37 `claude.exe`
  processes; ArmorPaint launches and bash forks were crashing. Closing idle sessions
  makes every integration run faster and more reliable.
- **Execute inline instead of via subagents.** Tasks 1-4 took ~1 h per subagent under
  memory pressure. Inline execution saves the review seats but loses per-task
  review, which the plan's size argues for keeping.

## ❓ Open questions

- **#2148:** still open with no review. When it merges, rebuild `AP_BINARY` from plain
  upstream and retire the local fix branch.
- **Known Issue #8 (open, source-read):** decimate, smooth, bevel and subdivide all call
  `util_mesh_uv_unwrap()`, which likely scrambles paint on every object.
  - Needs a repro on a painted multi-object project, plus a docstring warning.
  - An upstream "skip re-unwrap" option would be a Phase 7 candidate.
- **Known Issue #9 (open):** a cold-start first call can exceed the 30 s default
  timeout.
- **Zero-area rule consequence:** a Blender extrude round-trip (4.1% of the surface in
  zero-UV-area faces) will fail `replace_mesh`. Revisit when Task 10 recalibrates on
  real ArmorPaint.
- **Parked small items:**
  - the `_failure()` key-set assertion gap;
  - spec Amendment 3's "6 of 7" prose;
  - optional decimate follow-ups (corner close-up gallery render, normals assertion).
- **Live mode:** still deferred.

## 🗂️ Changed this session

- **Branches:** `main` has `e1163ae` and `7082646` plus this wrap-up commit. `claude/phase6`
  adds `77fca31` (fixtures + prototypes), `0ddccec` (plan) and `9070a14` (Task 1).
- **Grill decisions (+ why):** all recorded in `docs/PLAN.md`.
  - Item 8 supports both `round_trip` and `swap`, because both workflows are real.
  - The UV match uses IoU **plus texel retention**. S3 showed IoU alone passes
    island swaps and mirrors.
  - All native formats are accepted, with an FBX size warning (Blender FBX lands at 100x).
  - Verify-then-commit via "open original, save fresh sibling, `os.replace`". It also fixes
    Known Issue #11's broken relative asset paths.
  - D3: upstream-first with a local integration bridge. This is not standing approval
    for PRs.
  - D2: a `script_object_merge` wrapper, not the one-liner. The maintainer is moving
    away from exposing raw `mesh_object_t` pointers to scripts.
  - Split: Phase 6 needs no C changes; Phase 7 holds all the C work.
- **Spike findings (overturned assumptions):**
  - Stdout **is** pipe-capturable since upstream `3b77ab8c`.
  - The `--api` JSON has unescaped backslashes, so the shipped `inspect_project` fails
    on real Windows projects (Known Issue #10, reproduced).
  - `WITH_PLUGINS` means fbx/glb/gltf import natively; S3's "no FBX" was wrong.
  - `script_append_mesh` needs doubled backslashes.
  - `project_save` must be a script's last statement.
- **Decimate gallery symptom:** closed as Known Issue #7. It's a fixture-scale effect:
  only the 0.03-unit bevel strips collapse. The "doesn't call the fixed functions" claim
  was wrong.
- **Housekeeping:** retired the `pickup-4c87f9` worktree. Memory got a new
  append/--api gotchas note, and the stdout note was superseded.

---
📜 Full session history: `handoff-log/` (one dated file per session, oldest to newest)
