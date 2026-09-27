# Spike S3 — UV-coverage IoU calibration + rasterizer prototype

Run 2026-09-27 by subagent; saved by the controller from its hand-back (harness blocked the
subagent's own write). Blender 5.1.1 headless (factory startup), venv CPython 3.13, stdlib only.
ArmorPaint NOT run; ArmorPaint-specific claims source-read at `287e63f4` or emulated.
Controller verification: `selftest.py` re-run = 0 failures; `results.json` d4 / sphere_d_mirror
IoU match the table; `iron_path.c:28-35`, `iron_obj.c:628-638`, `io/import_mesh.c:38-42` read and match F2/F3.

## Method (short)
- Base A: rounded box + cylinder boss + UV-sphere knob, subdivided, Smart UV 66°/0.02 → 3148 tris,
  24 islands, 61.9% coverage. Base B: 32x16 UV sphere, default full-square UVs (93.75%).
- Variants from a fresh load of base `.blend`; OBJ export un-triangulated, UVs+normals, Y-up.
- `uvraster.py`: OBJ parser (v/vt/f/o, negative indices, all corner forms, fan-triangulate, per `o`);
  exact integer fixed-point scanline raster, top-left-equivalent tie rule, N×N count raster, UVs
  clipped to [0,1]. Metrics: coverage (count≥1), overlap (count>1 / covered), zero-area on
  ArmorPaint's 16-bit grid (+ how many have real 3D area and their 3D-surface share), flipped
  (vs area-weighted majority sign), out-of-range (>1.5e-5 outside [0,1]), islands, IoU on masks.
- Retention: share of old-layout texels (covered exactly once old, ≤1 new) whose interpolated new
  3D position is within tol × old bbox diagonal; `norm` removes translation + uniform scale (not
  rotation/mirror). Stacked texels excluded, reported as `excluded_overlap_share`.
- ArmorPaint emulation (`ap_roundtrip_uv`): import folds >1 to fraction, `(int)(u*32767)`,
  `(int)((1-v)*32767)` → int16; export back via `/32767`. `q` columns apply it to both sides.

## Results (N=256 unless noted; q = quantized, never differs by >0.0015)

| pair | family | IoU 128/256/512 | retained@5% norm |
|---|---|---|---|
| r1_noise | r | 1.0 / 1.0 / 1.0 | 1.0 |
| r2_subdiv | r | 1.0 / 1.0 / 1.0 | 1.0 |
| r3_bevel | r | 0.9999 / 0.9999 / 1.0 | 0.9999 |
| r4_extrude | r | 1.0 / 1.0 / 1.0 | 1.0 (0.914 at 2%) |
| r5_decimate 0.5 | r | 0.9989 / 0.9987 / 0.9986 | 0.9988 |
| r5b_decimate 0.2 | r | 0.9812 / 0.9825 / 0.9827 | 0.978 |
| r6_subsurf | r | 1.0 | 1.0 |
| r6b_subsurf smooth-all | r | 0.9955 / 0.9920 / 0.9941 | 0.9942 |
| r7_bigmove (~14% bbox diag) | r | 1.0 | 0.907 |
| r8_scaled 1.25 + moved | r | 1.0 | 1.0 (absolute 0.0) |
| d1_smartuv45 | d | 0.4286 / 0.4329 / 0.4294 | 0.006 |
| d2a_lightmap | d | 0.6003 / 0.5974 / 0.6035 | 0.0024 |
| d2b_cube | d | 0.5793 / 0.5916 / 0.5916 | 0.0 (85% stacked, excluded) |
| d3_repack rotate-any | d | 0.7441 / 0.7651 / 0.7628 | 0.3755 |
| d6_repack no-rotation | d | 0.9887 / 0.9895 / 0.9901 | 0.6415 |
| d4_swap 2 congruent islands | adversarial | 0.9968 / 0.9963 / 0.9961 | 0.7385 |
| d5_rot180 | adversarial | 0.3589 / 0.3590 / 0.3628 | 0.0013 |
| d7 Smart UV rerun, same settings | jitter | 0.9981 / 0.9980 / 0.9980 | 0.975 |
| sphere_r1_noise | r | 1.0 | 1.0 |
| sphere_d_mirror | adversarial | 1.0 | 0.1254 |
| sphere_d_rot180 | adversarial | 1.0 | 0.0025 |
| sphere_d_smartuv | d | 0.5168 / 0.5179 / 0.5174 | 0.001 |

Full generated tables (T1 pairs, T2 per-file metrics raw/quantized, T3 files, T4 timing): `tables.md`.

## Threshold recommendation
- **N = 256.** IoU varies ≤0.02 across N, retention ≤0.002; N=128 misses up to 3.6 coverage points
  on many-tiny-island layouts.
- **IoU alone: 0.95** — gap between lowest requested round trip (r5 0.9987) and highest requested
  re-unwrap (d3 0.7651). **But IoU cannot be the round_trip gate alone:** coverage-preserving
  rearrangements (d6 0.9895, d4 0.9963, d7 0.998, sphere mirror/rot180 1.0000) sit inside the
  round-trip range and scramble 2.5-100% of paint. No IoU threshold separates them.
- **Recommended: add texel 3D-position retention.** Error if `IoU < 0.95` or `retained(5%, norm) < 0.85`;
  warning if `retained < 0.98`. Gap for 0.85: r7 0.907 (next r5b 0.978) vs d4 0.7385. d7 (0.975) is
  below any texel statistic's resolution. 5% tolerance and 0.85 are knobs (r4 = 0.914 at 2%).
- Retention limits: stacked texels unassessable (fully stacked layout → IoU only; scramble confined
  to stacked regions escapes); needs a shared frame (translation/scale normalised, rotation/axis
  change rejects loudly); big legit part moves false-reject loudly → caller uses `mode="swap"`.

## Timing (pure stdlib, min of 5)
- r6_subsurf (12.9k tris): check_mesh_uvs 0.125 s; full replace comparison 0.33 s; raster@256 0.044 s.
- Synthetic 100k tris: check 1.59 s; compare 1.63 s; raster 128/256/512 = 0.15/0.24/0.53 s; parse 0.39 s.
- numpy NOT installed in the venv; no numpy variant built.

## Findings for 6.2 / 6.3
- **F1 zero-area rule:** strict "any zero-area UV tri = error" rejects valid meshes (fan-triangulated
  n-gon slivers; r1 noise gives them 3D area → legit round trip fails; 16-bit quantization adds/
  removes 1-3 slivers; a real extrude r4 has 16 zero-UV-area side tris = 4.14% of surface).
  Proposal: error only when UV-degenerate tris **with real 3D area** exceed ~0.1% of surface; warn below.
- **F2 importer mangles out-of-range UVs** (`iron_obj.c:628-638`): u,v > 1 fold to fraction per vertex
  (1.0000001 → ~0); negative u kept to −1; negative v below ~−3e-5 overflows int16 → v ≈ 1.9-2.0.
  Out-of-range is only reliably checkable on the **source OBJ pre-launch**; in a post-import export it
  shows only as u < 0 or v > 1.
- **F3 no native FBX:** `path_mesh_formats()` = `obj`, `blend` only (`iron_path.c:28-35`). `.blend`
  import shells out to the Blender path in ArmorPaint's config (`io/import_blend_mesh.c`), fails
  silently if unset. Other extensions go to the plugin importer map (STL only, no UVs); an
  unregistered extension's importer is called without a NULL check (`io/import_mesh.c:39-42`).
  Non-OBJ fixture should be `base.blend`.
- **F4 Smart UV Project is nondeterministic** in Blender 5.1.1: commit fixtures, never regenerate in CI.
- **F5** island count matches Blender's on every file. **F6** overlap/flipped as warnings is right
  (cube projection: 100% overlap / 50% flipped; lightmap 5.8% flipped).

## Not verified
- ArmorPaint round trip emulated, not run: ear-clip slivers for >4-gons and the export frame after
  transform carry-over unknown → re-run calibration on real ArmorPaint exports.
- F3 source-read only. No visual paint check. Only two base assets. No numpy variant.
  Fan vs ear-clip triangulation differs on concave n-gons in source OBJs.

## Files
Scripts: `gen_meshes.py`, `verify_fixtures.py`, `uvraster.py`, `selftest.py` (32/32), `run_s3.py` →
`results.json`, `timing.py` → `timing.json`, `make_tables.py` → `tables.md`. Logs: `run_s3.log`,
`timing.log`. Meshes in `meshes\` (base/base_tri/base.fbx/base.blend/nouv, r1-r8, d1-d7, sphere set,
`stats.json`). `_determinism_run1\` = evidence for F4.
