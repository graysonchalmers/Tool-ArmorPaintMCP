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
                tmp, "decimate_mesh", lambda **kw: decimate_mesh(strength=0.85, **kw)),
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
