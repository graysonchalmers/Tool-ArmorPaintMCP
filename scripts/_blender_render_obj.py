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
area, also unavailable in --background mode.

Settings below are named constants, not scattered magic numbers -- tune
these (and update the spec's rationale) if a render looks wrong."""
import sys

import bpy
import mathutils

RESOLUTION = (800, 600)
CAMERA_DIRECTION = (-1.0, 1.0, -0.75)  # fixed diagonal view angle, same for every render
ORTHO_MARGIN = 1.3  # headroom multiplier on the mesh's bounding-sphere radius


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
    return imported[0]


def _mark_all_edges_freestyle(mesh_obj) -> None:
    """Force every polygon edge into Freestyle's line set, not just
    silhouette/crease-angle-detected edges -- otherwise flat/near-coplanar
    topology changes (decimate, subdivide) render invisibly, since a
    perfectly coplanar edge is 0 degrees no matter how the crease-angle
    threshold is tuned. Confirmed via a synthetic flat-grid regression
    test: internal grid lines were invisible before this, visible after."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.mark_freestyle_edge(clear=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    lineset = bpy.context.view_layer.freestyle_settings.linesets["LineSet"]
    lineset.select_edge_mark = True


def _frame_camera(target, scene) -> None:
    corners = [target.matrix_world @ mathutils.Vector(c) for c in target.bound_box]
    center = sum(corners, mathutils.Vector()) / 8
    radius = max((c - center).length for c in corners)

    cam_data = bpy.data.cameras.new("gallery_camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = radius * 2 * ORTHO_MARGIN
    cam_obj = bpy.data.objects.new("gallery_camera", cam_data)
    scene.collection.objects.link(cam_obj)

    direction = mathutils.Vector(CAMERA_DIRECTION).normalized()
    cam_obj.location = center - direction * radius * 4
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
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
    mesh_obj = _import_obj(obj_path)
    _frame_camera(mesh_obj, scene)
    _light_scene(scene)

    scene.render.resolution_x, scene.render.resolution_y = RESOLUTION
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = png_path
    scene.render.use_freestyle = True
    bpy.context.view_layer.use_freestyle = True
    _mark_all_edges_freestyle(mesh_obj)

    bpy.ops.render.render(write_still=True)
    print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
