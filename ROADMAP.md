# 🧭 ROADMAP — Tool-ArmorPaintMCP

> North star, feature path, gaps, open questions. The living compass — update this,
> don't let it drift the way a one-time spec can. Companion to
> [docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md)
> (the original architecture decisions, still valid) and its
> [Amendment 3](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md#amendment-3-scoped-patch-policy-for-meshuv-2026-09-16)
> (the patch-policy revision this doc exists because of).

**Last updated:** 2026-09-27 (#2139 merged upstream; zero-init PR drafted)

---

## North Star

**Tool-ArmorPaintMCP is becoming a headless mesh/UV editing backend, driven from
ArmorPaint's own C source via a small, scoped, empirically-verified patch to its
scripting engine — not just a batch texture/material exporter.**

v1 shipped a working batch-export/rebake/inspect tool surface against ArmorPaint's
*stock* binary, on the explicit decision not to patch ArmorPaint's source. That
decision held because v1's scope was fully covered by what ArmorPaint already
exposed. It no longer holds for the current priority: Grayson's actual use case is
automating mesh fixes (poly reduction, UV unwrapping, smoothing/beveling/
subdividing) and non-destructive mesh updates — and ArmorPaint 1.0 ships real,
working GUI tools for exactly this, none of them wired to `--script`. A same-session
spike proved the gap is closable with a one-line-per-function patch, not a rewrite:
see "Patch policy" below.

**Priority order, confirmed 2026-09-16:**
1. Mesh/UV automation (new primary focus) — decimate, subdivide, bevel, smooth,
   duplicate, merge, UV unwrap, eventually non-destructive mesh replace.
2. v1's existing texture/material batch tooling — **kept as-is**, not deprioritized
   in the sense of being removed or unmaintained, just no longer where new work goes.
3. Materials/blockout authoring — secondary want, already served adequately by v1's
   `create_procedural_material`.

## Where this sits relative to sibling tools

**Tool-MeshTriage** (`C:\Projects-local\Tool-MeshTriage`) already does non-destructive
poly reduction + UV auto-unwrap-or-delegate, on Blender headless. It is an
**assessment/triage** tool: ingest an asset, score it, fix it only when the fix
measurably clears a quality bar, otherwise hand a human a precise brief. It does not
edit projects Grayson is actively authoring in ArmorPaint.

**Tool-ArmorPaintMCP's mesh/UV role is different and complementary, not
competing:** it's the **editor**, acting directly on live `.arm` projects, once a
problem is identified (by MeshTriage, by Grayson, or by inspection) — a "make this
specific change to this specific project" tool, not a "score and decide" tool. The
two don't call each other today; this project does not delegate mesh/UV work to
MeshTriage, and MeshTriage's scope is unaffected by this pivot.

## Feature roadmap (stack-ranked)

| # | Item | Status |
|---|---|---|
| 1 | `unwrap_mesh_uvs` | ✅ shipped (Phase 5) |
| 2 | `decimate_mesh` | ✅ shipped (Phase 5) |
| 3 | `subdivide_mesh` | ✅ shipped (Phase 5) |
| 4 | `bevel_mesh` | ✅ shipped (Phase 5) |
| 5 | `smooth_mesh` | ✅ shipped (Phase 5) |
| 6 | `duplicate_mesh` | ✅ shipped (Phase 5) |
| 7 | `merge_mesh_geometry` | ✅ shipped (Phase 5) |
| 8 | Non-destructive mesh replace/swap | ✅ shipped (Phase 6) — `replace_mesh`, composes with no patch as `script_append_mesh` + `script_object_remove` (`c0df922d`). D4 answered 2026-09-27: `round_trip`/`swap` modes, UV-IoU gate, all formats, verify-then-commit, name/transform/material carried over |
| 9 | Targeted 2-object merge (`merge_geometry_down`'s real use case) | ⬜ decided, not approved (Phase 7) — D2 answered 2026-09-27: upstream-first `script_object_merge(object_t*, object_t*)` wrapper in the maintainer's `c0df922d` shape; no `->ext` spike |
| 10 | UV validity check (1.0 changelog item) | ✅ shipped (Phase 6) — `check_mesh_uvs`; upstream's check (`b62fd323`) isn't script-reachable; read-only Python check over `script_export_mesh`, tiered errors/warnings, `allow_udim` escape hatch, no patch |
| 11 | `inspect_project` | ✅ shipped (v1, Phase 3) |
| 12 | `reexport_project` | ✅ shipped (v1, Phase 1) |
| 13 | `create_procedural_material` | ✅ shipped (v1, Phase 2) — covers the materials/blockout secondary want |
| 14 | `run_script` | ✅ shipped (v1, Phase 4) — escape hatch, stays useful regardless of new tools |
| 15 | `list_available_presets` | ✅ shipped (v1, Phase 1/2) |

Items 1-7 shipped as Phase 5 (2026-09-16, see docs/PLAN.md and STATUS.md) — every
one of them was already empirically de-risked going in, unlike the rest of v1's
phases, which each needed their own hands-on investigation before implementation
could start. Items 8-10 are scoped into a **draft** Phase 6 in docs/PLAN.md
(2026-09-27, source-read only, not approved). It found item 8 composes today
with no patch (`script_append_mesh` + `script_object_remove`), and item 9's
"no accessor" blocker was wrong (`object_t.ext` is reachable from minic). Item
10 is best done Python-side on `script_export_mesh`.

## Patch policy

**Current default (D3, 2026-09-27): upstream-first, bridged locally.** Every
ArmorPaint C change (registration or small fix) goes upstream as one small,
single-purpose PR. The same commit is stacked on a local integration branch
(upstream `main` + every open PR), which `AP_BINARY` builds from, so tools
don't wait on review. When a PR merges, rebuild and drop it from the stack.
The local-patch policy below is now the **fallback** for changes upstream
declines. This is a default route, not standing approval: each PR and each
change to the ArmorPaint checkout still needs Grayson's explicit go. Queued
for Phase 7: `texa` zero-init, object-mask remap on delete, and
`script_object_merge` (docs/PLAN.md).

**Decision (2026-09-16, supersedes part of the original spec — see Amendment 3):**
a small, scoped local patch to `paint\sources\minic_api_list.h` in the ArmorPaint
checkout (`C:\Projects-local\z-Git\ArmorPaint`) is the accepted path for exposing
GUI-only mesh/UV functions to `--script`, **for this specific class of gap only**
(a function that already exists, already works, and just isn't registered). This
does not reopen source-patching for anything else — rebake/texture-swap remain
exactly as blocked and out-of-scope as Phase 2 found them; that finding is
unaffected.

**Exception, 2026-09-17 (Grayson's explicit go-ahead):** one algorithm fix to
`util_mesh.c` — zero-initializing the accumulator arrays in
`util_mesh_smooth`/`util_mesh_bevel`/`util_mesh_calc_normals` that were reading
uninitialized heap memory (STATUS.md Known Issues #4/#5). This is a real change
to an existing function's body, not a registration — a different category than
the policy above. It's a one-time, narrowly-scoped exception for a confirmed
correctness bug already blocking two of the seven shipped mesh/UV tools, not a
reopening of source-patching generally. Commit `e246089d`, on the ArmorPaint
checkout's `spike/minic-decimate` (also on `gc-fork`), on top of the
registration patch `2b528475` but independent of it. **Upstream PR open:**
upstream `main` (`85f6cf1c`) still had the bug as of 2026-09-27
(`f32_array_resize` is a bare `realloc`; all three functions still `+=` into
never-zeroed buffers). Rebased and comment-trimmed (11 `memset` lines, one
file, clang-format clean) as `287e63f4` on the checkout's
`fix/mesh-accumulator-zero-init`, opened 2026-09-27 as
[armory3d/armorpaint#2148](https://github.com/armory3d/armorpaint/pull/2148).
Repro on current upstream `main`, 10 runs: stock 3/10 smooth + 9/10 bevel
corrupted, fixed 0/10 + 0/10.

- **Mechanism:** one line per function in `minic_api_list.h`
  (`X0`/`X1`/... macro, matching the C function's real signature) — ArmorPaint's own
  X-macro system in `minic_api.c` auto-generates the calling thunk. No other file
  needs touching when the target C function already exists (contrast: a genuinely
  new C function, like `script_timeline_resume`/`_pause`, needs three files).
- **Current state: upstream.** Merged as
  [armory3d/armorpaint#2139](https://github.com/armory3d/armorpaint/pull/2139)
  (merge commit `ee2f3635`, 2026-09-17), so stock upstream `main` now registers
  all 7 functions. Maintainer's note on merge: the script API "will need a
  cleanup," so breaking renames may come later (`6c84667a paint: script api
  cleanup` landed the same day). Originally: branch `spike/minic-decimate`, one
  file changed, 7 functions registered and empirically verified.
  A further function, `util_mesh_merge_geometry_down` (the GUI's targeted
  "merge with the object below"), was considered and rejected as a one-liner
  at the time, on the belief that minic had no accessor for "the other
  object". That belief was wrong (`object_t.ext` is reachable; Phase 6
  draft), and D2 (2026-09-27) chose a `script_object_merge` wrapper instead
  of the one-liner anyway (roadmap item 9, Phase 7). Incremental rebuild after the full batch: 2.3s.
- **Upstream ambition: done.** Grayson's first open-source contribution, merged
  same day it was opened. Item 9's dead end was left out of it.
- **Operational dependency now:** `AP_BINARY` must be a build of upstream `main`
  at or after `01bae6c5` (which renamed `plugin_uv_unwrap_button` to
  `util_mesh_uv_unwrap`, the name this project now calls; STATUS.md Known
  Issue #6), plus the zero-init commit above for reliable
  `smooth_mesh`/`bevel_mesh` until #2148 lands. `--check`'s "mesh-edit patch"
  preflight (`src/armorpaint_mcp/doctor.py`) catches an older build with a
  clear error instead of a silent "function not found" minic failure. Since
  2026-09-27 the local `AP_BINARY` is built from the checkout's
  `fix/mesh-accumulator-zero-init` (`287e63f4` = upstream `main` `85f6cf1c` +
  the fix), with unit/integration/smoke all green on it.

## Known gaps / open questions

- **"Remesh" doesn't mean what it might sound like here.** ArmorPaint has no
  retopology/quad-remeshing algorithm at all (confirmed: zero source matches for
  `remesh|decimat|retopolog|voxel_remesh` beyond `decimate` itself, zero matches in
  a full runtime `--api` dump, no such plugin bundled). `decimate_mesh` (item 2) is
  the closest analogous operation ArmorPaint can do. If true quad-remeshing/
  retopology ever becomes a real need, that's Tool-MeshTriage's territory
  (`quadriflow`/`voxel` methods already shipped there), not something this project
  should attempt to add to ArmorPaint.
- **No multi-object test fixture exists yet.** Item 8's bisection and any future
  multi-object work (item 9, and anything else touching `paint_objects->buffer[1+]`)
  needs one — `tests/fixtures/sample_project_multi.arm` is multi-*material*, still
  single-object, despite the name.
- **UV unwrap's algorithm quality is unverified**, only its reachability. `xatlas`
  (what Tool-MeshTriage uses) is a known-good, well-packed unwrapper; ArmorPaint's
  own `proc_uv_unwrap` has not been compared against it for packing efficiency or
  atlas coverage. Worth a real quality check before leaning on it for production
  assets, not just a "did it change the UVs at all" smoke test.
- Live mode (interactive GUI-attached sessions) remains separately deferred per the
  original spec — this patch strategy doesn't change that, since every mesh-edit
  patch here still runs through the same one-shot `--script` process model v1 uses.

## Links

- [docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md) — original architecture, still valid for v1's surface
- [HANDOFF.md](HANDOFF.md) — session-by-session history
- [STATUS.md](STATUS.md) — phase gate ledger
- Project memory: `minic mesh-edit patching`, `Bash tool silently no-ops ArmorPaint.exe` (this session's spike findings, durable across future sessions)
