# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-27 18:10 CT (wrap-up)_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

v1 (5 tools) + Phase 5 (7 mesh/UV editing tools) shipped. The `smooth_mesh`/
`bevel_mesh` accumulator-corruption bug (STATUS.md Known Issues #4/#5) is
now **fixed**, not just root-caused: zero-init for `util_mesh_smooth`/
`util_mesh_bevel`/`util_mesh_calc_normals`'s accumulator arrays landed in
the ArmorPaint checkout, verified via a 10-run repro (4/10 and 8/10
corrupted pre-fix → 0/10 for both post-fix) plus a full regression sweep
(122 unit + 18 integration + 13/13 smoke, no regressions). The near-zero-
component scan that caught it is now permanent regression coverage in
`test_smooth_mesh_integration.py`/`test_bevel_mesh_integration.py`.

The ArmorPaint checkout (`C:\Projects-local\z-Git\ArmorPaint`) carries both
patches on one branch now: `spike/minic-decimate` at `e246089d` (fast-
forward-merged this session from the now-deleted `fix/mesh-accumulator-
zero-init`) — `2b528475` (registration-only, upstream PR #2139) and
`e246089d` (the algorithm fix) stay separately diffable for two future
PRs. A `gc-fork` remote (`graysonchalmers/armorpaint`) exists alongside
`origin` for that.

Upstream PR [#2139](https://github.com/armory3d/armorpaint/pull/2139) is
still open, awaiting review, unchanged.

## 📌 Where we stopped

`main` pushed and in sync with `origin/main` (confirmed `0  0`). Working
tree clean. Nothing mid-flight. The ArmorPaint checkout's `spike/minic-
decimate` is unpushed (no separate yes given yet for pushing that branch
anywhere — `origin` is upstream `armory3d/armorpaint`, `gc-fork` is
Grayson's own fork).

## ▶️ Next concrete step

**Decide on upstreaming.** Two independent options, neither urgent:
- Wait for upstream review on #2139 (registration-only patch) — nothing to
  do until a maintainer responds.
- Decide whether/when to open a second PR for the `e246089d` algorithm fix
  (zero-init), and whether it goes through `gc-fork` first or straight to
  `origin`.

Other open items, still none urgent:
- ROADMAP.md items 8-10 (non-destructive mesh replace, targeted 2-object
  merge, UV validity check) — none scoped into a phase yet.
- `.claude\worktrees\mesh-uv-visual-gallery` — still `Device or resource
  busy`, 4 sessions running now. `git worktree list` doesn't even see it
  anymore (unregistered), so `Clear-MergedWorktrees.ps1` silently no-ops on
  it. Probably needs a reboot or Sysinternals `handle.exe`, not another
  retry from inside a session.
- `origin/claude/mystifying-banach-e42a6d` on GitHub — merged locally weeks
  ago, never deleted on the remote (needs its own separate yes, still not
  given).

## ❓ Open questions

- Whether `util_mesh_calc_normals(true)`'s zero-init fix (which covers all
  4 of its call sites at once) fully retires the "does it corrupt normals
  elsewhere" question, or whether one of the other 3 call sites
  (`util_mesh.c:1100`, `1503`, `1633`) still deserves its own targeted
  verification — leaning toward "retired," not empirically re-checked
  against those specific tools' outputs this session.
- Whether `decimate_mesh`'s unrelated-looking gallery symptom (no visible
  change in a wireframe render despite a real numeric vertex/face drop)
  shares any root cause with #4/#5 — it doesn't call any of the three fixed
  functions, so probably not, still not empirically ruled out.
- Live mode (deferred, not rejected) — untouched, unchanged for weeks.
- The parked `_failure()` key-set assertion gap (2 of 10 call sites) —
  still open, unrelated, worth its own tiny task.
- Design spec's own Amendment 3 prose still says "6 of 7 functions
  patched" (cosmetic).
- `merge_mesh_geometry`'s docstring still has no general "ok=True proves
  only completion" caveat — one sentence, trivial whenever `server.py` is
  next open.

## 🗂️ Changed this session

- Branch: `main` · Pushed the two commits a 2026-09-23 Skills-Core session
  had deliberately left unpushed (`cdf3985` — the Known Issue #4/#5 fix
  itself, `bd8d2da` — `build_stamp.py` UTF-8/full-stamp fix, unrelated),
  plus this session's `HANDOFF.md`/`CLAUDE.md` update. `origin/main`
  confirmed in sync (`0  0`).
- ArmorPaint checkout: fast-forward-merged `fix/mesh-accumulator-zero-init`
  into `spike/minic-decimate` (`e246089d`), deleted the now-redundant
  branch. No rewrite — both commits still individually diffable.
- Decision (+ why): merged the two ArmorPaint branches into one rather than
  leaving them diverged, since the fix branch was a strict, one-commit-
  ahead descendant (trivial fast-forward) and a single coherent build
  branch is less error-prone going forward than two branch names pointing
  at nearly-the-same-but-not-quite state.

---
📜 Full session history: `handoff-log/` (one dated file per session, oldest to newest)
