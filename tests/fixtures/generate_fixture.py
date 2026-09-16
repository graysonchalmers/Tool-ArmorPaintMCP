# tests/fixtures/generate_fixture.py
"""Regenerates tests/fixtures/sample_project.arm.

Run manually whenever the fixture needs to change:
    .venv\\Scripts\\python.exe tests\\fixtures\\generate_fixture.py

Requires AP_BINARY set (env var or .env) to a working ArmorPaint.exe.
Uses --background --script (NOT the broken --background + --export-textures
combo -- see docs/PLAN.md Phase 1) to call ArmorPaint's own minic scripting
API headlessly: script_project_new() creates a new project (defaults to the
cube_bevel primitive mesh + a default material + initialized layers),
project_filepath_set() points it at this fixture's path, project_save(0)
writes it without quitting (the --background flag's own args_run_script_stop
callback handles quitting afterward).
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from armorpaint_mcp.config import load_config  # noqa: E402

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "sample_project.arm")

# minic requires a void main() wrapper -- bare top-level statements silently
# no-op (confirmed the hard way while planning this phase).
SCRIPT_TEMPLATE = """\
void main() {{
	script_project_new();
	project_filepath_set("{path}");
	project_save(0);
	printf("fixture created\\n");
}}
"""


def main() -> int:
    cfg = load_config()
    if not cfg.binary or not os.path.isfile(cfg.binary):
        print(f"AP_BINARY not set to a valid ArmorPaint.exe (got '{cfg.binary}')",
              file=sys.stderr)
        return 1

    # minic wants forward slashes even on Windows (matches the ArmorPaint
    # source's own iron_file path handling); os.path.abspath keeps backslashes,
    # so normalize explicitly.
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
