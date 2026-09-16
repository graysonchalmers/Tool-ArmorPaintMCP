# scripts/generate_gallery.py
"""Regenerates the procedural-material gallery images under
docs/images/gallery/ (procedural_noise_base.png, procedural_voronoi_base.png).

Run manually whenever the gallery needs to change:
    .venv\\Scripts\\python.exe scripts\\generate_gallery.py

Requires AP_BINARY set (env var or .env) to a working ArmorPaint.exe.

Hand-written minic, like tests/fixtures/generate_fixture.py -- deliberately
NOT routed through script_gen.py/create_procedural_material, which ship only
"checker" and "solid" node types by design (see docs/PLAN.md Phase 2). This
script exists purely to produce example imagery; it does not change the
shipped tool surface.

Renders every variant in its own script_project_new()/build/fill/export
cycle, all inside one ArmorPaint --script process -- confirmed working
(three cycles, three node types, one process) via a spike on 2026-09-16.
Cheaper than one process per image and avoids relaunching the GUI repeatedly.
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from armorpaint_mcp import runner  # noqa: E402
from armorpaint_mcp.config import load_config  # noqa: E402

GALLERY_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "images", "gallery")

# Each node's minic lines, wired to OUTPUT_MATERIAL_PBR's Base Color input
# (out, socket 0). Which output socket carries Color varies per node type --
# see each node's own *_init() in ArmorPaint's nodes_material/ source
# (TEX_NOISE and TEX_VORONOI both put Color at output socket 1, not 0).
_VARIANTS = {
    "noise": [
        '\tui_node_t *src = script_material_create_node_at("TEX_NOISE", -400.0, 0.0);',
        '\tscript_material_set_float(src, 1, 1, 6.0);',  # Scale
        '\tscript_material_set_float(src, 1, 2, 4.0);',  # Detail
        '\tscript_material_set_float(src, 1, 3, 0.6);',  # Roughness
        '\tscript_material_set_float(src, 1, 4, 2.0);',  # Lacunarity
        '\tscript_material_set_float(src, 1, 5, 0.0);',  # Distortion
        '\tscript_material_connect(src, 1, out, 0);',    # output 1 = Color
    ],
    "voronoi": [
        '\tui_node_t *src = script_material_create_node_at("TEX_VORONOI", -400.0, 0.0);',
        '\tscript_material_set_float(src, 1, 1, 8.0);',  # Scale
        '\tscript_material_set_float(src, 1, 2, 0.0);',  # Detail
        '\tscript_material_set_float(src, 1, 3, 0.5);',  # Roughness
        '\tscript_material_set_float(src, 1, 4, 2.0);',  # Lacunarity
        '\tscript_material_set_float(src, 1, 5, 1.0);',  # Randomness
        '\tscript_material_connect(src, 1, out, 0);',    # output 1 = Color
    ],
}


def _cycle_lines(variant: str, output_dir: str) -> list[str]:
    return [
        "\tscript_project_new();",
        '\tui_node_t *out = script_material_get_node("OUTPUT_MATERIAL_PBR");',
        *_VARIANTS[variant],
        "\tscript_fill_layer();",
        f'\texport_texture_run("{output_dir.replace(os.sep, "/")}", 0);',
    ]


def main() -> int:
    cfg = load_config()
    if not cfg.binary or not os.path.isfile(cfg.binary):
        print(f"AP_BINARY not set to a valid ArmorPaint.exe (got '{cfg.binary}')",
              file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        out_dirs = {name: os.path.join(tmp, name) for name in _VARIANTS}
        for d in out_dirs.values():
            os.makedirs(d, exist_ok=True)

        body: list[str] = []
        for name in _VARIANTS:
            body += _cycle_lines(name, out_dirs[name])
        script_text = "void main() {\n" + "\n".join(body) + "\n}\n"

        expected = []
        for d in out_dirs.values():
            expected += runner.expected_output_files(cfg.binary, "untitled.arm", "png",
                                                       "generic", d)
        before = runner._snapshot(expected)

        fd, script_path = tempfile.mkstemp(suffix=".c")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(script_text)
            proc = subprocess.Popen(
                [cfg.binary, "--script", script_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
            result = runner._poll_and_terminate(proc, expected, before, 45.0, "generic", tmp)
        finally:
            os.unlink(script_path)

        if not result.ok:
            print(f"gallery generation failed: {result.error}", file=sys.stderr)
            return 1

        os.makedirs(GALLERY_DIR, exist_ok=True)
        for name, d in out_dirs.items():
            src = os.path.join(d, "untitled_base.png")
            dst = os.path.join(GALLERY_DIR, f"procedural_{name}_base.png")
            shutil.copyfile(src, dst)
            print(f"wrote {dst} ({os.path.getsize(dst)} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
