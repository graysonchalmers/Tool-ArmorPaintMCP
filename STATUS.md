# 🧭 Status — Tool-ArmorPaintMCP

_Last updated: 2026-10-25 · split; history archived_

> Truth ledger (per `CLAUDE.md`): three states only. ✅ verified (gate evidence exists) · 🔌 wired (code, no gate) · ⬜ not started. Never mark ✅ without recorded evidence.
> Full pre-split text (per-phase file tables, long evidence, closed-issue write-ups, deviations): `handoff-log/archive/STATUS-snapshot-2026-10-25.md`. Facts below were carried over from it and HANDOFF.md (last dated 2026-09-27) and were NOT re-verified on 2026-10-25.

## 🎯 Current state

**Phase 6 gate green, 2026-09-27; merged to `main` as `c23f437`.** Phase 7 (3 upstream ArmorPaint C changes + item 9 targeted merge, `merge_mesh_pair`) approved 2026-09-27 (`36262e1`); 16-task plan committed (`ce03241`): `docs/superpowers/plans/2026-09-27-phase7-c-changes-merge-pair.md`. Execution was at setup (worktree `.claude\worktrees\phase7`, branch `claude/phase7`); no task dispatched as of 2026-09-27.

### Phase gates (all ✅)

| Phase | Scope | Gate date | Key evidence |
|---|---|---|---|
| 0 | Scaffold + smoke harness | 2026-09-15 | `smoke/smoke.ps1` 3/3 |
| 1 | `reexport_project` (native export flags) | 2026-09-15 | integration: 5 real PNGs from `tests/fixtures/sample_project.arm` |
| 2 | `create_procedural_material` (single-process build+fill+export) | 2026-09-15 | pytest 53 passed; gallery `docs/images/gallery/procedural_checker_base.png` visually confirmed |
| 3 | `inspect_project` + dynamic catalog | 2026-09-16 | pytest 76 passed, integration 4, smoke 5/5; review fix wave closed 2 Critical (blend-mode enum mismatch, bogus path false `ok`) |
| 4 | `run_script` escape hatch + packaging polish | 2026-09-16 | pytest 88, integration 6, smoke 6/6; clean-clone check OK |
| Cleanup | Post-Phase-4 minor findings pass | 2026-09-16 | pytest 95, integration 9, smoke 6/6 |
| 5 | 7 mesh/UV tools: decimate/bevel/subdivide/smooth/duplicate/merge_geometry/unwrap_mesh_uvs (scoped minic patch) | 2026-09-16 | pytest 118, integration 18, smoke 13/13; each tool checked by independent `script_export_mesh` OBJ diff |
| 6 | Rename hardening, `check_mesh_uvs`, `replace_mesh`, Known Issues #10/#11 fixed | 2026-09-27 | final: `pytest -q` 230 passed (38 deselected); integration 38/38 across 15 files, run file-by-file serially (two first-run timeouts passed on rerun, see #9); smoke 15/15; `ap-mcp --check` green ("all 34 minic functions registered") |

Tools shipped (all ✅): `reexport_project`, `create_procedural_material`, `inspect_project`, `run_script`, `decimate_mesh`, `bevel_mesh`, `subdivide_mesh`, `smooth_mesh`, `duplicate_mesh`, `merge_mesh_geometry`, `unwrap_mesh_uvs`, `check_mesh_uvs`, `replace_mesh`. Every tool returns `ok=False` on a script-error stdout line, nonzero exit or timeout. `--check` diffs every emitted minic name against the binary.

### How to run / gate (see CLAUDE.md Commands)

- Setup preflight `ap-mcp --check`; server `ap-mcp` (stdio); smoke `pwsh smoke/smoke.ps1` (must exit 0); tests `.venv\Scripts\python.exe -m pytest -q`, integration `-m integration` (run file-by-file, serially, one ArmorPaint process at a time).
- `AP_BINARY` is built from the ArmorPaint checkout `C:\Projects-local\z-Git\ArmorPaint`, branch `fix/mesh-accumulator-zero-init` @ `287e63f4` (= upstream `main` `85f6cf1c` + zero-init fix), built 2026-09-27. Changing that checkout counts as outside this project: ask Grayson first.
- Upstream: registrations merged as armory3d/armorpaint#2139 (2026-09-17); zero-init fix open as [#2148](https://github.com/armory3d/armorpaint/pull/2148) (no review as of 2026-09-27). Fork remote `gc-fork` (`git@github.com:graysonchalmers/armorpaint.git`). Upstream `main` was `eec04adf` on 2026-09-27; the checkout's `origin/main` was stale at `85f6cf1c`.
- Build for old binaries: this project no longer runs `unwrap_mesh_uvs` against pre-`01bae6c5` builds (minic name is now `util_mesh_uv_unwrap`).

### Standing traps

- Out of scope by structure: mesh-detail baking and texture-set swap are unreachable from CLI/minic (Known Issue #1, closed). Live/GUI mode is deferred, not rejected.
- Windows `ArmorPaint.exe` stdout/stderr capture works on the current build (upstream `3b77ab8c`); the Phase 4 note that they are structurally empty is superseded.
- `run_script`'s `AP_ALLOWED_ROOTS` only bounds `project`, not the script body; minic `project_save()` can overwrite the project in place.
- Mutating tools default to a COPY at `output_project`; only `in_place=True` touches the caller's file.
- `layer_blend_modes()` is a hardcoded 18-name enum (deliberate deviation from the dynamic-catalog rule; no dynamic source exists).
- `run_script` takes inline script text, not `script_path` (deliberate deviation from the design spec).
- Phase 3+ gate rule: never start Phase N+1 until Phase N's gate is green and recorded here.

### Known issues still open or mitigated

| # | State | Summary / plan |
|---|---|---|
| 8 | OPEN (source-read, not reproduced) | `decimate`/`smooth`/`bevel`/`subdivide_mesh` each end in upstream `util_mesh_uv_unwrap()`, which re-atlases every object's UVs, so existing paint is likely scrambled on all objects. No docstring warns. Next: reproduce on a painted multi-object fixture, add a docstring warning; skip-unwrap option upstream is a Phase 7/D3 candidate. |
| 9 | OPEN | Cold-start: first ArmorPaint call of a session can exceed the 30 s default `timeout_s` (later calls 1.2-4 s). Candidates: longer default or warm-up in `--check`. Spike agents pass `timeout_s=120`. |
| 12 | MITIGATED (`24dded1`) | Non-ASCII argv paths corrupt on the Windows build (ANSI argv decoded as UTF-8) and yield false default-scene `ok=True`. `server._argv_path_error` rejects such paths pre-launch. Real fix needs ArmorPaint to read `__wargv` (parked). Residual: an ASCII path that vanishes mid-run. |

Closed (details in the snapshot): #1 baking/texture-swap out of scope; #2, #3 moot; #4/#5 accumulator zero-init (`e246089d`, upstream PR #2148, bevel/smooth now have near-zero-vertex regression scans); #6 rename to `util_mesh_uv_unwrap`; #7 decimate gallery "no change" is a fixture-scale effect, not a bug; #10 backslash JSON (`3743093`); #11 cross-directory asset paths (`d9b9964`).

## 📌 Where we stopped

2026-09-27 late: Phase 6 merged and pushed. Phase 7 SDD at setup: ledger and global constraints in `.claude\worktrees\phase7\.superpowers\sdd\2026-09-27-phase7-c-changes-merge-pair\`; a background agent was writing `preflight-scan.md` there (check it exists and is complete, else rerun). No task dispatched. Grayson has NOT given his go for Tasks 5-8 (ArmorPaint checkout branches for the 3 C changes plus the `integration/ap-mcp` build of `AP_BINARY`). No newer activity is recorded in this file; check `git log` and HANDOFF.md before assuming this is current.

## ▶️ Next concrete step

Resume SDD on the Phase 7 plan: (1) rule on each preflight-scan finding and record in the ledger; (2) dispatch Tasks 1-4 (pure Python, no gate: dependency registry + `--check` rows, build-manifest writer, `merge_mesh_pair` against a mocked runner, GLB fixture with no UVs); (3) ask Grayson for the Task 5-8 go-aheads in one message quoting each task's HUMAN GATE line (each yes covers only its named action). PR go-aheads (Tasks 14-16) come after Task 13 writes the PR texts. Optional first: rebase the plan onto current upstream if Grayson wants to review the drift.

## ❓ Open questions

- Task 5-8 go-aheads (all four pending with Grayson).
- #2148 still open, no review as of 2026-09-27.
- Change 2 may rest on code-reading evidence only; a layer-mask fixture needs the GUI (optional Task 11).
- Unproven until Task 9: whether minic accepts `!=`; whether merge-down keeps the kept object's material; whether a child keeps its world pose when its parent is merged in.
- Parked, not Phase 7: `__wargv`; non-ASCII `%TEMP%` breaks every script tool; `armpack` string escaping (a quote in a name is a documented hazard); splicing `atlas_objects` on delete; Known Issues #8, #9.
- Phase 6 deferred minors (test naming, error text, docstring history): `_to_delete\ArmorPaintMCP-sdd-phase6-2026-09-27\progress.md`.

## 🗂️ Changed this session

- Split oversized STATUS.md; full prior text in handoff-log/archive/STATUS-snapshot-2026-10-25.md

---
📜 History: handoff-log/ (archive/ holds the pre-split snapshot)
