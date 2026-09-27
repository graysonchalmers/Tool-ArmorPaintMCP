"""Synthetic self-tests for uvraster.py (run before trusting any real-mesh number)."""
import random
import sys

import uvraster as ur

FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILS.append(name)


def obj_from_tris(tris, name="t"):
    lines = [f"o {name}"]
    for t in tris:
        for k in range(3):
            lines.append(f"v {t[2*k]} {t[2*k+1]} 0")
            lines.append(f"vt {t[2*k]} {t[2*k+1]}")
    for i in range(len(tris)):
        b = 3 * i
        lines.append(f"f {b+1}/{b+1} {b+2}/{b+2} {b+3}/{b+3}")
    return ur.parse_obj("\n".join(lines))


def cov(tris, n):
    c = ur.rasterize(tris, n)
    covered = sum(1 for x in c if x)
    over = sum(1 for x in c if x > 1)
    return covered, over, c


# 1. unit square as 2 triangles: 100% coverage, 0 overlap, every N (incl. odd)
sq = [(0, 0, 1, 0, 1, 1), (0, 0, 1, 1, 0, 1)]
for n in (7, 128, 256, 512):
    c, o, _ = cov(sq, n)
    check(f"unit square N={n}", c == n * n and o == 0, f"covered={c}/{n*n} overlap={o}")

# 2. duplicated triangle -> every covered texel is overlap
tri = (0.1, 0.1, 0.9, 0.2, 0.4, 0.8)
c, o, _ = cov([tri, tri], 256)
check("duplicate tri -> 100% overlap", c > 0 and o == c, f"covered={c} overlap={o}")

# 3. wound-reversed copy covers the same texels, and analyze() counts it as flipped
rev = (tri[0], tri[1], tri[4], tri[5], tri[2], tri[3])
c1, _, r1 = cov([tri], 256)
c2, _, r2 = cov([rev], 256)
check("reversed winding covers same texels", r1 == r2 and c1 == c2 and c1 > 0, f"{c1} vs {c2}")
small_rev = (0.05, 0.05, 0.05, 0.1, 0.1, 0.05)   # CW, small
f_obj = obj_from_tris(sq + [small_rev])
m = ur.analyze(f_obj, f_obj.groups[0], 256)
check("flipped counted vs area-majority", m["flipped_tris"] == 1 and m["zero_area_tris"] == 0, str(m))

# 4. triangle partly outside [0,1]: clipped in raster, counted out-of-range
out = (0.5, 0.5, 1.5, 0.5, 0.5, 1.5)
o_obj = obj_from_tris([out])
m = ur.analyze(o_obj, o_obj.groups[0], 256)
check("partly-outside tri: out_of_range_uvs == 2", m["out_of_range_uvs"] == 2, str(m["out_of_range_uvs"]))
check("partly-outside tri: clipped coverage ~25%", 24.0 < m["coverage_pct"] <= 25.5, str(m["coverage_pct"]))

# 5. zero-area (collinear / coincident) triangles
z_obj = obj_from_tris([(0.1, 0.1, 0.1, 0.1, 0.1, 0.1), (0.1, 0.1, 0.5, 0.5, 0.9, 0.9), (0.1, 0.1, 0.9, 0.1, 0.1, 0.9)])
m = ur.analyze(z_obj, z_obj.groups[0], 256)
check("zero-area count == 2", m["zero_area_tris"] == 2, str(m["zero_area_tris"]))

# 6. watertightness: jittered grid mesh over [0,1]^2 (arbitrary float verts) and a grid
#    whose verts sit exactly on pixel centres (maximal tie cases). Expect 100% / 0 overlap.
def grid(k, jitter, rnd, snap_n=None):
    pts = {}
    for i in range(k + 1):
        for j in range(k + 1):
            u, v = i / k, j / k
            if 0 < i < k and 0 < j < k:
                u += rnd.uniform(-jitter, jitter) / k
                v += rnd.uniform(-jitter, jitter) / k
                if snap_n:
                    u = (round(u * snap_n - 0.5) + 0.5) / snap_n
                    v = (round(v * snap_n - 0.5) + 0.5) / snap_n
            pts[i, j] = (u, v)
    tris = []
    for i in range(k):
        for j in range(k):
            a, b, c, d = pts[i, j], pts[i + 1, j], pts[i + 1, j + 1], pts[i, j + 1]
            if (i + j) % 2:
                tris += [(*a, *b, *c), (*a, *c, *d)]
            else:
                tris += [(*a, *b, *d), (*b, *c, *d)]
    return tris


rnd = random.Random(7)
for n in (128, 256, 512):
    t = grid(37, 0.2, rnd)
    c, o, _ = cov(t, n)
    check(f"jittered grid watertight N={n}", c == n * n and o == 0, f"covered={c}/{n*n} overlap={o}")
    t = grid(16, 0.2, rnd, snap_n=n)
    c, o, _ = cov(t, n)
    check(f"pixel-centre-snapped grid watertight N={n}", c == n * n and o == 0, f"covered={c}/{n*n} overlap={o}")
# fan of 8 triangles around a vertex that sits exactly on a pixel centre
cx = cy = (100 + 0.5) / 256
ring = [(0.2, 0.2), (0.4, 0.15), (0.6, 0.2), (0.65, 0.4), (0.6, 0.6), (0.4, 0.65), (0.2, 0.6), (0.15, 0.4)]
fan = [(cx, cy, *ring[i], *ring[(i + 1) % 8]) for i in range(8)]
c, o, r = cov(fan, 256)
k = 100 * 256 + 100
check("fan around pixel-centre vertex: centre texel counted once", r[k] == 1 and o == 0, f"count={r[k]} overlap={o}")

# 7. brute-force cross-check against a float point-in-triangle test (non-tie texels)
def brute(tris, n):
    out = [0] * (n * n)
    for t in tris:
        (x0, y0, x1, y1, x2, y2) = t
        for j in range(n):
            py = (j + 0.5) / n
            for i in range(n):
                px = (i + 0.5) / n
                e0 = (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0)
                e1 = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
                e2 = (x0 - x2) * (py - y2) - (y0 - y2) * (px - x2)
                if (e0 > 1e-12 and e1 > 1e-12 and e2 > 1e-12) or (e0 < -1e-12 and e1 < -1e-12 and e2 < -1e-12):
                    out[j * n + i] += 1
    return out


rnd = random.Random(3)
soup = [tuple(rnd.uniform(-0.2, 1.2) for _ in range(6)) for _ in range(25)]
n = 64
# snap to the rasterizer's fixed-point grid so the float brute force is exact (not a tie-free
# comparison otherwise: vertex rounding alone moves edges by up to 1/(2*n*SUB))
soup = [tuple(round(x * n * ur.SUB) / (n * ur.SUB) for x in t) for t in soup]
a = ur.rasterize(soup, n)
b = brute(soup, n)
diff = sum(1 for x, y in zip(a, b) if x != y)
check("random soup matches brute force (N=64, 25 tris incl. out-of-range)", diff == 0, f"differing texels={diff}")

# 8. OBJ parser forms
txt = """# test
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
v 0.5 1.5 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
vt 0.5 1.0
vn 0 0 1
o A
f 1/1/1 2/2/1 3/3/1 4/4/1
f -5/-5 -4/-4 -2/-2
o B
f 1//1 2//1 3//1
f 1 2 3
f 1/1/1 2/2/1 3/3/1 5/5/1 4/4/1
"""
p = ur.parse_obj(txt)
A, B = p.groups
check("parser: two o groups", [g.name for g in p.groups] == ["A", "B"])
check("parser: quad fanned + negative indices", len(A.tri_vt) == 3 and A.tri_vt[2] == (0, 1, 3), str(A.tri_vt))
check("parser: v//vn and bare v = faces without UV", B.faces_without_uv == 2, str(B.faces_without_uv))
check("parser: pentagon fanned to 3 tris, counted as ngon", len(B.tri_vt) == 3 and B.ngons == 1)

# 9. ArmorPaint round-trip emulation
check("ap: 0.0 stays 0", ur.ap_roundtrip_uv(0.0, 0.0) == (0.0, 0.0), str(ur.ap_roundtrip_uv(0.0, 0.0)))
check("ap: 1.0 stays 1.0", ur.ap_roundtrip_uv(1.0, 1.0) == (1.0, 1.0), str(ur.ap_roundtrip_uv(1.0, 1.0)))
u, v = ur.ap_roundtrip_uv(1.25, 0.3)
check("ap: u 1.25 folds to 0.25", abs(u - 0.25) < 1e-4, str((u, v)))
u, v = ur.ap_roundtrip_uv(-0.1, 0.3)
check("ap: u -0.1 is NOT folded", abs(u + 0.1) < 1e-4, str((u, v)))
u, v = ur.ap_roundtrip_uv(-1.5, 0.3)
check("ap: u -1.5 wraps int16 (garbage)", abs(u + 1.5) > 0.1, str((u, v)))
u, v = ur.ap_roundtrip_uv(0.123456, 0.654321)
check("ap: in-range error < 2 steps", abs(u - 0.123456) < 2 / 32767 and abs(v - 0.654321) < 2 / 32767, str((u, v)))

# 10. IoU
_, _, ra = cov([(0, 0, 0.5, 0, 0, 0.5)], 128)
_, _, rb = cov([(0.5, 0.5, 1, 0.5, 0.5, 1)], 128)
check("iou identical == 1", ur.iou(ra, ra) == 1.0)
check("iou disjoint == 0", ur.iou(ra, rb) == 0.0)

# 11. position retention must not depend on triangle order (stacked texels are excluded)
def posmap(tris, n=128):
    pos = [((t[0], t[1], 0.0), (t[2], t[3], 0.0), (t[4], t[5], 0.0)) for t in tris]
    return ur.rasterize_positions(tris, pos, n)


stacked = [(0.1, 0.1, 0.9, 0.1, 0.1, 0.9), (0.1, 0.1, 0.1, 0.9, 0.9, 0.1)]  # same footprint, opposite winding
flat = grid(8, 0.1, random.Random(5))
r = ur.position_agreement(posmap(stacked), posmap(stacked[::-1]), 1.0)
check("retention: fully stacked layout is not assessable (None), not 0", r["retained_0.05"] is None, str(r))
r = ur.position_agreement(posmap(flat), posmap(flat[::-1]), 1.0)
check("retention: identical mesh, reversed tri order == 1.0", r["retained_0.05"] == 1.0, str(r))

print("\n%d failure(s)" % len(FAILS))
sys.exit(1 if FAILS else 0)
