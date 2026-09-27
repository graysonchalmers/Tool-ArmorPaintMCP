import os
import random

import pytest

from armorpaint_mcp import uv_analysis as ua

UV_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "phase6", "uv")

QUAD = """o Quad
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
f 1/1 2/2 3/3 4/4
"""


def _single(text):
    obj = ua.parse_obj(text)
    (g,) = ua.groups_by_name(obj).values()
    return obj, g


def test_unit_quad_covers_everything_once():
    obj, g = _single(QUAD)
    m = ua.analyze(obj, g)
    assert m["coverage_pct"] == 100.0
    assert m["overlap_pct"] == 0.0
    assert ua.verdict(m) == {"valid": True, "errors": [], "warnings": []}


def test_duplicated_triangle_is_an_overlap_warning_not_an_error():
    text = QUAD.replace("f 1/1 2/2 3/3 4/4", "f 1/1 2/2 3/3\nf 1/1 2/2 3/3")
    obj, g = _single(text)
    v = ua.verdict(ua.analyze(obj, g))
    assert v["valid"] is True
    assert any("overlapping" in w for w in v["warnings"])


def test_reversed_winding_counts_as_flipped_warning():
    text = QUAD.replace("f 1/1 2/2 3/3 4/4", "f 1/1 2/2 3/3\nf 1/1 4/4 3/3\nf 1/1 3/3 2/2")
    obj, g = _single(text)
    m = ua.analyze(obj, g)
    assert m["flipped_tris"] == 1
    assert any("flipped" in w for w in ua.verdict(m)["warnings"])


def test_out_of_range_uvs_are_an_error_unless_allow_udim():
    obj, g = _single(QUAD.replace("vt 1 1", "vt 1.5 1"))
    m = ua.analyze(obj, g)
    assert m["out_of_range_uvs"] == 1
    assert ua.verdict(m)["valid"] is False
    relaxed = ua.verdict(m, allow_udim=True)
    assert relaxed["valid"] is True
    assert any("outside [0,1]" in w for w in relaxed["warnings"])


def test_faces_without_uvs_are_an_error():
    obj, g = _single(QUAD.replace("f 1/1 2/2 3/3 4/4", "f 1 2 3 4"))
    v = ua.verdict(ua.analyze(obj, g))
    assert v["valid"] is False
    assert any("no UVs" in e for e in v["errors"])


def test_uv_degenerate_triangles_with_3d_area_error_only_above_the_share_limit():
    # big quad (UV fine) + one small triangle whose three UVs coincide
    small = QUAD + "v 0 0 1\nv 0.01 0 1\nv 0 0.01 1\nvt 0.5 0.5\nf 5/5 6/5 7/5\n"
    obj, g = _single(small)
    m = ua.analyze(obj, g)
    assert m["zero_area_tris_with_3d_area"] == 1
    assert 0 < m["zero_area_3d_share_pct"] <= ua.ZERO_AREA_ERROR_PCT
    assert ua.verdict(m)["valid"] is True
    big = QUAD + "v 0 0 1\nv 1 0 1\nv 0 1 1\nvt 0.5 0.5\nf 5/5 6/5 7/5\n"
    obj, g = _single(big)
    assert ua.verdict(ua.analyze(obj, g))["valid"] is False


def test_raster_matches_brute_force_on_random_triangles():
    """Prototype selftest check 7: a random soup (incl. out-of-range
    triangles) snapped to the rasterizer's fixed-point grid, so the float
    point-in-triangle test is exact."""
    rng = random.Random(3)
    n = 64
    soup = [tuple(rng.uniform(-0.2, 1.2) for _ in range(6)) for _ in range(25)]
    soup = [tuple(round(x * n * ua.SUB) / (n * ua.SUB) for x in t) for t in soup]
    counts = ua.rasterize(soup, n)

    expected = [0] * (n * n)
    for x0, y0, x1, y1, x2, y2 in soup:
        for j in range(n):
            py = (j + 0.5) / n
            for i in range(n):
                px = (i + 0.5) / n
                e0 = (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0)
                e1 = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
                e2 = (x0 - x2) * (py - y2) - (y0 - y2) * (px - x2)
                if (e0 > 1e-12 and e1 > 1e-12 and e2 > 1e-12) or \
                   (e0 < -1e-12 and e1 < -1e-12 and e2 < -1e-12):
                    expected[j * n + i] += 1
    assert sum(1 for a, b in zip(counts, expected) if a != b) == 0


def test_groups_are_keyed_by_name_and_faces_rebase_cleanly():
    two = QUAD + "o Other\nv 5 5 5\nv 6 5 5\nv 5 6 5\nvt 0 0\nvt 1 0\nvt 0 1\nf 5/5 6/6 7/7\n"
    obj = ua.parse_obj(two)
    by_name = ua.groups_by_name(obj)
    assert sorted(by_name) == ["Other", "Quad"]
    solo, g = _single("o Other\nv 5 5 5\nv 6 5 5\nv 5 6 5\nvt 0 0\nvt 1 0\nvt 0 1\nf 1/1 2/2 3/3\n")
    assert ua.group_signature(obj, by_name["Other"]) == ua.group_signature(solo, g)


def _fixture(name):
    with open(os.path.join(UV_DIR, f"{name}.obj"), encoding="utf-8") as fh:
        return _single(fh.read())


def _gate_passes(cmp):
    retention_ok = cmp["retention"] is None or cmp["retention"] >= ua.RETENTION_MIN
    return cmp["iou"] >= ua.IOU_MIN and retention_ok


@pytest.mark.parametrize("name", ["r1_noise", "r2_subdiv", "r3_bevel", "r4_extrude",
                                  "r5_decimate", "r5b_decimate_heavy",
                                  "r6b_subsurf_smoothall", "r7_bigmove", "r8_scaled"])
def test_round_trip_variants_pass_the_gate(name):
    cmp = ua.compare_layouts(*_fixture("base"), *_fixture(name))
    assert _gate_passes(cmp), cmp


@pytest.mark.parametrize("name", ["d1_smartuv45", "d2a_lightmap", "d2b_cube", "d3_repack",
                                  "d4_swap", "d5_rot180", "d6_repack_norot"])
def test_different_uv_variants_fail_the_gate(name):
    cmp = ua.compare_layouts(*_fixture("base"), *_fixture(name))
    assert not _gate_passes(cmp), cmp


@pytest.mark.parametrize("name,passes", [("sphere_r1_noise", True), ("sphere_d_mirror", False),
                                         ("sphere_d_rot180", False), ("sphere_d_smartuv", False)])
def test_sphere_set_including_iou_blind_mirror_and_rotation(name, passes):
    cmp = ua.compare_layouts(*_fixture("sphere"), *_fixture(name))
    assert _gate_passes(cmp) is passes, cmp


def test_size_ratio_reports_uniform_scale():
    cmp = ua.compare_layouts(*_fixture("base"), *_fixture("r8_scaled"))
    assert cmp["size_ratio"] == pytest.approx(1.25, rel=0.02)
