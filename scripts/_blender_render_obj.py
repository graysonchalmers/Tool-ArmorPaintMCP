"""Runs inside Blender's own Python (`blender --background --python
scripts/_blender_render_obj.py -- <obj_path> <png_path>`), never imported by
anything else. Renders `obj_path` as a wireframe-over-solid orthographic
still to `png_path`.

Wireframe uses Freestyle edge rendering, not the 3D viewport's "wireframe
overlay" -- the latter never reaches bpy.ops.render.render()'s output and
--background mode has no viewport/window context to capture one from
anyway (confirmed empirically; see the design spec's Settings table).

Camera framing uses manual bounding-box math, not
view3d.camera_to_view_selected -- that operator needs a live 3D viewport
area, also unavailable in --background mode. Framing projects onto the
camera's own right/up axes (not a simple 3D bounding-sphere radius) so an
elongated multi-object arrangement (see _separate_overlapping_objects)
frames correctly instead of cropping.

Settings below are named constants, not scattered magic numbers -- tune
these (and update the spec's rationale) if a render looks wrong."""
import sys

import bpy
import mathutils

RESOLUTION = (800, 600)
CAMERA_DIRECTION = (-1.0, 1.0, -0.75)  # fixed diagonal view angle, same for every render
ORTHO_MARGIN = 1.3  # headroom multiplier on the mesh's projected half-extent
OFFSET_GAP = 0.5  # extra world-unit gap between objects when separating overlaps


def _parse_args() -> tuple[str, str]:
    argv = sys.argv
    if "--" not in argv:
        raise SystemExit(
            "usage: blender --background --python _blender_render_obj.py "
            "-- <obj_path> <png_path>")
    obj_path, png_path = argv[argv.index("--") + 1:][:2]
    return obj_path, png_path


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def _import_obj(obj_path: str):
    bpy.ops.wm.obj_import(filepath=obj_path)
    imported = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    if not imported:
        raise SystemExit(f"no mesh object imported from '{obj_path}'")
    return imported


def _separate_overlapping_objects(mesh_objects) -> None:
    """Some gallery pairs (duplicate_mesh's 'after', merge_mesh_geometry's
    'before') genuinely contain two objects at the exact same transform --
    that overlap is real, tested behavior of the tool, not a bug. But it
    renders as a single indistinguishable box. Nudge every object but the
    first sideways here, in this throwaway render scene only -- never
    touches the source OBJ data or any tool's real output -- so the camera
    can show them as separate. Requires a depsgraph update afterward before
    any bounding-box math reads matrix_world (see main())."""
    if len(mesh_objects) < 2:
        return
    first = mesh_objects[0]
    width = max(c[0] for c in first.bound_box) - min(c[0] for c in first.bound_box)
    step = width + OFFSET_GAP
    for i, obj in enumerate(mesh_objects[1:], start=1):
        obj.location.x += step * i


def _mark_all_edges_freestyle(mesh_obj) -> None:
    """Force every polygon edge into Freestyle's line set, not just
    silhouette/crease-angle-detected edges -- otherwise flat/near-coplanar
    topology changes (decimate, subdivide) render invisibly, since a
    perfectly coplanar edge is 0 degrees no matter how the crease-angle
    threshold is tuned. Confirmed via a synthetic flat-grid regression
    test: internal grid lines were invisible before this, visible after."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.mark_freestyle_edge(clear=False)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    linesets = bpy.context.view_layer.freestyle_settings.linesets
    lineset = linesets.get("LineSet") or linesets.new("LineSet")
    lineset.select_edge_mark = True


def _frame_camera(targets, scene) -> None:
    """targets is a list of one or more mesh objects. Projects every
    bound_box corner onto the camera's own right/up axes (not a 3D
    bounding-sphere radius) so an elongated multi-object arrangement is
    framed correctly -- a bounding-sphere radius under-estimated the
    required view width for two side-by-side offset objects and cropped
    the second one (confirmed empirically)."""
    corners = [obj.matrix_world @ mathutils.Vector(c) for obj in targets for c in obj.bound_box]
    center = sum(corners, mathutils.Vector()) / len(corners)
    radius = max((c - center).length for c in corners)

    direction = mathutils.Vector(CAMERA_DIRECTION).normalized()
    rotation = direction.to_track_quat("-Z", "Y")
    right = rotation @ mathutils.Vector((1, 0, 0))
    up = rotation @ mathutils.Vector((0, 1, 0))

    half_width = max(abs((c - center).dot(right)) for c in corners)
    half_height = max(abs((c - center).dot(up)) for c in corners)
    aspect = RESOLUTION[0] / RESOLUTION[1]
    ortho_scale = max(half_width * 2, half_height * 2 * aspect) * ORTHO_MARGIN

    cam_data = bpy.data.cameras.new("gallery_camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho_scale
    cam_obj = bpy.data.objects.new("gallery_camera", cam_data)
    scene.collection.objects.link(cam_obj)

    cam_obj.location = center - direction * radius * 4
    cam_obj.rotation_euler = rotation.to_euler()
    scene.camera = cam_obj


def _light_scene(scene) -> None:
    light_data = bpy.data.lights.new("gallery_sun", type="SUN")
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new("gallery_sun", light_data)
    light_obj.rotation_euler = (0.6, 0.2, 0.4)
    scene.collection.objects.link(light_obj)


def main() -> None:
    obj_path, png_path = _parse_args()
    scene = bpy.context.scene

    _clear_scene()
    mesh_objects = _import_obj(obj_path)
    _separate_overlapping_objects(mesh_objects)
    bpy.context.view_layer.update()  # matrix_world must reflect the offset before framing
    _frame_camera(mesh_objects, scene)
    _light_scene(scene)

    scene.render.resolution_x, scene.render.resolution_y = RESOLUTION
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = png_path
    scene.render.use_freestyle = True
    bpy.context.view_layer.use_freestyle = True
    for mesh_obj in mesh_objects:
        _mark_all_edges_freestyle(mesh_obj)

    bpy.ops.render.render(write_still=True)
    print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
