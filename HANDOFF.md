# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-17 02:15 CT (wrap-up)_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

v1 (5 tools) + Phase 5 (7 mesh/UV editing tools) shipped, plus a new
**mesh/UV visual gallery** in [README.md](README.md) — before/after
wireframe renders for all 7 Phase 5 tools, built via Blender-headless
rendering of the tools' own OBJ exports (`scripts/_blender_render_obj.py`
+ `scripts/generate_mesh_gallery.py`). Merged to `main` (`e0467e4`) and
pushed. Upstream PR [#2139](https://github.com/armory3d/armorpaint/pull/2139)
(the mesh-edit minic patch) is still open, awaiting review, unchanged this
session.

Building the gallery surfaced a real correctness bug: `smooth_mesh` and
`decimate_mesh` (both Phase 5 tools, both marked ✅) don't reliably do
what their own docstrings/tests claim — see STATUS.md Known Issue #4. A
follow-up investigation (spawned mid-session, `spawn_task` →
`task_7ebcc65d`) already **root-caused it**: ArmorPaint's own C source
(`util_mesh_smooth`/`util_mesh_bevel`/`util_mesh_calc_normals`)
accumulates into uninitialized heap memory. That finding lives in a
**separate, still-unmerged worktree/branch**
(`claude/mystifying-banach-e42a6d`) — not part of this session's merge.
See project memory `armorpaint-smooth-mesh-flaky-vertex-count.md` for the
full writeup before touching any of `smooth_mesh`/`bevel_mesh`/
`decimate_mesh`.

## 📌 Where we stopped

Gallery work is fully shipped and this HANDOFF is the last thing written
this session. Nothing is mid-flight in this repo's `main`. The
`claude/mystifying-banach-e42a6d` worktree/branch (the root-cause
investigation) has NOT been reviewed or merged by this session — that's
someone else's next step, not a loose end of this one.

## ▶️ Next concrete step

**Review and merge (or explicitly decide not to) the root-cause
investigation's branch, `claude/mystifying-banach-e42a6d`.** It has real,
well-evidenced findings (STATUS.md/memory updates) sitting unmerged. At
minimum its documentation updates should land on `main`; whether to
actually write the heap zero-fill fix in ArmorPaint's C source is a
separate, bigger decision the memory file says needs Grayson's explicit
go-ahead first (see "Open questions").

Other options, still none urgent:
- **Wait for upstream review on #2139** — nothing to do until a
  maintainer responds; if it comes back with requested changes, amend
  `graysonchalmers/armorpaint:expose-util-mesh-uv-unwrap-to-minic`
  (mirrors local `spike/minic-decimate`, commit `2b528475`) and
  force-push, don't re-derive the patch.
- **ROADMAP.md items 8-10** — non-destructive mesh replace, targeted
  2-object merge, UV validity check. None scoped into a phase yet.
- **Delete the leftover worktree folder** at
  `.claude\worktrees\mesh-uv-visual-gallery` by hand (File Explorer) —
  git already unregistered it, the directory just wouldn't delete this
  session (`Device or resource busy`, no process found holding it).

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

- Branch: `main` (via merged `worktree-mesh-uv-visual-gallery`) · Files:
  `scripts/_blender_render_obj.py`, `scripts/generate_mesh_gallery.py`
  (new), 14 gallery PNGs, `README.md`/`STATUS.md`/`CLAUDE.md`/
  `.env.example` updates, plus the spec/plan docs.
- Decisions (+ why): Blender-headless over any ArmorPaint-native approach
  (ArmorPaint genuinely cannot render a mesh picture, verified against
  source, not assumed); Freestyle edge-marking over viewport overlay
  (the latter never reaches `--background` render output); a render-only
  object offset for `duplicate_mesh`/`merge_mesh_geometry` (never touches
  the real tool's tested zero-offset behavior); honest README captions for
  `unwrap_mesh_uvs` (structurally unfixable) and `smooth_mesh`/
  `decimate_mesh` (real tool bugs, not gallery bugs) instead of chasing
  fixes or hiding the gap; `BLENDER_BINARY` kept out of `config.py`'s
  `Config`/`AP_*` surface (dev tooling, not server runtime config).
  Full reasoning and every ruling: `handoff-log/2026-09-17-mesh-uv-visual-gallery.md`.
- Memory: `armorpaint-smooth-mesh-flaky-vertex-count.md` upgraded twice
  today (once by this session with repeatable-flake evidence, once by the
  spawned follow-up task with the full root cause).

---
📜 Full session history: `handoff-log/` (one dated file per session, oldest to newest)
