# 2026-09-27 — upstream sync: #2139 merged, #2148 opened, rebuilt on current upstream

- Pickup caught HANDOFF drift: #2139 had merged 2026-09-17. Grayson picked all
  five options (upstream PR, rebuild, doc fix, Phase 6 scoping, housekeeping).
- The auto-mode classifier blocked changing the shared ArmorPaint checkout and
  the remote-branch delete until Grayson confirmed explicitly. While blocked,
  prepped the patch and PR body in the scratchpad.
- Rebased the zero-init fix onto upstream `main` `85f6cf1c` and trimmed its
  comments to upstream density. Moved one `memset` below an aligned-assignment
  block so upstream's `.clang-format` shows 0 drift.
- Built stock upstream first as a baseline:
  - 10x `smooth`/`bevel` integration tests: 3/10 and 9/10 corrupted. All 12
    failures were the corruption assertions.
  - Applied the fix and rebuilt (21s incremental): 0/10 and 0/10.
- Opened #2148 from `gc-fork`.
- Diffing `--api` old vs new binary showed the script-API cleanup. The only
  name the project used that changed is `plugin_uv_unwrap_button` →
  `util_mesh_uv_unwrap` (`01bae6c5`, 39 minutes after #2139 merged). Switched
  the project to it. Full suite green.
- Fast-forwarded local `main` so the installed MCP server matches the new
  binary. Not pushed.
- Phase 6 draft by a subagent, source-read only; I spot-checked its citations.
  - Item 9's "no accessor" dead end was wrong (`object_t.ext` is exposed).
  - Item 8 now composes via `script_append_mesh` + `script_object_remove`.
  - Its 6.0 section was already done by this session; marked done.
