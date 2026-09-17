# Mesh/UV Visual Gallery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a before/after wireframe render pair for each of Phase 5's 7 mesh/UV editing tools and wire them into the README gallery, closing the gap where these tools are only verified numerically (vertex/face counts), never shown visually.

**Architecture:** Two new dev-only scripts (same tier as the existing `scripts/generate_gallery.py` — not part of the MCP server's callable surface). `scripts/_blender_render_obj.py` runs inside Blender's own Python (`blender --background --python`) and renders one OBJ file to one wireframe-over-solid PNG. `scripts/generate_mesh_gallery.py` orchestrates: call each real shipped tool against the existing Phase 5 test fixture, export before/after OBJ via the existing test helper, shell out to Blender per pair, write 14 PNGs into `docs/images/gallery/mesh_edit/`.

**Tech Stack:** Python 3.13, Blender 5.1 (headless CLI, `bpy`'s `wm.obj_import` + Freestyle rendering), the existing `armorpaint_mcp` package and `tests/_mesh_edit_test_helpers.py`.

**Spec:** [docs/superpowers/specs/2026-09-17-mesh-uv-visual-gallery-design.md](../specs/2026-09-17-mesh-uv-visual-gallery-design.md)

## Global Constraints

- No new MCP tool, no `server.py` registration, no `STATUS.md` phase gate — this is dev/docs tooling, out of the server's callable surface (spec's "Scope").
- No test-suite (`pytest`) entry — verification is "the script ran, produced non-empty PNGs, exits 0" (headless-checkable) plus a controller visual pass (host-only), per the spec.
- `BLENDER_BINARY` must NOT be added to `armorpaint_mcp/config.py`'s `Config`/`AP_*` surface — that surface is the actual MCP server's runtime config; this env var is read directly by the new script instead.
- Never mutate `tests/fixtures/sample_project.arm` — every mesh tool already defaults to copy-mode (`in_place=False`), so no extra copy step is needed before calling a tool against it directly.
- Wireframe rendering must use Freestyle (`scene.render.use_freestyle`), never viewport `shading`/`overlay` settings — confirmed empirically during brainstorming that the latter never reaches `bpy.ops.render.render()` output and has no context to run against in `--background` mode.
- Camera framing must use manual bounding-box math, never `view3d.camera_to_view_selected` — confirmed empirically that operator needs a live 3D viewport area unavailable in `--background` mode.
- `scene.render.filepath` (and any Blender-facing path) must be a native path (`C:/Users/...`, forward slashes fine) — a POSIX-style `/c/Users/...` path silently resolves to the wrong location (`C:\c\Users\...`) with no error.

---

### Task 1: Blender headless render script

**Files:**
- Create: `scripts/_blender_render_obj.py`

**Interfaces:**
- Consumes: nothing from this project's Python package — runs standalone inside Blender's own Python interpreter, invoked as `blender --background --python scripts/_blender_render_obj.py -- <obj_path> <png_path>`.
- Produces: a PNG file at `<png_path>`, 800x600, transparent background, wireframe-over-solid render of the mesh in `<obj_path>`. Task 2 shells out to this via `subprocess.run`.

This script is never imported by anything else and never runs under pytest (no `bpy` outside Blender's own interpreter) — verification is a real headless run, checked with Pillow (already a dev dependency: `pillow>=10.0.0` in `pyproject.toml`).

- [ ] **Step 1: Write the render script**

```python
# scripts/_blender_render_obj.py
"""Runs inside Blender's own Python (`blender --background --python
scripts/_blender_render_obj.py -- <obj_path> <png_path>`), never imported by
anything else. Renders `obj_path` as a wireframe-over-solid orthographic
still to `png_path`.

Wireframe uses Freestyle edge rendering, not the 3D viewport's "wireframe
overlay" -- the latter never reaches bpy.ops.render.render()'s output and
--background mode has no viewport/window context to capture one from
anyway (confirmed empirically; see the design spec's Settings table).

Camera framing uses manual bounding-box math, not
view3d.camera_to_view_selected -- that operator needs a live 3D viewport
area, also unavailable in --background mode.

Settings below are named constants, not scattered magic numbers -- tune
these (and update the spec's rationale) if a render looks wrong."""
import sys

import bpy
import mathutils

RESOLUTION = (800, 600)
CAMERA_DIRECTION = (-1.0, 1.0, -0.75)  # fixed diagonal view angle, same for every render
ORTHO_MARGIN = 1.3  # headroom multiplier on the mesh's bounding-sphere radius


def _parse_args() -> tuple[str, str]:
    argv = sys.argv
    if "--" not in argv:
        raise SystemExit(
            "usage: blender --background --python _blender_render_obj.py "
            "-- <obj_path> <png_path>")
    obj_path, png_path = argv[argv.index("--") + 1:][:2]
    return obj_path, png_path


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def _import_obj(obj_path: str):
    bpy.ops.wm.obj_import(filepath=obj_path)
    imported = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    if not imported:
        raise SystemExit(f"no mesh object imported from '{obj_path}'")
    return imported[0]


def _frame_camera(target, scene) -> None:
    corners = [target.matrix_world @ mathutils.Vector(c) for c in target.bound_box]
    center = sum(corners, mathutils.Vector()) / 8
    radius = max((c - center).length for c in corners)

    cam_data = bpy.data.cameras.new("gallery_camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = radius * 2 * ORTHO_MARGIN
    cam_obj = bpy.data.objects.new("gallery_camera", cam_data)
    scene.collection.objects.link(cam_obj)

    direction = mathutils.Vector(CAMERA_DIRECTION).normalized()
    cam_obj.location = center - direction * radius * 4
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj


def _light_scene(scene) -> None:
    light_data = bpy.data.lights.new("gallery_sun", type="SUN")
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new("gallery_sun", light_data)
    light_obj.rotation_euler = (0.6, 0.2, 0.4)
    scene.collection.objects.link(light_obj)


def main() -> None:
    obj_path, png_path = _parse_args()
    scene = bpy.context.scene

    _clear_scene()
    mesh_obj = _import_obj(obj_path)
    _frame_camera(mesh_obj, scene)
    _light_scene(scene)

    scene.render.resolution_x, scene.render.resolution_y = RESOLUTION
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = png_path
    scene.render.use_freestyle = True
    bpy.context.view_layer.use_freestyle = True

    bpy.ops.render.render(write_still=True)
    print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write a throwaway verification OBJ**

This is a manual verification aid, not a committed test fixture — an
off-origin, non-cubic box, chosen specifically to catch a camera-framing
bug that a origin-centered cube would hide.

Run (from the repo root, in a Python shell or a scratch `.py` file — do
NOT commit this file):

```python
import os
obj_text = """\
v 5.0 10.0 10.5
v 5.0 10.0 10.0
v 5.0 10.5 10.5
v 5.0 10.5 10.0
v 9.0 10.0 10.5
v 9.0 10.0 10.0
v 9.0 10.5 10.5
v 9.0 10.5 10.0
f 1 5 7 3
f 4 3 7 8
f 8 7 5 6
f 6 2 4 8
f 2 1 3 4
f 6 5 1 2
"""
with open("scratch_test.obj", "w") as f:
    f.write(obj_text)
```

- [ ] **Step 3: Run the render script against the throwaway OBJ**

Run (adjust the Blender path to whichever `BLENDER_BINARY` you'll set in
Task 2 — any Blender 3.2+ works, `bpy.ops.wm.obj_import` has been stable
since then):

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --background --python scripts\_blender_render_obj.py -- "C:/Projects-local/Tool-ArmorPaintMCP/scratch_test.obj" "C:/Projects-local/Tool-ArmorPaintMCP/scratch_render.png"
```

Expected: exits 0, prints `wrote C:/Projects-local/Tool-ArmorPaintMCP/scratch_render.png`, no Python traceback in the output.

- [ ] **Step 4: Verify the render is real, correctly framed content**

```powershell
& "C:\Program Files\Python313\python.exe" -c "from PIL import Image; im = Image.open('scratch_render.png'); assert im.size == (800, 600), im.size; colors = im.getcolors(maxcolors=1000000); assert colors is not None and len(colors) > 2, 'render looks blank/uniform'; print('OK', im.size, len(colors), 'distinct colors')"
```

Expected: `OK (800, 600) N distinct colors` with N comfortably > 2 (a blank/failed render collapses to 1-2 colors: background plus maybe one flat fill). Also open `scratch_render.png` directly and confirm by eye: the box is fully visible, not cropped or off-center, with visible black wireframe edges over a shaded gray surface.

- [ ] **Step 5: Delete the throwaway files, commit the render script**

```bash
rm -f scratch_test.obj scratch_render.png
git add scripts/_blender_render_obj.py
git commit -m "feat: add Blender headless wireframe render script for the mesh gallery"
```

---

### Task 2: Gallery orchestrator + BLENDER_BINARY config

**Files:**
- Create: `scripts/generate_mesh_gallery.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `scripts/_blender_render_obj.py` (Task 1, invoked via `subprocess.run`, no Python-level import); the 7 shipped tool functions from `armorpaint_mcp.server` (`decimate_mesh`, `bevel_mesh`, `subdivide_mesh`, `smooth_mesh`, `duplicate_mesh`, `merge_mesh_geometry`, `unwrap_mesh_uvs` — all `(project, output_project=None, in_place=False, timeout_s=...) -> {"ok", "output_project", "error"}`, `decimate_mesh`/`bevel_mesh` additionally take `strength`/`amount`); `export_obj(project: str, out_path: str) -> str` from `tests/_mesh_edit_test_helpers.py`.
- Produces: 14 PNGs at `docs/images/gallery/mesh_edit/<tool>_before.png` / `<tool>_after.png`. Task 3 references these exact filenames from README.

- [ ] **Step 1: Add `BLENDER_BINARY` to `.env.example`**

Add after the existing `AP_ALLOWED_ROOTS` block:

```
# Path to Blender's executable, used only by scripts/generate_mesh_gallery.py
# to render the mesh/UV before-after gallery. Not read by the MCP server or
# armorpaint_mcp/config.py -- this is dev/docs tooling, not server runtime
# config. Any Blender 3.2+ works (bpy.ops.wm.obj_import has been stable
# since then).
BLENDER_BINARY=C:\path\to\Blender\blender.exe
```

- [ ] **Step 2: Write the orchestrator script**

```python
# scripts/generate_mesh_gallery.py
"""Regenerates the mesh/UV before-after gallery under
docs/images/gallery/mesh_edit/ (14 PNGs: one before/after pair per Phase 5
mesh-edit tool).

Run manually whenever the gallery needs to change:
    .venv\\Scripts\\python.exe scripts\\generate_mesh_gallery.py

Requires AP_BINARY (env var or .env, same as every other script here) and
BLENDER_BINARY (env var or .env -- see .env.example; deliberately NOT part
of armorpaint_mcp.config.Config, since this never runs at MCP server
runtime) set to working executables.

Routes through the real, shipped mesh-edit tools (not hand-written minic)
against the existing Phase 5 test fixture -- genuine tool output, matching
generate_gallery.py's own precedent. Renders via Blender headless
(_blender_render_obj.py) against the real OBJ exports the tools' own test
helper produces. See
docs/superpowers/specs/2026-09-17-mesh-uv-visual-gallery-design.md for why
ArmorPaint itself can't render a picture of a mesh (no such capability
exists in its CLI or GUI in this build)."""
import os
import subprocess
import sys
import tempfile

from dotenv import dotenv_values

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))
from armorpaint_mcp.server import (  # noqa: E402
    decimate_mesh, bevel_mesh, subdivide_mesh, smooth_mesh,
    duplicate_mesh, merge_mesh_geometry, unwrap_mesh_uvs,
)
from _mesh_edit_test_helpers import export_obj  # noqa: E402

GALLERY_DIR = os.path.join(
    os.path.dirname(__file__), "..", "docs", "images", "gallery", "mesh_edit")
FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "tests", "fixtures", "sample_project.arm")
RENDER_SCRIPT = os.path.join(os.path.dirname(__file__), "_blender_render_obj.py")


def _blender_binary() -> str:
    env = dict(dotenv_values(os.path.join(os.getcwd(), ".env")))
    env.update({k: v for k, v in os.environ.items() if k == "BLENDER_BINARY"})
    binary = env.get("BLENDER_BINARY", "")
    if not binary or not os.path.isfile(binary):
        print(f"BLENDER_BINARY not set to a valid blender.exe (got '{binary}'). "
              "Set it in .env or as an environment variable -- see .env.example.",
              file=sys.stderr)
        sys.exit(1)
    return binary


def _render(blender_binary: str, obj_path: str, png_path: str) -> None:
    proc = subprocess.run(
        [blender_binary, "--background", "--python", RENDER_SCRIPT,
         "--", obj_path.replace("\\", "/"), png_path.replace("\\", "/")],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0 or not os.path.isfile(png_path):
        print(f"Blender render failed for '{obj_path}':\n{proc.stdout}\n{proc.stderr}",
              file=sys.stderr)
        sys.exit(1)


def _render_pair(blender_binary: str, name: str, before_obj: str, after_obj: str) -> None:
    _render(blender_binary, before_obj, os.path.join(GALLERY_DIR, f"{name}_before.png"))
    _render(blender_binary, after_obj, os.path.join(GALLERY_DIR, f"{name}_after.png"))


def _simple_tool(tmp: str, name: str, tool) -> tuple[str, str]:
    """Tools whose gallery pair needs no setup beyond the pristine fixture --
    every mesh tool defaults to copy-mode (in_place=False), so the fixture
    itself, unmodified, is the 'before' state."""
    after_project = os.path.join(tmp, f"{name}.arm")
    before_obj = os.path.join(tmp, f"{name}_before.obj")
    after_obj = os.path.join(tmp, f"{name}_after.obj")

    export_obj(FIXTURE, before_obj)
    result = tool(project=FIXTURE, output_project=after_project)
    if not result["ok"]:
        print(f"gallery generation failed for '{name}': {result['error']}", file=sys.stderr)
        sys.exit(1)
    export_obj(after_project, after_obj)
    return before_obj, after_obj


def _merge_mesh_geometry_pair(tmp: str) -> tuple[str, str]:
    """merge_mesh_geometry needs 2+ objects -- no fixture provides that
    (sample_project_multi.arm is multi-material, single-object). Build the
    2-object source the same way this tool's own integration test does:
    duplicate_mesh(FIXTURE) first."""
    duplicated = os.path.join(tmp, "merge_source.arm")
    dup_result = duplicate_mesh(project=FIXTURE, output_project=duplicated)
    if not dup_result["ok"]:
        print("gallery generation failed building merge_mesh_geometry's "
              f"2-object source: {dup_result['error']}", file=sys.stderr)
        sys.exit(1)

    merged = os.path.join(tmp, "merged.arm")
    before_obj = os.path.join(tmp, "merge_mesh_geometry_before.obj")
    after_obj = os.path.join(tmp, "merge_mesh_geometry_after.obj")

    export_obj(duplicated, before_obj)
    merge_result = merge_mesh_geometry(project=duplicated, output_project=merged)
    if not merge_result["ok"]:
        print(f"gallery generation failed for 'merge_mesh_geometry': "
              f"{merge_result['error']}", file=sys.stderr)
        sys.exit(1)
    export_obj(merged, after_obj)
    return before_obj, after_obj


def main() -> int:
    blender_binary = _blender_binary()
    os.makedirs(GALLERY_DIR, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        pairs = {
            "decimate_mesh": _simple_tool(
                tmp, "decimate_mesh", lambda **kw: decimate_mesh(strength=0.5, **kw)),
            "bevel_mesh": _simple_tool(
                tmp, "bevel_mesh", lambda **kw: bevel_mesh(amount=0.1, **kw)),
            "subdivide_mesh": _simple_tool(tmp, "subdivide_mesh", subdivide_mesh),
            "smooth_mesh": _simple_tool(tmp, "smooth_mesh", smooth_mesh),
            "duplicate_mesh": _simple_tool(tmp, "duplicate_mesh", duplicate_mesh),
            "unwrap_mesh_uvs": _simple_tool(tmp, "unwrap_mesh_uvs", unwrap_mesh_uvs),
            "merge_mesh_geometry": _merge_mesh_geometry_pair(tmp),
        }

        for name, (before_obj, after_obj) in pairs.items():
            _render_pair(blender_binary, name, before_obj, after_obj)
            print(f"wrote {name}_before.png / {name}_after.png")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run it for real**

Requires `AP_BINARY` and `BLENDER_BINARY` both set in `.env`.

```powershell
Push-Location C:\Projects-local\Tool-ArmorPaintMCP; .venv\Scripts\python.exe scripts\generate_mesh_gallery.py; Pop-Location
```

Expected: exits 0, prints 7 `wrote <tool>_before.png / <tool>_after.png` lines, no stderr output.

- [ ] **Step 4: Verify all 14 files exist and are non-empty**

```powershell
Get-ChildItem docs\images\gallery\mesh_edit\*.png | Select-Object Name, Length
```

Expected: exactly 14 files, each with a nonzero `Length` (a few KB to a few hundred KB, consistent with the existing gallery images' sizes).

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_mesh_gallery.py .env.example docs/images/gallery/mesh_edit/
git commit -m "feat: add mesh/UV before-after gallery generator"
```

---

### Task 3: README wiring + controller visual review

**Files:**
- Modify: `README.md:70` (insert new subsection right after the existing procedural-material gallery paragraph, before `## How it works`)

**Interfaces:**
- Consumes: the 14 PNG filenames Task 2 produced (`docs/images/gallery/mesh_edit/<tool>_before.png` / `_after.png`), exact names as listed in Task 2's `pairs` dict keys.
- Produces: nothing consumed by a later task — this is the terminal, user-facing deliverable.

- [ ] **Step 1: Look at all 14 renders before writing anything**

Open each of the 14 PNGs in `docs/images/gallery/mesh_edit/` and confirm,
per pair: the mesh is fully visible (not cropped by the camera framing),
wireframe edges are visibly black/dark over the shaded surface, and the
before/after difference is visually apparent (e.g. `decimate_mesh` should
show visibly fewer faces after; `subdivide_mesh` visibly more; `smooth_mesh`
should look similar in silhouette but smoother-shaded; `merge_mesh_geometry`
should show two separate boxes before, one contiguous shape after). If any
pair looks wrong (cropped, blank, no visible wireframe), stop here and fix
Task 1/2 before continuing — this step is the actual quality gate the
design spec calls for, not a formality.

- [ ] **Step 2: Insert the new README subsection**

Insert after `README.md`'s existing line "ceiling, tracked as open scope, not a platform limit." (end of the procedural-material gallery paragraph) and before the `## How it works` heading:

```markdown

Real before/after output from Phase 5's 7 mesh/UV editing tools, each
verified numerically in `tests/` (vertex/face-count diffs against an
independent OBJ export) and, here, shown visually for the first time.
Wireframe-over-solid renders via Blender headless, not ArmorPaint itself —
ArmorPaint has no capability to render a picture of a mesh, headless or
GUI, in this build (see
[docs/superpowers/specs/2026-09-17-mesh-uv-visual-gallery-design.md](docs/superpowers/specs/2026-09-17-mesh-uv-visual-gallery-design.md)).
[scripts/generate_mesh_gallery.py](scripts/generate_mesh_gallery.py)
regenerates all 14 images through the real shipped tools.

| `decimate_mesh` — before | `decimate_mesh` — after |
|:--:|:--:|
| ![decimate_mesh before](docs/images/gallery/mesh_edit/decimate_mesh_before.png) | ![decimate_mesh after](docs/images/gallery/mesh_edit/decimate_mesh_after.png) |

| `bevel_mesh` — before | `bevel_mesh` — after |
|:--:|:--:|
| ![bevel_mesh before](docs/images/gallery/mesh_edit/bevel_mesh_before.png) | ![bevel_mesh after](docs/images/gallery/mesh_edit/bevel_mesh_after.png) |

| `subdivide_mesh` — before | `subdivide_mesh` — after |
|:--:|:--:|
| ![subdivide_mesh before](docs/images/gallery/mesh_edit/subdivide_mesh_before.png) | ![subdivide_mesh after](docs/images/gallery/mesh_edit/subdivide_mesh_after.png) |

| `smooth_mesh` — before | `smooth_mesh` — after |
|:--:|:--:|
| ![smooth_mesh before](docs/images/gallery/mesh_edit/smooth_mesh_before.png) | ![smooth_mesh after](docs/images/gallery/mesh_edit/smooth_mesh_after.png) |

| `duplicate_mesh` — before | `duplicate_mesh` — after |
|:--:|:--:|
| ![duplicate_mesh before](docs/images/gallery/mesh_edit/duplicate_mesh_before.png) | ![duplicate_mesh after](docs/images/gallery/mesh_edit/duplicate_mesh_after.png) |

| `merge_mesh_geometry` — before | `merge_mesh_geometry` — after |
|:--:|:--:|
| ![merge_mesh_geometry before](docs/images/gallery/mesh_edit/merge_mesh_geometry_before.png) | ![merge_mesh_geometry after](docs/images/gallery/mesh_edit/merge_mesh_geometry_after.png) |

| `unwrap_mesh_uvs` — before | `unwrap_mesh_uvs` — after |
|:--:|:--:|
| ![unwrap_mesh_uvs before](docs/images/gallery/mesh_edit/unwrap_mesh_uvs_before.png) | ![unwrap_mesh_uvs after](docs/images/gallery/mesh_edit/unwrap_mesh_uvs_after.png) |
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add mesh/UV before-after gallery to README"
```

---

## Self-Review Notes

- **Spec coverage:** Problem (gallery gap) → Task 3's controller review step; "Why not render from ArmorPaint" → documented inline in both scripts' docstrings and linked from README; Scope (all 7 tools, docs-only, reused fixture) → Task 2's `pairs` dict covers all 7, no `server.py`/`STATUS.md` touched; Settings table (Freestyle, camera math, resolution, lighting) → Task 1's named constants; Error handling (missing `BLENDER_BINARY`, tool failure, Blender subprocess failure) → `_blender_binary()`/`_simple_tool()`/`_render()`'s fail-fast branches; Testing/verification boundary → Task 1 Step 4 (Pillow check) and Task 2 Step 4 (file-count check) for headless-checkable, Task 3 Step 1 for the host-only visual pass.
- **Placeholder scan:** none found — every step has real, complete code or an exact command.
- **Type consistency:** `_simple_tool`/`_merge_mesh_geometry_pair` both return `tuple[str, str]` (before_obj, after_obj), matching `_render_pair`'s signature and the `pairs` dict's value type used in `main()`'s final loop.
