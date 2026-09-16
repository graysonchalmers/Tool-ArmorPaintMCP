# Tool-ArmorPaintMCP

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant
batch-drive [ArmorPaint](https://armorpaint.org) — re-export existing
projects at different presets, build small procedural materials
(checker/solid node graphs built, rendered, and exported in a single pass),
inspect an existing project's objects, materials, and layers, and run
arbitrary minic scripts against a project for anything the purpose-built
tools don't cover — without opening the GUI for each pass. Mesh-detail
rebaking and swapping texture sets into an existing project are structurally
unreachable on this ArmorPaint build (no CLI or scripting path exists for
either) and are permanently out of scope — see [STATUS.md](STATUS.md)'s
Known Issues for the specifics.

Full design (including why this deliberately does **not** patch ArmorPaint's
source, unlike the reference implementation it started from) is in
[docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md](docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md).

## Status

**Alpha — v1 tool surface complete (Phase 4: `run_script` shipped).** All
five planned tools (`reexport_project`, `create_procedural_material`,
`list_available_presets`, `inspect_project`, `run_script`) are implemented,
tested, and gated. See [docs/PLAN.md](docs/PLAN.md) for the phase plan and
[STATUS.md](STATUS.md) for the gate ledger. Live/interactive "live mode" is
deferred, not shipped — see the design spec's "Deferred: live mode" section.

## Gallery

Real output from `reexport_project`, run against the tracked sample project
(`tests/fixtures/sample_project.arm` — ArmorPaint's own default cube-bevel
primitive + default material, generated headlessly, see
`tests/fixtures/generate_fixture.py`). The fixture is intentionally blank
(no painted layers), so these are flat, single-color swatches, not textured
renders — the point is the real preset-to-preset difference in what gets
exported, not visual richness. Same project, two export presets:

| `generic` preset (separate channels) | `unreal` preset (packed) |
|:--:|:--:|
| ![generic preset base color export](docs/images/gallery/generic_base.png) | ![unreal preset packed export](docs/images/gallery/unreal_packed.png) |

Real procedural output from `create_procedural_material` (Phase 2) — a
checker-pattern node graph built, rendered, and exported in a single
ArmorPaint process, on the default cube-bevel primitive:

![procedural checker material, base color export](docs/images/gallery/procedural_checker_base.png)

ArmorPaint's minic scripting surface reaches further than the two node types
`create_procedural_material` ships (a deliberate v1 scope decision, not a
platform limit — see [docs/PLAN.md](docs/PLAN.md) Phase 2). `TEX_NOISE` and
`TEX_VORONOI` both work the same way through the same `script_material_*`
calls; [scripts/generate_gallery.py](scripts/generate_gallery.py) renders
them (hand-written minic, outside the shipped tool, for example imagery
only) to show what the underlying engine is actually capable of:

| Noise | Voronoi |
|:--:|:--:|
| ![procedural noise material, base color export](docs/images/gallery/procedural_noise_base.png) | ![procedural voronoi material, base color export](docs/images/gallery/procedural_voronoi_base.png) |

## How it works

ArmorPaint ships real, unpatched CLI automation:
`--background` (headless), `--export-textures/--export-mesh/--export-material`
(native batch export), `--script <path>` (runs a script against the opened
project), and `--api` (prints the full scripting API reference). This server
drives those directly — no source patching, no custom rebuild, runs against
the stock binary.

The escape-hatch tool, `run_script`, hands the caller's own minic source
straight to `--script` against an already-open project — for the cases the
four purpose-built tools above don't cover.

## Requirements

- **Python 3.10+** (developed on 3.13)
- **Windows** is the only platform this targets for now.
- An **ArmorPaint build** on disk. Clone `armory3d/armorpaint` (`main`,
  `--recurse-submodules`), run `base\make.bat` from `paint\`, then build
  `ArmorPaint.vcxproj` (Release/x64; needs the VS2022 "C++ Clang Compiler for
  Windows" component, `Microsoft.VisualStudio.Component.VC.Llvm.Clang`, not
  part of the default C++ workload).
  - **Build gotcha:** MSBuild drops `ArmorPaint.exe` in
    `paint\build\x64\Release\`, but it needs `paint\build\out\data\` (the
    asset/shader export from `make.bat`) next to it or it access-violates on
    launch with zero log output. Copy the exe into `paint\build\out\` and
    run it from there.

## Install

```bash
git clone https://github.com/graysonchalmers/Tool-ArmorPaintMCP.git
cd Tool-ArmorPaintMCP
python -m venv .venv
# Windows:  .\.venv\Scripts\activate
pip install -e .
cp .env.example .env
```

Then edit `.env`:

```
AP_BINARY=C:\path\to\ArmorPaint\paint\build\out\ArmorPaint.exe
AP_OUTPUT_DIR=C:\path\to\output
```

## Check your setup

```bash
ap-mcp --check
```

Prints a green/red checklist (binary path, data dir alongside it, output dir
writable) and exits non-zero if anything's missing. `ap-mcp --version` prints
the version.

## Verify

```powershell
pwsh smoke/smoke.ps1
```

Headless proof the project is alive: package imports, `--version` and
`--help` exit 0, and `reexport_project` is registered as an MCP tool. Each
phase adds a probe here.

```bash
pytest -q                # unit tests (fast, no ArmorPaint process)
pytest -q -m integration # the real one: launches ArmorPaint, needs AP_BINARY
```

The integration test is deselected by default (`addopts` in `pyproject.toml`),
so `pytest -q` never launches a GUI; `-m integration` on the command line
replaces that default and runs only the real one.

## Connect it to an MCP client

The server speaks MCP over stdio, on PATH as `ap-mcp` once installed.

```json
{
  "mcpServers": {
    "armorpaint": {
      "command": "ap-mcp",
      "env": {
        "AP_BINARY": "C:\\path\\to\\ArmorPaint\\paint\\build\\out\\ArmorPaint.exe",
        "AP_OUTPUT_DIR": "C:\\path\\to\\output"
      }
    }
  }
}
```

## License

MIT (see [LICENSE](LICENSE)). ArmorPaint retains its own license; this
project drives a separate ArmorPaint build and does not modify or
redistribute its source.
