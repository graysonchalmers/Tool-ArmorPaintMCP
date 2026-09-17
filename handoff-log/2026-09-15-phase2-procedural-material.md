# 2026-09-15 — Phase 2 rescope + `create_procedural_material` subagent-driven execution

- Picked up mid-Phase-2 with an already-blocked finding (baking unreachable)
  and a fresh AskUserQuestion pivot to "material-graph editing." Immediately
  found texture-swap ALSO blocked (minic struct-access limit, isolated via a
  3-step bisection spike) and pivoted again to "procedural material
  authoring" — the user confirmed both pivots via AskUserQuestion.
- Spiked the new scope directly: a checker-node-to-output connection,
  saved via `--script`, then exported via Phase 1's existing
  `reexport_project()` — produced flat gray, indistinguishable from an
  untouched default project. Root-caused via elimination (not guessing):
  confirmed `script_fill_layer()` + `export_texture_run()` both work when
  called in the SAME process as the graph-build, and confirmed the
  save/reload split is what loses the rendered pixels, via two spikes
  (solid RGB, then checker) that each failed through the split path and
  succeeded through the same-process path.
- Surfaced the finding to the user via AskUserQuestion (not a silent
  architecture swap) — confirmed proceeding with the single-process design.
- Updated `docs/PLAN.md`'s Phase 2 section and added a second spec
  amendment documenting all three findings (baking blocked, texture-swap
  blocked, procedural-authoring-single-process-only) before writing any
  implementation plan, so the "why this architecture" reasoning has a
  durable home independent of this conversation.
- Wrote and executed a 7-task implementation plan via subagent-driven-
  development: extracted a shared `_poll_and_terminate` helper (Task 1),
  built the minic script generator for a deliberately narrow v1 node-spec
  schema (checker/solid only — Task 2), added `run_procedural_material`
  (single-process launch, no `--background` — Task 3), wired the MCP tool
  plus a small bonus `list_available_presets` tool (Task 4), added a real
  integration test with genuine pixel-content verification (Task 5),
  generated and personally viewed real gallery output (Task 6), and ran a
  final verification sweep updating `STATUS.md` (Task 7). All 7 task
  reviews came back clean.
- Final whole-branch review (opus) caught a cross-task bug invisible to any
  single task's review: `preset` was a no-op in the script-export path, and
  `preset="base_color"` specifically returned a false `ok=True` for the
  wrong export. Also caught unguarded overflow/NaN/Infinity in numeric
  node-spec params. Fixed both plus 3 Minor doc-consistency issues in one
  fix wave; scoped re-review came back clean (one cosmetic finding parked,
  not fixed).
- Merged `phase2-procedural-material` into `main` (fast-forward,
  `aa5de5c..1ac4d47`), re-verified green on the merged result, pushed to
  origin, removed the worktree and branch.
