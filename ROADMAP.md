# 🧭 ROADMAP — Tool-ArmorPaintMCP

> North star, feature path, gaps, open questions. The living compass — update this,
> don't let it drift the way a one-time spec can. Companion to
> [docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md)
> (the original architecture decisions, still valid) and its
> [Amendment 3](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md#amendment-3-scoped-patch-policy-for-meshuv-2026-09-16)
> (the patch-policy revision this doc exists because of).

**Last updated:** 2026-09-16 (pivot session)

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
| 1 | `unwrap_mesh_uvs` | 🔬 proven (`plugin_uv_unwrap_button` → real `proc_uv_unwrap`, not plugin-dependent) — not yet an MCP tool |
| 2 | `decimate_mesh` | 🔬 proven (`util_mesh_decimate`, real triangle-count reduction) — not yet an MCP tool |
| 3 | `subdivide_mesh` | 🔬 proven (`util_mesh_subdivide`, exact 4× face count) — not yet an MCP tool |
| 4 | `bevel_mesh` | 🔬 proven (`util_mesh_bevel`) — not yet an MCP tool |
| 5 | `smooth_mesh` | 🔬 proven (`util_mesh_smooth`, normals verified changed) — not yet an MCP tool |
| 6 | `duplicate_mesh` | 🔬 proven (`util_mesh_duplicate`, exact 2× vert/face count) — not yet an MCP tool |
| 7 | `merge_mesh_geometry` | 🔬 proven (`util_mesh_merge_geometry`, via duplicate→merge chain) — not yet an MCP tool |
| 8 | Non-destructive mesh replace/swap | ⬜ inconclusive — two real code paths identified (`script_import_asset` destructive, `script_append_mesh` additive), neither empirically confirmed; needs its own bisection + a real multi-object test fixture |
| 9 | Targeted 2-object merge (`merge_geometry_down`'s real use case) | ⬜ blocked — needs a new minic accessor for "the other object," bigger patch than a one-liner |
| 10 | UV validity check (1.0 changelog item) | ⬜ unchecked — minic reachability not yet investigated |
| 11 | `inspect_project` | ✅ shipped (v1, Phase 3) |
| 12 | `reexport_project` | ✅ shipped (v1, Phase 1) |
| 13 | `create_procedural_material` | ✅ shipped (v1, Phase 2) — covers the materials/blockout secondary want |
| 14 | `run_script` | ✅ shipped (v1, Phase 4) — escape hatch, stays useful regardless of new tools |
| 15 | `list_available_presets` | ✅ shipped (v1, Phase 1/2) |

Items 1-7 are the next implementation phase's natural scope — every one of them is
already empirically de-risked, unlike the rest of v1's phases, which each needed
their own hands-on investigation before implementation could start.

## Patch policy

**Decision (2026-09-16, supersedes part of the original spec — see Amendment 3):**
a small, scoped local patch to `paint\sources\minic_api_list.h` in the ArmorPaint
checkout (`C:\Projects-local\z-Git\ArmorPaint`) is the accepted path for exposing
GUI-only mesh/UV functions to `--script`, **for this specific class of gap only**
(a function that already exists, already works, and just isn't registered). This
does not reopen source-patching for anything else — rebake/texture-swap remain
exactly as blocked and out-of-scope as Phase 2 found them; that finding is
unaffected.

- **Mechanism:** one line per function in `minic_api_list.h`
  (`X0`/`X1`/... macro, matching the C function's real signature) — ArmorPaint's own
  X-macro system in `minic_api.c` auto-generates the calling thunk. No other file
  needs touching when the target C function already exists (contrast: a genuinely
  new C function, like `script_timeline_resume`/`_pause`, needs three files).
- **Current state:** branch `spike/minic-decimate` in the ArmorPaint checkout,
  unpushed, one file changed, 7 functions attempted, 6 registered and empirically
  verified, 1 confirmed a real dead end (see roadmap item 9). Incremental rebuild
  after the full batch: 2.3s.
- **Upstream ambition:** Grayson wants to submit this as a PR to
  `armory3d/armorpaint` — his first open-source contribution. The patch is a strong
  candidate for that: small, mechanical, every line empirically proven against real
  geometry, no architectural risk. Before submitting: read the project's actual
  contribution guidelines (not yet checked), decide whether item 9's dead end
  belongs in the same PR or a separate follow-up, and give each registration a
  proper commit message / PR description explaining why each function is safe to
  expose headlessly.
- **Until upstream lands (if it does):** Tool-ArmorPaintMCP's own `AP_BINARY` must
  point at a build carrying this patch, not stock ArmorPaint. This is a new
  operational dependency the project didn't have before — needs a `--check`
  preflight update once these tools are actually wired into `server.py`, so a
  caller pointed at an unpatched binary gets a clear error instead of a silent
  "function not found" minic failure.

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
