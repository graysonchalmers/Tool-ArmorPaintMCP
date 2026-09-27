"""Scratch helpers for the Phase 6 spikes (A). Not production code.

Drives ArmorPaint only via Python subprocess (project runner helpers), one
process at a time, timeout 120 s. Never prints .env contents.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

PROJ = r"C:\Projects-local\Tool-ArmorPaintMCP"
sys.path.insert(0, os.path.join(PROJ, "src"))
os.environ.setdefault("AP_DOTENV", os.path.join(PROJ, ".env"))

from armorpaint_mcp.config import load_config  # noqa: E402
from armorpaint_mcp.runner import run_minic_script, run_api  # noqa: E402
from armorpaint_mcp.catalog import extract_project_state, scene_objects  # noqa: E402

A = os.path.dirname(os.path.abspath(__file__))
CFG = load_config()
BIN = CFG.binary
TIMEOUT = 120


def _wait_no_other_ap():
    """Never overlap with another ArmorPaint process (ours or a sibling's)."""
    for _ in range(240):
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ArmorPaint.exe", "/NH"],
                             capture_output=True, text=True).stdout
        if "ArmorPaint.exe" not in out:
            return
        time.sleep(0.5)
    raise RuntimeError("another ArmorPaint.exe kept running for 120 s")


def fwd(p):
    return os.path.abspath(p).replace("\\", "/")


def md5(p):
    with open(p, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


AV = "3221225477"
CRASHES = {"script": 0, "api": 0, "noproj": 0}
CRASH_LOG = os.path.join(A, "crash_log.txt")


def _log_crash(kind, label):
    CRASHES[kind] += 1
    with open(CRASH_LOG, "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%H:%M:%S')} {kind} {label}\n")


def run(project, script, label=""):
    _wait_no_other_ap()
    t = time.monotonic()
    r = run_minic_script(BIN, project, script, timeout_s=TIMEOUT)
    dt = time.monotonic() - t
    print(f"[run {label}] ok={r.ok} err={r.error} {dt:.1f}s")
    if not r.ok and r.error and AV in r.error:
        _log_crash("script", label)
    return r


def run_fresh(src, proj, script, cleanup=(), label="", tries=5):
    """Copy src->proj and delete `cleanup` paths before EVERY attempt; retry
    only on an access-violation exit (machine is commit-starved, see
    crash_log.txt). Returns (result, attempts)."""
    import shutil
    for attempt in range(1, tries + 1):
        if src is not None:
            shutil.copy(src, proj)
        for p in cleanup:
            if os.path.exists(p):
                os.remove(p)
        r = run(proj, script, f"{label}#{attempt}")
        if r.ok or not (r.error and AV in r.error):
            return r, attempt
        time.sleep(3)
    return r, tries


def run_noproj(script, label=""):
    """--background --script with no project (fixture generation)."""
    _wait_no_other_ap()
    fd, sp = tempfile.mkstemp(suffix=".c")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(script)
    try:
        for attempt in range(1, 6):
            t = time.monotonic()
            p = subprocess.run([BIN, "--background", "--script", sp],
                               capture_output=True, text=True, timeout=TIMEOUT)
            print(f"[noproj {label}#{attempt}] rc={p.returncode} {time.monotonic() - t:.1f}s")
            if p.returncode != int(AV) and p.returncode != -1073741819:
                break
            _log_crash("noproj", label)
            time.sleep(3)
    finally:
        os.unlink(sp)
    return p


LENIENT_USED = []


def _lenient_state(text):
    """Fallback when --api's JSON has unescaped backslashes (Windows paths)."""
    import re
    start = text.find("/* Current project state:\n") + len("/* Current project state:\n")
    end = text.find("\n\nScene objects in world space", start)
    raw = text[start:end]
    # iron_armpack.c armpack_to_json_value writes strings as "%s" with NO
    # escaping, so every backslash in the dump is literal: double them all.
    fixed = raw.replace("\\", "\\\\")
    return json.loads(fixed)


def api(project, tries=5):
    for attempt in range(1, tries + 1):
        _wait_no_other_ap()
        r = run_api(BIN, project, timeout_s=TIMEOUT)
        if r.ok:
            break
        if r.error and AV in r.error:
            _log_crash("api", os.path.basename(project))
            time.sleep(3)
            continue
        raise RuntimeError(r.error)
    else:
        raise RuntimeError(f"--api crashed {tries} times")
    try:
        st = extract_project_state(r.text)
    except Exception as exc:  # CatalogError
        LENIENT_USED.append((os.path.basename(project), str(exc)))
        print(f"  [api] strict parse FAILED ({exc}); using lenient parse")
        st = _lenient_state(r.text)
    return st, scene_objects(r.text), r.text


def summarize(project):
    st, objs, _ = api(project)
    mds = st.get("mesh_datas") or []
    return {
        "scene_objects": objs,
        "mesh_data_names": [m.get("name") for m in mds],
        "mesh_transforms": st.get("mesh_transforms"),
        # typed arrays carry a suffix in the --api JSON key (iron_armpack.c
        # armpack_to_json_map: key + peek_typed_array_suffix())
        "mesh_materials": st.get("mesh_materials[i32]"),
        "mesh_parents": st.get("mesh_parents[i32]"),
        "mesh_assets": st.get("mesh_assets"),
        "materials": [m.get("name") for m in (st.get("material_nodes") or [])],
        "layers": [l.get("name") for l in (st.get("layer_datas") or [])],
        "stages": [(s.get("name"), s.get("objects"), s.get("hidden")) for s in (st.get("stages") or [])],
    }


def bk(p):
    """Backslash path escaped for a minic string literal. REQUIRED for any
    path that ArmorPaint checks with iron_file_exists (script_append_mesh,
    script_project_open, script_import_asset): forward slashes make
    iron_file_exists return 0 (probe s1_append_probe.py)."""
    return os.path.abspath(p).replace("\\", "\\\\")


def export_obj(project, out, label="export"):
    r, _ = run_fresh(None, project,
                     f'void main() {{\n\tscript_export_mesh("{fwd(out)}");\n}}\n',
                     cleanup=[out], label=label)
    if not os.path.exists(out):
        raise RuntimeError(f"export did not produce {out}")
    with open(out, encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------- OBJ parsing

def parse_obj_groups(text):
    """Split an ArmorPaint OBJ export into ordered per-object groups.

    Returns list of dicts: name, v/vt/vn (lists of tuples, in file order for
    that group), global index ranges, faces (raw global index triples), and
    resolved faces (coordinates). Also returns diagnostics about contiguity
    and whether face indices stay inside the group's own ranges.
    """
    groups = []
    cur = None
    gv = gvt = gvn = 0  # global counts so far
    for line in text.splitlines():
        if line.startswith("o "):
            cur = {"name": line[2:], "v": [], "vt": [], "vn": [], "f": [],
                   "v0": gv, "vt0": gvt, "vn0": gvn, "interleaved": False}
            groups.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("v "):
            if cur["f"]:
                cur["interleaved"] = True
            cur["v"].append(tuple(float(x) for x in line.split()[1:4])); gv += 1
        elif line.startswith("vt "):
            if cur["f"]:
                cur["interleaved"] = True
            cur["vt"].append(tuple(float(x) for x in line.split()[1:3])); gvt += 1
        elif line.startswith("vn "):
            if cur["f"]:
                cur["interleaved"] = True
            cur["vn"].append(tuple(float(x) for x in line.split()[1:4])); gvn += 1
        elif line.startswith("f "):
            tri = []
            for tok in line.split()[1:]:
                parts = [int(p) if p else 0 for p in tok.split("/")]
                tri.append(tuple((parts + [0, 0])[:3]))
            cur["f"].append(tuple(tri))
    allv = [v for g in groups for v in g["v"]]
    allvt = [t for g in groups for t in g["vt"]]
    for g in groups:
        lo_v, hi_v = g["v0"] + 1, g["v0"] + len(g["v"])
        lo_t, hi_t = g["vt0"] + 1, g["vt0"] + len(g["vt"])
        lo_n, hi_n = g["vn0"] + 1, g["vn0"] + len(g["vn"])
        local = True
        res_pos, res_uv = [], []
        for tri in g["f"]:
            for (vi, ti, ni) in tri:
                if not (lo_v <= vi <= hi_v and lo_t <= ti <= hi_t and (ni == 0 or lo_n <= ni <= hi_n)):
                    local = False
            res_pos.append(tuple(allv[vi - 1] for (vi, _, _) in tri))
            res_uv.append(tuple(allvt[ti - 1] for (_, ti, _) in tri))
        g["faces_in_own_range"] = local
        g["resolved_pos"] = res_pos
        g["resolved_uv"] = res_uv
    return groups


def group_signature(g):
    """Order-sensitive resolved signature of one group (pos + uv per face)."""
    h = hashlib.md5()
    for p, u in zip(g["resolved_pos"], g["resolved_uv"]):
        h.update(repr((p, u)).encode())
    return h.hexdigest()


def group_summary(groups):
    return [
        {"name": g["name"], "v": len(g["v"]), "vt": len(g["vt"]), "vn": len(g["vn"]),
         "f": len(g["f"]), "faces_in_own_range": g["faces_in_own_range"],
         "interleaved": g["interleaved"], "sig": group_signature(g)}
        for g in groups
    ]


def dump(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=str)
