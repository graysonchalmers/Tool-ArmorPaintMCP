"""Re-check replace_mesh's round_trip thresholds on REAL ArmorPaint exports
(the S3 spike emulated ArmorPaint's UV quantization; this runs the real
import/export path). Builds a one-object project per base mesh, replaces it
with every committed variant in swap mode, and prints IoU/retention.
Re-run after any AP_BINARY rebuild.

    .venv\\Scripts\\python.exe scripts\\calibrate_uv_gate.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from armorpaint_mcp import uv_analysis as ua  # noqa: E402
from armorpaint_mcp.server import replace_mesh, run_script  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
UV = os.path.join(ROOT, "phase6", "uv")
SETS = {
    "base": ["r1_noise", "r2_subdiv", "r3_bevel", "r4_extrude", "r5_decimate",
             "r5b_decimate_heavy", "r6b_subsurf_smoothall", "r7_bigmove", "r8_scaled",
             "d1_smartuv45", "d2a_lightmap", "d2b_cube", "d3_repack", "d4_swap",
             "d5_rot180", "d6_repack_norot", "d7_smartuv_rerun"],
    "sphere": ["sphere_r1_noise", "sphere_d_mirror", "sphere_d_rot180", "sphere_d_smartuv"],
}


def one_object_project(obj_name: str, out: str) -> str:
    """sample_project.arm + the base mesh appended, the default cube removed."""
    mesh = os.path.abspath(os.path.join(UV, f"{obj_name}.obj")).replace("\\", "\\\\")
    script = ("void main() {\n"
              f'\tscript_append_mesh("{mesh}");\n'
              '\tobject_t *t = script_get_object("Tessellated");\n'
              "\tscript_object_remove(t);\n"
              f'\tproject_filepath_set("{os.path.abspath(out).replace(os.sep, "/")}");\n'
              "\tproject_save(0);\n}\n")
    result = run_script(project=os.path.join(ROOT, "sample_project.arm"), script=script)
    if not result["ok"] or not os.path.isfile(out):
        raise SystemExit(f"could not build {out}: {result['error']}")
    return out


def main() -> int:
    print(f"{'variant':26} {'iou':>7} {'retention':>9}  gate(round_trip)")
    with tempfile.TemporaryDirectory(prefix="ap-mcp-cal-") as tmp:
        for base, variants in SETS.items():
            project = one_object_project(base, os.path.join(tmp, f"{base}.arm"))
            old = "Base" if base == "base" else "Sphere"
            for name in variants:
                r = replace_mesh(project=project, old_object=old,
                                 new_mesh=os.path.join(UV, f"{name}.obj"), mode="swap",
                                 output_project=os.path.join(tmp, f"{name}.arm"),
                                 timeout_s=120)
                if not r["ok"]:
                    print(f"{name:26} FAILED: {r['error']}")
                    continue
                ret = r["retention"]
                passes = r["iou"] >= ua.IOU_MIN and (ret is None or ret >= ua.RETENTION_MIN)
                print(f"{name:26} {r['iou']:7.4f} {ret if ret is None else f'{ret:9.4f}'}  "
                      f"{'pass' if passes else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
