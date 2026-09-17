"""Shared helpers for Phase 5's mesh-edit integration tests: verify a real
effect via an independent script_export_mesh OBJ export, never trust ok=True
alone (see this project's established minic-silent-failure history)."""

from armorpaint_mcp.server import run_script


def export_obj(project: str, out_path: str) -> str:
    """Export `project`'s current mesh to `out_path` (OBJ) via a fresh,
    edit-free run_script call, then return the file's text. Raises
    AssertionError with the tool's own error message if the export itself
    fails -- a failure here means the verification step is broken, not the
    thing under test, so it should fail loud rather than silently return
    empty text."""
    posix_out = out_path.replace("\\", "/")
    script = f'void main() {{\n\tscript_export_mesh("{posix_out}");\n}}\n'
    result = run_script(project=project, script=script)
    assert result["ok"], result["error"]
    with open(out_path, encoding="utf-8") as fh:
        return fh.read()


def count_obj_vertices_and_faces(text: str) -> tuple[int, int]:
    """(vertex count, face count) -- lines starting with 'v ' and 'f '
    specifically (not 'vn '/'vt ', which also start with 'v')."""
    vertices = sum(1 for line in text.splitlines() if line.startswith("v "))
    faces = sum(1 for line in text.splitlines() if line.startswith("f "))
    return vertices, faces


def obj_normal_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("vn ")]


def obj_uv_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("vt ")]
