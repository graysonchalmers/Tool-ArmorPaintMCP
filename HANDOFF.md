# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-17 (pickup — merged the root-cause branch)_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

v1 (5 tools) + Phase 5 (7 mesh/UV editing tools) shipped, plus the mesh/UV
visual gallery in [README.md](README.md) — before/after wireframe renders
for all 7 Phase 5 tools, built via Blender-headless rendering of the
tools' own OBJ exports (`scripts/_blender_render_obj.py` +
`scripts/generate_mesh_gallery.py`). Upstream PR
[#2139](https://github.com/armory3d/armorpaint/pull/2139) (the mesh-edit
minic patch) is still open, awaiting review, unchanged.

Building the gallery surfaced a real correctness bug: `smooth_mesh` and
`bevel_mesh` (both Phase 5 tools, both marked ✅) don't reliably do what
their own docstrings/tests claim — see STATUS.md Known Issues #4/#5. A
follow-up investigation (`superpowers:systematic-debugging` in worktree
`mystifying-banach-e42a6d`) **root-caused it**: ArmorPaint's own C source
(`util_mesh_smooth`/`util_mesh_bevel`/`util_mesh_calc_normals`)
accumulates into uninitialized heap memory, never zero-filled. That
investigation's branch has now been merged into `main` (this session,
resolving HANDOFF.md/STATUS.md conflicts by hand since the branch had
forked before the prior session's handoff-log migration). See project
memory `armorpaint-smooth-mesh-flaky-vertex-count.md` for the full
writeup before touching any of `smooth_mesh`/`bevel_mesh`/`decimate_mesh`.

No fix has been written, built, or upstreamed for the root cause — that's
explicitly a separate, bigger decision (real algorithm patch to
ArmorPaint's own C source, not this project's registration-only patch
policy) that needs Grayson's go-ahead first.

## 📌 Where we stopped

The root-cause branch (`claude/mystifying-banach-e42a6d`) is merged into
`main` locally; not yet pushed. Its old pre-handoff-log-migration session
history was not reproduced verbatim in this file (it predates the
migration and would have duplicated content) — its one new session entry
was written to `handoff-log/2026-09-17-smooth-mesh-rootcause.md` instead,
matching this project's established convention.

## ▶️ Next concrete step

**Push `main`** once the merge is verified (smoke/pytest still green —
only docs changed in the merge, no source). Then decide the two
still-open items below.

Other options, still none urgent:
- **Wait for upstream review on #2139** — nothing to do until a
  maintainer responds; if it comes back with requested changes, amend
  `graysonchalmers/armorpaint:expose-util-mesh-uv-unwrap-to-minic`
  (mirrors local `spike/minic-decimate`, commit `2b528475`) and
  force-push, don't re-derive the patch.
- **ROADMAP.md items 8-10** — non-destructive mesh replace, targeted
  2-object merge, UV validity check. None scoped into a phase yet.
- **Delete the leftover worktree folders** at
  `.claude\worktrees\mesh-uv-visual-gallery` (git already unregistered it,
  directory itself wouldn't delete, `Device or resource busy`) and
  `.claude\worktrees\mystifying-banach-e42a6d` (now merged, safe to
  `git worktree remove` and delete the branch) by hand.

## ❓ Open questions

- Whether/when to write the actual `util_mesh_smooth`/`util_mesh_bevel`
  zero-fill fix in ArmorPaint's C source — explicitly Grayson's call per
  the root-cause memory file, not something to do proactively. A real
  algorithm patch, a bigger category of change than this project's
  existing registration-only patch policy.
- Whether `util_mesh_calc_normals(true)`'s shared bug also corrupts
  *normals* (not positions) in other patched tools that call it
  (`util_mesh.c:1100`, `1503`, `1633`) — flagged in memory, not yet
  empirically confirmed against those tools' own outputs.
- Whether `decimate_mesh`'s unrelated-looking gallery symptom (no visible
  change in a wireframe render despite a real numeric vertex/face drop)
  shares this root cause — `decimate_mesh` doesn't call any of the three
  named functions, so probably not, but not empirically ruled out either.
- Upstream review timeline for #2139 — still unknown, no maintainer
  response yet.
- Live mode (deferred, not rejected) — untouched, unchanged for weeks.
- The parked `_failure()` key-set assertion gap (2 of 10 call sites) —
  still open, unrelated to anything recent. Worth its own tiny task.
- Design spec's own Amendment 3 prose still says "6 of 7 functions
  patched" (cosmetic, ROADMAP.md's own copy was corrected already).
- `merge_mesh_geometry`'s docstring still has no general "ok=True proves
  only completion" caveat (only its precondition-guard-specific one) —
  one sentence, trivial whenever `server.py` is next open.

## 🗂️ Changed this session

- Merged `claude/mystifying-banach-e42a6d` into `main` (`--no-ff`),
  resolving conflicts in `HANDOFF.md`/`STATUS.md` by hand: kept the
  branch's full root-cause writeup for Known Issues #4/#5, folded in the
  prior session's `decimate_mesh` observation as a caveat rather than
  losing it, and wrote the branch's stranded session-log entry to
  `handoff-log/2026-09-17-smooth-mesh-rootcause.md` instead of
  reproducing its pre-migration inline history verbatim.
- Decision (+ why): did not write/build/upstream the C-source fix — that
  remains explicitly Grayson's call, unchanged from the branch's own
  scoping.

---
📜 Full session history: `handoff-log/` (one dated file per session, oldest to newest)
