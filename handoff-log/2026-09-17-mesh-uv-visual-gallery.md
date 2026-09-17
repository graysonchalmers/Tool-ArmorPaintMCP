# 2026-09-17 — mesh/UV visual gallery: brainstorm, plan, build, ship

- Picked up clean (Phase 5 shipped, upstream PR #2139 still awaiting
  review, no drift). Grayson asked whether the 7 Phase 5 mesh/UV tools had
  ever been shown visually (before/after wireframe), not just verified
  numerically — they hadn't.
- Ran `superpowers:brainstorming` (architectural path). Checked
  ArmorPaint's own source before assuming a render capability existed:
  confirmed `--export-mesh` only exports geometry data, the only
  "wireframe" mention in the UI source is dead/commented-out code, and
  ArmorPaint's internal off-screen render path is hardcoded to icon/
  thumbnail use cases, not exposed to minic/CLI. Net: ArmorPaint cannot
  render a picture of a mesh at all in this build — Blender-headless
  rendering the existing OBJ exports is the real option, not a workaround.
  Grayson pushed back once ("why not just use ArmorPaint, we're already
  using it") — answered with the source investigation rather than
  reasserting the recommendation.
- Wrote and committed the design spec
  (`docs/superpowers/specs/2026-09-17-mesh-uv-visual-gallery-design.md`),
  corrected twice during planning after two real spikes: (1) the
  `merge_mesh_geometry` fixture claim was wrong (no multi-object fixture
  exists; the tool's own test builds one at runtime via `duplicate_mesh`),
  (2) the wireframe technique itself was wrong — viewport "wireframe
  overlay" never reaches `bpy.ops.render.render()`'s output and has no
  context to run against in `--background` mode; Freestyle edge rendering
  is the real headless technique, confirmed via a spike before writing it
  into the spec.
- Wrote the implementation plan
  (`docs/superpowers/plans/2026-09-17-mesh-uv-visual-gallery.md`, 3 tasks)
  and executed it via `superpowers:subagent-driven-development` in
  worktree `worktree-mesh-uv-visual-gallery` (native `EnterWorktree`;
  needed to cherry-pick the spec/plan commits onto the worktree branch
  since it forked from `origin/main`, not local `main`, which had those
  commits unpushed).
- Task 1 (`scripts/_blender_render_obj.py`) and Task 2
  (`scripts/generate_mesh_gallery.py`) both reviewed clean initially, but
  the controller personally re-inspecting the rendered images (ahead of
  Task 3) caught that `decimate_mesh`/`subdivide_mesh` looked visually
  identical before/after — Freestyle's default crease-angle detection
  misses edges between faces that stay coplanar, which is exactly what
  those two tools do on this fixture's mostly-flat cube. Verified the root
  cause AND the fix (mark every edge as a Freestyle edge explicitly) on a
  synthetic flat-grid test case before dispatching the real fix — two
  rounds (the fix itself, then a hardening round for a hardcoded lineset
  lookup and a missing try/finally), both re-reviewed clean.
- Task 3's implementer did its own rigorous pixel-diff (not eyeballing)
  and correctly reported BLOCKED: `duplicate_mesh`/`unwrap_mesh_uvs` were
  pixel-identical, `merge_mesh_geometry` near-identical. Root cause:
  `duplicate_mesh` places its copy at the source's exact transform (real,
  tested tool behavior), invisible to a plain camera. Fixed with a
  render-only object offset — which surfaced a genuine Blender gotcha
  (`matrix_world` doesn't refresh synchronously in `--background` mode
  after a location change) and required rewriting camera framing from a
  3D bounding-sphere radius to a camera-space projected bounding box.
  `unwrap_mesh_uvs` is structurally unfixable (UV-only change, invisible
  to any 3D wireframe) — captioned honestly instead of faked.
- **Bigger finding, from personally re-inspecting images again after the
  above fix:** the committed `smooth_mesh` sample was built from a
  genuinely degenerate tool run (vertex count 96→90, several vertices
  collapsed to near-zero coordinates) — a real correctness bug in a
  Phase 5 tool already marked ✅, not a gallery issue. Confirmed via 5
  repeated calls against the identical fixture (only 3/5 preserved vertex
  count). Surfaced to Grayson with two questions (gallery handling;
  whether to spin off an investigation); he chose a verified-clean sample
  + honest caption for the gallery. Logged as STATUS.md Known Issue #4,
  updated project memory, used `spawn_task` to flag a separate root-cause
  investigation (`task_7ebcc65d`) rather than scope-creep this plan.
- Final whole-branch review (opus) caught that `decimate_mesh`'s pair
  *also* didn't visually show its own effect (Task 3's own report had
  overstated what the image showed). Independently tried decimating a
  *subdivided* source first (378v/752f → 50v/96f, a real, large numeric
  reduction) to rule out "fixture too simple" — did NOT fix the visual
  mismatch, suggesting `decimate_mesh` may share `smooth_mesh`'s class of
  bug. Captioned honestly, folded into the same Known Issue #4 rather than
  opening a third issue. One fix wave closed this plus 5 Minors (inline
  script warnings, `AP_DOTENV` support, STATUS.md/CLAUDE.md pointers);
  scoped re-review clean.
- Merged to `main` (`e0467e4`, real merge commit), re-verified green (122
  passed, 18 deselected), pushed to `origin` on Grayson's go-ahead.
  Worktree/branch cleaned up (one leftover directory,
  `.claude\worktrees\mesh-uv-visual-gallery`, failed to delete — `Device
  or resource busy`, no process found holding it via `tasklist`; already
  unregistered from git via `worktree prune`, safe to delete by hand
  later).
- **Late-breaking, while wrapping up:** the spawned `task_7ebcc65d`
  reported back with a full root cause for the `smooth_mesh`/
  `decimate_mesh` flakiness, in its own separate, still-unmerged worktree
  (`claude/mystifying-banach-e42a6d`) — `util_mesh_smooth`/
  `util_mesh_bevel`/`util_mesh_calc_normals` in ArmorPaint's own C source
  accumulate into uninitialized heap memory (buffers from
  `realloc(NULL,...)`, never zero-filled). A real upstream ArmorPaint bug,
  not this project's minic-registration patch's fault. Also confirmed to
  affect `bevel_mesh`; possibly other tools via the shared
  `util_mesh_calc_normals` path (flagged, not yet verified). That
  session's own STATUS.md/memory updates are NOT part of this session's
  `main` merge — see project memory
  (`armorpaint-smooth-mesh-flaky-vertex-count.md`) for the full writeup.
  The memory file explicitly says not to write/build/upstream the actual
  fix without Grayson's go-ahead first (it's a real algorithm patch to
  ArmorPaint's C source, a bigger category of change than the existing
  registration-only patch policy).
