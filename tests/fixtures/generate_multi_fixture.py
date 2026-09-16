# tests/fixtures/generate_multi_fixture.py
"""Regenerates tests/fixtures/sample_project_multi.arm -- a project with two
materials, used to verify inspect_project's array-index correlation
assumptions (material_nodes[i] describes the i-th material) against a real
multi-entity project, not just the single-entity sample_project.arm.

Run manually whenever the fixture needs to change:
    .venv\\Scripts\\python.exe tests\\fixtures\\generate_multi_fixture.py

Requires AP_BINARY set (env var or .env) to a working ArmorPaint.exe.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from armorpaint_mcp.config import load_config  # noqa: E402

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "sample_project_multi.arm")

SCRIPT_TEMPLATE = """\
void main() {{
	script_project_new();
	ui_node_t *out = script_material_get_node("OUTPUT_MATERIAL_PBR");
	ui_node_t *src = script_material_create_node_at("TEX_CHECKER", -400.0, 0.0);
	script_material_set_color(src, 1, 1, 0.9, 0.1, 0.1, 1.0);
	script_material_set_color(src, 1, 2, 0.1, 0.1, 0.9, 1.0);
	script_material_set_float(src, 1, 3, 8.0);
	script_material_connect(src, 0, out, 0);
	script_fill_layer();

	slot_material_t *mat2 = script_material_create("Second Material");
	script_material_set(mat2);
	ui_node_t *out2 = script_material_get_node("OUTPUT_MATERIAL_PBR");
	ui_node_t *src2 = script_material_create_node_at("RGB", -400.0, 0.0);
	script_material_set_color(src2, 0, 0, 0.2, 0.8, 0.2, 1.0);
	script_material_connect(src2, 0, out2, 0);

	project_filepath_set("{path}");
	project_save(0);
	printf("multi fixture created\\n");
}}
"""


def main() -> int:
    cfg = load_config()
    if not cfg.binary or not os.path.isfile(cfg.binary):
        print(f"AP_BINARY not set to a valid ArmorPaint.exe (got '{cfg.binary}')",
              file=sys.stderr)
        return 1

    fixture_path = os.path.abspath(FIXTURE_PATH).replace("\\", "/")
    script_content = SCRIPT_TEMPLATE.format(path=fixture_path)

    with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
        f.write(script_content)
        script_path = f.name

    try:
        proc = subprocess.run(
            [cfg.binary, "--background", "--script", script_path],
            capture_output=True, text=True, timeout=30,
        )
    finally:
        os.unlink(script_path)

    if proc.returncode != 0:
        print(f"ArmorPaint exited {proc.returncode}\nstdout: {proc.stdout}\n"
              f"stderr: {proc.stderr}", file=sys.stderr)
        return 1
    if not os.path.isfile(FIXTURE_PATH):
        print(f"expected fixture at '{FIXTURE_PATH}' but it wasn't created",
              file=sys.stderr)
        return 1

    size = os.path.getsize(FIXTURE_PATH)
    print(f"wrote {FIXTURE_PATH} ({size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
