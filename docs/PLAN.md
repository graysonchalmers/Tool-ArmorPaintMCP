# Phase plan — Tool-ArmorPaintMCP

Full design: [superpowers/specs/2026-09-15-armorpaint-mcp-design.md](superpowers/specs/2026-09-15-armorpaint-mcp-design.md).

Gate rule: never start Phase N+1 until Phase N's gate is green and recorded
in [STATUS.md](../STATUS.md) with evidence.

## Phase 0 — Scaffold + smoke harness

Standard kit (README, CLAUDE.md, HANDOFF.md, STATUS.md, this file,
`.gitignore`, `.env.example`, build stamp), package skeleton
(`config.py`/`doctor.py`/`server.py`) with **zero MCP tools yet**, git repo,
GitHub repo.

**Gate:** `smoke/smoke.ps1` exits 0. `ap-mcp --version` and `ap-mcp --help`
both exit 0. (`pytest -q` collects zero tests at this phase — pytest's own
exit 5 for that case is expected, not a failure; the first real tests land
in Phase 1.)

## Phase 1 — `reexport_project`

The first real tool: re-export an existing `.arm` project at a different
export preset/resolution, using ArmorPaint's native
`--background --export-textures <type> <preset> <path>` flags directly — no
minic script involved. Includes `runner.py` (the subprocess wrapper:
build args, spawn, timeout, capture exit code/stdout/stderr, scan output
dir) and `paths.py` (AP_ALLOWED_ROOTS enforcement, path-traversal rejection).

**Gate:** an integration smoke test shells out to the real local ArmorPaint
build against a small sample `.arm` project and asserts the expected texture
files land on disk. Unit tests for arg-building pass without ArmorPaint
running.

## Phase 2 — `rebake_and_export`

Rebaking needs a minic script (baking isn't a CLI flag). Before writing
`catalog.py`/`templates/`, hands-on verify against a real project that
`minic_api_list.h`'s registered functions actually cover bake invocation and
texture-set swaps (flagged as an open item in the design spec — this
assumption is not yet confirmed). Operates on a **copy** of the source
project by default; `in_place: true` opts out.

**Gate:** integration smoke test rebakes a sample project and confirms new
bake output differs from the pre-rebake state (e.g. a content hash or mtime
check), without mutating the original source file (unless `in_place: true`
was passed).

## Phase 3 — `list_export_presets` + `inspect_project` + dynamic catalog

`catalog.py` builds bake-type/blend-mode/export-preset lists from `--api`
output and `export_presets/*.json` on disk — no hardcoded magic numbers.
`inspect_project` is a read-only `.arm` metadata query (objects, materials,
layers).

**Gate:** catalog build succeeds against the real local ArmorPaint
checkout/build and returns a non-empty, sane-looking list for each category.

## Phase 4 — `run_script` escape hatch + polish

The purpose-built escape-hatch tool for anything the above don't cover.
Documentation pass, packaging check (`pip install -e .` from a clean clone),
README accuracy pass.

**Gate:** a clean-clone install + `ap-mcp --check` + smoke test all pass with
no undocumented manual steps.

## Deferred (not scoped into any phase above)

- **Live mode** — interactive, GUI-attached control. See the design spec's
  "Deferred: live mode" section. Two architecture options are named there;
  neither is chosen. Only take this on once batch mode (Phases 0-4) is solid
  and live mode is actually wanted, per Grayson's "both, batch first"
  direction from the brainstorming session.
- **Material authoring from scratch** (node-graph generation from a
  text/style description) — the harder generative problem the reference
  project also attempts; explicitly out of v1 scope.
