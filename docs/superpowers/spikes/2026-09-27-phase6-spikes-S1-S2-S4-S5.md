# Phase 6 spikes A — S1, S5, S4, S2 (ArmorPaint, AP_BINARY @ 287e63f4)

Run 2026-09-27 by subagent via the project's own `run_minic_script`/`run_api`, one process at a time,
`timeout_s=120`. Saved by the controller from the hand-back (harness blocked the subagent's write).
Evidence JSON/scripts under this folder. Controller verification: `plugins.c:167-172` +
`project.c:14` (WITH_PLUGINS → gltf/glb/fbx importers), `iron_system.c:44-54` (pipe → WriteFile) with
`3b77ab8c` an ancestor of `287e63f4`, `iron_armpack.c:799-801` (unescaped strings); reproduced
`inspect_project(s5\A_cone_plain_out.arm)` → `ok=False`, "Invalid \escape", fixture still `ok=True`.

Environment: machine at commit limit (37 claude.exe ≈ 14 GB, `WinError 1455`). ~7/150 launches died
0xC0000005 (some before the script's first statement), all fine on fresh-copy retry; one hung to
timeout with a complete saved file. → nonzero exit or timeout must be `ok=False` (safe: commit only
after verify).

## Fixtures
`script_project_new(); script_shape_add("cone"); script_shape_add("torus"); project_filepath_set(p); project_save(0);`
→ `Tessellated`, `Cone`, `Torus`. `fixtures\objects3.arm` (md5 6487c549…); `objects3_v2.arm` (MatB
override on Cone, loc (1.5,-0.75,0.25), rot 30° z, scale (1,2,0.5)); `objects3_v4_parented.arm` (Cone
parented under Tessellated).

## S1 — per-object isolation: HOLDS (`s1\s1_results.json`)
- `o` names = inspect names. Each group contiguous: `o`, v…, vn…, vt…, f…. Dedup per object.
- Face indices global (offset by earlier groups); every face references only its own group → rebase safe.
- Separate-process exports byte-identical. After append (same process and reopened) untouched groups'
  resolved signatures unchanged; appended group last.
- Key groups by `o` name; compare v/vt/vn + faces rebased to local indices. Raw `f` lines NOT comparable.
- Export is object-local, no transforms → verify transforms via `--api` `mesh_transforms`.

## S5 — four-call composition: WORKS WITH FIXES (`s5\`, `s5fmt\`)
- Replace Cone or root Tessellated: count stays 3, old name gone, layer count unchanged, untouched
  transforms/material overrides kept, replaced geometry = source OBJ within 2.3e-5 (pos + UV).
- New object takes the OBJ's `o` name (`Cone.001` on clash), appended at end of list.
- Wrong old name, unguarded: silently saves 4 objects. Guard `if (old == NULL) {…; return;}` works → no file.
- Single-object project: remove-first no-ops (2 objects); append-first → 1.
- Formats (WITH_PLUGINS): GLB appends natively, matches within 3.0e-5 (→ committed non-OBJ fixture
  `fixtures\repl_grid5.glb`); FBX appends but positions 100x (Blender default unit scale), UVs exact;
  `.blend` silent no-op (config `blender` = "" in `paint\build\out\data\config.json`,
  `config.c:44-56`, `import_blend_mesh.c:34-37`; message now reaches stdout).

## S4 — carry-over: ALL REACHABLE, verified after reopen (`s4\`, `s4d\`)
- Name: `script_object_set_name(object_t*, char*)`.
- Transform: read/write `old->transform->loc.x` etc. (vec4/quat embedded fields OK), then
  `transform_build_matrix(t)` REQUIRED (else lost on save). Local matrix max diff 0.0.
- Parent REQUIRED: without it a parented object's world moves 0.83. `op = old->parent` +
  `object_set_parent(nw, op)` → exact. Children of a replaced parent: move `old->children` to new first.
- Material: minic can't enumerate materials/read override index. Python reads `mesh_materials[i32][i]` +
  `material_nodes[idx].name` from `--api`; script cross-checks `omo->material->name == "_material_<m->id>"`.
  `-1` → `script_object_set_material(nw, NULL)`. Duplicate names fail closed (no file).
- Stage-list duplicate if renamed to the old name → rename old to `__ap_mcp_replaced__` BEFORE append
  (also lets a same-named round-trip OBJ import as its own name).

## Working snippet (`s4d\FINAL_v2_cone.c`, generator `final_snippet.py`) — all checks passed
```c
void main() {
	object_t *old = script_get_object("{OLD}");
	if (old == NULL) { console_log("REPLACE_ERR old_not_found"); return; }
	char *oname = string_copy(old->name);
	transform_t *ot = old->transform;
	float lx = ot->loc.x; float ly = ot->loc.y; float lz = ot->loc.z;
	float rx = ot->rot.x; float ry = ot->rot.y; float rz = ot->rot.z; float rw = ot->rot.w;
	float sx = ot->scale.x; float sy = ot->scale.y; float sz = ot->scale.z;
	object_t *op = old->parent;
	mesh_object_t *omo = old->ext;
	char *omat = string_copy(omo->material->name);
	script_object_set_name(old, "__ap_mcp_replaced__");
	context_t *cx = script_get_context();
	mesh_object_t *before = cx->paint_object;
	script_append_mesh("{NEW_PATH_WITH_BACKSLASHES_DOUBLED}");
	mesh_object_t *nmo = cx->paint_object;
	if (nmo == before) { console_log("REPLACE_ERR append_failed"); return; }
	object_t *nw = nmo->base;
	int nc = old->children->length;
	for (int i = 0; i < nc; i++) { object_t *c = old->children->buffer[0]; object_set_parent(c, nw); }
	script_object_remove(old);
	script_object_set_name(nw, oname);
	object_set_parent(nw, op);
	transform_t *nt = nw->transform;
	nt->loc.x = lx; nt->loc.y = ly; nt->loc.z = lz;
	nt->rot.x = rx; nt->rot.y = ry; nt->rot.z = rz; nt->rot.w = rw;
	nt->scale.x = sx; nt->scale.y = sy; nt->scale.z = sz;
	transform_build_matrix(nt);
	slot_material_t *m = script_get_material("{MAT_NAME}");
	if (m == NULL) { console_log("REPLACE_ERR material_not_found"); return; }
	string_array_t *mk = string_array_create(0);
	string_array_push(mk, "_material_"); string_array_push(mk, i32_to_string(m->id));
	if (!string_equals(omat, string_array_join(mk, ""))) { console_log("REPLACE_ERR material_ambiguous"); return; }
	script_object_set_material(nw, m);
	project_filepath_set("{FRESH_SIBLING_PATH_IN_TARGET_DIR}");
	project_save(0);
}
```
- `mesh_materials` entry -1: drop `omo`/`omat` + the `m` block, call `script_object_set_material(nw, NULL);`.
- Append path MUST be backslashes (doubled in the literal): forward slashes → `iron_file_exists` = 0 →
  silent no-op (`s1append\fwd.txt` exists=0, `back.txt` exists=1).
- Append guard REQUIRED (in `.blend` cases, without it the script would rename the prior paint object).

## S2 — completion sentinel (`s2\`, `instr\`)
- (a) `project_filepath_set(fresh)` + `project_save(0)` on an opened project: works (either slash
  style), 6 runs byte-identical, input md5 never changed, result reopens with identical signatures.
- (b) undefined call before save → no file. (b2) undefined call AFTER save → file still written →
  `project_save` must be the LAST statement.
- (c) Non-saving: `iron_file_save_bytes("<p>", u8_array_create_from_string("done"), 0);` is synchronous
  and cheap (bytes include a trailing NUL); also a data channel out of a script. A `__user_main()`
  wrapper does NOT work (errors unwind only their own frame, `base/sources/libs/minic.c:978-1015`).
  `script_export_mesh` as sentinel works but is quadratic-dedup costly (71 KB here). Not recommended.
- **stdout IS capturable** since upstream `3b77ab8c` (2026-09-17, in AP_BINARY; `iron_system.c:44-54`):
  `<script>:N: error: …` for unknown function / missing field / null pointer / syntax error,
  `console_log`, `Project saved`, `Blender executable path not set`.
- Recommendation: every tool `ok=False` on nonzero exit, timeout, or any `:\d+: error:` / `REPLACE_ERR`
  line. Saving tools also require the fresh sibling file (+ `Project saved`), then post-verify.
  `run_script`/read-only: stdout scan suffices; optional trailing `iron_file_save_bytes` (early `return`
  would false-fail).

## Contradictions to "Decisions applied"
1. "Untouched objects byte-identical in the export" false: raw `f` lines shift for groups after the
   removed one; v/vt/vn and resolved data identical.
2. Staging the input elsewhere breaks relative assets (`.arm` stores mesh/texture/font/sound/envmap paths
   relative to itself, `io/export_arm.c:70,90,110,130,288,453`; s2 case d). Open the original directly
   (never written), save to a fresh sibling in the target dir, verify, `os.replace`. Phase 5
   `_run_mesh_edit` (`server.py:109-118`, copy2 then open) has the same latent hazard.
3. "Stdout isn't capturable" stale (runner/run_script docstrings, memory note).
4. Load + re-save doesn't reliably keep md5 (objects3 identical; v2 bac4954d → f402d63c, deterministic).
5. `--api` JSON breaks on backslashes (`iron_armpack.c:799-801`, unescaped): every post-append project
   has a backslash `mesh_assets` entry → `extract_project_state` `CatalogError` → shipped
   `inspect_project` `ok=False`. Workaround: double every backslash before `json.loads` (quotes in names
   still a hazard). Typed-array keys carry suffixes: `mesh_materials[i32]`, `mesh_parents[i32]`.
6. Scene-text order ≠ `paint_objects` order once parented; map index arrays through `mesh_datas[].name`.
7. Carry-over also needs parent, pre-rename, append guard, child move.
8. Material carry conditional: Python supplies the name; pre-check duplicate material names.
9. Replacement lands at list end; hierarchy sort may reorder; minic can't restore order (feeds D5 mask risk).
10. "Matches replacement geometry" fails for Blender FBX (100x) unless scale-normalized.
11. `project_save` must be last.
12. Append paths must be backslashes (not `script_gen`'s forward-slash convention).

## Not verified
Linked (non-packed) textures under the staging hazard (only `mesh_assets` observed); multi-stage
projects (remove only hides → post-verify must assert `__ap_mcp_replaced__` absent); multi-mesh GLB/FBX
(guard sees first appended; count check catches rest); UV-less replacements; object masks (D5);
`split_by` on OBJ appends; non-uniformly scaled parents (shear); paint pixel content (layer counts only);
in-place-save variant; crash/hang root cause (memory pressure likely).
