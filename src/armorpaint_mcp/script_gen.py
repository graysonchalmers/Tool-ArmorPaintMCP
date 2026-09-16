"""Generates minic scripts for procedural material authoring.

v1 supports exactly two node types -- "checker" and "solid" -- each a
single node wired straight to OUTPUT_MATERIAL_PBR's Base Color input
(socket 0). This is deliberately narrow (YAGNI): a general multi-node
graph DSL is future scope, not this phase's job -- see docs/PLAN.md's
Phase 2 section for why the scope stops here.

Every generated script does the same four things in order: create a fresh
default project, build the one node the spec asks for and connect it to
the output, render it into the paint layer (script_fill_layer), and export
(export_texture_run) -- all inside a single ArmorPaint process. That
ordering is load-bearing: see the design spec's Amendment 2 for why a
save-then-reexport split silently loses the rendered pixels.
"""


class NodeSpecError(Exception):
    """`node_spec` is malformed or requests an unsupported node type."""


def _number(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NodeSpecError(f"{name} must be a number, got {value!r}")
    return float(value)


def _color3(name: str, value) -> tuple[float, float, float]:
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(isinstance(c, bool) or not isinstance(c, (int, float)) for c in value)):
        raise NodeSpecError(f"{name} must be a [r, g, b] list of 3 numbers, got {value!r}")
    return tuple(float(c) for c in value)


def _checker_node_lines(params: dict) -> list[str]:
    scale = _number("scale", params.get("scale", 5.0))
    r1, g1, b1 = _color3("color1", params.get("color1", [0.8, 0.8, 0.8]))
    r2, g2, b2 = _color3("color2", params.get("color2", [0.2, 0.2, 0.2]))
    return [
        '\tui_node_t *src = script_material_create_node_at("TEX_CHECKER", -400.0, 0.0);',
        f'\tscript_material_set_color(src, 1, 1, {r1}, {g1}, {b1}, 1.0);',
        f'\tscript_material_set_color(src, 1, 2, {r2}, {g2}, {b2}, 1.0);',
        f'\tscript_material_set_float(src, 1, 3, {scale});',
        '\tscript_material_connect(src, 0, out, 0);',
    ]


def _solid_node_lines(params: dict) -> list[str]:
    r, g, b = _color3("color", params.get("color", [0.8, 0.8, 0.8]))
    return [
        '\tui_node_t *src = script_material_create_node_at("RGB", -400.0, 0.0);',
        f'\tscript_material_set_color(src, 0, 0, {r}, {g}, {b}, 1.0);',
        '\tscript_material_connect(src, 0, out, 0);',
    ]


_NODE_BUILDERS = {
    "checker": _checker_node_lines,
    "solid": _solid_node_lines,
}


def _output_dir_literal(output_dir: str) -> str:
    """Render `output_dir` as a minic double-quoted string literal. minic
    (matching the rest of ArmorPaint's own path handling) wants forward
    slashes even on Windows, so backslashes are normalized first -- that is
    the normal, expected transformation for every real Windows path this
    receives, not something to reject. A literal double-quote is rejected
    outright rather than escaped: it is the one character that could break
    out of the string literal into the surrounding script, and no real
    filesystem path legitimately contains one."""
    normalized = output_dir.replace("\\", "/")
    if '"' in normalized:
        raise NodeSpecError(
            f"output_dir cannot be safely embedded in a minic script "
            f"(contains a double-quote): {output_dir!r}")
    return f'"{normalized}"'


def generate_script(node_spec: dict, output_dir: str) -> str:
    """Build the complete minic script text for `node_spec`, which exports
    to `output_dir` when run. Raises NodeSpecError for a malformed or
    unsupported node_spec, or an output_dir that can't be safely embedded
    in the generated script."""
    if not isinstance(node_spec, dict) or "type" not in node_spec:
        raise NodeSpecError(
            f"node_spec must be a dict with a 'type' key, got {node_spec!r}")
    node_type = node_spec["type"]
    builder = _NODE_BUILDERS.get(node_type)
    if builder is None:
        raise NodeSpecError(
            f"unsupported node_spec type '{node_type}'; supported: "
            f"{', '.join(sorted(_NODE_BUILDERS))}")
    node_lines = builder(node_spec.get("params", {}))

    lines = [
        "void main() {",
        "\tscript_project_new();",
        '\tui_node_t *out = script_material_get_node("OUTPUT_MATERIAL_PBR");',
        *node_lines,
        "\tscript_fill_layer();",
        f"\texport_texture_run({_output_dir_literal(output_dir)}, 0);",
        "}",
        "",
    ]
    return "\n".join(lines)
