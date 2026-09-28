# Phase 6 fixtures (committed 2026-09-27 from spikes; see docs/superpowers/spikes/)

Do NOT regenerate `uv/`: Blender 5.1.1's Smart UV Project is nondeterministic
(S3 finding F4), so a regenerated set would not reproduce the calibration.
`MANIFEST.md5` pins every file; `.gitattributes` keeps line endings byte-exact.

- `objects3.arm`: `script_project_new()` + `script_shape_add("cone")` +
  `script_shape_add("torus")` -> objects `Tessellated`, `Cone`, `Torus`.
- `objects3_v2.arm`: as above, plus material override `MatB` on `Cone` and
  loc (1.5, -0.75, 0.25), 30 deg about z, scale (1, 2, 0.5).
- `objects3_v4_parented.arm`: v2 with `Cone` parented under `Tessellated`.
- `repl_grid5.{obj,glb,fbx,blend}`: one UV'd replacement mesh (`o` name
  `ReplGrid`), exported from Blender 5.1.1. The FBX imports at 100x (Blender
  default unit scale). `.blend` needs ArmorPaint's Blender path configured.
- `repl_grid5_named_cone.obj`: same mesh, `o` name `Cone`.
- `repl_grid5_nouv.obj`: same mesh, no `vt`.
- `uv/`: S3 calibration set. `base.obj` + round-trip variants `r*` (UVs
  kept) + different-UV variants `d*` + the sphere set. `stats.json`
  describes how each was made (no d7 entry: d7 is run 1's base).

Generators/prototypes: `docs/superpowers/spikes/prototypes/`.
