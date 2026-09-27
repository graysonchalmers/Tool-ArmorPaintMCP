# CLAUDE.md — Tool-ArmorPaintMCP

> Standing instructions for agent sessions. Keep this short and true — a stale CLAUDE.md
> is worse than none.

## What this project is

An MCP server (Python) that lets Claude batch-drive ArmorPaint — re-export
existing `.arm` projects at different presets, rebake, swap
texture sets — via ArmorPaint's own native CLI flags and minic scripting
engine. Read
[docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md)
before making changes, especially before reaching for anything that patches
ArmorPaint's source — that was the reference implementation's approach and
was deliberately rejected here (see the spec's "Why not the reference
approach" section). Live/interactive GUI-attached control ("live mode") is
explicitly deferred, not rejected — see the spec's "Deferred: live mode".

## Session protocol

- **Baton:** read `HANDOFF.md` at session start (`pickup`); update it at session end (`wrap-up`).
- **Truth ledger:** `STATUS.md` — three states only (✅ verified / 🔌 wired / ⬜ not started).
  Never mark ✅ without recorded evidence.
- **Plan:** `docs/PLAN.md` — don't start Phase N+1 until Phase N's gate is green.

## Commands

| Action | Command |
|---|---|
| Setup preflight | `ap-mcp --check` |
| Run the server | `ap-mcp` (stdio) |
| Smoke test | `pwsh smoke/smoke.ps1` (must exit 0) |
| Unit tests | `pytest -q` (integration deselected by default via `addopts`) |
| Integration test | `pytest -q -m integration` (real ArmorPaint, needs `AP_BINARY`) |
| Build stamp | `python scripts/build_stamp.py` |
| Mesh/UV gallery | `python scripts\generate_mesh_gallery.py` |

## Environment (this machine)

- Shell is PowerShell 5.1. Use `;` to sequence, `Push-Location`/`Pop-Location`,
  and `& "C:\path\tool.exe"` for quoted executables. `&&` is a parse error.
- Python: `C:\Program Files\Python313\python.exe` (3.13). Project venv at
  `.venv\` (created via `python -m venv .venv`).
- ArmorPaint checkout: `C:\Projects-local\z-Git\ArmorPaint` (from-scratch
  C/"iron"+Kore engine rewrite). Upstream default branch is `main`. Currently
  on branch `fix/mesh-accumulator-zero-init` at `287e63f4` = upstream `main`
  `85f6cf1c` + one commit, the zero-init fix for
  `util_mesh_smooth`/`util_mesh_bevel`/`util_mesh_calc_normals`'s
  accumulator arrays (STATUS.md Known Issues #4/#5), open upstream as
  armory3d/armorpaint#2148. Pushed to `gc-fork`
  (`git@github.com:graysonchalmers/armorpaint.git`). `AP_BINARY` was built
  from it on 2026-09-27. The mesh-edit registrations themselves are
  upstream (#2139, `ee2f3635`). The old `spike/minic-decimate` (`e246089d`,
  pre-rename base) is superseded; this project no longer runs
  `unwrap_mesh_uvs` against it. Changing this checkout counts as changing
  something outside this project: ask Grayson first. Flag any further local
  changes on top of it the same way.
- Reference implementation (for comparison only, not a dependency):
  `C:\Projects-local\z-Git\armorpaint-mcp`.
- Config lives in `.env` (copy from `.env.example`). Never echo its contents.

## Key facts about ArmorPaint (verified 2026-09-15)

- `paint\sources\args.c` — native CLI: `--background` (headless),
  `--export-textures <type> <preset> <path>`, `--export-mesh <path>`,
  `--export-material <path>`, `--script <path>` (runs once at startup against
  the opened project), `--api` (prints the full scripting API reference,
  project-context-aware if a project is open).
- `paint\sources\minic_api_list.h` (607 lines) — the native scripting API
  surface (`minic`), hundreds of registered functions. This is what a
  `--script` invocation or the in-app Scripts tab (`ui\tab_scripts.c`,
  `minic_eval()`) can call.
- `--script` is one-shot per process launch — there's no built-in "keep a
  headless process alive, feed it more work later" mode. This is the reason
  v1's tools are coarse pipeline calls (subprocess-per-call), not
  fine-grained one-tool-per-operation like the reference project.
- **Build gotcha:** `ArmorPaint.exe` needs `paint\build\out\data\` next to it
  or it access-violates on launch with zero log output. See README.

## Conventions

- No source patching, no custom ArmorPaint rebuild, in v1. If a future
  session considers it (e.g. for live mode), re-read the spec's "Deferred:
  live mode" section first — it names the two options already considered.
- Gate rule: never start Phase N+1 until Phase N's gate is green and recorded in STATUS.md.
- Dynamic catalogs, not hardcoded enums — bake types/blend modes/export
  presets get read from the app itself (`--api`, `export_presets/*.json`),
  never hardcoded as magic numbers (the reference project did this and it's
  a named anti-pattern in the design spec).
- Mutating operations (rebake) default to operating on a **copy** of the
  source project, never in-place, unless the caller explicitly opts in.
- Secrets/paths come from env (`.env` locally — see `.env.example`); never hardcode.

## Verification boundaries

- Headless-verifiable: package imports, `--check`/`--version`/`--help`,
  subprocess exit codes, expected output files existing on disk.
- Host-only (manual checklist): actually opening ArmorPaint's GUI to confirm
  a rebaked/re-exported project looks right (visual correctness of the bake
  itself isn't something a script can judge).

## Shipping

- Commits land on GitHub via the `github-push` skill (authorized path from cloud sessions).

## Gotchas

- ArmorPaint's `ArmorPaint.exe` must run from `paint\build\out\` (next to the
  `data\` dir `make.bat` exports), not `paint\build\x64\Release\` where
  MSBuild actually drops it.
- VS2022 BuildTools on this machine needed the Clang C++ component installed
  separately (`Microsoft.VisualStudio.Component.VC.Llvm.Clang` +
  `...ClangToolset`) — not part of the default C++ workload, requires
  elevation to install.
