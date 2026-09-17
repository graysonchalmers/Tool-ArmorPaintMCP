# 2026-09-17 — root-caused smooth_mesh's flaky vertex count

- Picked up STATUS.md's open Known Issue #4 (`smooth_mesh` flaky vertex
  count, first flagged 2026-09-16 during the mesh/UV gallery session) as a
  dedicated root-cause investigation via `superpowers:systematic-debugging`,
  in a fresh worktree (`mystifying-banach-e42a6d`).
- Read ArmorPaint's own C source directly (`util_mesh.c`, `iron_array.c`,
  `args.c`, `import_arm.c`, `export_obj.c`) rather than guessing from
  symptoms. Found `util_mesh_smooth()` accumulates into `vsum`/`vbsum`/`vn`/
  `vbn` via `+=`/`++`, but those arrays are allocated with `f32_array_create`/
  `i32_array_create`, whose buffer comes from `realloc(NULL, size)` — never
  zero-filled. Every other array the function allocates is covered by plain
  assignment before use, so this is the one genuine gap.
- Called `advisor` before committing to the hypothesis or spending time on a
  rebuild. It flagged three cheap checks to run before touching the build:
  confirm no allocator override exists (one grep, confirmed clean), use
  `bevel_mesh` (same accumulate-without-zero-init pattern spotted at
  `util_mesh.c:1369-1374`) as a free discriminator against the *current*
  binary with no rebuild, and switch the repro's pass/fail metric from
  vertex count (noisy, 3/5 clean) to the near-zero-component scan (0/5 clean
  originally — the real discriminator).
- Set up `.env`/`.venv` in the worktree and ran real repros against the
  already-built `AP_BINARY` (no source changes, no rebuild): `smooth_mesh`
  10x reconfirmed the original finding (6/10 clean, 4/10 corrupted, up to
  29/96 near-zero vertices); `bevel_mesh` 10x showed the identical signature
  on the unmodified binary, confirming the bug isn't specific to
  `smooth_mesh`'s call site.
- Traced `--script`'s actual frame scheduling (`args_run_on_next_frame` →
  `import_arm_run_project` → `sys_notify_on_next_frame(&args_run_script)`)
  to rule out a project-load timing race: loading completes synchronously a
  full frame before the script runs. The apparent "timing/process-state
  dependency" is real but is heap-allocator state at process-launch time
  (fresh zeroed OS pages vs. recycled dirty heap), not frame timing.
- Wrote the confirmed root cause into STATUS.md (Known Issue #4 rewritten,
  new Known Issue #5 for `bevel_mesh`) and project memory. Deliberately did
  not write, build, or upstream a fix — task scope was root-cause only, and
  an algorithm patch to ArmorPaint's own C source is a bigger category of
  change than this project's existing registration-only patch policy.
- Commons log:
  `_agent-commons\log\2026-09-17-claude-code-armorpaint-smooth-mesh-rootcause.md`.
- Merged into `main` in a follow-up pickup session (this branch,
  `claude/mystifying-banach-e42a6d`, had gone stale — forked before the
  gallery session's handoff-log migration landed, so its HANDOFF.md/
  STATUS.md diverged and needed manual conflict resolution rather than a
  clean fast-forward).
