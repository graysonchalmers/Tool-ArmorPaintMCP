"""Spike S3 (Phase 6) - generate UV test meshes in Blender, headless.

Run:  blender --background --factory-startup --python gen_meshes.py

Builds two base assets, saves each as a .blend, then derives every variant
from a fresh load of that saved base (so variants never inherit each other's
edits) and exports OBJ with UVs.  Writes meshes/stats.json with per-file
vert/face/tri counts, UV-layer presence and UV island count.

Base A ("base"): rounded box + cylinder boss + sphere knob, joined, subdivided
once, Smart UV Project (66 deg, margin 0.02). ~3k tris, dozens of islands.
Base B ("sphere"): UV sphere with Blender's default full-square UV layout -
the adversarial case for coverage IoU.
"""
import bpy
import bmesh
import json
import math
import os
import random
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "meshes").replace("\\", "/")
os.makedirs(OUT, exist_ok=True)
SEED = 1234
STATS = {}
NOTES = {}


# ----------------------------------------------------------------- helpers
def clear_scene():
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.object and bpy.context.object.mode != "OBJECT" else None
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def activate(ob):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def edit_select_all(ob):
    activate(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.mesh.select_all(action="SELECT")


def to_object_mode():
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def uv_islands(me):
    """Count UV islands: faces joined across an edge whose two endpoint UVs match."""
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.active
    if uvl is None:
        bm.free()
        return None
    bm.faces.ensure_lookup_table()
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def same(a, b):
        return abs(a.x - b.x) < 1e-6 and abs(a.y - b.y) < 1e-6

    for f in bm.faces:
        for l in f.loops:
            r = l.link_loop_radial_next
            if r == l or r.face == f:
                continue
            # radial loop runs the opposite direction along the shared edge
            if same(l[uvl].uv, r.link_loop_next[uvl].uv) and same(l.link_loop_next[uvl].uv, r[uvl].uv):
                a, b = find(f.index), find(r.face.index)
                if a != b:
                    parent[a] = b
    n = len({find(i) for i in range(len(bm.faces))})
    bm.free()
    return n


def island_faces(bm, uvl):
    bm.faces.ensure_lookup_table()
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def same(a, b):
        return abs(a.x - b.x) < 1e-6 and abs(a.y - b.y) < 1e-6

    for f in bm.faces:
        for l in f.loops:
            r = l.link_loop_radial_next
            if r == l or r.face == f:
                continue
            if same(l[uvl].uv, r.link_loop_next[uvl].uv) and same(l.link_loop_next[uvl].uv, r[uvl].uv):
                a, b = find(f.index), find(r.face.index)
                if a != b:
                    parent[a] = b
    groups = {}
    for f in bm.faces:
        groups.setdefault(find(f.index), []).append(f)
    return list(groups.values())


def record(name, ob, path):
    me = ob.data
    has_uv = len(me.uv_layers) > 0
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    STATS[name] = {
        "file": os.path.basename(path),
        "verts": len(me.vertices),
        "faces": len(me.polygons),
        "tris": tris,
        "uv_layer": has_uv,
        "uv_islands_blender": uv_islands(me) if has_uv else None,
    }
    if name in NOTES:
        STATS[name]["note"] = NOTES[name]
    print(f"[S3] {name}: {STATS[name]}")


def export_obj(ob, name, triangulate=False, uv=True):
    to_object_mode()
    activate(ob)
    path = f"{OUT}/{name}.obj"
    bpy.ops.wm.obj_export(
        filepath=path,
        check_existing=False,
        export_selected_objects=True,
        export_uv=uv,
        export_normals=True,
        export_materials=False,
        export_triangulated_mesh=triangulate,
        apply_modifiers=True,
        forward_axis="NEGATIVE_Z",
        up_axis="Y",
    )
    record(name, ob, path)
    return path


def load_base(blend):
    bpy.ops.wm.open_mainfile(filepath=f"{OUT}/{blend}.blend")
    ob = [o for o in bpy.data.objects if o.type == "MESH"][0]
    activate(ob)
    return ob


def bm_edit(ob, fn):
    to_object_mode()
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    fn(bm)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


# ----------------------------------------------------------------- bases
def build_base():
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    box = bpy.context.object
    edit_select_all(box)
    bpy.ops.mesh.bevel(offset=0.25, segments=3, affect="EDGES")
    to_object_mode()
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.5, depth=0.8, location=(0, 0, 1.2))
    cyl = bpy.context.object
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.45, location=(1.3, 0, 0))
    sph = bpy.context.object
    for o in bpy.context.view_layer.objects:
        o.select_set(o in (box, cyl, sph))
    bpy.context.view_layer.objects.active = box
    bpy.ops.object.join()
    base = bpy.context.object
    base.name = "Base"
    base.data.name = "Base"
    edit_select_all(base)
    bpy.ops.mesh.subdivide(number_cuts=1)
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
    to_object_mode()
    bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/base.blend", check_existing=False)
    return base


def build_sphere():
    clear_scene()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, calc_uvs=True)
    s = bpy.context.object
    s.name = "Sphere"
    s.data.name = "Sphere"
    bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/sphere.blend", check_existing=False)
    return s


# ----------------------------------------------------------------- edits
def noise_displace(ob, amp):
    rnd = random.Random(SEED)

    def fn(bm):
        for v in bm.verts:
            v.co.x += rnd.uniform(-amp, amp)
            v.co.y += rnd.uniform(-amp, amp)
            v.co.z += rnd.uniform(-amp, amp)

    bm_edit(ob, fn)


def uv_transform(ob, fn_uv):
    def fn(bm):
        uvl = bm.loops.layers.uv.active
        for f in bm.faces:
            for l in f.loops:
                u, v = l[uvl].uv
                l[uvl].uv = fn_uv(u, v)

    bm_edit(ob, fn)


def swap_congruent_islands(ob):
    info = {}

    def fn(bm):
        uvl = bm.loops.layers.uv.active
        isl = island_faces(bm, uvl)
        desc = []
        for faces in isl:
            us = [l[uvl].uv.x for f in faces for l in f.loops]
            vs = [l[uvl].uv.y for f in faces for l in f.loops]
            area = sum(f.calc_area() for f in faces)  # 3D area as a congruence hint
            uva = 0.0
            for f in faces:
                pts = [l[uvl].uv for l in f.loops]
                for k in range(1, len(pts) - 1):
                    a, b, c = pts[0], pts[k], pts[k + 1]
                    uva += abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)) * 0.5
            desc.append(dict(faces=faces, n=len(faces), uva=uva, a3=area,
                             w=max(us) - min(us), h=max(vs) - min(vs),
                             cx=(max(us) + min(us)) / 2, cy=(max(vs) + min(vs)) / 2))
        best = None
        for i in range(len(desc)):
            for j in range(i + 1, len(desc)):
                a, b = desc[i], desc[j]
                if a["n"] != b["n"] or a["uva"] <= 0:
                    continue
                if abs(a["uva"] - b["uva"]) > 1e-4 * max(a["uva"], b["uva"]) + 1e-9:
                    continue
                if abs(a["w"] - b["w"]) > 1e-4 or abs(a["h"] - b["h"]) > 1e-4:
                    continue
                if best is None or a["uva"] > best[0]["uva"]:
                    best = (a, b)
        congruent = best is not None
        if best is None:
            desc.sort(key=lambda d: -d["uva"])
            best = (desc[0], desc[1])
        a, b = best
        dx, dy = b["cx"] - a["cx"], b["cy"] - a["cy"]
        moved = set()
        for f in a["faces"]:
            for l in f.loops:
                l[uvl].uv = (l[uvl].uv.x + dx, l[uvl].uv.y + dy)
        for f in b["faces"]:
            for l in f.loops:
                l[uvl].uv = (l[uvl].uv.x - dx, l[uvl].uv.y - dy)
        info.update(congruent_pair_found=congruent, islands=len(desc),
                    swapped_faces=[a["n"], b["n"]], swapped_uv_area=[round(a["uva"], 6), round(b["uva"], 6)],
                    swapped_bbox=[[round(a["w"], 4), round(a["h"], 4)], [round(b["w"], 4), round(b["h"], 4)]],
                    offset=[round(dx, 4), round(dy, 4)])

    bm_edit(ob, fn)
    return info


def cylinder_rim_edges(bm):
    out = []
    for e in bm.edges:
        ok = True
        for v in e.verts:
            r = math.hypot(v.co.x, v.co.y)
            # rim after subdivide: original verts at r=0.5, edge midpoints at r=0.5*cos(7.5deg)
            if not (abs(v.co.z - 1.6) < 1e-4 and 0.49 < r < 0.501):
                ok = False
        if ok:
            out.append(e)
    return out


# ----------------------------------------------------------------- main
def run():
    # ---- Base A
    base = build_base()
    export_obj(base, "base")
    export_obj(base, "base_tri", triangulate=True)
    # FBX (not natively importable by this ArmorPaint build - candidate only)
    to_object_mode()
    activate(base)
    try:
        bpy.ops.export_scene.fbx(filepath=f"{OUT}/base.fbx", use_selection=True, mesh_smooth_type="OFF",
                                 bake_anim=False, add_leaf_bones=False)
        STATS["base_fbx"] = {"file": "base.fbx", "note": "Blender FBX exporter, use_selection, UVs included"}
    except Exception as e:  # noqa: BLE001
        STATS["base_fbx"] = {"file": None, "error": repr(e)}
    STATS["base_blend"] = {"file": "base.blend", "note": "saved right after unwrap; only object = Base"}

    # no-UV variant
    ob = load_base("base")
    while ob.data.uv_layers:
        ob.data.uv_layers.remove(ob.data.uv_layers[0])
    export_obj(ob, "nouv", uv=False)

    # r1 vertex moves only
    ob = load_base("base")
    noise_displace(ob, 0.03)
    NOTES["r1_noise"] = "every vertex += uniform(-0.03,0.03)^3, seed 1234; UVs untouched"
    export_obj(ob, "r1_noise")

    # r2 subdivide (UVs interpolated by the operator)
    ob = load_base("base")
    edit_select_all(ob)
    bpy.ops.mesh.subdivide(number_cuts=1)
    NOTES["r2_subdiv"] = "mesh.subdivide number_cuts=1 on all faces (flat, UVs interpolated)"
    export_obj(ob, "r2_subdiv")

    # r3 bevel on some edges (cylinder top rim)
    ob = load_base("base")
    to_object_mode()
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    rim = cylinder_rim_edges(bm)
    for e in bm.edges:
        e.select_set(False)
    for f in bm.faces:
        f.select_set(False)
    for v in bm.verts:
        v.select_set(False)
    for e in rim:
        e.select_set(True)
    bm.select_flush(True)
    bm.to_mesh(ob.data)
    bm.free()
    activate(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="EDGE")
    bpy.ops.mesh.bevel(offset=0.08, segments=2, affect="EDGES")
    NOTES["r3_bevel"] = f"mesh.bevel offset 0.08 segments 2 on {len(rim)} cylinder top-rim edges"
    export_obj(ob, "r3_bevel")

    # r4 extrude a few faces (bmesh extrude_face_region, like the E key)
    ob = load_base("base")

    def extrude(bm):
        bm.faces.ensure_lookup_table()
        cand = [f for f in bm.faces if f.normal.y < -0.99 and abs(f.calc_center_median().x) < 0.45
                and abs(f.calc_center_median().z) < 0.45]
        ret = bmesh.ops.extrude_face_region(bm, geom=cand)
        verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
        # the bmesh op keeps the source faces; the E-key operator deletes them - do the same
        bmesh.ops.delete(bm, geom=cand, context="FACES")
        bmesh.ops.translate(bm, verts=verts, vec=(0.0, -0.2, 0.0))
        NOTES["r4_extrude"] = (f"bmesh extrude_face_region of {len(cand)} front faces (source faces deleted, "
                               "as the E key does), moved -0.2 in Y")

    bm_edit(ob, extrude)
    export_obj(ob, "r4_extrude")

    # r5 decimate collapse
    ob = load_base("base")
    m = ob.modifiers.new("Dec", "DECIMATE")
    m.decimate_type = "COLLAPSE"
    m.ratio = 0.5
    m.use_collapse_triangulate = False
    activate(ob)
    bpy.ops.object.modifier_apply(modifier="Dec")
    NOTES["r5_decimate"] = "Decimate modifier COLLAPSE ratio 0.5, triangulate off, applied (delimit n/a to collapse)"
    export_obj(ob, "r5_decimate")

    # r6 subdivision surface (UV smoothing = realistic round-trip edit)
    ob = load_base("base")
    m = ob.modifiers.new("Sub", "SUBSURF")
    m.levels = 1
    m.render_levels = 1
    NOTES["r6_subsurf"] = f"Subsurf level 1, uv_smooth={m.uv_smooth}, applied"
    activate(ob)
    bpy.ops.object.modifier_apply(modifier="Sub")
    export_obj(ob, "r6_subsurf")

    # ---- extra calibration variants (probe the low end of the round-trip family)
    # r5b heavy decimate
    ob = load_base("base")
    m = ob.modifiers.new("Dec", "DECIMATE")
    m.decimate_type = "COLLAPSE"
    m.ratio = 0.2
    activate(ob)
    bpy.ops.object.modifier_apply(modifier="Dec")
    NOTES["r5b_decimate_heavy"] = "Decimate COLLAPSE ratio 0.2, applied"
    export_obj(ob, "r5b_decimate_heavy")

    # r6b subsurf with UV smoothing that also moves island boundaries
    ob = load_base("base")
    m = ob.modifiers.new("Sub", "SUBSURF")
    m.levels = 1
    m.uv_smooth = "SMOOTH_ALL"
    activate(ob)
    bpy.ops.object.modifier_apply(modifier="Sub")
    NOTES["r6b_subsurf_smoothall"] = "Subsurf level 1, uv_smooth=SMOOTH_ALL (boundaries smoothed too), applied"
    export_obj(ob, "r6b_subsurf_smoothall")

    # r7 big local move: sphere knob shifted +0.6 X (UVs identical, paint follows the surface)
    ob = load_base("base")

    def move_knob(bm):
        k = 0
        for v in bm.verts:
            if v.co.x > 0.84 and math.dist((v.co.x, v.co.y, v.co.z), (1.3, 0, 0)) < 0.47:
                v.co.x += 0.6
                k += 1
        NOTES["r7_bigmove"] = f"{k} sphere-knob verts moved +0.6 in X (~13% of bbox diag); UVs untouched"

    bm_edit(ob, move_knob)
    export_obj(ob, "r7_bigmove")

    # r8 whole mesh uniformly scaled x1.25 and translated (e.g. unit/origin change on re-export)
    ob = load_base("base")

    def scale_move(bm):
        for v in bm.verts:
            v.co = v.co * 1.25
            v.co.x += 0.5
            v.co.z -= 0.3

    bm_edit(ob, scale_move)
    NOTES["r8_scaled"] = "all verts *1.25 then +0.5 X, -0.3 Z (mesh data, UVs untouched)"
    export_obj(ob, "r8_scaled")

    # d6 repack without rotation, similar margin (possibly near-identical layout)
    ob = load_base("base")
    edit_select_all(ob)
    bpy.ops.uv.pack_islands(rotate=False, margin=0.02, shape_method="CONCAVE")
    NOTES["d6_repack_norot"] = "uv.pack_islands rotate off, margin 0.02, shape CONCAVE"
    export_obj(ob, "d6_repack_norot")

    # d1 re-unwrap Smart UV, different angle/margin
    ob = load_base("base")
    edit_select_all(ob)
    bpy.ops.uv.smart_project(angle_limit=math.radians(45.0), island_margin=0.05)
    NOTES["d1_smartuv45"] = "Smart UV Project angle 45, margin 0.05"
    export_obj(ob, "d1_smartuv45")

    # d2a lightmap pack
    ob = load_base("base")
    edit_select_all(ob)
    try:
        bpy.ops.uv.lightmap_pack(PREF_CONTEXT="ALL_FACES", PREF_PACK_IN_ONE=True, PREF_NEW_UVLAYER=False,
                                 PREF_MARGIN_DIV=0.1)
        NOTES["d2a_lightmap"] = "uv.lightmap_pack all faces, margin 0.1"
        export_obj(ob, "d2a_lightmap")
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        STATS["d2a_lightmap"] = {"error": traceback.format_exc(limit=1)}
        to_object_mode()

    # d2b cube projection
    ob = load_base("base")
    edit_select_all(ob)
    try:
        bpy.ops.uv.cube_project(cube_size=2.0, correct_aspect=True, clip_to_bounds=False, scale_to_bounds=True)
        NOTES["d2b_cube"] = "uv.cube_project cube_size 2, scale_to_bounds"
        export_obj(ob, "d2b_cube")
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        STATS["d2b_cube"] = {"error": traceback.format_exc(limit=1)}
        to_object_mode()

    # d3 same islands, repacked with rotation (rearranged)
    ob = load_base("base")
    edit_select_all(ob)
    try:
        bpy.ops.uv.select_all(action="SELECT")
    except Exception:  # noqa: BLE001
        pass
    bpy.ops.uv.pack_islands(rotate=True, rotate_method="ANY", margin=0.005, shape_method="CONCAVE")
    NOTES["d3_repack"] = "uv.pack_islands rotate ANY, margin 0.005, shape CONCAVE (island shapes kept, rearranged)"
    export_obj(ob, "d3_repack")

    # d4 swap two congruent islands (coverage-preserving scramble)
    ob = load_base("base")
    info = swap_congruent_islands(ob)
    NOTES["d4_swap"] = "bmesh: swap bbox centres of two islands; " + json.dumps(info)
    export_obj(ob, "d4_swap")

    # d5 whole layout rotated 180 deg about (0.5, 0.5)
    ob = load_base("base")
    uv_transform(ob, lambda u, v: (1.0 - u, 1.0 - v))
    NOTES["d5_rot180"] = "all UVs (u,v) -> (1-u, 1-v)"
    export_obj(ob, "d5_rot180")

    # ---- Base B: sphere with default full-square layout
    s = build_sphere()
    export_obj(s, "sphere")
    ob = load_base("sphere")
    noise_displace(ob, 0.02)
    NOTES["sphere_r1_noise"] = "every vertex += uniform(-0.02,0.02)^3, seed 1234"
    export_obj(ob, "sphere_r1_noise")
    ob = load_base("sphere")
    uv_transform(ob, lambda u, v: (1.0 - u, v))
    NOTES["sphere_d_mirror"] = "u -> 1-u (mirror)"
    export_obj(ob, "sphere_d_mirror")
    ob = load_base("sphere")
    uv_transform(ob, lambda u, v: (1.0 - u, 1.0 - v))
    NOTES["sphere_d_rot180"] = "(u,v) -> (1-u,1-v)"
    export_obj(ob, "sphere_d_rot180")
    ob = load_base("sphere")
    edit_select_all(ob)
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
    NOTES["sphere_d_smartuv"] = "Smart UV Project 66/0.02 on the sphere"
    export_obj(ob, "sphere_d_smartuv")


try:
    run()
    STATS["_blender_version"] = bpy.app.version_string
    with open(f"{OUT}/stats.json", "w") as fh:
        json.dump(STATS, fh, indent=2)
    print("[S3] DONE")
except Exception:  # noqa: BLE001
    traceback.print_exc()
    with open(f"{OUT}/stats.json", "w") as fh:
        json.dump(STATS, fh, indent=2)
    print("[S3] FAILED")
    sys.exit(1)
