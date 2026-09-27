import os
import sys
import tempfile
import uuid

from mcp.server.mcpserver import MCPServer

from armorpaint_mcp import __version__, uv_analysis
from armorpaint_mcp import replace as rp
from armorpaint_mcp.config import load_config, require_valid
from armorpaint_mcp.doctor import run_check
from armorpaint_mcp.catalog import (CatalogError, extract_project_state,
                                    layer_blend_modes, scene_objects)
from armorpaint_mcp.paths import ensure_within_roots, PathNotAllowed
from armorpaint_mcp.runner import (DEFAULT_TIMEOUT_S, ScriptResult, export_textures,
                                   list_export_presets, run_api, run_minic_script,
                                   run_procedural_material)
from armorpaint_mcp.script_gen import (_finite_float, generate_script, minic_path_literal,
                                       NodeSpecError)

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


def _argv_path_error(path: str, what: str) -> str | None:
    """An error message if `path` can't survive ArmorPaint's command line,
    else None. Call it on every path ArmorPaint receives as an argv argument
    (not paths written inside a --script file, which arrive as UTF-8), before
    launching. ArmorPaint's Windows build reads argv as ANSI
    (base/sources/backends/windows_system.c: WinMain passes __argv), then
    decodes it as UTF-8 (base/sources/iron_file.c), so any non-ASCII character
    corrupts the path. The project then fails to open, ArmorPaint only logs
    "Could not open file" (paint/sources/io/import_arm.c), keeps its default
    scene, and still runs the script: a saving tool would save the default
    scene with ok=True (Known Issue #12). Spaces are fine."""
    if path.isascii():
        return None
    return (f"{what} '{path}' contains non-ASCII characters, which ArmorPaint "
            f"cannot open: its Windows build receives command-line paths as "
            f"ANSI (argv), so the path arrives corrupted and ArmorPaint would "
            f"silently use its default scene instead -- use an ASCII-only path "
            f"(spaces are fine)")


def _resolve_edit_target(project: str, output_project: str | None,
                         in_place: bool, cfg,
                         output_via_argv: bool = False) -> tuple[str, str] | dict:
    """Validate a saving tool's inputs. Returns (project, target) -- both
    absolute and inside AP_ALLOWED_ROOTS, target's directory created -- or
    a _failure(..., "output_project") dict. Mutating tools default to a new
    output file; in_place=True targets the caller's own project. `project`
    always reaches ArmorPaint via argv; pass output_via_argv=True when the
    tool also re-opens the output that way (checked before the directory is
    created)."""
    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "output_project")
    if not _is_arm_project_file(project):
        return _failure(f"'{project}' is not an existing .arm project file",
                        "output_project")
    if (error := _argv_path_error(project, "project")) is not None:
        return _failure(error, "output_project")
    if in_place:
        if output_project is not None:
            return _failure(
                "output_project must not be set when in_place=True (the "
                "caller's own project is mutated directly)", "output_project")
        return project, project
    if not output_project:
        return _failure(
            "output_project is required unless in_place=True (mutating "
            "operations default to a copy, never the caller's own file)",
            "output_project")
    try:
        output_project = ensure_within_roots(output_project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "output_project")
    if os.path.realpath(project) == os.path.realpath(output_project):
        return _failure(
            "output_project must not be the same file as project -- use "
            "in_place=True to edit project itself", "output_project")
    if output_via_argv and (error := _argv_path_error(output_project, "output_project")):
        return _failure(error, "output_project")
    try:
        os.makedirs(os.path.dirname(output_project) or ".", exist_ok=True)
    except OSError as exc:
        return _failure(f"could not create output_project's directory: {exc}",
                        "output_project")
    return project, output_project


def _fresh_sibling(target: str) -> str:
    """A not-yet-existing save path next to `target`. Saving beside the final
    location matters: .arm files store asset paths relative to themselves
    (io/export_arm.c), so a file saved elsewhere and moved would break them
    (Known Issue #11). The random part keeps a crashed run's leftover from
    ever colliding with a new one."""
    stem = os.path.splitext(os.path.basename(target))[0]
    return os.path.join(os.path.dirname(os.path.abspath(target)),
                        f"{stem}.ap-mcp-{uuid.uuid4().hex[:12]}.tmp.arm")


def _save_script(body_lines: list[str], fresh: str) -> str:
    """`body_lines` wrapped in void main(), then save to `fresh`. The save is
    deliberately LAST: a minic error after project_save would still leave a
    saved file, so nothing may follow it (Phase 6 spike S2)."""
    save_to = minic_path_literal(fresh, "output path")
    lines = ["void main() {", *(f"\t{line}" for line in body_lines),
             f"\tproject_filepath_set({save_to});", "\tproject_save(0);", "}", ""]
    return "\n".join(lines)


def _run_saving_script(cfg, project: str, script: str, fresh: str,
                       timeout_s: float) -> ScriptResult:
    """Run a _save_script against the caller's ORIGINAL `project` (opened,
    never written). Success requires, in order: exit code 0 and no timeout,
    no minic error line (both run_minic_script), and `fresh` existing
    afterwards -- a script that returned early prints nothing, and only the
    file proves project_save ran."""
    result = run_minic_script(cfg.binary, project, script, timeout_s)
    if result.ok and not os.path.isfile(fresh):
        return ScriptResult(ok=False, stdout=result.stdout, stderr=result.stderr, error=(
            "ArmorPaint finished without saving: the script stopped before "
            "project_save and printed no error"))
    return result


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _run_mesh_edit(project: str, minic_call: str, output_project: str | None,
                   in_place: bool, timeout_s: float) -> dict:
    """Shared plumbing for every mesh-edit tool: open the caller's project
    (never writing it), run `minic_call`, save to a fresh sibling of the
    target, then move that over the target. A failure at any point leaves
    the target untouched and no temp file behind.

    ok=True means ArmorPaint exited cleanly, printed no minic error, and
    saved the edited project -- not that the edit looks good.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    cfg = _ensure_ready()
    resolved = _resolve_edit_target(project, output_project, in_place, cfg)
    if isinstance(resolved, dict):
        return resolved
    project, target = resolved
    fresh = _fresh_sibling(target)
    try:
        script = _save_script([minic_call], fresh)
    except NodeSpecError as exc:
        return _failure(str(exc), "output_project")
    try:
        result = _run_saving_script(cfg, project, script, fresh, timeout_s)
        error = result.error
        if result.ok:
            os.replace(fresh, target)
    except OSError as exc:
        error = f"could not write output_project: {exc}"
    finally:
        _remove_quietly(fresh)
    if error is not None:
        return _failure(error, "output_project")
    return {"ok": True, "output_project": target, "error": None}


def decimate_mesh(project: str, strength: float, output_project: str | None = None,
                  in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Reduce the project's mesh polycount via ArmorPaint's own decimate
    algorithm (util_mesh_decimate -- a real, working GUI tool as of
    ArmorPaint 1.0, exposed to --script by this project's scoped local
    patch; see ROADMAP.md's "Patch policy"). `strength` is 0.0-1.0-ish
    (ArmorPaint's own GUI default is 0.5); higher removes more geometry.
    Writes the result to `output_project` by default (the caller's `project`
    is never modified) -- pass in_place=True to mutate `project` itself
    instead, in which case output_project must be omitted. Requires
    AP_BINARY to be a build carrying the mesh-edit patch (run `ap-mcp
    --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    ok=True means ArmorPaint exited cleanly, printed no script error, and
    saved the result -- not that the reduction looks good; inspect the result yourself for anything
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
    (ArmorPaint's own GUI default is 0.1). Writes the result to
    `output_project` by default (the caller's `project` is never modified)
    -- pass in_place=True to mutate `project` itself instead, in which case
    output_project must be omitted. Requires AP_BINARY to be a build
    carrying the mesh-edit patch (run `ap-mcp --check` to confirm).
    Bounded by AP_ALLOWED_ROOTS when set.

    ok=True means ArmorPaint exited cleanly, printed no script error, and
    saved the result -- not that the bevel looks good.

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
    be an exact 4x face-count operation on this build. Writes the result to
    `output_project` by default (the caller's `project` is never modified)
    -- pass in_place=True to mutate `project` itself instead, in which case
    output_project must be omitted. Requires AP_BINARY to be a build
    carrying the mesh-edit patch (run `ap-mcp --check` to confirm). Bounded
    by AP_ALLOWED_ROOTS when set.

    ok=True means ArmorPaint exited cleanly, printed no script error, and
    saved the result -- not that the subdivision looks good; inspect the result yourself for
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
    Writes the result to `output_project` by default (the caller's `project`
    is never modified) -- pass in_place=True to mutate `project` itself
    instead, in which case output_project must be omitted. Requires
    AP_BINARY to be a build carrying the mesh-edit patch (run `ap-mcp
    --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    ok=True means ArmorPaint exited cleanly, printed no script error, and
    saved the result -- not that the smoothing looks good; inspect the result yourself for
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
    second object to the scene. Writes the result to `output_project` by
    default (the caller's `project` is never modified) -- pass
    in_place=True to mutate `project` itself instead, in which case
    output_project must be omitted. Requires AP_BINARY to be a build
    carrying the mesh-edit patch (run `ap-mcp --check` to confirm). Bounded
    by AP_ALLOWED_ROOTS when set.

    ok=True means ArmorPaint exited cleanly, printed no script error, and
    saved the result -- not that the duplication looks good; inspect the result yourself for
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

    Writes the result to `output_project` by default (the caller's `project`
    is never modified) -- pass in_place=True to mutate `project` itself
    instead, in which case output_project must be omitted. Requires
    AP_BINARY to be a build carrying the mesh-edit patch (run `ap-mcp
    --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    cfg = _ensure_ready()

    try:
        checked_project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "output_project")

    if not _is_arm_project_file(checked_project):
        return _failure(f"'{checked_project}' is not an existing .arm project file",
                        "output_project")
    if (error := _argv_path_error(checked_project, "project")) is not None:
        return _failure(error, "output_project")

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
    unwrap algorithm (util_mesh_uv_unwrap; exposed to --script upstream via
    #2139, renamed from plugin_uv_unwrap_button in 01bae6c5; see ROADMAP.md's
    "Patch policy"). Confirmed empirically to genuinely change UV coordinates
    (unlike a no-op), unwrap quality/atlas-efficiency vs. xatlas
    (Tool-MeshTriage's unwrapper) has not been compared -- see ROADMAP.md's
    "Known gaps" before relying on this for production-quality UVs.

    Writes the result to `output_project` by default (the caller's `project`
    is never modified) -- pass in_place=True to mutate `project` itself
    instead, in which case output_project must be omitted. Requires
    AP_BINARY to be a build carrying the mesh-edit patch (run `ap-mcp
    --check` to confirm). Bounded by AP_ALLOWED_ROOTS when set.

    ok=True means ArmorPaint exited cleanly, printed no script error, and
    saved the result -- not that the unwrap looks good (that's a separate claim from the
    unverified-quality-vs-xatlas caveat above; verified here only via real
    UV-coordinate diffs showing a change, not asserted here at runtime).

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    return _run_mesh_edit(project, "util_mesh_uv_unwrap();",
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
    for path, what in ((project, "project"), (output_dir, "output_dir")):
        if (error := _argv_path_error(path, what)) is not None:
            return _failure(error, "files")

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
    if (error := _argv_path_error(project, "project")) is not None:
        return _failure(error, "objects", "materials", "layers")

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


def _export_obj(cfg, project: str, out_path: str,
                timeout_s: float) -> tuple[str | None, str | None]:
    """Export `project`'s meshes to `out_path` via script_export_mesh (one
    `o <name>` group per paint object, object-local coordinates -- spike S1)
    and return (text, None), or (None, error)."""
    try:
        target = minic_path_literal(out_path, "export path")
    except NodeSpecError as exc:
        return None, str(exc)
    script = f"void main() {{\n\tscript_export_mesh({target});\n}}\n"
    result = run_minic_script(cfg.binary, project, script, timeout_s)
    if not result.ok:
        return None, result.error
    if not os.path.isfile(out_path):
        return None, "ArmorPaint finished without writing the mesh export"
    with open(out_path, encoding="utf-8", errors="replace") as fh:
        return fh.read(), None


def check_mesh_uvs(project: str, allow_udim: bool = False,
                   timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Read-only UV validity report for every object in an existing .arm
    project. Exports the meshes through ArmorPaint and analyzes the UVs in
    Python (docs/PLAN.md 6.2); makes no changes to the project. Bounded by
    AP_ALLOWED_ROOTS when set.

    Per object, `errors` make `valid` false: faces without UVs, UV-degenerate
    triangles covering more than 0.1% of the 3D surface (paint can't land
    there), and UVs outside [0,1] (a warning instead with allow_udim=True).
    `warnings` are often deliberate: overlapping UVs (stacked/mirrored
    islands) and flipped UV triangles. `metrics` carries the numbers
    (coverage_pct, overlap_pct, flipped_pct, uv_islands, ...). ArmorPaint's
    importer folds UVs above 1 into [0,1] (base/sources/iron_obj.c), so an
    imported project rarely shows out-of-range UVs even if its source had
    them.

    Returns {"ok": bool, "valid": bool | None, "objects": [{"name", "valid",
    "errors", "warnings", "metrics"}] | None, "error": str | None}."""
    cfg = _ensure_ready()
    try:
        project = ensure_within_roots(project, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _failure(str(exc), "valid", "objects")
    if not _is_arm_project_file(project):
        return _failure(f"'{project}' is not an existing .arm project file",
                        "valid", "objects")
    if (error := _argv_path_error(project, "project")) is not None:
        return _failure(error, "valid", "objects")
    with tempfile.TemporaryDirectory(prefix="ap-mcp-") as tmp:
        text, error = _export_obj(cfg, project, os.path.join(tmp, "mesh.obj"), timeout_s)
    if error is not None:
        return _failure(error, "valid", "objects")
    obj = uv_analysis.parse_obj(text)
    objects = []
    for name, group in uv_analysis.groups_by_name(obj).items():
        metrics = uv_analysis.analyze(obj, group)
        objects.append({"name": name, **uv_analysis.verdict(metrics, allow_udim),
                        "metrics": metrics})
    return {"ok": True, "valid": all(o["valid"] for o in objects),
            "objects": objects, "error": None}


mcp.tool()(check_mesh_uvs)


def _project_state(cfg, project: str, timeout_s: float) -> tuple[dict | None, str | None]:
    """(--api project-state JSON, None) or (None, error)."""
    result = run_api(cfg.binary, project, timeout_s)
    if not result.ok:
        return None, result.error
    try:
        return extract_project_state(result.text), None
    except CatalogError as exc:
        return None, str(exc)


_REPLACE_FIELDS = ("output_project", "iou", "retention", "warnings")


def _replace_failure(error: str) -> dict:
    return _failure(error, *_REPLACE_FIELDS)


def _replace_uv_gate(before_text: str, after_text: str, old_object: str, mode: str,
                     allow_udim: bool, n_objects: int) -> tuple[dict, str | None]:
    """UV checks on the replaced object: its UVs must be valid (both modes);
    in round_trip mode its layout must match the old one (IoU and texel
    retention, thresholds in uv_analysis). Returns ({"iou", "retention",
    "warnings"}, error-or-None)."""
    before_obj, after_obj = uv_analysis.parse_obj(before_text), uv_analysis.parse_obj(after_text)
    old_g = uv_analysis.groups_by_name(before_obj)[old_object]
    new_g = uv_analysis.groups_by_name(after_obj)[old_object]
    check = uv_analysis.verdict(uv_analysis.analyze(after_obj, new_g), allow_udim)
    if not check["valid"]:
        # before compare_layouts: a UV-less mesh has no rasterizable triangles
        return ({"iou": None, "retention": None, "warnings": list(check["warnings"])},
                "the replacement's UVs are invalid: " + "; ".join(check["errors"]))
    cmp = uv_analysis.compare_layouts(before_obj, old_g, after_obj, new_g)
    gate = {"iou": cmp["iou"], "retention": cmp["retention"], "warnings": list(check["warnings"])}
    ratio = cmp["size_ratio"]
    ratio_lo, ratio_hi = uv_analysis.SIZE_RATIO_WARN
    if ratio and not ratio_lo <= ratio <= ratio_hi:
        gate["warnings"].append(
            f"the new mesh is {ratio:.3g}x the old one's size (a Blender FBX lands at "
            f"100x: check the export's unit scale)")
    if n_objects > 1:
        gate["warnings"].append(
            "ArmorPaint's Reimport Mesh would now reload only the replacement file and "
            "remove the project's other objects")
    if mode == "round_trip":
        if cmp["iou"] < uv_analysis.IOU_MIN:
            return gate, (f"the UV layout changed (IoU {cmp['iou']} < {uv_analysis.IOU_MIN}); "
                          f"the paint would scramble -- use mode='swap' if that's expected")
        retention = cmp["retention"]
        if retention is not None and retention < uv_analysis.RETENTION_MIN:
            return gate, (f"only {retention:.0%} of painted texels would stay in place "
                          f"(retention {retention} < {uv_analysis.RETENTION_MIN}); use "
                          f"mode='swap' if the mesh really changed that much")
        if retention is not None and retention < uv_analysis.RETENTION_WARN:
            gate["warnings"].append(
                f"{1 - retention:.1%} of painted texels move by more than "
                f"{uv_analysis.RETENTION_TOL:.0%} of the object's size")
    return gate, None


def replace_mesh(project: str, old_object: str, new_mesh: str, mode: str = "round_trip",
                 allow_udim: bool = False, output_project: str | None = None,
                 in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Replace one object's mesh with `new_mesh` (obj, fbx, glb, gltf, or
    blend -- the last needs ArmorPaint's own Blender path configured),
    keeping every layer, every other object, and the replaced object's name,
    transform, parent, children and material. ArmorPaint's own mesh import
    would clear every layer instead.

    Paint lives in UV space, so it carries over unchanged only if the new
    mesh keeps the old UV layout. mode="round_trip" (default) is for the same
    asset re-exported with edited geometry and UVs kept: it fails unless the
    UV layouts match (UV-coverage IoU >= 0.95 and >= 85% of painted texels
    landing where they were in 3D; warning below 98%). mode="swap" is for a
    different mesh: paint is expected to scramble, and the numbers are
    reported but not enforced. Either way the new mesh must have valid UVs.

    Writes to `output_project` by default (the caller's `project` is never
    modified); in_place=True replaces `project` itself, only after the
    result verifies. Warnings (not failures): a new mesh more than 2x off
    the old one's size (a Blender FBX lands at 100x), UV warnings from
    check_mesh_uvs, and -- on multi-object projects -- that ArmorPaint's
    Reimport Mesh would now reload only `new_mesh` and drop the other
    objects. Bounded by AP_ALLOWED_ROOTS when set.

    Returns {"ok": bool, "output_project": str | None, "iou": float | None,
    "retention": float | None, "warnings": [str] | None, "error": str | None}."""
    if mode not in ("round_trip", "swap"):
        return _replace_failure(f"mode must be 'round_trip' or 'swap', got {mode!r}")
    cfg = _ensure_ready()
    # The result is re-opened via argv (--api, --script) from a fresh sibling
    # of the target, so the target path must survive argv too.
    resolved = _resolve_edit_target(project, output_project, in_place, cfg,
                                    output_via_argv=True)
    if isinstance(resolved, dict):
        return _replace_failure(resolved["error"])
    project, target = resolved
    try:
        new_mesh = ensure_within_roots(new_mesh, cfg.allowed_roots)
    except PathNotAllowed as exc:
        return _replace_failure(str(exc))
    if not os.path.isfile(new_mesh):
        return _replace_failure(f"new_mesh '{new_mesh}' does not exist")
    try:
        rp.precheck_replacement(new_mesh, allow_udim)
    except rp.ReplaceError as exc:
        return _replace_failure(str(exc))

    before, error = _project_state(cfg, project, timeout_s)
    if error is not None:
        return _replace_failure(error)
    fresh = _fresh_sibling(target)
    try:
        names_before = rp.object_names(before)
        duplicates = names_before.count(old_object)
        if duplicates > 1:
            raise rp.ReplaceError(
                f"'{old_object}' matches {duplicates} objects in the project "
                f"(names: {', '.join(names_before)}); rename the duplicates so "
                f"the replace can target one unambiguously")
        material = rp.material_override_name(before, old_object)  # also checks it exists
        script = rp.build_replace_script(old_object, new_mesh, fresh, material)
    except (rp.ReplaceError, NodeSpecError, KeyError, IndexError, TypeError,
            AttributeError) as exc:
        if isinstance(exc, (KeyError, IndexError, TypeError, AttributeError)):
            return _replace_failure(f"unexpected project state: {exc}")
        return _replace_failure(str(exc))

    warnings: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="ap-mcp-") as tmp:
            before_text, error = _export_obj(cfg, project, os.path.join(tmp, "before.obj"), timeout_s)
            if error is not None:
                return _replace_failure(error)
            result = _run_saving_script(cfg, project, script, fresh, timeout_s)
            marker = rp.marker_error(result.stdout)
            if marker is not None:
                detail = (result.stderr or "").strip()
                return _replace_failure(f"replace aborted: {marker}" + (f" ({detail})" if detail else ""))
            if not result.ok:
                return _replace_failure(result.error)
            after, error = _project_state(cfg, fresh, timeout_s)
            if error is not None:
                return _replace_failure(error)
            after_text, error = _export_obj(cfg, fresh, os.path.join(tmp, "after.obj"), timeout_s)
            if error is not None:
                return _replace_failure(error)

        problem = _verify_replace_structure(before, after, names_before, old_object,
                                            before_text, after_text, new_mesh)
        if problem is not None:
            return _replace_failure(f"replace did not verify: {problem}")
        gate, problem = _replace_uv_gate(before_text, after_text, old_object, mode,
                                         allow_udim, len(names_before))
        if problem is not None:
            return _replace_failure(f"{problem} (IoU {gate['iou']}, retention {gate['retention']})")
        warnings = gate["warnings"]
        os.replace(fresh, target)
    except (OSError, KeyError, IndexError, TypeError, AttributeError,
            ValueError, rp.ReplaceError) as exc:
        if isinstance(exc, OSError):
            return _replace_failure(f"could not write output_project: {exc}")
        if isinstance(exc, rp.ReplaceError):
            return _replace_failure(f"replace did not verify: {exc}")
        return _replace_failure(f"unexpected project state: {exc}")
    finally:
        _remove_quietly(fresh)
    return {"ok": True, "output_project": target, "iou": gate["iou"], "retention": gate["retention"],
            "warnings": warnings, "error": None}


def _verify_replace_structure(before: dict, after: dict, names_before: list[str],
                              old_object: str, before_text: str, after_text: str,
                              new_mesh: str) -> str | None:
    """Everything that must hold after a replace, or a description of the
    first thing that doesn't (docs/PLAN.md 6.3 post-verify)."""
    names_after = rp.object_names(after)
    if rp.REPLACED_PLACEHOLDER in names_after:
        return "the old object is still present (hidden, not removed -- multi-stage project?)"
    if sorted(names_after) != sorted(names_before):
        return f"objects changed from {sorted(names_before)} to {sorted(names_after)}"
    if len(after.get("layer_datas") or []) != len(before.get("layer_datas") or []):
        return "the layer count changed"
    for name in names_before:
        if rp.parent_name(after, name) != rp.parent_name(before, name):
            return f"'{name}' changed parent"
        old_t, new_t = rp.local_transform(before, name), rp.local_transform(after, name)
        if any(abs(a - b) > 1e-4 for a, b in zip(old_t, new_t)):
            return f"'{name}' changed transform"
    if rp.material_override_name(after, old_object) != rp.material_override_name(before, old_object):
        return f"'{old_object}' lost its material"
    before_obj = uv_analysis.parse_obj(before_text)
    after_obj = uv_analysis.parse_obj(after_text)
    before_groups = uv_analysis.groups_by_name(before_obj)
    after_groups = uv_analysis.groups_by_name(after_obj)
    for name in names_before:
        if name == old_object:
            continue
        if (uv_analysis.group_signature(before_obj, before_groups[name])
                != uv_analysis.group_signature(after_obj, after_groups[name])):
            return f"untouched object '{name}' changed geometry"
    replaced = after_groups.get(old_object)
    if replaced is None or not replaced.tri_v:
        return f"'{old_object}' has no geometry after the replace"
    if new_mesh.lower().endswith(".obj"):
        with open(new_mesh, encoding="utf-8", errors="replace") as fh:
            source = uv_analysis.parse_obj(fh.read())
        expected = sum(len(g.tri_v) for g in source.groups)
        if len(replaced.tri_v) != expected:
            return (f"'{old_object}' has {len(replaced.tri_v)} triangles, but the "
                    f"replacement has {expected}")
    return None


mcp.tool()(replace_mesh)


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

    A minic script error (unknown function, bad field, null pointer, syntax
    error) returns ok=False with the "<script>:N: error: ..." line(s) in
    `error` -- the process itself exits 0 either way. ok=True means the
    process finished and printed no script error; it is still not proof the
    script did what you meant (a script that returns early prints nothing),
    so verify results yourself (e.g. call inspect_project afterward). The
    `project` path is bounded by AP_ALLOWED_ROOTS when set; the script body
    itself is not sandboxed and can read/write anywhere the ArmorPaint
    process has OS-level permission to.

    `stdout`/`stderr` carry the script's console_log()/printf output and
    ArmorPaint's own messages (e.g. "Project saved") -- and, on a script
    error, the "<script>:N: error: ..." line(s) that caused ok=False, so
    they stay populated on failure too. They are only `None` when the
    project/path check rejects the call before ArmorPaint ever launches
    (e.g. `project` outside AP_ALLOWED_ROOTS, or not an existing .arm file).

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
    if (error := _argv_path_error(project, "project")) is not None:
        return _failure(error, "stdout", "stderr")

    result = run_minic_script(cfg.binary, project, script, timeout_s)
    return {"ok": result.ok, "stdout": result.stdout, "stderr": result.stderr,
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
