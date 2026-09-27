# 2026-09-27: Phase 6 grill, spikes, plan, and Task 1

- **Pickup options chosen: 1, 3 and 4.**
  - Retired the `pickup-4c87f9` worktree.
  - Ran a background subagent on the decimate gallery symptom.
- **Decimate verdict: not a bug (Known Issue #7).**
  - Grid clustering (0.067-unit cells) collapses only the fixture's 0.03-unit bevel strips.
    That change is about 4.5 px at gallery framing. A 6x close-up shows it.
  - The save and export are byte-consistent, and the "after" image isn't stale.
  - Side finding: decimate does call `util_mesh_calc_normals(true)`.
- **Grill: 12 questions, D1-D5 answered.** Decisions are in `docs/PLAN.md` "Decisions
  applied". The advisor flagged Q3 vs Q6 (the no-UV reject can only be checked on OBJ),
  so the rule is split by format.
- **Grayson approved Phase 6.**
- **Advisor catches:**
  - Hash-based completion sentinel → fresh-path save instead, since a re-save keeps the md5.
  - Known Issue #8: decimate, smooth, bevel and subdivide call `util_mesh_uv_unwrap()` →
    likely paint scramble.
  - Known Issue #9: cold-start timeout.
- **Spikes.**
  - **Agent A (ArmorPaint, run serially), S1/S5/S4/S2.**
    - 12 contradictions to the plan.
    - Stdout is capturable (upstream `3b77ab8c`).
    - `inspect_project` breaks on backslash paths (Known Issue #10; I reproduced it).
    - The `copy2` staging breaks relative asset paths (Known Issue #11).
    - `WITH_PLUGINS` enables FBX/GLB; Blender FBX lands at 100x.
    - `.blend` silently no-ops unless ArmorPaint's config has a Blender path.
    - Carry-over needs parent + children + a pre-rename; append needs backslashes.
  - **Agent B (S3, Blender only).**
    - IoU alone passes island swaps and mirrors (sphere mirror scores 1.0000), so a
      texel-retention signal was added.
    - N=256. The rasterizer is pure stdlib and fast enough.
    - Smart UV Project is nondeterministic, so the fixtures are committed.
- **Grayson's calls after the spikes:**
  - Retention signal: yes.
  - Zero-area rule: 3D-area share over 0.1% errors.
  - FBX: accept with a size warning.
  - Fix Known Issues #10 and #11 inside Phase 6.1.
- **Harness gotcha:** the harness blocks subagents from writing FINDINGS/report files,
  so I saved them from the hand-back text. Copies are in `docs/superpowers/spikes/`.
- **Plan.** Wrote the 11-task plan; the advisor review added:
  - a RED-first test for Known Issue #11;
  - ordered success checks;
  - stripping string literals in the registry test;
  - a pinned mesh_datas rename test;
  - a real-ArmorPaint calibration task.
  - Dropped the `.blend` config pre-check: `config.c:52-57` puts the config in AppData
    when the exe is under a protected path.
- **Execution (subagent-driven).**
  - Task 1 landed as `9070a14`; unit 126 passed, integration 2/2.
  - Review found 2 Important issues:
    - `run_script` nulls stdout on failure;
    - a stale integration test asserts the old silent behavior.
  - Rulings are in the ledger.
  - Fix round 1 was interrupted by the session ending, with no changes.
- **Environment.** The machine ran out of commit memory: 2.6 GB free with 37
  `claude.exe` processes. ArmorPaint crashed with 0xC0000005 and bash failed to fork.
  The stale-only node reaper freed nothing, and the push notification went nowhere
  because mobile push is disabled.
