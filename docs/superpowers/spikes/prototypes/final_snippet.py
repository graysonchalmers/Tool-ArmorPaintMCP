"""The uninstrumented replace-with-carry-over composition, as a tool would emit it."""


def gen(old_name, new_path_bk, fresh_out, mat_name=None, carry_parent=True,
        move_children=True, export_path=None):
    """old_name / mat_name: pre-checked in Python (no double quotes).
    new_path_bk: backslash path, each '\\' doubled for the minic literal (REQUIRED:
    forward slashes make script_append_mesh's iron_file_exists check fail).
    fresh_out: a not-yet-existing path in the TARGET's directory.
    mat_name: canvas name of the old object's override material, or None when
    the old object's mesh_materials entry is -1."""
    L = []
    a = L.append
    a(f'\tobject_t *old = script_get_object("{old_name}");')
    a('\tif (old == NULL) { console_log("REPLACE_ERR old_not_found"); return; }')
    a('\tchar *oname = string_copy(old->name);')
    a('\ttransform_t *ot = old->transform;')
    a('\tfloat lx = ot->loc.x; float ly = ot->loc.y; float lz = ot->loc.z;')
    a('\tfloat rx = ot->rot.x; float ry = ot->rot.y; float rz = ot->rot.z; float rw = ot->rot.w;')
    a('\tfloat sx = ot->scale.x; float sy = ot->scale.y; float sz = ot->scale.z;')
    if carry_parent:
        a('\tobject_t *op = old->parent;')
    if mat_name is not None:
        a('\tmesh_object_t *omo = old->ext;')
        a('\tchar *omat = string_copy(omo->material->name);')
    a('\tscript_object_set_name(old, "__ap_mcp_replaced__");')
    a('\tcontext_t *cx = script_get_context();')
    a('\tmesh_object_t *before = cx->paint_object;')
    a(f'\tscript_append_mesh("{new_path_bk}");')
    a('\tmesh_object_t *nmo = cx->paint_object;')
    a('\tif (nmo == before) { console_log("REPLACE_ERR append_failed"); return; }')
    a('\tobject_t *nw = nmo->base;')
    if move_children:
        a('\tint nc = old->children->length;')
        a('\tfor (int i = 0; i < nc; i++) { object_t *c = old->children->buffer[0]; object_set_parent(c, nw); }')
    a('\tscript_object_remove(old);')
    a('\tscript_object_set_name(nw, oname);')
    if carry_parent:
        a('\tobject_set_parent(nw, op);')
    a('\ttransform_t *nt = nw->transform;')
    a('\tnt->loc.x = lx; nt->loc.y = ly; nt->loc.z = lz;')
    a('\tnt->rot.x = rx; nt->rot.y = ry; nt->rot.z = rz; nt->rot.w = rw;')
    a('\tnt->scale.x = sx; nt->scale.y = sy; nt->scale.z = sz;')
    a('\ttransform_build_matrix(nt);')
    if mat_name is not None:
        a(f'\tslot_material_t *m = script_get_material("{mat_name}");')
        a('\tif (m == NULL) { console_log("REPLACE_ERR material_not_found"); return; }')
        a('\tstring_array_t *mk = string_array_create(0);')
        a('\tstring_array_push(mk, "_material_"); string_array_push(mk, i32_to_string(m->id));')
        a('\tif (!string_equals(omat, string_array_join(mk, ""))) { console_log("REPLACE_ERR material_ambiguous"); return; }')
        a('\tscript_object_set_material(nw, m);')
    else:
        a('\tscript_object_set_material(nw, NULL);')
    if export_path:
        a(f'\tscript_export_mesh("{export_path}");')
    a(f'\tproject_filepath_set("{fresh_out}");')
    a('\tproject_save(0);')
    return "void main() {\n" + "\n".join(L) + "\n}\n"
