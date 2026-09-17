# Mesh/UV visual gallery — design spec

**Date:** 2026-09-17
**Status:** approved by Grayson via brainstorming session.
**Author:** Claude (claude-code), with Grayson Chalmers steering.

## Problem

Phase 5 shipped 7 mesh/UV editing tools (`decimate_mesh`, `bevel_mesh`,
`subdivide_mesh`, `smooth_mesh`, `duplicate_mesh`, `merge_mesh_geometry`,
`unwrap_mesh_uvs`), each verified in `tests/` by diffing vertex/face counts
between an independent before/after `script_export_mesh` OBJ export. That
proves correctness but nobody has ever *looked* at a decimated or beveled
mesh — the gallery under `docs/images/gallery/` only has Phase 1/2 material
and texture exports, nothing from Phase 5. Grayson asked for a visual
before/after (specifically: a wireframe comparison) for all 7 tools, plus
the render settings behind it documented and tuned, not left as one-off GUI
state.

## Why not render from ArmorPaint itself

Checked `C:\Projects-local\z-Git\ArmorPaint\paint\sources` directly rather
than assuming:

- `--export-mesh <path>` (`args.c`) is real and CLI-exposed — this is the
  OBJ geometry export the Phase 5 tests already use. It exports geometry
  *data*, never a rendered image.
- The only "wireframe" reference anywhere in the UI source is a single
  commented-out line in `viewport.c` (`// draw_wireframe = true;`) — dead
  code, not a working toggle, in either the CLI or the GUI.
- ArmorPaint's internal off-screen rendering (`util_render_make_material_preview`
  and siblings in `util/util_render.c`) is hardcoded to specific icon/preview
  use cases (material sphere, decal, font, brush thumbnails) and isn't
  exposed to `--script`/minic or any CLI flag. No `render_viewport_to_file`
  or equivalent exists.

Net: ArmorPaint cannot render a picture of a mesh to a file, headless or
GUI, in this build. It can only produce geometry (OBJ) and material bakes.
Rendering the geometry into a picture is a separate concern — Blender is
the natural tool for that, not a workaround for something ArmorPaint could
otherwise do.

## Scope

All 7 Phase 5 tools get one before/after wireframe pair each (14 images
total). Reuses the exact fixture and setup Phase 5's own tests already use:
`tests/fixtures/sample_project.arm` (ArmorPaint's default `cube_bevel`
primitive) for 6 tools directly. `merge_mesh_geometry` needs 2+ objects,
which no fixture provides — `sample_project_multi.arm` is a
multi-*material*, single-object fixture (for `inspect_project`'s tests),
not multi-object. Its own integration test builds the 2-object setup at
runtime instead (`duplicate_mesh(sample_project.arm) -> duplicated.arm`,
then merge); the gallery script does the same.

**Out of scope:**
- No new MCP tool. This is dev/docs tooling only, at the same tier as the
  existing `scripts/generate_gallery.py` — not part of the server's
  callable surface, no `server.py` registration, no `STATUS.md` phase gate.
- No `--check`/`doctor.py` integration — that preflight is for the actual
  MCP server's runtime dependencies (`AP_BINARY`), not a dev script's.
- No test-suite entry. Verification is "the script ran and produced 14
  non-empty PNGs" (headless-checkable) plus a controller visual pass
  (host-only, same convention as Phase 2's gallery image).

## Architecture

```
tools/ (existing, via tests/_mesh_edit_test_helpers.export_obj)
  -> for each of the 7 tools: run tool -> export before OBJ, after OBJ
       (reuses run_script + script_export_mesh, no new ArmorPaint-side code)
  -> scripts/generate_mesh_gallery.py hands both OBJs to Blender headless
       (blender --background --python scripts/_blender_render_obj.py)
  -> Blender applies fixed render settings, renders before.png/after.png
  -> docs/images/gallery/mesh_edit/<tool>_before.png, <tool>_after.png
```

Two new scripts, mirroring the existing `scripts/generate_gallery.py`
precedent exactly:

- **`scripts/generate_mesh_gallery.py`** — the orchestrator. For each of
  the 7 tools: calls the real shipped tool function (not hand-written
  minic, matching `generate_gallery.py`'s own "genuine tool output, not
  example-only imagery" rule) against a temp copy of the right fixture,
  exports before/after OBJs via the existing test helper, then shells out
  to Blender per pair.
- **`scripts/_blender_render_obj.py`** — runs *inside* Blender
  (`--background --python`), not imported by anything else. Takes an OBJ
  path and output PNG path via `sys.argv`, imports the mesh, applies the
  fixed camera/shading/lighting settings below, renders, exits.

## Settings (documented, not scattered)

All named constants at the top of `_blender_render_obj.py`, each with a
one-line rationale — this is the thing to tune if a render looks wrong:

| Setting | Value | Why |
|---|---|---|
| Shading mode | Solid + wireframe overlay (`shading.type='SOLID'`, `overlay.show_wireframe=True`) | Pure Wireframe shading hides face changes (bevel/subdivide read as line density only); solid+overlay shows both topology and silhouette. |
| Camera | Orthographic, fixed angle, auto-framed to the mesh's bounding box | Consistent viewing angle across all 7 pairs makes before/after visually comparable; orthographic avoids perspective distortion misleading a viewer about size change. |
| Lighting | Flat/minimal (single sun, no dramatic shadows) | This is a topology diagram, not a material/lighting showcase — shadows would compete with the wireframe for attention. |
| Resolution | 800x600, transparent background | Matches the existing gallery images' rough scale; transparent background composites cleanly into the README table. |

## Data flow

1. Copy the relevant fixture (`sample_project.arm` or `_multi.arm`) to a
   temp path per tool (never mutate the checked-in fixture).
2. Export "before" OBJ via `export_obj()` (existing helper, no new code).
3. Call the real tool (e.g. `decimate_mesh(project=temp_copy, ...)`).
4. Export "after" OBJ via `export_obj()` again.
5. Invoke Blender headless twice (before, after) with `_blender_render_obj.py`,
   writing `docs/images/gallery/mesh_edit/<tool>_{before,after}.png`.
6. Update `README.md`'s Gallery section with a new subsection, same
   2-column table style as the existing procedural-material rows.

## Error handling

- Missing `BLENDER_BINARY` env var (or `.env` entry): fail fast with an
  actionable message before touching ArmorPaint at all, same
  fail-fast-with-actionable-message spirit as `config.require_valid()`
  uses for `AP_BINARY` — but implemented locally in the new script, not
  added to `config.py`'s `Config`/`AP_*` surface (that surface is the
  actual MCP server's runtime config; this script touches nothing at
  server runtime).
- If a tool call itself fails (`ok=False`), the script stops and reports
  which tool/step failed rather than silently skipping to the next pair —
  matches this project's `assert result["ok"], result["error"]` convention
  used throughout the test helpers.
- Blender subprocess non-zero exit or missing output file: fail loud with
  the captured stderr, don't leave a partial/missing image silently in the
  gallery folder.

## Testing / verification boundary

- **Headless-checkable:** the script runs, produces 14 non-empty PNG files,
  exits 0. Worth a one-line manual note in `README.md`/`HANDOFF.md` on how
  to regenerate, same as `generate_gallery.py`'s own docstring — not a
  pytest entry, since nothing here is part of the shipped package.
- **Host-only:** whether a given render actually looks right (wireframe
  visible, camera framing sane, before/after actually distinguishable) is
  a controller visual pass before calling this done — same convention
  Phase 2 used for `procedural_checker_base.png`.

## Open items for implementation planning

- Exact Blender Python API calls for bounding-box-based camera auto-framing
  (`bpy.ops.view3d.camera_to_view_selected` or manual bbox math) — a
  planning-time/task-time detail, not an architectural fork.
- Whether `BLENDER_BINARY` needs Windows-path quoting handling identical to
  `AP_BINARY`'s (likely yes, same `subprocess.run([binary, ...])` list-arg
  pattern avoids the issue entirely — confirm during implementation).
