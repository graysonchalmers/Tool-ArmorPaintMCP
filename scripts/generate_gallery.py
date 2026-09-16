"""Regenerates the procedural-material gallery images under
docs/images/gallery/ (procedural_checker_base.png, procedural_solid_base.png,
procedural_noise_base.png, procedural_voronoi_base.png).

Run manually whenever the gallery needs to change:
    .venv\\Scripts\\python.exe scripts\\generate_gallery.py

Requires AP_BINARY set (env var or .env) to a working ArmorPaint.exe.

Routes through the real, shipped create_procedural_material tool (not
hand-written minic) -- all four node types below ("checker", "solid",
"noise", "voronoi") are part of script_gen.py's actual whitelist, so this
is genuine tool output, not example-only imagery.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from armorpaint_mcp.server import create_procedural_material  # noqa: E402

GALLERY_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "images", "gallery")

_VARIANTS = {
    "checker": {"type": "checker", "params": {"scale": 8.0}},
    "solid": {"type": "solid", "params": {"color": [0.75, 0.35, 0.15]}},
    "noise": {"type": "noise"},
    "voronoi": {"type": "voronoi"},
}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(GALLERY_DIR, exist_ok=True)
        for name, node_spec in _VARIANTS.items():
            out_dir = os.path.join(tmp, name)
            os.makedirs(out_dir, exist_ok=True)
            result = create_procedural_material(
                node_spec=node_spec, output_dir=out_dir, preset="generic")
            if not result["ok"]:
                print(f"gallery generation failed for '{name}': {result['error']}",
                      file=sys.stderr)
                return 1
            src = next(f for f in result["files"] if f.endswith("_base.png"))
            dst = os.path.join(GALLERY_DIR, f"procedural_{name}_base.png")
            shutil.copyfile(src, dst)
            print(f"wrote {dst} ({os.path.getsize(dst)} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
