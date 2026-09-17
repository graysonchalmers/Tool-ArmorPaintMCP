import os
import shutil
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
from armorpaint_mcp.script_gen import _finite_float, generate_script, NodeSpecError

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


def _failure(error: str, *null_fields: str) -> dict:
    """The common shape of every tool's early-exit failure: ok=False, the
    error message, and every OTHER field the tool's success shape declares
    explicitly nulled out (never omitted -- callers pattern-match on a
    stable key set regardless of which branch returned)."""
    return {"ok": False, "error": error, **{f: None for f in null_fields}}


def _is_arm_project_file(path: str) -> bool:
    """True only for an existing, real .arm file on disk. ArmorPaint
    silently ignores a bogus --script/project positional argument and opens
    its own empty default project instead of failing -- both
    inspect_project and run_script must reject a bad path themselves before
    launching ArmorPaint, or a typo'd path would report ok:True against
    that phantom default project's data instead of an error."""
    return os.path.isfile(path) and path.lower().endswith(".arm")


def _run_mesh_edit(project: str, minic_call: str, output_project: str | None,
                   in_place: bool, timeout_s: float) -> dict:
    """Shared plumbing for every mesh-edit tool: validate `project`, resolve
    the edit target (a copy at `output_project` by default -- never touching
    the caller's own file unless `in_place=True`), run `minic_call` followed
    by project_save(0) against that target, and report the outcome.

    ok=True proves only that the ArmorPaint process completed and
    project_save(0) ran -- same caveat as run_script and every other minic
    call in this project (see run_script's docstring). `minic_call` here is
    always one of this project's own, already-verified function calls
    (never caller-supplied text), so the practical risk is much narrower
    than run_script's arbitrary-script case, but the underlying guarantee
    is identical.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    cfg = _ensure_ready()

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "output_project")

    if not _is_arm_project_file(project):
        return _failure(f"'{project}' is not an existing .arm project file",
                        "output_project")

    if in_place:
        if output_project is not None:
            return _failure(
                "output_project must not be set when in_place=True (the "
                "caller's own project is mutated directly)", "output_project")
        target = project
    else:
        if not output_project:
            return _failure(
                "output_project is required unless in_place=True (mutating "
                "operations default to a copy, never the caller's own file)",
                "output_project")
        try:
            output_project = ensure_within_roots(output_project, cfg.allowed_roots)
        except PathNotAllowed as exc:
            return _failure(str(exc), "output_project")
        # A same-file output_project (directly, or via a directory path that
        # resolves to the same file) would make shutil.copy2 raise -- observed
        # as PermissionError [WinError 32] on this machine, though
        # shutil.copy2 documents SameFileError for the exact-same-path case.
        # Which exception actually fires can vary, so this is checked
        # up front rather than caught by type.
        if os.path.realpath(project) == os.path.realpath(output_project):
            return _failure(
                "output_project must not be the same file as project -- use "
                "in_place=True to edit project itself", "output_project")
        os.makedirs(os.path.dirname(output_project) or ".", exist_ok=True)
        try:
            shutil.copy2(project, output_project)
        except OSError as exc:
            # Any other copy failure (permissions, disk full, etc.) -- convert
            # to this project's standard failure shape instead of letting it
            # escape as an opaque, uncaught exception.
            return _failure(f"failed to copy project to output_project: {exc}",
                            "output_project")
        target = output_project

    script = f"void main() {{\n\t{minic_call}\n\tproject_save(0);\n}}\n"
    result = run_minic_script(cfg.binary, target, script, timeout_s)
    if not result.ok:
        if not in_place:
            # A copy was made at `target` above; it's now a stale, unedited
            # duplicate of the original project (run_minic_script failed
            # before or during project_save(0)). Leaving it on disk would
            # look like a normal, valid .arm file to anyone who finds it
            # later, with no indication it was never actually edited.
            # Best-effort cleanup: a deletion failure must not mask the
            # original error. Never touched when in_place=True, since target
            # there IS the caller's own project.
            try:
                os.remove(target)
            except OSError:
                pass
        return _failure(result.error, "output_project")
    return {"ok": True, "output_project": target, "error": None}


def decimate_mesh(project: str, strength: float, output_project: str | None = None,
                  in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Reduce the project's mesh polycount via ArmorPaint's own decimate
    algorithm (util_mesh_decimate -- a real, working GUI tool as of
    ArmorPaint 1.0, exposed to --script by this project's scoped local
    patch; see ROADMAP.md's "Patch policy"). `strength` is 0.0-1.0-ish
    (ArmorPaint's own GUI default is 0.5); higher removes more geometry.
    Operates on a copy of `project` by default -- pass in_place=True to
    mutate `project` itself instead, in which case output_project must be
    omitted. Requires AP_BINARY to be a build carrying the mesh-edit patch
    (run `ap-mcp --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    ok=True proves the ArmorPaint process completed and saved -- not that
    the reduction looks good; inspect the result yourself for anything
    beyond "did geometry change" (verified by this tool's own test suite via
    real vertex/face counts, not asserted here at runtime).

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    try:
        strength = _finite_float("strength", strength)
    except NodeSpecError as exc:
        return _failure(str(exc), "output_project")
    return _run_mesh_edit(project, f"util_mesh_decimate({strength});",
                          output_project, in_place, timeout_s)


mcp.tool()(decimate_mesh)


def bevel_mesh(project: str, amount: float, output_project: str | None = None,
               in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Bevel the project's mesh edges via ArmorPaint's own bevel algorithm
    (util_mesh_bevel -- exposed to --script by this project's scoped local
    patch; see ROADMAP.md's "Patch policy"). `amount` is the bevel distance
    (ArmorPaint's own GUI default is 0.1). Operates on a copy of `project`
    by default -- pass in_place=True to mutate `project` itself instead, in
    which case output_project must be omitted. Requires AP_BINARY to be a
    build carrying the mesh-edit patch (run `ap-mcp --check` to confirm).
    Bounded by AP_ALLOWED_ROOTS when set.

    ok=True proves the ArmorPaint process completed and saved -- not that
    the bevel looks good.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    try:
        amount = _finite_float("amount", amount)
    except NodeSpecError as exc:
        return _failure(str(exc), "output_project")
    return _run_mesh_edit(project, f"util_mesh_bevel({amount});",
                          output_project, in_place, timeout_s)


mcp.tool()(bevel_mesh)


def subdivide_mesh(project: str, output_project: str | None = None,
                   in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Subdivide the project's mesh via ArmorPaint's own subdivide algorithm
    (util_mesh_subdivide -- exposed to --script by this project's scoped
    local patch; see ROADMAP.md's "Patch policy"). Confirmed empirically to
    be an exact 4x face-count operation on this build. Operates on a copy of
    `project` by default -- pass in_place=True to mutate `project` itself
    instead, in which case output_project must be omitted. Requires
    AP_BINARY to be a build carrying the mesh-edit patch (run `ap-mcp
    --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    ok=True proves only that the ArmorPaint process completed and saved --
    not that the subdivision looks good; inspect the result yourself for
    anything beyond "did geometry change" (verified by this tool's own test
    suite via real face-count diffs, not asserted here at runtime).

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    return _run_mesh_edit(project, "util_mesh_subdivide();",
                          output_project, in_place, timeout_s)


mcp.tool()(subdivide_mesh)


def smooth_mesh(project: str, output_project: str | None = None,
                in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Smooth the project's mesh via ArmorPaint's own smoothing algorithm
    (util_mesh_smooth -- exposed to --script by this project's scoped local
    patch; see ROADMAP.md's "Patch policy"). Does not change vertex/face
    count (confirmed empirically), only vertex positions and normals.
    Operates on a copy of `project` by default -- pass in_place=True to
    mutate `project` itself instead, in which case output_project must be
    omitted. Requires AP_BINARY to be a build carrying the mesh-edit patch
    (run `ap-mcp --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    ok=True proves only that the ArmorPaint process completed and saved --
    not that the smoothing looks good; inspect the result yourself for
    anything beyond "did vertex positions/normals change" (verified by this
    tool's own test suite via real geometry diffs, not asserted here at
    runtime).

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    return _run_mesh_edit(project, "util_mesh_smooth();",
                          output_project, in_place, timeout_s)


mcp.tool()(smooth_mesh)


def duplicate_mesh(project: str, output_project: str | None = None,
                   in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Duplicate the project's mesh object via ArmorPaint's own duplicate
    function (util_mesh_duplicate -- exposed to --script by this project's
    scoped local patch; see ROADMAP.md's "Patch policy"). Confirmed
    empirically to be an exact 2x vertex/face-count operation, adding a
    second object to the scene. Operates on a copy of `project` by default
    -- pass in_place=True to mutate `project` itself instead, in which case
    output_project must be omitted. Requires AP_BINARY to be a build
    carrying the mesh-edit patch (run `ap-mcp --check` to confirm). Bounded
    by AP_ALLOWED_ROOTS when set.

    ok=True proves only that the ArmorPaint process completed and saved --
    not that the duplication looks good; inspect the result yourself for
    anything beyond "did the object/vertex/face count double" (verified by
    this tool's own test suite via real vertex/face counts, not asserted
    here at runtime).

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    return _run_mesh_edit(project, "util_mesh_duplicate();",
                          output_project, in_place, timeout_s)


mcp.tool()(duplicate_mesh)


def merge_mesh_geometry(project: str, output_project: str | None = None,
                        in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Merge every object in the project into one, via ArmorPaint's own
    util_mesh_merge_geometry (exposed to --script by this project's scoped
    local patch; see ROADMAP.md's "Patch policy").

    IMPORTANT: this merges ALL objects in the project, not a specific pair.
    ArmorPaint's GUI "merge with the object below" targeting
    (util_mesh_merge_geometry_down) needs a second minic accessor that does
    not exist -- see ROADMAP.md item 9. There is no way to merge only two
    of three-or-more objects with this tool.

    Requires at least 2 objects in the project -- util_mesh_merge_geometry
    silently no-ops (by its own internal guard) on a project with fewer,
    confirmed empirically. This tool checks the object count itself first
    (via inspect_project's same --api machinery) and returns a clear error
    rather than a false ok=True with zero visible effect.

    Operates on a copy of `project` by default -- pass in_place=True to
    mutate `project` itself instead, in which case output_project must be
    omitted. Requires AP_BINARY to be a build carrying the mesh-edit patch
    (run `ap-mcp --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    cfg = _ensure_ready()

    try:
        checked_project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "output_project")

    if not _is_arm_project_file(checked_project):
        return _failure(f"'{checked_project}' is not an existing .arm project file",
                        "output_project")

    api_result = run_api(cfg.binary, checked_project)
    if not api_result.ok:
        return _failure(api_result.error, "output_project")

    try:
        objects = scene_objects(api_result.text)
    except CatalogError as exc:
        return _failure(str(exc), "output_project")

    if len(objects) < 2:
        return _failure(
            f"project has only {len(objects)} object(s); merge_mesh_geometry "
            f"needs at least 2 (util_mesh_merge_geometry collapses ALL objects "
            f"in the project into one and silently does nothing with fewer -- "
            f"see this tool's docstring for why a specific-pair merge isn't "
            f"possible)", "output_project")

    return _run_mesh_edit(project, "util_mesh_merge_geometry();",
                          output_project, in_place, timeout_s)


mcp.tool()(merge_mesh_geometry)


def unwrap_mesh_uvs(project: str, output_project: str | None = None,
                    in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Re-unwrap the project's mesh UVs via ArmorPaint's own real, built-in
    unwrap algorithm (plugin_uv_unwrap_button -- calls proc_uv_unwrap()
    directly, NOT a loaded plugin despite the C function's name; exposed to
    --script by this project's scoped local patch; see ROADMAP.md's "Patch
    policy"). Confirmed empirically to genuinely change UV coordinates
    (unlike a no-op), unwrap quality/atlas-efficiency vs. xatlas
    (Tool-MeshTriage's unwrapper) has not been compared -- see ROADMAP.md's
    "Known gaps" before relying on this for production-quality UVs.

    Operates on a copy of `project` by default -- pass in_place=True to
    mutate `project` itself instead, in which case output_project must be
    omitted. Requires AP_BINARY to be a build carrying the mesh-edit patch
    (run `ap-mcp --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    ok=True proves only that the ArmorPaint process completed and saved --
    not that the unwrap looks good (that's a separate claim from the
    unverified-quality-vs-xatlas caveat above; verified here only via real
    UV-coordinate diffs showing a change, not asserted here at runtime).

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    return _run_mesh_edit(project, "plugin_uv_unwrap_button();",
                          output_project, in_place, timeout_s)


mcp.tool()(unwrap_mesh_uvs)


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
        return _failure(
            f"unknown preset '{preset}'; available: {', '.join(available)}", "files")

    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
        output_dir = ensure_within_roots(output_dir, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "files")

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
        return _failure(
            f"unknown preset '{preset}'; available: {', '.join(available)}", "files")

    if preset != "generic":
        return _failure(
            (f"create_procedural_material only supports the 'generic' "
             f"preset: the single-process script flow calls "
             f"export_texture_run(), which has no preset argument and "
             f"no minic setter exists for it -- it always exports "
             f"whatever preset last configured the export box, which "
             f"in this headless flow is always ArmorPaint's own "
             f"'generic' fallback. Requesting '{preset}' would either "
             f"time out waiting for files that never arrive, or (for "
             f"a preset whose files are a strict subset of generic's) "
             f"silently report success for the wrong export."), "files")

    try:
        output_dir = ensure_within_roots(output_dir, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "files")

    try:
        script_text = generate_script(node_spec, output_dir)
    except NodeSpecError as exc:
        return _failure(str(exc), "files")

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
        return _failure(str(exc), "objects", "materials", "layers")

    # ArmorPaint silently ignores a bogus --script/project argument and opens
    # its own default empty project instead of failing -- without this check,
    # a typo'd or nonexistent path would report ok:True with that phantom
    # default project's data, which is worse than an error for a read-only
    # reporting tool.
    if not _is_arm_project_file(project):
        return _failure(f"'{project}' is not an existing .arm project file",
                        "objects", "materials", "layers")

    result = run_api(cfg.binary, project)
    if not result.ok:
        return _failure(result.error, "objects", "materials", "layers")

    try:
        state = extract_project_state(result.text)
        objects = scene_objects(result.text)
    except CatalogError as exc:
        return _failure(str(exc), "objects", "materials", "layers")

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
    return {"ok": True, "objects": objects,
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
        return _failure(str(exc), "stdout", "stderr")

    # Same phantom-default-project trap inspect_project guards against
    # (Phase 3 Finding 2): a bogus/nonexistent project path makes ArmorPaint
    # silently open its own empty default project instead of failing, which
    # would let the caller's script run against nothing while still
    # reporting ok: True.
    if not _is_arm_project_file(project):
        return _failure(f"'{project}' is not an existing .arm project file",
                        "stdout", "stderr")

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
