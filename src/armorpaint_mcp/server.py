import os
import sys

from mcp.server.mcpserver import MCPServer

from armorpaint_mcp import __version__
from armorpaint_mcp.config import load_config, require_valid
from armorpaint_mcp.doctor import run_check
from armorpaint_mcp.catalog import (CatalogError, extract_project_state,
                                    layer_blend_modes, scene_objects)
from armorpaint_mcp.paths import ensure_within_roots, PathNotAllowed
from armorpaint_mcp.runner import (DEFAULT_TIMEOUT_S, export_textures, list_export_presets,
                                   run_api, run_minic_script, run_procedural_material)
from armorpaint_mcp.script_gen import generate_script, NodeSpecError

# Startup is lazy: importing this module must NOT validate config, so
# `ap-mcp --check` / `--version` work even when config is broken (the exact
# case the doctor exists for), and tests can import cheaply.
_cfg = None

mcp = MCPServer("armorpaint-mcp")


def _ensure_ready():
    """Load and validate config once, then memoize. Validation happens
    BEFORE the memo is written: memoizing first would make an invalid
    config fail only on the first call and then be silently accepted by
    every call after it."""
    global _cfg
    if _cfg is None:
        cfg = load_config()
        require_valid(cfg)
        _cfg = cfg
    return _cfg


def reexport_project(project: str, preset: str, output_dir: str) -> dict:
    """Re-export an existing .arm project's textures at a given preset,
    using ArmorPaint's native --export-textures flag (PNG). No resolution
    parameter: ArmorPaint has no CLI flag or confirmed scripting call for it
    in this version -- see docs/PLAN.md's Phase 1 section. `preset` must be
    one of the names returned by listing <ArmorPaint install>/data/export_presets/*.json
    (this checkout has: base_color, generic, minecraft_mer, specular,
    unigine, unity, unreal, xplane). Bounded by AP_ALLOWED_ROOTS when set.
    Returns {"ok": bool, "files": [str] | None, "error": str | None}."""
    # Validates config (not just loads it): without require_valid, a missing
    # or wrong AP_BINARY surfaces further down as "unknown preset 'generic';
    # available: " -- blaming the preset for a config fault.
    cfg = _ensure_ready()

    available = list_export_presets(cfg.binary)
    if preset not in available:
        return {"ok": False, "files": None,
                "error": f"unknown preset '{preset}'; available: {', '.join(available)}"}

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
        output_dir = ensure_within_roots(output_dir, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return {"ok": False, "files": None, "error": str(exc)}

    result = export_textures(cfg.binary, project, "png", preset, output_dir)
    return {"ok": result.ok, "files": result.files if result.ok else None,
            "error": result.error}


mcp.tool()(reexport_project)


def create_procedural_material(node_spec: dict, output_dir: str,
                               preset: str = "generic") -> dict:
    """Build a small procedural material on a fresh default project and
    export it at `preset`. `node_spec` is one node wired straight to the
    material output's Base Color, all params optional:
    {"type": "checker", "params": {"scale": float, "color1": [r,g,b],
    "color2": [r,g,b]}}, {"type": "solid", "params": {"color": [r,g,b]}},
    {"type": "noise", "params": {"scale": float, "detail": float,
    "roughness": float, "lacunarity": float, "distortion": float}}, or
    {"type": "voronoi", "params": {"scale": float, "detail": float,
    "roughness": float, "lacunarity": float, "randomness": float}}.
    Everything happens in
    one ArmorPaint process (build the graph, render it into the paint
    layer, export): saving to .arm and exporting separately does not
    preserve the rendered pixels on this build -- see docs/PLAN.md's
    Phase 2 section. Only the 'generic' preset is actually supported (see
    the in-function check below for why). Bounded by AP_ALLOWED_ROOTS when
    set. Returns {"ok": bool, "files": [str] | None, "error": str | None}."""
    cfg = _ensure_ready()

    available = list_export_presets(cfg.binary)
    if preset not in available:
        return {"ok": False, "files": None,
                "error": f"unknown preset '{preset}'; available: {', '.join(available)}"}

    if preset != "generic":
        return {"ok": False, "files": None,
                "error": (f"create_procedural_material only supports the 'generic' "
                          f"preset: the single-process script flow calls "
                          f"export_texture_run(), which has no preset argument and "
                          f"no minic setter exists for it -- it always exports "
                          f"whatever preset last configured the export box, which "
                          f"in this headless flow is always ArmorPaint's own "
                          f"'generic' fallback. Requesting '{preset}' would either "
                          f"time out waiting for files that never arrive, or (for "
                          f"a preset whose files are a strict subset of generic's) "
                          f"silently report success for the wrong export.")}

    try:
        output_dir = ensure_within_roots(output_dir, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return {"ok": False, "files": None, "error": str(exc)}

    try:
        script_text = generate_script(node_spec, output_dir)
    except NodeSpecError as exc:
        return {"ok": False, "files": None, "error": str(exc)}

    result = run_procedural_material(cfg.binary, script_text, output_dir, preset)
    return {"ok": result.ok, "files": result.files if result.ok else None,
            "error": result.error}


mcp.tool()(create_procedural_material)


def list_available_presets() -> dict:
    """List the export preset names available from the connected
    ArmorPaint install (<binary_dir>/data/export_presets/*.json) -- for
    picking a `preset` value for reexport_project or
    create_procedural_material without guessing. Returns
    {"presets": [str]}."""
    cfg = _ensure_ready()
    return {"presets": list_export_presets(cfg.binary)}


mcp.tool()(list_available_presets)


def inspect_project(project: str) -> dict:
    """Read-only metadata for an existing .arm project -- objects,
    materials, and layers -- via ArmorPaint's own `--api` flag (a project
    path plus --api prints a full project-state dump, not just static API
    docs). Makes no changes to the project. Bounded by AP_ALLOWED_ROOTS
    when set. Returns {"ok": bool, "objects": [...] | None,
    "materials": [...] | None, "layers": [...] | None, "error": str | None}."""
    cfg = _ensure_ready()

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": str(exc)}

    # ArmorPaint silently ignores a bogus --script/project argument and opens
    # its own default empty project instead of failing -- without this check,
    # a typo'd or nonexistent path would report ok:True with that phantom
    # default project's data, which is worse than an error for a read-only
    # reporting tool.
    if not os.path.isfile(project) or not project.lower().endswith(".arm"):
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": f"'{project}' is not an existing .arm project file"}

    result = run_api(cfg.binary, project)
    if not result.ok:
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": result.error}

    try:
        state = extract_project_state(result.text)
    except CatalogError as exc:
        return {"ok": False, "objects": None, "materials": None, "layers": None,
                "error": str(exc)}

    modes = layer_blend_modes()
    materials = [
        {"name": m.get("name"), "node_count": len(m.get("nodes") or [])}
        for m in (state.get("material_nodes") or [])
    ]
    layers = [
        {
            "name": layer.get("name"),
            "resolution": layer.get("res"),
            "visible": layer.get("visible"),
            "blending": modes[layer["blending"]]
                        if isinstance(layer.get("blending"), int)
                        and 0 <= layer["blending"] < len(modes) else None,
        }
        for layer in (state.get("layer_datas") or [])
    ]
    return {"ok": True, "objects": scene_objects(result.text),
            "materials": materials, "layers": layers, "error": None}


mcp.tool()(inspect_project)


def run_script(project: str, script: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Escape hatch: run an arbitrary minic script against an existing .arm
    project via ArmorPaint's own --script flag, for anything the
    purpose-built tools (reexport_project, create_procedural_material,
    inspect_project) don't cover yet. `script` is minic (.c) source text --
    written to a temp file and passed via --script, never executed as
    arbitrary OS-level code (minic is ArmorPaint's own curated scripting
    surface registered in minic_api_list.h, not a general-purpose language).
    Same trust level as this project's other tools -- not gated behind an
    extra opt-in flag.

    WARNING: this tool CAN modify and save the project in place. Minic
    registers project_save() (and similar persistence calls) as part of its
    normal API surface, so a script that calls it will overwrite the
    caller's .arm file on disk -- confirmed empirically. This is an
    intentional, accepted property of an unrestricted escape-hatch tool
    (see the design spec's framing for why it is deliberately not gated
    behind a copy-by-default or allow-save flag), not a bug. If you care
    about the project's current state, back it up yourself before calling
    this with a script you haven't fully reviewed.

    IMPORTANT: ArmorPaint gives no diagnostic signal for a script runtime
    error (confirmed empirically -- calling an undefined function exits 0
    with empty output, identical to success). ok=True here means only "the
    ArmorPaint process completed", not "the script did what you expected" --
    verify results yourself (e.g. check that expected output files appeared,
    or call inspect_project afterward). The `project` path is bounded by
    AP_ALLOWED_ROOTS when set; the script body itself is not sandboxed and
    can read/write anywhere the ArmorPaint process has OS-level permission
    to.

    NOTE: ArmorPaint's script-facing console output (console_log() and
    friends) writes directly to the console handle (WriteConsoleW), which is
    not captured by this tool's subprocess piping on this platform -- in
    practice `stdout`/`stderr` are typically empty even on a fully
    successful run. Don't rely on them as a diagnostic channel.

    `timeout_s` (default 30s) bounds how long the ArmorPaint process is
    allowed to run before this call gives up and reports an uncertain
    outcome -- raise it for scripts you expect to take longer.

    Returns {"ok": bool, "stdout": str | None, "stderr": str | None,
    "error": str | None}."""
    cfg = _ensure_ready()

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return {"ok": False, "stdout": None, "stderr": None, "error": str(exc)}

    # Same phantom-default-project trap inspect_project guards against
    # (Phase 3 Finding 2): a bogus/nonexistent project path makes ArmorPaint
    # silently open its own empty default project instead of failing, which
    # would let the caller's script run against nothing while still
    # reporting ok: True.
    if not os.path.isfile(project) or not project.lower().endswith(".arm"):
        return {"ok": False, "stdout": None, "stderr": None,
                "error": f"'{project}' is not an existing .arm project file"}

    result = run_minic_script(cfg.binary, project, script, timeout_s)
    return {"ok": result.ok,
            "stdout": result.stdout if result.ok else None,
            "stderr": result.stderr if result.ok else None,
            "error": result.error}


mcp.tool()(run_script)


_USAGE = (
    "usage: ap-mcp [--check | --version | --help]\n"
    "  (no args)   start the MCP server over stdio\n"
    "  --check     run the setup preflight (green/red checklist), exit 1 if any fail\n"
    "  --version   print the version\n"
    "  --help      show this message"
)


def main(argv: list | None = None) -> int:
    """Console entry point (`ap-mcp`). Returns a process exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--help" in args or "-h" in args:
        print(_USAGE)
        return 0
    if "--version" in args:
        print(f"ap-mcp {__version__}")
        return 0
    if "--check" in args:
        return run_check()
    if args:
        print(f"ap-mcp: unrecognized argument(s): {' '.join(args)}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    _ensure_ready()
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
