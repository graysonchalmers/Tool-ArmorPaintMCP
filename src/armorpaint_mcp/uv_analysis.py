"""UV-layout analysis for check_mesh_uvs and replace_mesh (Phase 6).

Pure standard library (numpy is not a dependency). Ported from spike S3's
prototype (docs/superpowers/spikes/prototypes/uvraster.py); calibration
evidence in docs/superpowers/spikes/2026-09-27-phase6-spike-S3.md.
OBJ faces are fan-triangulated; ArmorPaint ear-clips faces with more than
4 corners (base/sources/iron_obj.c), so a concave n-gon in a *source* OBJ
can rasterize slightly differently. ArmorPaint's own exports are all
triangles.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

Q = 32767                     # ArmorPaint's UV scale: int16 = uv * 32767
SUB = 256                     # raster fixed-point sub-pixel steps per pixel
HALF = SUB // 2               # pixel centre offset in fixed point
OUT_OF_RANGE_TOL = 0.5 / Q    # |excess| below half a 16-bit step = print noise
RASTER_N = 256            # S3: IoU/retention stable across N; 128 undercounts tiny islands
ZERO_AREA_ERROR_PCT = 0.1 # % of 3D surface in UV-degenerate triangles that errors (S3 F1)
# replace_mesh round_trip gate, from S3's calibration (worst round trip
# r7 retention 0.907 vs worst scramble d4 0.7385; IoU r5 0.9987 vs d3
# 0.7651). Re-checked on real ArmorPaint exports by scripts/calibrate_uv_gate.py.
IOU_MIN = 0.95
RETENTION_MIN = 0.85
RETENTION_WARN = 0.98
RETENTION_TOL = 0.05      # fraction of the old bbox diagonal
# replace_mesh warn-only band on compare_layouts' size_ratio: below half or
# over double the old object's bounding size. Not a pass/fail gate -- S2/S3
# showed a Blender FBX round trip landing at ratio 100 (unit-scale mismatch).
SIZE_RATIO_WARN = (0.5, 2.0)


# ----------------------------------------------------------------------- OBJ
@dataclass
class ObjGroup:
    name: str
    tri_v: list = field(default_factory=list)    # (i0, i1, i2) 0-based v
    tri_vt: list = field(default_factory=list)   # (t0, t1, t2) 0-based vt, parallel to tri_v
    faces: int = 0
    faces_without_uv: int = 0
    tris_without_uv: int = 0
    ngons: int = 0                                # faces with > 4 corners


@dataclass
class ObjData:
    v: list
    vt: list
    groups: list


def _idx(tok: str, count: int) -> int:
    i = int(tok)
    return i - 1 if i > 0 else count + i


def parse_obj(text: str) -> ObjData:
    v: list = []
    vt: list = []
    groups: list = []
    cur = None
    for line in text.splitlines():
        if not line or line[0] == "#":
            continue
        head = line[:2]
        if head == "v ":
            p = line.split()
            v.append((float(p[1]), float(p[2]), float(p[3])))
        elif head == "vt":
            p = line.split()
            vt.append((float(p[1]), float(p[2]) if len(p) > 2 else 0.0))
        elif head == "f ":
            if cur is None:
                cur = ObjGroup("")
                groups.append(cur)
            corners = line.split()[1:]
            nv, nt = len(v), len(vt)
            vi, ti = [], []
            has_uv = True
            for c in corners:
                parts = c.split("/")
                vi.append(_idx(parts[0], nv))
                if len(parts) > 1 and parts[1]:
                    ti.append(_idx(parts[1], nt))
                else:
                    has_uv = False
            n = len(vi)
            if n < 3:
                continue
            cur.faces += 1
            if n > 4:
                cur.ngons += 1
            if not has_uv:
                cur.faces_without_uv += 1
                cur.tris_without_uv += n - 2
                continue
            for k in range(1, n - 1):
                cur.tri_v.append((vi[0], vi[k], vi[k + 1]))
                cur.tri_vt.append((ti[0], ti[k], ti[k + 1]))
        elif head == "o " or line.rstrip() == "o":
            cur = ObjGroup(line[2:].strip())
            groups.append(cur)
    return ObjData(v, vt, groups)


def groups_by_name(obj: ObjData) -> dict[str, ObjGroup]:
    """Face-bearing groups keyed by `o` name. ArmorPaint exports one
    uniquely named group per paint object (spike S1); key by name, never
    by position -- a replace moves the new object to the end."""
    return {g.name: g for g in obj.groups if g.faces}


def group_signature(obj: ObjData, g: ObjGroup) -> tuple:
    """Resolved triangles (positions + UVs, rounded to 1e-6): equal for
    identical geometry however the global OBJ indices are offset. Raw `f`
    lines are NOT comparable across exports -- removing an object shifts
    every later group's indices (spike A, contradiction 1)."""
    v, vt = obj.v, obj.vt
    return tuple(
        tuple(tuple(round(c, 6) for c in v[i]) for i in tv)
        + tuple(tuple(round(c, 6) for c in vt[t]) for t in tt)
        for tv, tt in zip(g.tri_v, g.tri_vt))


def tri_uvs(obj: ObjData, g: ObjGroup, uv_map=None) -> list:
    """Per-triangle (u0, v0, u1, v1, u2, v2). ``uv_map`` optionally transforms each vt."""
    vt = obj.vt if uv_map is None else [uv_map(u, w) for (u, w) in obj.vt]
    out = []
    for a, b, c in g.tri_vt:
        ua, va = vt[a]
        ub, vb = vt[b]
        uc, vc = vt[c]
        out.append((ua, va, ub, vb, uc, vc))
    return out


def tri_positions(obj: ObjData, g: ObjGroup) -> list:
    v = obj.v
    return [(v[a], v[b], v[c]) for a, b, c in g.tri_v]


# ----------------------------------------------------------------- raster
def _fixed(tris: list, n: int):
    s = n * SUB
    for t in tris:
        yield (round(t[0] * s), round(t[1] * s), round(t[2] * s),
               round(t[3] * s), round(t[4] * s), round(t[5] * s))


def _row_span(ax, ay, bx, by, Y, lo, hi):
    """Narrow [lo, hi] to pixel columns i where edge a->b's inside test holds on row Y."""
    dx = bx - ax
    dy = by - ay
    bias = 0 if (dy < 0 or (dy == 0 and dx > 0)) else 1
    K = -dy * SUB
    M = dx * (Y - ay) - dy * (HALF - ax)
    need = bias - M                      # need K*i >= need
    if K > 0:
        i = -((-need) // K)              # ceil
        if i > lo:
            lo = i
    elif K < 0:
        i = (-need) // (-K)              # floor(need / K) with K < 0
        if i < hi:
            hi = i
    elif need > 0:
        return 1, 0
    return lo, hi


def rasterize(tris: list, n: int = RASTER_N) -> list:
    """Coverage-count raster (flat list, row-major, row 0 = v near 0)."""
    counts = [0] * (n * n)
    top = n - 1
    for x0, y0, x1, y1, x2, y2 in _fixed(tris, n):
        area2 = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
        if area2 == 0:
            continue
        if area2 < 0:                    # normalise to CCW; flipped tris still cover
            x1, y1, x2, y2 = x2, y2, x1, y1
        ymin = min(y0, y1, y2)
        ymax = max(y0, y1, y2)
        j0 = -((HALF - ymin) // SUB)     # ceil((ymin - HALF) / SUB)
        j1 = (ymax - HALF) // SUB
        if j0 < 0:
            j0 = 0
        if j1 > top:
            j1 = top
        for j in range(j0, j1 + 1):
            Y = j * SUB + HALF
            lo, hi = _row_span(x0, y0, x1, y1, Y, 0, top)
            lo, hi = _row_span(x1, y1, x2, y2, Y, lo, hi)
            lo, hi = _row_span(x2, y2, x0, y0, Y, lo, hi)
            if lo <= hi:
                r = j * n
                counts[r + lo:r + hi + 1] = [c + 1 for c in counts[r + lo:r + hi + 1]]
    return counts


def rasterize_positions(tris: list, pos: list, n: int = 256):
    """Like ``rasterize`` but also returns per-texel interpolated 3D position (first writer)."""
    counts = [0] * (n * n)
    px = [None] * (n * n)
    top = n - 1
    for (x0, y0, x1, y1, x2, y2), (pa, pb, pc) in zip(_fixed(tris, n), pos):
        area2 = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
        if area2 == 0:
            continue
        if area2 < 0:
            x1, y1, x2, y2 = x2, y2, x1, y1
            pb, pc = pc, pb
            area2 = -area2
        inv = 1.0 / area2
        ymin = min(y0, y1, y2)
        ymax = max(y0, y1, y2)
        j0 = max(0, -((HALF - ymin) // SUB))
        j1 = min(top, (ymax - HALF) // SUB)
        for j in range(j0, j1 + 1):
            Y = j * SUB + HALF
            lo, hi = _row_span(x0, y0, x1, y1, Y, 0, top)
            lo, hi = _row_span(x1, y1, x2, y2, Y, lo, hi)
            lo, hi = _row_span(x2, y2, x0, y0, Y, lo, hi)
            r = j * n
            for i in range(lo, hi + 1):
                k = r + i
                if counts[k] == 0:
                    X = i * SUB + HALF
                    wa = ((x2 - x1) * (Y - y1) - (y2 - y1) * (X - x1)) * inv   # edge b->c
                    wb = ((x0 - x2) * (Y - y2) - (y0 - y2) * (X - x2)) * inv   # edge c->a
                    wc = 1.0 - wa - wb
                    px[k] = (wa * pa[0] + wb * pb[0] + wc * pc[0],
                             wa * pa[1] + wb * pb[1] + wc * pc[1],
                             wa * pa[2] + wb * pb[2] + wc * pc[2])
                counts[k] += 1
    return counts, px


# ---------------------------------------------------------------- metrics
def _q(x: float) -> int:
    return round(x * Q)


def signed_area2_q(t) -> int:
    """Twice the signed UV area on ArmorPaint's 16-bit grid (exact integer)."""
    au, av, bu, bv, cu, cv = (_q(x) for x in t)
    return (bu - au) * (cv - av) - (bv - av) * (cu - au)


def _area3(p) -> float:
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = p
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    return 0.5 * math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2)


def _longest2(p) -> float:
    a, b, c = p
    return max(math.dist(a, b), math.dist(b, c), math.dist(c, a)) ** 2


def uv_islands(obj: ObjData, g: ObjGroup) -> int:
    """Triangles joined across a 3D edge whose endpoint UVs match (16-bit grid)."""
    nt = len(g.tri_v)
    parent = list(range(nt))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    vt = obj.vt
    seen = {}
    for t, (tv, tt) in enumerate(zip(g.tri_v, g.tri_vt)):
        for k in range(3):
            va, vb = tv[k], tv[(k + 1) % 3]
            ua, ub = vt[tt[k]], vt[tt[(k + 1) % 3]]
            qa = (_q(ua[0]), _q(ua[1]))
            qb = (_q(ub[0]), _q(ub[1]))
            key = (va, qa, vb, qb) if va < vb else (vb, qb, va, qa)
            o = seen.get(key)
            if o is None:
                seen[key] = t
            else:
                a, b = find(t), find(o)
                if a != b:
                    parent[a] = b
    return len({find(i) for i in range(nt)})


def analyze(obj: ObjData, g: ObjGroup, n: int = RASTER_N, uv_map=None, counts=None) -> dict:
    """check_mesh_uvs-style metrics for one object group."""
    tris = tri_uvs(obj, g, uv_map)
    ntri = len(tris)
    vt = obj.vt if uv_map is None else [uv_map(u, w) for (u, w) in obj.vt]
    used = {i for t in g.tri_vt for i in t}
    lo, hi = -OUT_OF_RANGE_TOL, 1.0 + OUT_OF_RANGE_TOL
    oor = [i for i in used if not (lo <= vt[i][0] <= hi and lo <= vt[i][1] <= hi)]
    oor_set = set(oor)
    oor_tris = sum(1 for t in g.tri_vt if t[0] in oor_set or t[1] in oor_set or t[2] in oor_set)

    areas = [signed_area2_q(t) for t in tris]
    zero = sum(1 for a in areas if a == 0)
    # A UV-degenerate triangle only loses paint if it has real 3D surface. Fan-triangulated
    # n-gons with collinear corners give triangles degenerate in BOTH spaces: harmless.
    pos3 = tri_positions(obj, g)
    a3 = [_area3(p) for p in pos3]
    tot3 = sum(a3) or 1.0
    # "has 3D area" = not a 3D sliver: height > 1e-4 x its longest edge (area > 5e-5 * L^2).
    # Catches collinear fan triangles whose printed coords (6 decimals) left ~1e-7 of area.
    zero_3d = [x for a, x, p in zip(areas, a3, pos3) if a == 0 and x > 5e-5 * _longest2(p)]
    pos_n = sum(1 for a in areas if a > 0)
    neg_n = sum(1 for a in areas if a < 0)
    pos_a = sum(a for a in areas if a > 0)
    neg_a = -sum(a for a in areas if a < 0)
    # Majority orientation = the sign carrying more UV area (ties -> positive/CCW).
    if pos_a >= neg_a:
        flip_n, flip_a = neg_n, neg_a
    else:
        flip_n, flip_a = pos_n, pos_a
    nondeg = pos_n + neg_n
    tot_a = pos_a + neg_a

    if counts is None:
        counts = rasterize(tris, n)
    covered = sum(1 for c in counts if c)
    over = sum(1 for c in counts if c > 1)
    return {
        "object": g.name,
        "faces": g.faces,
        "tris": ntri + g.tris_without_uv,
        "faces_without_uv": g.faces_without_uv,
        "ngons_gt4": g.ngons,
        "uv_islands": uv_islands(obj, g) if ntri else 0,
        "zero_area_tris": zero,
        "zero_area_tris_with_3d_area": len(zero_3d),
        "zero_area_3d_share_pct": round(100.0 * sum(zero_3d) / tot3, 4),
        "flipped_tris": flip_n,
        "flipped_pct": round(100.0 * flip_n / nondeg, 3) if nondeg else 0.0,
        "flipped_area_pct": round(100.0 * flip_a / tot_a, 3) if tot_a else 0.0,
        "out_of_range_uvs": len(oor),
        "out_of_range_tris": oor_tris,
        "raster_n": n,
        "coverage_pct": round(100.0 * covered / (n * n), 3),
        "overlap_pct": round(100.0 * over / covered, 3) if covered else 0.0,
    }


def iou(ca: list, cb: list) -> float:
    inter = union = 0
    for a, b in zip(ca, cb):
        if a or b:
            union += 1
            if a and b:
                inter += 1
    return inter / union if union else 1.0


def bbox_diag(points) -> float:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return math.dist((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def _normaliser(counts_a, pa, counts_b):
    """Centroid + RMS radius of positions on texels covered exactly once in both rasters."""
    pts = [pa[k] for k in range(len(counts_a)) if counts_a[k] == 1 and counts_b[k] == 1]
    if not pts:
        return (0.0, 0.0, 0.0), 1.0
    n = len(pts)
    c = (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)
    s = math.sqrt(sum((p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2 for p in pts) / n) or 1.0
    return c, s


def position_agreement(old: tuple, new: tuple, diag: float, tols=(0.02, 0.05), normalize=False) -> dict:
    """Texel 3D-position agreement between two (counts, positions) rasters.

    Only texels covered exactly once in the old raster and at most once in the new
    one are assessable: a stacked texel (count > 1) has no single 3D position, and
    the first-writer position depends on triangle order. ``excluded_overlap_share``
    reports how much of the old coverage that leaves out.

    * ``retained_<tol>``: share of assessable old texels that the new layout covers
      AND maps to within tol * diag (paint that lands where it was). A texel the new
      layout no longer covers counts as not retained.
    * ``agree_<tol>``: same, but only over texels covered once in both.
    """
    ca, pa = old
    cb, pb = new
    if normalize:
        # remove translation + uniform scale (NOT rotation/mirror: those scramble paint on
        # symmetric meshes and must stay visible); distances end up in old-mesh units
        c0, s0 = _normaliser(ca, pa, cb)
        c1, s1 = _normaliser(cb, pb, ca)
        sc = s0 / s1

        def fix(q):
            return None if q is None else (c0[0] + (q[0] - c1[0]) * sc, c0[1] + (q[1] - c1[1]) * sc,
                                           c0[2] + (q[2] - c1[2]) * sc)
        pb = [fix(p) for p in pb]
    old_cov = 0
    assessable = 0
    dists = []
    for k in range(len(ca)):
        c = ca[k]
        if not c:
            continue
        old_cov += 1
        if c != 1 or cb[k] > 1:
            continue
        assessable += 1
        if cb[k] == 1:
            dists.append(math.dist(pa[k], pb[k]))
    out = {"old_covered": old_cov, "assessable_texels": assessable, "compared_texels": len(dists),
           "excluded_overlap_share": round(1 - assessable / old_cov, 4) if old_cov else None}
    if dists:
        srt = sorted(dists)
        out["median_dist_rel"] = round(srt[len(srt) // 2] / diag, 5)
    for t in tols:
        lim = t * diag
        within = sum(1 for x in dists if x <= lim)
        out[f"agree_{t}"] = round(within / len(dists), 4) if dists else None
        out[f"retained_{t}"] = round(within / assessable, 4) if assessable else None
    return out


def verdict(metrics: dict, allow_udim: bool = False) -> dict:
    """Tiered judgement of one object's analyze() metrics (docs/PLAN.md
    6.2): errors make the UVs unusable for painting, warnings are often
    deliberate (mirrored/stacked islands)."""
    errors, warnings = [], []
    if metrics["faces_without_uv"]:
        errors.append(f"{metrics['faces_without_uv']} face(s) have no UVs")
    share = metrics["zero_area_3d_share_pct"]
    if share > ZERO_AREA_ERROR_PCT:
        errors.append(f"UV-degenerate triangles cover {share}% of the surface "
                      f"(limit {ZERO_AREA_ERROR_PCT}%): paint can't land there")
    elif metrics["zero_area_tris_with_3d_area"]:
        warnings.append(f"{metrics['zero_area_tris_with_3d_area']} UV-degenerate "
                        f"triangle(s) with 3D area ({share}% of the surface)")
    if metrics["out_of_range_uvs"]:
        msg = f"{metrics['out_of_range_uvs']} UV(s) outside [0,1]"
        if allow_udim:
            warnings.append(msg)
        else:
            errors.append(msg + " (pass allow_udim=True for a UDIM layout)")
    if metrics["overlap_pct"]:
        warnings.append(f"{metrics['overlap_pct']}% of covered texels are shared "
                        f"by overlapping UVs")
    if metrics["flipped_tris"]:
        warnings.append(f"{metrics['flipped_tris']} flipped UV triangle(s) "
                        f"({metrics['flipped_pct']}%)")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def compare_layouts(old_obj: ObjData, old_g: ObjGroup, new_obj: ObjData,
                    new_g: ObjGroup, n: int = RASTER_N) -> dict:
    """replace_mesh's UV-match signals. `iou`: UV-coverage overlap. `retention`:
    share of the old layout's texels whose new 3D position lies within
    RETENTION_TOL of the old bbox diagonal after removing translation and
    uniform scale -- catches coverage-preserving scrambles IoU can't see
    (island swaps, mirrors). None when no texel is assessable (fully stacked
    layout). `size_ratio`: new bbox diagonal / old."""
    old_pos, new_pos = tri_positions(old_obj, old_g), tri_positions(new_obj, new_g)
    old_r = rasterize_positions(tri_uvs(old_obj, old_g), old_pos, n)
    new_r = rasterize_positions(tri_uvs(new_obj, new_g), new_pos, n)
    old_diag = bbox_diag([p for t in old_pos for p in t])
    new_diag = bbox_diag([p for t in new_pos for p in t])
    agree = position_agreement(old_r, new_r, old_diag, tols=(RETENTION_TOL,),
                               normalize=True)
    return {"iou": round(iou(old_r[0], new_r[0]), 4),
            "retention": agree[f"retained_{RETENTION_TOL}"],
            "excluded_overlap_share": agree["excluded_overlap_share"],
            "size_ratio": round(new_diag / old_diag, 4) if old_diag else None}
