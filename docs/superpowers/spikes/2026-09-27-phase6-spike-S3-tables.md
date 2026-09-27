### T1. Pair table: IoU (raw / ArmorPaint-quantized) and texel position retention

| ref | candidate | family | IoU 128 | IoU 256 | IoU 512 | IoU-q 128 | IoU-q 256 | IoU-q 512 | ret@5% abs | ret@5% norm | ret@5% norm q | ret@2% norm | ret@5% norm N128 | ret@5% norm N512 | stacked (excluded) % |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base | base_tri | self | 1.0000 | **1.0000** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0 | **1.0** | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| base | r1_noise | r | 1.0000 | **1.0000** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0 | **1.0** | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| base | r2_subdiv | r | 1.0000 | **1.0000** | 1.0000 | 0.9999 | 1.0000 | 1.0000 | 1.0 | **1.0** | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| base | r3_bevel | r | 0.9999 | **0.9999** | 1.0000 | 0.9999 | 0.9999 | 0.9999 | 0.9999 | **0.9999** | 0.9999 | 0.9999 | 0.9999 | 1.0 | 0.0 |
| base | r4_extrude | r | 1.0000 | **1.0000** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0 | **1.0** | 1.0 | 0.9142 | 1.0 | 1.0 | 0.0 |
| base | r5_decimate | r | 0.9989 | **0.9987** | 0.9986 | 0.9988 | 0.9987 | 0.9986 | 0.9988 | **0.9988** | 0.9988 | 0.9988 | 0.9989 | 0.9987 | 0.0 |
| base | r6_subsurf | r | 1.0000 | **1.0000** | 1.0000 | 0.9999 | 1.0000 | 1.0000 | 1.0 | **1.0** | 1.0 | 0.9417 | 1.0 | 1.0 | 0.0 |
| base | r5b_decimate_heavy | r | 0.9812 | **0.9825** | 0.9827 | 0.9811 | 0.9825 | 0.9826 | 0.978 | **0.978** | 0.9779 | 0.977 | 0.9764 | 0.9779 | 0.0 |
| base | r6b_subsurf_smoothall | r | 0.9955 | **0.9920** | 0.9941 | 0.9955 | 0.9919 | 0.9941 | 0.9942 | **0.9942** | 0.9941 | 0.94 | 0.9965 | 0.9949 | 0.0 |
| base | r7_bigmove | r | 1.0000 | **1.0000** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.8936 | **0.907** | 0.907 | 0.5774 | 0.9055 | 0.9072 | 0.0 |
| base | r8_scaled | r | 1.0000 | **1.0000** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0 | **1.0** | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| base | d6_repack_norot | d | 0.9887 | **0.9895** | 0.9901 | 0.9887 | 0.9910 | 0.9901 | 0.6415 | **0.6415** | 0.6415 | 0.641 | 0.6408 | 0.6412 | 0.0 |
| base | d1_smartuv45 | d | 0.4286 | **0.4329** | 0.4294 | 0.4288 | 0.4330 | 0.4294 | 0.0053 | **0.006** | 0.006 | 0.0003 | 0.0056 | 0.0061 | 0.0 |
| base | d2a_lightmap | d | 0.6003 | **0.5974** | 0.6035 | 0.6002 | 0.5974 | 0.6023 | 0.0025 | **0.0024** | 0.0024 | 0.0002 | 0.0024 | 0.0022 | 0.0 |
| base | d2b_cube | d | 0.5793 | **0.5916** | 0.5916 | 0.5792 | 0.5916 | 0.5916 | 0.0 | **0.0** | 0.0 | 0.0 | 0.0 | 0.0 | 85.34 |
| base | d3_repack | d | 0.7441 | **0.7651** | 0.7628 | 0.7440 | 0.7642 | 0.7632 | 0.3756 | **0.3755** | 0.3755 | 0.3721 | 0.3736 | 0.3754 | 0.0 |
| base | d4_swap | d-adv | 0.9968 | **0.9963** | 0.9961 | 0.9968 | 0.9963 | 0.9961 | 0.7385 | **0.7385** | 0.7385 | 0.7385 | 0.7383 | 0.7372 | 0.0 |
| base | d5_rot180 | d-adv | 0.3589 | **0.3590** | 0.3628 | 0.3589 | 0.3591 | 0.3628 | 0.0013 | **0.0013** | 0.0013 | 0.0003 | 0.0012 | 0.0013 | 0.0 |
| base | d7_smartuv_rerun | d-jitter | 0.9981 | **0.9980** | 0.9980 | 0.9981 | 0.9980 | 0.9980 | 0.975 | **0.975** | 0.975 | 0.975 | 0.9748 | 0.9751 | 0.0 |
| sphere | sphere_r1_noise | r | 1.0000 | **1.0000** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0 | **1.0** | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| sphere | sphere_d_mirror | d-adv | 1.0000 | **1.0000** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.1254 | **0.1254** | 0.1254 | 0.0491 | 0.125 | 0.1243 | 0.0 |
| sphere | sphere_d_rot180 | d-adv | 1.0000 | **1.0000** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0025 | **0.0025** | 0.0025 | 0.0004 | 0.0026 | 0.0026 | 0.0 |
| sphere | sphere_d_smartuv | d | 0.5168 | **0.5179** | 0.5174 | 0.5167 | 0.5179 | 0.5174 | 0.0018 | **0.001** | 0.001 | 0.0 | 0.001 | 0.001 | 0.0 |

### T2. Per-file check_mesh_uvs metrics, N=256 (raw file / after emulated ArmorPaint import+export)

| file | tris | n-gons>4 | islands | zero-area | zero-area w/ 3D area | zero-area 3D share % | flipped | flipped % | flipped area % | out-of-[0,1] vt | coverage % | overlap % | cov % N128 | cov % N512 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base | 3148 | 2 | 24 | 3 / 2 | 0 | 0.0 | 0 / 1 | 0.0 / 0.032 | 0.0 | 0 | 61.913 / 61.914 | 0.0 | 61.469 | 61.911 |
| base_tri | 3148 | 0 | 24 | 0 | 0 | 0.0 | 0 | 0.0 | 0.0 | 0 | 61.913 / 61.914 | 0.0 | 61.469 | 61.911 |
| d1_smartuv45 | 3148 | 2 | 38 | 1 / 3 | 0 | 0.0 | 3 / 1 | 0.095 / 0.032 | 0.0 | 0 | 44.894 / 44.896 | 0.0 | 45.081 | 44.913 |
| d2a_lightmap | 3148 | 2 | 1642 | 1 / 4 | 0 | 0.0 | 184 | 5.847 / 5.852 | 4.274 | 0 | 87.946 | 0.0 | 84.32 | 86.047 |
| d2b_cube | 3148 | 2 | 36 | 1 / 0 | 0 | 0.0 | 1574 / 1573 | 50.016 / 49.968 | 50.0 | 0 | 80.231 / 80.229 | 100.0 | 79.169 | 79.892 |
| d3_repack | 3148 | 2 | 24 | 3 / 0 | 0 | 0.0 | 1 / 2 | 0.032 / 0.064 | 0.0 | 0 | 67.459 / 67.363 | 0.0 | 68.134 | 67.162 |
| d4_swap | 3148 | 2 | 24 | 3 / 2 | 0 | 0.0 | 0 / 1 | 0.0 / 0.032 | 0.0 | 0 | 61.916 / 61.919 | 0.0 | 61.469 | 61.907 |
| d5_rot180 | 3148 | 2 | 24 | 3 / 1 | 0 | 0.0 | 0 / 3 | 0.0 / 0.095 | 0.0 | 0 | 61.913 / 61.914 | 0.0 | 61.469 | 61.913 |
| d6_repack_norot | 3148 | 2 | 24 | 3 / 1 | 0 | 0.0 | 1 | 0.032 | 0.0 | 0 | 61.827 / 61.74 | 0.0 | 61.456 | 61.958 |
| d7_smartuv_rerun | 3148 | 2 | 24 | 3 / 2 | 0 | 0.0 | 0 / 1 | 0.0 / 0.032 | 0.0 | 0 | 61.913 / 61.914 | 0.0 | 61.462 | 61.916 |
| nouv | 3148 | 2 | 0 | 0 | 0 | 0.0 | 0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 |  |  |
| r1_noise | 3148 | 2 | 24 | 3 / 2 | 3 / 2 | 0.0124 / 0.0063 | 0 / 1 | 0.0 / 0.032 | 0.0 | 0 | 61.913 / 61.914 | 0.0 | 61.469 | 61.911 |
| r2_subdiv | 12412 | 2 | 24 | 4 | 0 | 0.0 | 4 | 0.032 | 0.0 | 0 | 61.913 / 61.916 | 0.0 | 61.469 | 61.911 |
| r3_bevel | 3340 | 2 | 24 | 3 / 2 | 0 | 0.0 | 0 / 2 | 0.0 / 0.06 | 0.0 | 0 | 61.905 / 61.906 | 0.0 | 61.462 | 61.908 |
| r4_extrude | 3164 | 2 | 24 | 19 / 18 | 16 | 4.1388 | 0 / 1 | 0.0 / 0.032 | 0.0 | 0 | 61.913 / 61.914 | 0.0 | 61.469 | 61.911 |
| r5_decimate | 1574 | 2 | 30 | 0 | 0 | 0.0 | 0 | 0.0 | 0.0 | 0 | 61.852 | 0.0 | 61.401 | 61.839 |
| r5b_decimate_heavy | 628 | 2 | 39 | 0 | 0 | 0.0 | 0 | 0.0 | 0.0 | 0 | 60.997 / 60.994 | 0.0 | 60.315 | 60.914 |
| r6_subsurf | 12864 | 0 | 24 | 0 | 0 | 0.0 | 0 | 0.0 | 0.0 | 0 | 61.913 / 61.916 | 0.0 | 61.469 | 61.911 |
| r6b_subsurf_smoothall | 12864 | 0 | 24 | 0 | 0 | 0.0 | 0 | 0.0 | 0.0 | 0 | 61.684 / 61.69 | 0.0 | 61.316 | 61.645 |
| r7_bigmove | 3148 | 2 | 24 | 3 / 2 | 0 | 0.0 | 0 / 1 | 0.0 / 0.032 | 0.0 | 0 | 61.913 / 61.914 | 0.0 | 61.469 | 61.911 |
| r8_scaled | 3148 | 2 | 24 | 3 / 2 | 0 | 0.0 | 0 / 1 | 0.0 / 0.032 | 0.0 | 0 | 61.913 / 61.914 | 0.0 | 61.469 | 61.911 |
| sphere | 960 | 0 | 1 | 0 | 0 | 0.0 | 0 | 0.0 | 0.0 | 0 | 93.75 | 0.0 | 93.75 | 93.75 |
| sphere_d_mirror | 960 | 0 | 1 | 0 | 0 | 0.0 | 0 | 0.0 | 0.0 | 0 | 93.75 | 0.0 | 93.75 | 93.75 |
| sphere_d_rot180 | 960 | 0 | 1 | 0 | 0 | 0.0 | 0 | 0.0 | 0.0 | 0 | 93.75 | 0.0 | 93.75 | 93.75 |
| sphere_d_smartuv | 960 | 0 | 6 | 0 | 0 | 0.0 | 0 | 0.0 | 0.0 | 0 | 50.551 / 50.552 | 0.0 | 50.311 | 50.517 |
| sphere_r1_noise | 960 | 0 | 1 | 0 | 0 | 0.0 | 0 | 0.0 | 0.0 | 0 | 93.75 | 0.0 | 93.75 | 93.75 |

(`a / b` = raw / quantized where they differ. `nouv` has 1642 faces without UVs, 0 UV triangles.)

### T3. Files (Blender-side counts, `meshes/stats.json`)

| file | verts | faces | tris | UV layer | islands (Blender, 1e-6) | how it was made |
|---|---:|---:|---:|---|---:|---|
| base.obj | 1580 | 1642 | 3148 | True | 24 |  |
| base_tri.obj | 1580 | 1642 | 3148 | True | 24 |  |
| base.fbx |  |  |  |  |  | Blender FBX exporter, use_selection, UVs included |
| base.blend |  |  |  |  |  | saved right after unwrap; only object = Base |
| nouv.obj | 1580 | 1642 | 3148 | False |  |  |
| r1_noise.obj | 1580 | 1642 | 3148 | True | 24 | every vertex += uniform(-0.03,0.03)^3, seed 1234; UVs untouched |
| r2_subdiv.obj | 6212 | 6562 | 12412 | True | 24 | mesh.subdivide number_cuts=1 on all faces (flat, UVs interpolated) |
| r3_bevel.obj | 1676 | 1738 | 3340 | True | 24 | mesh.bevel offset 0.08 segments 2 on 48 cylinder top-rim edges |
| r4_extrude.obj | 1588 | 1650 | 3164 | True | 24 | bmesh extrude_face_region of 4 front faces (source faces deleted, as the E key does), moved -0.2 in Y |
| r5_decimate.obj | 793 | 1063 | 1574 | True | 30 | Decimate modifier COLLAPSE ratio 0.5, triangulate off, applied (delimit n/a to collapse) |
| r6_subsurf.obj | 6438 | 6432 | 12864 | True | 24 | Subsurf level 1, uv_smooth=PRESERVE_BOUNDARIES, applied |
| r5b_decimate_heavy.obj | 320 | 540 | 628 | True | 39 | Decimate COLLAPSE ratio 0.2, applied |
| r6b_subsurf_smoothall.obj | 6438 | 6432 | 12864 | True | 24 | Subsurf level 1, uv_smooth=SMOOTH_ALL (boundaries smoothed too), applied |
| r7_bigmove.obj | 1580 | 1642 | 3148 | True | 24 | 1059 sphere-knob verts moved +0.6 in X (~13% of bbox diag); UVs untouched |
| r8_scaled.obj | 1580 | 1642 | 3148 | True | 24 | all verts *1.25 then +0.5 X, -0.3 Z (mesh data, UVs untouched) |
| d6_repack_norot.obj | 1580 | 1642 | 3148 | True | 24 | uv.pack_islands rotate off, margin 0.02, shape CONCAVE |
| d1_smartuv45.obj | 1580 | 1642 | 3148 | True | 38 | Smart UV Project angle 45, margin 0.05 |
| d2a_lightmap.obj | 1580 | 1642 | 3148 | True | 1642 | uv.lightmap_pack all faces, margin 0.1 |
| d2b_cube.obj | 1580 | 1642 | 3148 | True | 36 | uv.cube_project cube_size 2, scale_to_bounds |
| d3_repack.obj | 1580 | 1642 | 3148 | True | 24 | uv.pack_islands rotate ANY, margin 0.005, shape CONCAVE (island shapes kept, rearranged) |
| d4_swap.obj | 1580 | 1642 | 3148 | True | 24 | bmesh: swap bbox centres of two islands; {"congruent_pair_found": true, "islands": 24, "swapped_faces": [62, 62], "swapped_uv_area": [0.081208, 0.081208], "swapped_bbox": [[0.2832, 0.2973], [0.2832, 0.2973]], "offset": [0.2976, 0.0]} |
| d5_rot180.obj | 1580 | 1642 | 3148 | True | 24 | all UVs (u,v) -> (1-u, 1-v) |
| sphere.obj | 482 | 512 | 960 | True | 1 |  |
| sphere_r1_noise.obj | 482 | 512 | 960 | True | 1 | every vertex += uniform(-0.02,0.02)^3, seed 1234 |
| sphere_d_mirror.obj | 482 | 512 | 960 | True | 1 | u -> 1-u (mirror) |
| sphere_d_rot180.obj | 482 | 512 | 960 | True | 1 | (u,v) -> (1-u,1-v) |
| sphere_d_smartuv.obj | 482 | 512 | 960 | True | 6 | Smart UV Project 66/0.02 on the sphere |

### T4. Timing (venv CPython 3.13.14, min / median of 5, seconds)

| stage | r6_subsurf (biggest real) (12864 tris) | synthetic 224x224 grid (100352 tris) |
|---|---:|---:|
| parse_s(min,median) | 0.025 / 0.026 | 0.39 / 0.413 |
| raster_128 | 0.025 / 0.029 | 0.147 / 0.178 |
| raster_256 | 0.044 / 0.055 | 0.237 / 0.268 |
| raster_512 | 0.076 / 0.08 | 0.529 / 0.576 |
| analyze_256_given_raster | 0.068 / 0.086 | 0.813 / 1.065 |
| of_which_islands | 0.038 / 0.056 | 0.464 / 0.589 |
| raster_positions_256 | 0.069 / 0.093 | 0.336 / 0.386 |
| position_agreement_256_norm | 0.099 / 0.105 | 0.116 / 0.131 |
| iou_256 | 0.003 / 0.003 | 0.005 / 0.006 |
| ap_quantize_all_vt | 0.011 / 0.013 | 0.095 / 0.1 |
| E2E check_mesh_uvs_256 | 0.125 / 0.144 | 1.588 / 1.77 |
| E2E replace_compare_256 | 0.331 / 0.692 | 1.629 / 1.914 |
