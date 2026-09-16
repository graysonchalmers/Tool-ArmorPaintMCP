# Tool-ArmorPaintMCP — design spec

**Date:** 2026-09-15
**Status:** approved by Grayson via brainstorming session; not yet implemented.
**Author:** Claude (claude-code), with Grayson Chalmers steering.

## Problem

Grayson wants an MCP server that lets an AI assistant drive
[ArmorPaint](https://armorpaint.org) — specifically, batch operations against
existing `.arm` projects: re-export at different presets/resolutions, rebake,
swap texture sets, without opening the GUI for each pass.

A reference implementation already exists
([gprethesh/armorpaint-mcp](https://github.com/gprethesh/armorpaint-mcp),
cloned locally to `z-Git\armorpaint-mcp`) but its architecture has real risks
this project intentionally avoids (see "Why not the reference approach").

## Why not the reference approach

The reference project **patches ArmorPaint's own C source and rebuilds a
custom binary**, on the stated premise that ArmorPaint has no
plugin/extension SDK. A direct read of the local ArmorPaint checkout
(`z-Git\ArmorPaint`, `main`, the from-scratch C/"iron"+Kore engine rewrite)
shows that premise is false, or at least far less true than assumed:

- `paint/sources/args.c` — real CLI flags: `--background` (headless),
  `--export-textures/--export-mesh/--export-material` (native batch export),
  `--script <path>` (runs an arbitrary script against the opened project),
  `--api` (prints the full scripting API reference, project-context-aware).
- `paint/sources/minic_api_list.h` (607 lines) — hundreds of natively
  registered script-callable functions (object/transform/camera/mesh/
  shader/data/etc.) — a real, first-party automation surface.
- `paint/sources/ui/tab_scripts.c` — the app's own in-editor Scripts tab is a
  `.c` script editor with a **Run** button wired directly to `minic_eval()`.

The reference's bridge reaches into ~40 private structs/globals with zero
stable API, has two source patches that silently no-op if upstream drifts,
zero tests, zero CI, and is unverified on Windows despite having Windows
code paths. None of that risk is necessary if the native scripting surface
covers what we need — and for the "batch re-export of existing projects"
scope, it does.

**Decision: no source patching, no custom rebuild.** This project drives the
stock ArmorPaint binary Grayson already built locally, via its own CLI flags
and scripting engine — the same non-invasive shape as the local sibling
project [Tool-MaterialMaker-MCP](../../../../Tool-MaterialMaker-MCP), which
solves a structurally identical problem (AI-drive a creative desktop app) by
driving Material Maker's existing headless export flag and an addon loaded
through Material Maker's own addon mechanism, never a source patch.

## Scope (v1)

**In scope:** batch operations against an existing `.arm` project — re-export
at a different preset/resolution, rebake, swap texture sets. This deliberately
excludes authoring a material from scratch (node-graph generation from a
text/style description) — that's a harder, generative problem deferred to a
later phase if this proves useful.

**Out of scope for v1:**
- Live/interactive GUI-attached sessions (see "Deferred: live mode" below).
- Painting (brush strokes) — inherently an interactive operation, doesn't fit
  the one-shot batch model.
- Arbitrary node-graph authoring/material creation from scratch.

## Architecture

Python MCP server, stdio transport, official `mcp` SDK (matches
Tool-MaterialMaker-MCP's stack exactly). Each tool call:

1. Validate parameters (paths within `AP_ALLOWED_ROOTS` if set).
2. Build a CLI arg list for `ArmorPaint.exe --background <project.arm> [native export flags | --script <generated.c>]`.
   - Pure re-export at a different preset/resolution needs only native flags
     (`--export-textures <type> <preset> <path>`) — **no script involved**.
   - Rebaking needs a script, since baking isn't exposed as a CLI flag; the
     script comes from a small parameterized template in `templates/`, not
     generated node-graph code.
3. Spawn the process, wait for exit (with timeout).
4. Scan the output directory for expected files.
5. Return a structured result (success/failure, file paths, trimmed
   stderr/log excerpt on failure) to the assistant.

No source patch, no rebuild step, runs against the stock binary already
built and verified locally today (2026-09-15).

### Components

| Piece | Job |
|---|---|
| `runner.py` | Subprocess wrapper — builds args, writes temp script if needed, launches, enforces timeout, captures exit code/stdout/stderr, cleans up temp files |
| `templates/` | Small parameterized minic (`.c`) script snippets for operations native flags don't cover (rebake, texture-set swap) |
| `catalog.py` | Builds bake-type/blend-mode/preset lists dynamically from `--api` output and `export_presets/*.json` on disk — no hardcoded magic numbers (the reference hardcoded 14 bake types and 18 blend modes as constants that can silently go stale; we don't) |
| `server.py` | MCP tool definitions (below) |
| `.env` / `AP_*` env vars | `AP_BINARY`, `AP_OUTPUT_DIR`, `AP_ALLOWED_ROOTS` — same config shape as Tool-MaterialMaker-MCP's `MM_*` |
| `--check` | Preflight command: binary path valid, output dir writable, one real `--api` invocation to catch the known "exe needs `paint\build\out\data` next to it" launch gotcha before a client hits it |

### Tools (v1)

- `list_export_presets` — read-only, from the catalog.
- `inspect_project(project)` — read-only `.arm` metadata (objects, materials,
  layers) via a read-only script.
- `reexport_project(project, preset, resolution, output_dir)` — native flags
  only, no script.
- `rebake_and_export(project, bake_types, preset, output_dir)` — minic script
  (from template) + export flags. Operates on a **copy** of the project by
  default (see Safety).
- `run_script(project, script_path)` — escape hatch for anything the
  purpose-built tools don't cover yet. Not gated behind an extra opt-in flag
  the way the reference's `armorpaint_run_script` is, since minic is not a
  general-purpose OS-level scripting language the way the reference's
  `minic_eval` framing implied — same trust level as the other tools, but
  flagged here as the one tool whose blast radius is scoped only by what the
  caller's script does, not by our own tool logic.

## Data flow

```
MCP tool call
  → validate params (path sandboxing via AP_ALLOWED_ROOTS)
  → build args / write temp script
  → subprocess.run(ArmorPaint.exe, timeout=...)
  → scan output dir for expected files
  → structured JSON result back to assistant
```

## Error handling

- **Timeout:** kill the process, return "outcome uncertain, inspect the
  project directly" — the one case that can't be fully verified.
- **Non-zero exit or missing expected output files:** surface a trimmed
  stderr/log excerpt as the tool error.
- Because each call is a clean one-shot process (no persistent session
  state), there's no lingering-state ambiguity the way the reference's
  file-mailbox protocol has (matching request/response ids, session
  rotation detection, etc.) — a real simplification, not just a smaller
  feature set.

## Safety

- No native-side trust boundary exists to reinforce, because this design
  never touches ArmorPaint's source — the stock binary has ArmorPaint's own
  normal OS-level file permissions and nothing else. All safety lives in the
  Python layer:
  - `AP_ALLOWED_ROOTS` (optional, `os.pathsep`-separated) enforced **before**
    any path reaches the subprocess.
  - `rebake_and_export` operates on a **copy** of the source `.arm` project
    by default, rather than mutating the caller's file in place (since
    baking can change a project's saved layer/texture state). An explicit
    `in_place: true` param opts out.
  - No arbitrary path traversal (`..`, absolute-path escapes) in any
    project/output-dir argument.

## Testing

- Unit tests for arg-building, catalog-loading, and template-substitution
  logic — fast, no ArmorPaint process involved.
- One real integration smoke test that shells out to the actual local
  `ArmorPaint.exe` against a small sample `.arm` project and asserts expected
  output files land. Mirrors Tool-MaterialMaker-MCP's
  `pytest -m "not integration"` split.
- This is a materially stronger testing story than the reference (zero
  tests of any kind), because the integration surface here is "a process
  exits 0 and expected files exist," not "a custom-compiled binary with
  ~40 private-struct dependencies behaves correctly."

## What "better than the reference" concretely means here

1. **No source patching or custom rebuild** — runs against the stock binary,
   eliminates the reference's entire silent-patch-drift and
   custom-compile-fragility risk class.
2. **Dynamic catalogs, not hardcoded enums** — bake types, blend modes, and
   export presets are read from the app itself (`--api`, `export_presets/*.json`),
   so they can't silently go stale the way the reference's magic numbers can.
3. **Windows-first, actually verified** — the reference's Windows code paths
   have never been built or run by anyone; this project is Windows-native
   from day one, on the same machine ArmorPaint itself already builds and
   runs on.
4. **A real testing story** — unit tests plus one true end-to-end smoke test,
   versus the reference's zero tests and zero CI.
5. **Copy-by-default safety** for mutating operations, versus the reference's
   reliance on the calling LLM to remember to checkpoint before destructive
   calls.
6. **Narrower, honest v1 scope** — batch re-export/rebake of existing
   projects, not a from-scratch attempt at parity with all 41 of the
   reference's tools (including painting and node-graph authoring, both of
   which fit a live/interactive model far better than a one-shot batch
   model).

## Deferred: live mode

Grayson's stated goal is "both, batch first." A live/interactive
GUI-attached session (assistant edits materials/layers while Grayson watches
in the open app, akin to Tool-MaterialMaker-MCP's "Live mode" addon) is
explicitly deferred, not rejected. `--script` runs a script once at startup
against a project opened via CLI args — there's no built-in "keep a headless
process alive and feed it more work later" mode, and no evidence yet of a way
to inject new script content into an already-running GUI instance without
some additional mechanism.

When live mode is tackled, two live-mode architecture options identified
during this brainstorm should be re-evaluated then, not decided now:

- **A (no patch, ever):** find some way to drive an already-open instance
  using only what ArmorPaint already exposes (needs further investigation —
  not yet confirmed possible).
- **B (small, scoped patch):** add one narrow, self-contained "watch a
  directory for new script files and eval them on change" loop — nowhere
  near the reference's ~40-struct-deep bridge, but still a real source patch
  and custom rebuild, with the same version-drift risk class (mitigated by
  keeping the patch surface to exactly one small, well-tested insertion
  point, unlike the reference's silent-no-op patches).

This project should not commit to B until A is proven insufficient by actual
attempted use.

## Open items for implementation planning

- Exact minic script templates for rebake/texture-swap need to be written
  and tested against a real `.arm` sample project — the design above assumes
  minic's registered API (`minic_api_list.h`) covers what's needed for
  bake-type invocation and layer/texture-set swaps, but this hasn't been
  hands-on verified yet (the `--api` output and a real script run against a
  throwaway project are the way to confirm before writing `catalog.py`).
- Project has no git repo, no package scaffold, no build-stamp yet (per root
  `C:\Projects-local\CLAUDE.md`'s SOP) — recommend running `project-setup`
  before or alongside the implementation plan.
- License: reference is MIT with no attribution burden for a derivative;
  this project doesn't reuse any of its code, so licensing here is a fresh
  choice, not a constraint inherited from the reference.
