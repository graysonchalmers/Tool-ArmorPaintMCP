"""Pure-Python pieces of replace_mesh (docs/PLAN.md 6.3): pre-checks, the
minic script, and lookups into ArmorPaint's --api project state. Every
minic statement here was verified against a real build in Phase 6 spikes
S4/S5 (docs/superpowers/spikes/2026-09-27-phase6-spikes-S1-S2-S4-S5.md)."""

import os
import re

from armorpaint_mcp import uv_analysis
from armorpaint_mcp.script_gen import minic_path_literal, minic_string_literal

# Mesh formats this build imports natively: path_mesh_formats() lists obj and
# blend (base/sources/iron_path.c:28-35) and WITH_PLUGINS (paint/project.c:14)
# registers gltf/glb/fbx (paint/plugins/plugins.c:167-172). Not exposed by
# --api, so hardcoded with this citation. Any other extension would reach an
# importer lookup that is called without a NULL check (io/import_mesh.c:39-42).
REPLACEMENT_FORMATS = ("obj", "fbx", "glb", "gltf", "blend")
REPLACED_PLACEHOLDER = "__ap_mcp_replaced__"
ERROR_MARKER = "REPLACE_ERR"


class ReplaceError(Exception):
    """The replacement can't be applied; the message is caller-facing."""


def precheck_replacement(path: str, allow_udim: bool) -> None:
    """Reject a replacement before ArmorPaint launches. Only OBJ can be read
    here: it must hold exactly one object (several `o` groups append several
    objects, io/import_mesh.c:49-57), every face must have UVs (missing ones
    come out as uninitialized memory, io/import_mesh.c:260-263), and UVs must
    stay in [0,1] unless allow_udim (the importer folds larger values,
    base/sources/iron_obj.c:628-638). Other formats are checked after the
    run by replace_mesh's post-verify."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext not in REPLACEMENT_FORMATS:
        raise ReplaceError(f"unsupported mesh format '.{ext}'; this ArmorPaint build "
                           f"imports: {', '.join(REPLACEMENT_FORMATS)}")
    if ext != "obj":
        return
    with open(path, encoding="utf-8", errors="replace") as fh:
        obj = uv_analysis.parse_obj(fh.read())
    groups = [g for g in obj.groups if g.faces]
    if len(groups) != 1:
        raise ReplaceError(f"the replacement OBJ has {len(groups)} objects; it must "
                           f"hold exactly one (each `o` group would become its own object)")
    metrics = uv_analysis.analyze(obj, groups[0])
    if metrics["faces_without_uv"]:
        raise ReplaceError(f"the replacement OBJ has no UVs on {metrics['faces_without_uv']} "
                           f"face(s); UV-unwrap it before replacing")
    if metrics["out_of_range_uvs"] and not allow_udim:
        raise ReplaceError(f"the replacement OBJ has {metrics['out_of_range_uvs']} UV(s) "
                           f"outside [0,1], which ArmorPaint's importer folds; pass "
                           f"allow_udim=True for a UDIM layout")


def object_names(state: dict) -> list[str]:
    """Paint-object names in paint_objects order. Index arrays
    (mesh_transforms, mesh_parents[i32], mesh_materials[i32]) follow this
    order; inspect_project's scene-text list does not once objects are
    parented (spike A, contradiction 6)."""
    return [m.get("name") for m in state.get("mesh_datas") or []]


def _index(state: dict, name: str) -> int:
    names = object_names(state)
    if name not in names:
        raise ReplaceError(f"no object named '{name}' (objects: {', '.join(names)})")
    return names.index(name)


def local_transform(state: dict, name: str) -> list[float]:
    return state["mesh_transforms"][_index(state, name)]


def parent_name(state: dict, name: str) -> str | None:
    parents = state.get("mesh_parents[i32]") or []
    i = _index(state, name)
    p = parents[i] if i < len(parents) else -1
    return None if p < 0 else object_names(state)[p]


def material_override_name(state: dict, object_name: str) -> str | None:
    """The name of `object_name`'s material override, or None if it uses the
    project default (-1). minic can't enumerate materials, so the script
    looks the material up by this name -- which only works if it's unique."""
    mats = state.get("mesh_materials[i32]") or []
    i = _index(state, object_name)
    idx = mats[i] if i < len(mats) else -1
    if idx < 0:
        return None
    nodes = state.get("material_nodes") or []
    name = nodes[idx].get("name")
    if [n.get("name") for n in nodes].count(name) > 1:
        raise ReplaceError(f"'{object_name}' uses material '{name}', but that name isn't "
                           f"unique in the project, so it can't be carried over; rename it")
    return name


def build_replace_script(old_name: str, new_mesh: str, fresh: str,
                         material_name: str | None) -> str:
    """The minic replace-with-carry-over script (spike A's verified snippet):
    rename the old object out of the way, append, move children, remove the
    old object, then restore name, parent, transform and material, and save
    to `fresh` as the LAST statement. Guards print a REPLACE_ERR marker and
    return early (so nothing is saved) if the old object is missing, the
    append silently did nothing (e.g. .blend without ArmorPaint's Blender
    path), or the material lookup doesn't match."""
    old = minic_string_literal(old_name, "old_object")
    placeholder = minic_string_literal(REPLACED_PLACEHOLDER, "placeholder")
    mesh = minic_path_literal(new_mesh, "new_mesh", backslashes=True)
    save_to = minic_path_literal(fresh, "output path")
    err = ERROR_MARKER
    lines = [
        f"object_t *old = script_get_object({old});",
        f'if (old == NULL) {{ console_log("{err} old_not_found"); return; }}',
        "char *oname = string_copy(old->name);",
        "transform_t *ot = old->transform;",
        "float lx = ot->loc.x; float ly = ot->loc.y; float lz = ot->loc.z;",
        "float rx = ot->rot.x; float ry = ot->rot.y; float rz = ot->rot.z; float rw = ot->rot.w;",
        "float sx = ot->scale.x; float sy = ot->scale.y; float sz = ot->scale.z;",
        "object_t *op = old->parent;",
    ]
    if material_name is not None:
        lines += ["mesh_object_t *omo = old->ext;",
                  "char *omat = string_copy(omo->material->name);"]
    lines += [
        f"script_object_set_name(old, {placeholder});",
        "context_t *cx = script_get_context();",
        "mesh_object_t *before = cx->paint_object;",
        f"script_append_mesh({mesh});",
        "mesh_object_t *nmo = cx->paint_object;",
        f'if (nmo == before) {{ console_log("{err} append_failed"); return; }}',
        "object_t *nw = nmo->base;",
        "int nc = old->children->length;",
        "for (int i = 0; i < nc; i++) { object_t *c = old->children->buffer[0]; object_set_parent(c, nw); }",
        "script_object_remove(old);",
        "script_object_set_name(nw, oname);",
        "object_set_parent(nw, op);",
        "transform_t *nt = nw->transform;",
        "nt->loc.x = lx; nt->loc.y = ly; nt->loc.z = lz;",
        "nt->rot.x = rx; nt->rot.y = ry; nt->rot.z = rz; nt->rot.w = rw;",
        "nt->scale.x = sx; nt->scale.y = sy; nt->scale.z = sz;",
        "transform_build_matrix(nt);",
    ]
    if material_name is not None:
        mat = minic_string_literal(material_name, "material name")
        lines += [
            f"slot_material_t *m = script_get_material({mat});",
            f'if (m == NULL) {{ console_log("{err} material_not_found"); return; }}',
            "string_array_t *mk = string_array_create(0);",
            'string_array_push(mk, "_material_"); string_array_push(mk, i32_to_string(m->id));',
            f'if (!string_equals(omat, string_array_join(mk, ""))) {{ console_log("{err} material_ambiguous"); return; }}',
            "script_object_set_material(nw, m);",
        ]
    else:
        lines.append("script_object_set_material(nw, NULL);")
    lines += [f"project_filepath_set({save_to});", "project_save(0);"]
    return "void main() {\n" + "".join(f"\t{line}\n" for line in lines) + "}\n"


_MARKER_RE = re.compile(rf"^{ERROR_MARKER} (\S+)", re.MULTILINE)


def marker_error(stdout: str) -> str | None:
    match = _MARKER_RE.search(stdout or "")
    return match.group(1) if match else None
