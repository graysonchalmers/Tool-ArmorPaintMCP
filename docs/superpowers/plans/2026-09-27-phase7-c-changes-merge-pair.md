# Phase 7 — ArmorPaint C Changes + `merge_mesh_pair` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Controller, read first.** Tasks 5-8 and 14-16 act on `C:\Projects-local\z-Git\ArmorPaint` or on GitHub. Each one opens with a **HUMAN GATE** step, and no subagent may be dispatched to it until Grayson has said yes to that exact action in chat. At the start of execution, send him **one** message listing the go-aheads for Tasks 5, 6, 7 and 8, quoting each task's gate line. Then run the pure-Python Tasks 1-4 while you wait. Ask for the PR go-aheads (Tasks 14-16) only after Task 13 has written the PR texts, so he can read them first. A "yes" covers only the action it names: a go for Task 5 is not a go for Task 6, and a go to push is not a go to open the PR.

**Goal:** Land the three ArmorPaint C changes from `docs/PLAN.md` Phase 7 as one small upstream-ready branch each, build `AP_BINARY` from a local integration branch (upstream `main` plus every open PR), make `ap-mcp --check` prove each of those dependencies is in the build, and ship `merge_mesh_pair`: merge one named object into another and leave every other object alone.

**Architecture:** The C work lives in the ArmorPaint checkout, one branch per change off upstream `main`, merged `--no-ff` into a local `integration/ap-mcp` branch that `AP_BINARY` is built from. Two of the changes add no minic name, so `--check` can't find them in `--api`. Instead, a new build manifest (`ap-mcp-build.json`, next to the binary) records, from the checkout's git history at build time, which dependency branches the build contains, and it is bound to the exact binary by SHA-256. `--check` reads it, and it cross-checks any dependency that does add a minic name against the live `--api` listing. `merge_mesh_pair` reuses `_run_mesh_edit`'s open-the-original, save-to-a-fresh-sibling plumbing. It pre-checks both names through `--api`, and the script checks its own result before it saves.

**Tech Stack:** Python 3.13 stdlib (no new dependencies; numpy is NOT installed), pytest, the MCP Python SDK already in use, the `git` CLI (read-only, for the manifest), ArmorPaint's C sources (iron/Kore) built with `..\base\make.bat` + VS2022 BuildTools MSBuild (Clang toolset), Release/x64.

**Spec:** `docs/PLAN.md` → "## Phase 7 (APPROVED 2026-09-27)" (route D3, the three C changes), its "7.1 (was 6.3) — Item 9" subsection (item 9's gate list is under "Pre-grill gate draft" → "Item 9"), the "**Phase 7 gate:**" paragraph (~line 830), "Decisions for Grayson" D2, D3 and D5, and Phase 6's "Known risks carried into Phase 6 (closed in Phase 7 where possible)". Where this plan's source reading disagrees with PLAN.md's line citations, the plan's are newer; see "Corrections to the spec's citations" below.

## Global Constraints

- **Worktree:** all Python work happens in `C:\Projects-local\Tool-ArmorPaintMCP\.claude\worktrees\phase7` on branch `claude/phase7`, created from `main` @ `36262e1`. Create it once: `git -C C:\Projects-local\Tool-ArmorPaintMCP worktree add .claude\worktrees\phase7 -b claude/phase7 main`. Never edit `C:\Projects-local\Tool-ArmorPaintMCP` (main) directly: the installed MCP server runs from main's editable install. (The Phase 6 worktree `.claude\worktrees\phase6` still exists; it isn't ours to remove.)
- **Python/env for every command** (PowerShell 5.1; the venv lives in main, the code under test in the worktree):
  ```powershell
  Push-Location C:\Projects-local\Tool-ArmorPaintMCP\.claude\worktrees\phase7; $env:PYTHONPATH = "$PWD\src"; $env:AP_DOTENV = 'C:\Projects-local\Tool-ArmorPaintMCP\.env'; $py = 'C:\Projects-local\Tool-ArmorPaintMCP\.venv\Scripts\python.exe'
  ```
  Before trusting any test run, confirm `& $py -c "import armorpaint_mcp; print(armorpaint_mcp.__file__)"` prints a path inside the worktree. Unit tests: `& $py -m pytest -q` (baseline at `36262e1`: **230 collected, 38 integration deselected**). Integration: `& $py -m pytest -q -m integration <file>`. Smoke: `pwsh smoke/smoke.ps1` (same `PYTHONPATH`; baseline 15/15). Never print `.env`.
- **ArmorPaint:** drive `ArmorPaint.exe` only through PowerShell or a Python subprocess. NEVER through the Bash tool: it silently no-ops the binary. Run one ArmorPaint process at a time: never run integration tests in parallel (no `-n`, no two shells).
- **Flaky launches:** the machine is under memory pressure. If an integration test fails with exit code `3221225477` (0xC0000005) or a timeout on the *first* ArmorPaint call of a run, rerun that test once. The first call after a rebuild is the known cold-start case (STATUS.md Known Issue #9). If it fails again, report it. Retries belong in how you run tests, never in production code.
- **The ArmorPaint checkout (`C:\Projects-local\z-Git\ArmorPaint`) is read-only** to every task except the gated ones (5, 6, 7, 8, 14, 15, 16). Read-only means `git log`/`git show`/`git grep`/`git ls-remote` and file reads. No `fetch`, `switch`, `commit`, build, `push` or file edit there outside a gated task, and each gated task does only what its gate names. If a gated task hits something its gate didn't cover (a merge conflict, a build error, a dirty tree), stop and report. Never "fix" it in the checkout.
- **Upstream state when this plan was written (2026-09-27):** the checkout is on `fix/mesh-accumulator-zero-init` @ `287e63f4` (= `85f6cf1c` + the #2148 commit), with a clean working tree. Its `origin/main` ref is stale at `85f6cf1c`: the real upstream `main` is `eec04adf` (`git ls-remote`), 4 commits on, which touch only `base/` shaders, kong, backends and amake, no `paint/sources` file, and add no `.c` file. armory3d/armorpaint#2148 is OPEN with head `287e63f4`. Task 5 re-pins all of this; never act on these SHAs without re-checking them.
- **Branch names (the registry in Task 1 depends on them, so don't rename):** `fix/import-mesh-texa-zero-init` (change 1), `fix/mesh-delete-object-mask-remap` (change 2), `feat/script-object-merge` (change 3), `integration/ap-mcp` (the build branch). #2148 stays on `fix/mesh-accumulator-zero-init`.
- **Build facts (this machine):**
  - Regenerate the project + `data\` with `..\base\make.bat` run from `C:\Projects-local\z-Git\ArmorPaint\paint`.
  - Then build with `& "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe" C:\Projects-local\z-Git\ArmorPaint\paint\build\ArmorPaint.vcxproj /p:Configuration=Release /p:Platform=x64 /m`. Use this 2022 path: the Phase 5 plan's `C:\Program Files\...` path doesn't exist, and 2019 BuildTools is installed too, so don't pick that one.
  - MSBuild writes `paint\build\x64\Release\ArmorPaint.exe`. It must be copied to `paint\build\out\ArmorPaint.exe` (= `AP_BINARY`), next to `data\`, or it access-violates silently.
  - clang-format: `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\Llvm\x64\bin\clang-format.exe`, repo style `C:\Projects-local\z-Git\ArmorPaint\.clang-format`.
- **Failure shape:** every tool returns `{"ok": False, "error": str, <every other declared field>: None}` via `server._failure(...)` on any failure. Never raise out of a tool.
- **Dynamic catalogs:** no hardcoded ArmorPaint enums. `UPSTREAM_DEPENDENCIES` (Task 1) is this project's own list of upstream PRs it needs, like `EMITTED_MINIC_FUNCTIONS` is its list of minic calls. It is not an app enum, and whether each entry is present is read from git (build time) and `--api` (run time), never assumed.
- **Commits in this repo:** one per task minimum, message prefix `feat:`/`fix:`/`test:`/`docs:`, ending with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. **Commits in the ArmorPaint checkout:** upstream style (`paint: <imperative summary>`, a short body explaining cause and fix), same trailer, as on #2148's `287e63f4`. PowerShell 5.1 syntax (`;` not `&&`) in anything handed to Grayson.
- **Minic facts this plan relies on:**
  - A script error prints `<script>:N: error: …` while the process still exits 0, and `run_minic_script` turns that into `ok=False` (Phase 6).
  - `project_save(0)` must be the script's LAST statement.
  - `script_append_mesh` needs a backslash path, each backslash doubled in the literal.
  - Names are never escaped: a `"`, `\` or line break is rejected (`script_gen.minic_string_literal`).
  - **New:** `script_get_object(name)` matches `paint_objects[i]->base->name` (`minic_impl.c:180-187`). Those are the names `inspect_project`/`catalog.scene_objects` report (`nodes_neural/text_to_text_node.c:49-50` iterates `paint_objects`), not `mesh_datas[].name`, which are mesh *data* names.
  - **New:** `script_object_merge(o, into)` keeps `into` and removes `o`, matching the GUI's "merge down", where `util_mesh_merge_geometry_down(main_object, below)` keeps `main_object`.
- **`--check` stays red on the worktree until Task 8.** Task 1 adds one row per upstream dependency and Task 3 adds `script_object_merge` to the emitted names, so `--check` fails on the current `287e63f4` binary. That's correct (the tools that need them wouldn't work). It doesn't affect main.

### Corrections to the spec's citations (verified 2026-09-27 against `287e63f4`)

- **Change 2's site.** `ui/tab_meshes.c:128-134` is the *reorder* remap (`tab_meshes_sort_hierarchy_from`), not the delete path. The delete path is `tab_meshes_draw_context_menu_delete` (`ui/tab_meshes.c:443-476`). It calls `array_remove(g_project->_->paint_objects, o)` at `:464` and then `tab_meshes_sort_hierarchy()`, which snapshots its "old order" *after* the removal, so it can never correct the index shift. The fix goes right after `:465`.
  - `script_object_remove` (`minic_impl.c:819-838`) reaches this path, so `replace_mesh` (which removes the old object) is exposed to it.
  - Not fixed here: the delete path also doesn't splice `g_project->atlas_objects`, which `util_mesh_merge_geometry_down` does (`util/util_mesh.c:626-628`). Task 12 logs it as a further upstream candidate. It isn't part of PR 2.
- **Change 1's sites** are exact: `io/import_mesh.c:183-186` (`import_mesh_make_mesh`) and `:260-263` (`import_mesh_add_mesh`), both `i16_array_create(verts * 2)` into a `realloc`'d, never-zeroed buffer (`base/sources/iron_array.c:552-559`, `:103`).
- **Change 3's shape.** `c0df922d` ("paint: add script_object_remove") touched `functions.h` (+1), `minic_api_list.h` (+1, plus commenting out two raw `*_remove` registrations) and `minic_impl.c` (+21). `script_object_merge` copies that shape in the same three files. Nothing needs commenting out.
- **`util_mesh_merge_geometry_down`** (`util/util_mesh.c:609-652`):
  - It returns silently unless both objects are in `paint_objects` and distinct.
  - It unshares and bakes both objects' transforms into `main_object`'s local space and joins their geometry (`util_mesh_join_geometry`, `:539-560`).
  - It re-parents `below`'s children to `main_object` with their world pose kept, splices `below` out (and out of `atlas_objects`), and remaps layer masks.
  - It does **not** re-unwrap UVs (it ends in `util_mesh_geometry_joined` → `util_mesh_merge(NULL)`, the render proxy only).

## Review Focus

1. **`keep` and `merge` naming the same object, or a name two objects share**: a reasonable person expects a clean `ok=False` before anything is saved, never a merge of the wrong object (`script_get_object` returns the first match). Pinned in Task 3 (`test_build_merge_lines_rejects_the_same_object_twice`, `test_check_pair_rejects_an_ambiguous_name`, `test_merge_mesh_pair_rejects_the_same_name_without_launching`).
2. **An `AP_BINARY` without `script_object_merge`** (stock upstream, or the pre-Phase-7 build): expect `merge_mesh_pair` to return `ok=False` naming the unknown function and write nothing, and `--check` to show a red row, never `ok=True` on an unmerged file. Pinned in Task 3 (`test_merge_mesh_pair_on_a_build_without_script_object_merge_fails_cleanly`) and Task 1 (`test_the_manifest_cannot_vouch_for_a_minic_name_the_api_lacks`).
3. **Merging a parent into its own child** (`objects3_v4_parented.arm`: keep `Cone`, merge its parent `Tessellated`): expect `ok=True`, one fewer object, `Cone` now unparented and still in the same place in the world. Pinned in Task 9 (`test_merging_a_parent_into_its_child_keeps_the_child_in_place`).
4. **`AP_BINARY` rebuilt without re-running the manifest writer**: expect `--check` to fail as "stale" rather than vouch for the old build's dependencies. Pinned in Task 1 (`test_a_stale_manifest_fails_every_row`).
5. **A bad `output_project` (missing, or `in_place` misuse) on `merge_mesh_pair`**: expect `ok=False` without even the `--api` launch. The older `merge_mesh_geometry` launches `--api` first, so don't copy it. Pinned in Task 3 (`test_merge_mesh_pair_checks_output_project_before_launching`).

### Not in this plan

These are parked as further upstream candidates in `docs/PLAN.md` Phase 7, each with its own go (D3). None of them is Phase 7 scope:
- reading argv as wide on Windows (`__wargv`, Known Issue #12's real fix);
- non-ASCII `%TEMP%`;
- escaping strings in `armpack_to_json_value` (Known Issue #10's root cause);
- a NULL check for an unregistered mesh-importer extension (`io/import_mesh.c:39-42`);
- splicing `atlas_objects` on delete (found by this plan).

Also out of scope: live/GUI-attached mode, and Known Issue #8 (the other mesh edits re-unwrap every object).

### Task order and dependencies

```
Python (no gate)      1 ──► 2 ──┐
                      3 ────────┼──► 9 ──┐
                      4 ────────┼──► 10 ─┼──► 12 ──► 13 ──► 14, 15, 16 (gated, optional for the gate)
Gated (checkout)      5 ──► 6 ──► 7 ──► 8 ─┘ (8 needs 1 + 2)   11 (optional host fixture) ─┘
```

Task 9 needs change 3 in `AP_BINARY` (Task 8) and the tool (Task 3). Task 10 needs change 1 in `AP_BINARY` (Task 8) and the fixture (Task 4). **The Phase 7 gate is green at Task 12**, and it doesn't depend on any PR being opened (Tasks 14-16 are D3's route, each on its own go).

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `src/armorpaint_mcp/dependencies.py` (new) | registry of upstream dependencies; build-manifest reader; `--check` rows | 1, 14-16 |
| `src/armorpaint_mcp/build_manifest.py` (new) | `python -m armorpaint_mcp.build_manifest`: writes the manifest from the checkout's git history | 2 |
| `src/armorpaint_mcp/doctor.py` | calls `--api` once, adds the dependency rows | 1 |
| `src/armorpaint_mcp/merge_pair.py` (new) | `merge_mesh_pair`'s pure pieces: name checks, minic lines, abort markers | 3 |
| `src/armorpaint_mcp/server.py` | `_run_mesh_edit` takes several lines + an abort explainer; `merge_mesh_pair`; docstrings | 3, 4 |
| `src/armorpaint_mcp/catalog.py` | `script_object_merge` in `EMITTED_MINIC_FUNCTIONS` | 3 |
| `src/armorpaint_mcp/replace.py` | docstring: UV-less non-OBJ behavior with/without the texa fix | 4 |
| `tests/fixtures/phase7/` (new) | `make_nouv_glb.py`, `repl_grid5_nouv.glb`, `.gitattributes`, `README.md`, optional `objects3_masked.arm` | 4, 11 |
| `tests/test_dependencies.py`, `tests/test_build_manifest.py`, `tests/test_merge_pair.py`, `tests/test_phase7_fixtures.py` (new) | unit tests | 1-4 |
| `tests/test_server.py`, `tests/test_catalog.py` | unit tests for the tool; completeness test covers the new script | 3 |
| `tests/test_merge_mesh_pair_integration.py`, `tests/test_phase7_texa_integration.py`, `tests/test_phase7_object_mask_integration.py` (new) | real ArmorPaint | 9, 10, 11 |
| `smoke/smoke.ps1` | `merge_mesh_pair` registration probe | 3 |
| `docs/upstream/2026-09-27-pr-*.md` (new) | the three PR bodies, for Grayson to approve | 13 |
| `README.md`, `CLAUDE.md`, `STATUS.md`, `docs/PLAN.md`, `ROADMAP.md`, `HANDOFF.md` | build recipe, gate record, baton | 12, 14-16 |
| `C:\Projects-local\z-Git\ArmorPaint\paint\sources\io\import_mesh.c` | change 1 (branch `fix/import-mesh-texa-zero-init`) | 5 |
| `C:\Projects-local\z-Git\ArmorPaint\paint\sources\ui\tab_meshes.c` | change 2 (branch `fix/mesh-delete-object-mask-remap`) | 6 |
| `C:\Projects-local\z-Git\ArmorPaint\paint\sources\{minic_impl.c,minic_api_list.h,functions.h}` | change 3 (branch `feat/script-object-merge`) | 7 |

---

### Task 1: Upstream-dependency registry and `--check` rows

**Files:**
- Create: `src/armorpaint_mcp/dependencies.py`
- Modify: `src/armorpaint_mcp/doctor.py` (imports; the `--api` block at lines 56-75)
- Test: `tests/test_dependencies.py` (new)

**Interfaces:**
- Produces (Tasks 2, 10, 11, 14-16 use these exact names):
  - `UpstreamDependency(key: str, branch: str, summary: str, pr: int | None = None, minic_names: tuple[str, ...] = (), upstream_commit: str | None = None)`, a frozen dataclass
  - `UPSTREAM_DEPENDENCIES: tuple[UpstreamDependency, ...]` with keys `"mesh-accumulator-zero-init"`, `"import-mesh-texa-zero-init"`, `"delete-object-mask-remap"`, `"script-object-merge"`
  - `MANIFEST_NAME = "ap-mcp-build.json"`, `MANIFEST_SCHEMA = 1`
  - `manifest_path(binary: str) -> str`, `binary_sha256(binary: str) -> str`
  - `load_manifest(binary: str) -> tuple[dict | None, str | None]`, which returns `(manifest, None)` or `(None, error)`
  - `dependency_row_name(dep) -> str` (`"upstream dependency <key> (#<pr>)"` or `"... (PR not opened)"`)
  - `dependency_checks(binary: str, api_text: str | None) -> list[tuple[str, bool, str]]`
- Manifest shape (Task 2 writes it): `{"schema": 1, "binary_sha256": str, "head": str, "branch": str, "upstream_base": str | None, "dependencies": {<key>: {"included": bool, "how": str, "head": str | None}}, ...}`

- [ ] **Step 1: Write the failing tests.** Create `tests/test_dependencies.py`:

```python
import hashlib
import json
from unittest.mock import patch

from armorpaint_mcp import dependencies as deps
from armorpaint_mcp.catalog import EMITTED_MINIC_FUNCTIONS
from armorpaint_mcp.config import Config
from armorpaint_mcp.doctor import check_setup

# Every name --check could look for: the emitted calls plus every dependency's
# own names (Task 3 adds script_object_merge to the emitted list later).
_ALL_NAMES = sorted(set(EMITTED_MINIC_FUNCTIONS)
                    | {n for d in deps.UPSTREAM_DEPENDENCIES for n in d.minic_names})
_FULL_API = "\n".join(f"void {n}();" for n in _ALL_NAMES)


def _binary(tmp_path, content=b"fake-binary"):
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_bytes(content)
    (tmp_path / "data").mkdir(exist_ok=True)
    return binary


def _write_manifest(binary, included=None):
    if included is None:
        included = {d.key: True for d in deps.UPSTREAM_DEPENDENCIES}
    manifest = {
        "schema": deps.MANIFEST_SCHEMA,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "head": "0123456789abcdef0123",
        "branch": "integration/ap-mcp",
        "upstream_base": "fedcba9876543210fedc",
        "dependencies": {
            key: {"included": ok, "how": "ancestor" if ok else "not merged into the build",
                  "head": "aaaabbbbccccdddd"}
            for key, ok in included.items()},
    }
    (binary.parent / deps.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")


def _rows(binary, api_text=_FULL_API):
    return {name: (ok, detail)
            for name, ok, detail in deps.dependency_checks(str(binary), api_text)}


def test_every_dependency_passes_with_a_matching_manifest_and_api(tmp_path):
    binary = _binary(tmp_path)
    _write_manifest(binary)

    rows = _rows(binary)

    assert len(rows) == len(deps.UPSTREAM_DEPENDENCIES)
    assert all(ok for ok, _ in rows.values()), rows


def test_row_names_carry_the_pr_number_once_there_is_one(tmp_path):
    binary = _binary(tmp_path)
    _write_manifest(binary)

    names = list(_rows(binary))

    assert "upstream dependency mesh-accumulator-zero-init (#2148)" in names


def test_a_missing_manifest_fails_every_row_and_says_how_to_fix_it(tmp_path):
    binary = _binary(tmp_path)

    rows = _rows(binary)

    assert rows and all(not ok for ok, _ in rows.values())
    assert all("no build manifest" in detail and "build_manifest" in detail
               for _, detail in rows.values())


def test_a_stale_manifest_fails_every_row(tmp_path):
    """Review Focus 4: AP_BINARY rebuilt, manifest not rewritten."""
    binary = _binary(tmp_path)
    _write_manifest(binary)
    binary.write_bytes(b"rebuilt-binary")

    rows = _rows(binary)

    assert all(not ok and "stale" in detail for ok, detail in rows.values())


def test_an_unreadable_manifest_fails_cleanly(tmp_path):
    binary = _binary(tmp_path)
    (tmp_path / deps.MANIFEST_NAME).write_text("{not json", encoding="utf-8")

    rows = _rows(binary)

    assert all(not ok and "unreadable" in detail for ok, detail in rows.values())


def test_a_dependency_missing_from_the_build_fails_only_its_own_row(tmp_path):
    binary = _binary(tmp_path)
    included = {d.key: True for d in deps.UPSTREAM_DEPENDENCIES}
    included["import-mesh-texa-zero-init"] = False
    _write_manifest(binary, included)

    failing = [name for name, (ok, _) in _rows(binary).items() if not ok]

    texa = next(d for d in deps.UPSTREAM_DEPENDENCIES if d.key == "import-mesh-texa-zero-init")
    assert failing == [deps.dependency_row_name(texa)]   # stays true once its PR number is set


def test_the_manifest_cannot_vouch_for_a_minic_name_the_api_lacks(tmp_path):
    """Review Focus 2: --api is live, the manifest can be wrong."""
    binary = _binary(tmp_path)
    _write_manifest(binary)
    api = "\n".join(f"void {n}();" for n in _ALL_NAMES if n != "script_object_merge")

    rows = _rows(binary, api)

    [(ok, detail)] = [r for name, r in rows.items() if "script-object-merge" in name]
    assert ok is False
    assert "script_object_merge" in detail


def test_check_setup_adds_one_row_per_dependency(tmp_path):
    binary = _binary(tmp_path)
    _write_manifest(binary)
    with patch("armorpaint_mcp.doctor.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = _FULL_API
        mock_run.return_value.stderr = ""
        checks = check_setup(Config(binary=str(binary), output_dir=str(tmp_path)))

    rows = [c for c in checks if c.name.startswith("upstream dependency")]
    assert len(rows) == len(deps.UPSTREAM_DEPENDENCIES)
    assert all(c.ok for c in rows), [(c.name, c.detail) for c in rows]
```

- [ ] **Step 2: Run to verify they fail.**

Run: `& $py -m pytest -q tests/test_dependencies.py`
Expected: FAIL at collection (`ImportError: cannot import name 'dependencies' from 'armorpaint_mcp'`).

- [ ] **Step 3: Implement** `src/armorpaint_mcp/dependencies.py`:

```python
"""Upstream ArmorPaint changes that AP_BINARY must contain (docs/PLAN.md
Phase 7, route D3), and how `ap-mcp --check` proves each one is in the build.

AP_BINARY is built from a local integration branch: upstream main plus every
open PR this project needs. Two of those PRs add no minic name, and neither
has a behavioural probe that could tell a fixed build from a lucky one. The
texa zero-init turns uninitialized memory into zeros, but fresh heap pages
often read as zero anyway. A layer's object_mask can't be set from minic at
all (no slot_layer_t registration). So the proof is a build manifest written
from the ArmorPaint checkout's git history at build time (build_manifest.py)
and bound to the exact binary by its SHA-256. A dependency that DOES add
minic names is also cross-checked against the live --api listing, which
can't go stale.

This is this project's own list of the upstream PRs it depends on, like
catalog.EMITTED_MINIC_FUNCTIONS is its list of minic calls. It is not an
ArmorPaint enum."""

import hashlib
import json
import os
import re
from dataclasses import dataclass

MANIFEST_NAME = "ap-mcp-build.json"
MANIFEST_SCHEMA = 1

_REBUILD_HINT = ("build AP_BINARY from the integration branch and then run "
                 "`python -m armorpaint_mcp.build_manifest` (README \"Building AP_BINARY\")")


@dataclass(frozen=True)
class UpstreamDependency:
    key: str                            # stable id: the manifest's "dependencies" key
    branch: str                         # its branch in the ArmorPaint checkout / on gc-fork
    summary: str                        # what goes wrong without it
    pr: int | None = None               # armory3d/armorpaint PR number, once opened
    minic_names: tuple[str, ...] = ()   # names --api must list when it's in the build
    upstream_commit: str | None = None  # upstream main's commit once merged (a squash changes the SHA)


UPSTREAM_DEPENDENCIES = (
    UpstreamDependency(
        "mesh-accumulator-zero-init", "fix/mesh-accumulator-zero-init",
        "smooth_mesh/bevel_mesh return intermittently corrupted geometry without it "
        "(STATUS.md Known Issues #4/#5)", pr=2148),
    UpstreamDependency(
        "import-mesh-texa-zero-init", "fix/import-mesh-texa-zero-init",
        "a UV-less FBX/GLB/glTF imports with garbage UVs, so replace_mesh only "
        "probably rejects it"),
    UpstreamDependency(
        "delete-object-mask-remap", "fix/mesh-delete-object-mask-remap",
        "a layer masked to one object can jump to another when replace_mesh removes "
        "the old object"),
    UpstreamDependency(
        "script-object-merge", "feat/script-object-merge",
        "merge_mesh_pair calls script_object_merge", minic_names=("script_object_merge",)),
)


def dependency_row_name(dep: UpstreamDependency) -> str:
    return f"upstream dependency {dep.key} ({f'#{dep.pr}' if dep.pr else 'PR not opened'})"


def manifest_path(binary: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(binary)), MANIFEST_NAME)


def binary_sha256(binary: str) -> str:
    digest = hashlib.sha256()
    with open(binary, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(binary: str) -> tuple[dict | None, str | None]:
    """(manifest, None) when a manifest next to `binary` describes exactly
    this binary, else (None, why not)."""
    path = manifest_path(binary)
    if not os.path.isfile(path):
        return None, f"no build manifest at '{path}': {_REBUILD_HINT}"
    try:
        with open(path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, f"unreadable build manifest '{path}': {exc}"
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        return None, f"build manifest '{path}' has an unknown schema: {_REBUILD_HINT}"
    try:
        actual = binary_sha256(binary)
    except OSError as exc:
        return None, f"could not hash AP_BINARY: {exc}"
    if manifest.get("binary_sha256") != actual:
        return None, (f"build manifest '{path}' is stale: AP_BINARY changed after it "
                      f"was written; {_REBUILD_HINT}")
    return manifest, None


def _declared(api_text: str, name: str) -> bool:
    return re.search(rf"\b{re.escape(name)}\s*\(", api_text) is not None


def dependency_checks(binary: str, api_text: str | None) -> list[tuple[str, bool, str]]:
    """One (row name, ok, detail) per UPSTREAM_DEPENDENCIES entry. `api_text`
    is `ArmorPaint.exe --api` output, or None if it couldn't be read."""
    manifest, error = load_manifest(binary)
    rows = []
    for dep in UPSTREAM_DEPENDENCIES:
        name = dependency_row_name(dep)
        if error is not None:
            rows.append((name, False, error))
            continue
        entry = (manifest.get("dependencies") or {}).get(dep.key)
        if not isinstance(entry, dict) or not entry.get("included"):
            how = entry.get("how") if isinstance(entry, dict) else "not in the build manifest"
            rows.append((name, False, f"not in this build ({how}): {dep.summary}; {_REBUILD_HINT}"))
            continue
        missing = [n for n in dep.minic_names if api_text is None or not _declared(api_text, n)]
        if missing:
            rows.append((name, False, f"the build manifest lists it, but --api does not "
                                      f"declare {', '.join(missing)}: {_REBUILD_HINT}"))
            continue
        head = str(entry.get("head") or "")[:8]
        rows.append((name, True, f"in this build ({entry.get('how')}, {dep.branch}@{head})"))
    return rows
```

- [ ] **Step 4: Wire it into `doctor.py`.** Add `from armorpaint_mcp.dependencies import dependency_checks` to the imports. Replace the whole second `if cfg.binary and os.path.isfile(cfg.binary):` block (the `--api` one, lines 56-75) with:

```python
    if cfg.binary and os.path.isfile(cfg.binary):
        api_text = None
        try:
            out = subprocess.run([cfg.binary, "--api"], capture_output=True,
                                  text=True, timeout=15, errors="replace")
            api_text = out.stdout if out.returncode == 0 else None
            missing = missing_minic_functions(api_text) if api_text is not None else None
            if missing is None:
                checks.append(Check("minic API", False,
                                    f"'--api' exited {out.returncode}, could not check"))
            elif missing:
                checks.append(Check("minic API", False,
                                    f"not registered on this build: {', '.join(missing)} "
                                    "-- tools that call them would fail. Rebuild AP_BINARY "
                                    "from the integration branch (README \"Building "
                                    "AP_BINARY\"), or update the renamed call."))
            else:
                checks.append(Check("minic API", True,
                                    f"all {len(EMITTED_MINIC_FUNCTIONS)} minic functions "
                                    "this project calls are registered"))
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append(Check("minic API", False, str(exc)))
        for name, ok, detail in dependency_checks(cfg.binary, api_text):
            checks.append(Check(name, ok, detail))
```

- [ ] **Step 5: Run the unit tests.**

Run: `& $py -m pytest -q`
Expected: all pass, **238 passed** (230 + 8), 38 deselected. `tests/test_doctor.py`'s two existing tests still pass: they assert only the `minic API` row.

- [ ] **Step 6: Commit**

```powershell
git add src/armorpaint_mcp/dependencies.py src/armorpaint_mcp/doctor.py tests/test_dependencies.py; git commit -m "feat: --check reports every upstream dependency of AP_BINARY via a build manifest" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Build-manifest writer

**Files:**
- Create: `src/armorpaint_mcp/build_manifest.py`
- Test: `tests/test_build_manifest.py` (new)

**Interfaces:**
- Consumes: `dependencies.UPSTREAM_DEPENDENCIES`, `UpstreamDependency`, `MANIFEST_SCHEMA`, `binary_sha256`, `manifest_path` (Task 1).
- Produces:
  - `rev_parse(checkout: str, ref: str) -> str | None` and `is_ancestor(checkout: str, commit: str, head: str) -> bool`
  - `dependency_status(checkout: str, head: str, dep: UpstreamDependency) -> dict`, which returns `{"included": bool, "how": str, "head": str | None}`
  - `build_manifest(checkout: str, binary: str, deps=None) -> dict`
  - `main(argv: list[str] | None = None) -> int`
  - CLI: `& $py -m armorpaint_mcp.build_manifest --checkout <dir> --binary <exe>` (Task 8 runs it).

- [ ] **Step 1: Write the failing tests.** Create `tests/test_build_manifest.py`. The git repos are hermetic: an empty global config, no system config, and a fixed identity, so the machine's own git config, hooks and default branch can't leak in.

```python
import hashlib
import json
import subprocess

import pytest

from armorpaint_mcp import build_manifest as bm
from armorpaint_mcp.dependencies import MANIFEST_NAME, UpstreamDependency


@pytest.fixture
def git_env(tmp_path, monkeypatch):
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(var, "test")
    for var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(var, "test@example.com")


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _commit(repo, filename):
    (repo / filename).write_text(filename, encoding="utf-8")
    _git(repo, "add", filename)
    _git(repo, "commit", "-q", "-m", filename)


@pytest.fixture
def checkout(tmp_path, git_env):
    """main = one base commit, also recorded as origin/main. fix/merged is
    merged --no-ff into integration/ap-mcp, fix/picked is cherry-picked into
    it, fix/absent never is. HEAD = integration/ap-mcp."""
    repo = tmp_path / "ArmorPaint"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "base.txt")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    for branch in ("fix/merged", "fix/picked", "fix/absent"):
        _git(repo, "switch", "-q", "-c", branch, "main")
        _commit(repo, branch.replace("/", "_") + ".txt")
    _git(repo, "switch", "-q", "-c", "integration/ap-mcp", "main")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "fix/merged")
    _git(repo, "cherry-pick", "fix/picked")
    return repo


DEPS = (
    UpstreamDependency("merged", "fix/merged", "merged with --no-ff"),
    UpstreamDependency("picked", "fix/picked", "cherry-picked"),
    UpstreamDependency("absent", "fix/absent", "never integrated"),
    UpstreamDependency("nobranch", "fix/nobranch", "branch doesn't exist"),
)


def test_dependency_status_by_ancestry_by_patch_and_by_absence(checkout):
    head = bm.rev_parse(str(checkout), "HEAD")

    status = {d.key: bm.dependency_status(str(checkout), head, d) for d in DEPS}

    assert status["merged"] == {"included": True, "how": "ancestor",
                                "head": bm.rev_parse(str(checkout), "fix/merged")}
    assert status["picked"]["included"] is True
    assert status["picked"]["how"] == "patch-equivalent"
    assert status["absent"]["included"] is False
    assert status["nobranch"]["included"] is False
    assert "not found" in status["nobranch"]["how"]


def test_a_dependency_merged_upstream_counts_by_its_upstream_commit(checkout):
    head = bm.rev_parse(str(checkout), "HEAD")
    base = bm.rev_parse(str(checkout), "main")
    dep = UpstreamDependency("up", "fix/deleted-after-merge", "squash-merged upstream",
                             upstream_commit=base)

    assert bm.dependency_status(str(checkout), head, dep) == {
        "included": True, "how": "merged upstream", "head": base}


def test_main_writes_a_manifest_bound_to_the_binary(checkout, tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "UPSTREAM_DEPENDENCIES", DEPS)
    out = tmp_path / "out"
    out.mkdir()
    binary = out / "ArmorPaint.exe"
    binary.write_bytes(b"exe")

    assert bm.main(["--checkout", str(checkout), "--binary", str(binary)]) == 0

    manifest = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["schema"] == 1
    assert manifest["binary_sha256"] == hashlib.sha256(b"exe").hexdigest()
    assert manifest["branch"] == "integration/ap-mcp"
    assert manifest["head"] == bm.rev_parse(str(checkout), "HEAD")
    assert manifest["upstream_base"] == bm.rev_parse(str(checkout), "main")
    assert manifest["dependencies"]["merged"]["included"] is True
    assert manifest["dependencies"]["absent"]["included"] is False


def test_main_refuses_a_checkout_with_uncommitted_tracked_changes(checkout, tmp_path):
    (checkout / "base.txt").write_text("edited after the build", encoding="utf-8")
    binary = tmp_path / "ArmorPaint.exe"
    binary.write_bytes(b"exe")

    assert bm.main(["--checkout", str(checkout), "--binary", str(binary)]) == 1
    assert not (tmp_path / MANIFEST_NAME).exists()
```

- [ ] **Step 2: Run to verify they fail.**

Run: `& $py -m pytest -q tests/test_build_manifest.py`
Expected: FAIL at collection (`ImportError: cannot import name 'build_manifest'`).

- [ ] **Step 3: Implement** `src/armorpaint_mcp/build_manifest.py`:

```python
"""Write AP_BINARY's build manifest. `ap-mcp --check` reads it to prove that
each upstream dependency (dependencies.UPSTREAM_DEPENDENCIES) is in the
build. Run it right after every AP_BINARY build:

    python -m armorpaint_mcp.build_manifest --checkout C:\\Projects-local\\z-Git\\ArmorPaint --binary C:\\Projects-local\\z-Git\\ArmorPaint\\paint\\build\\out\\ArmorPaint.exe

Read-only on the checkout (git rev-parse, merge-base, cherry, status). Writes
one file, <binary dir>\\ap-mcp-build.json. It refuses a checkout with
uncommitted changes to tracked files, because the binary might contain
them and the manifest couldn't say so."""

import argparse
import datetime
import json
import os
import subprocess
import sys

from armorpaint_mcp.dependencies import (MANIFEST_SCHEMA, UPSTREAM_DEPENDENCIES,
                                         UpstreamDependency, binary_sha256, manifest_path)


def _git(checkout: str, *args: str) -> tuple[int, str]:
    proc = subprocess.run(["git", "-C", checkout, *args], capture_output=True,
                          text=True, errors="replace")
    return proc.returncode, proc.stdout.strip()


def rev_parse(checkout: str, ref: str) -> str | None:
    code, out = _git(checkout, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return out if code == 0 and out else None


def is_ancestor(checkout: str, commit: str, head: str) -> bool:
    return _git(checkout, "merge-base", "--is-ancestor", commit, head)[0] == 0


def dependency_status(checkout: str, head: str, dep: UpstreamDependency) -> dict:
    """Is `dep` in the tree at `head`? Either the branch tip is an ancestor
    (the integration branch merges each PR branch with --no-ff), or `git
    cherry` finds an identical patch (a cherry-pick, or an unedited squash
    upstream). Once a PR merges upstream with edits, set its registry
    entry's upstream_commit."""
    if dep.upstream_commit:
        upstream = rev_parse(checkout, dep.upstream_commit)
        if upstream and is_ancestor(checkout, upstream, head):
            return {"included": True, "how": "merged upstream", "head": upstream}
    tip = (rev_parse(checkout, f"refs/heads/{dep.branch}")
           or rev_parse(checkout, f"refs/remotes/gc-fork/{dep.branch}"))
    if tip is None:
        return {"included": False, "how": f"branch {dep.branch} not found", "head": None}
    if is_ancestor(checkout, tip, head):
        return {"included": True, "how": "ancestor", "head": tip}
    code, cherry = _git(checkout, "cherry", head, tip)
    if code == 0 and cherry and all(line.startswith("-") for line in cherry.splitlines()):
        return {"included": True, "how": "patch-equivalent", "head": tip}
    return {"included": False, "how": "not merged into the build", "head": tip}


def build_manifest(checkout: str, binary: str, deps=None) -> dict:
    deps = UPSTREAM_DEPENDENCIES if deps is None else deps
    head = rev_parse(checkout, "HEAD")
    _, branch = _git(checkout, "rev-parse", "--abbrev-ref", "HEAD")
    code, base = _git(checkout, "merge-base", head, "refs/remotes/origin/main")
    return {
        "schema": MANIFEST_SCHEMA,
        "binary": os.path.abspath(binary),
        "binary_sha256": binary_sha256(binary),
        "checkout": os.path.abspath(checkout),
        "head": head,
        "branch": branch,
        "upstream_base": base if code == 0 and base else None,
        "written": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "dependencies": {d.key: dependency_status(checkout, head, d) for d in deps},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m armorpaint_mcp.build_manifest",
        description="Write ap-mcp-build.json next to AP_BINARY (read by ap-mcp --check).")
    parser.add_argument("--checkout", required=True, help="the ArmorPaint git checkout")
    parser.add_argument("--binary", required=True, help="the ArmorPaint.exe just built from it")
    args = parser.parse_args(argv)
    if not os.path.isfile(args.binary):
        print(f"no such binary: {args.binary}", file=sys.stderr)
        return 1
    if rev_parse(args.checkout, "HEAD") is None:
        print(f"not a git checkout: {args.checkout}", file=sys.stderr)
        return 1
    code, dirty = _git(args.checkout, "status", "--porcelain", "--untracked-files=no")
    if code != 0 or dirty:
        print("refusing: the checkout has uncommitted changes to tracked files, so the "
              "binary may not match any commit:\n" + dirty, file=sys.stderr)
        return 1
    manifest = build_manifest(args.checkout, args.binary)
    path = manifest_path(args.binary)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    for key, status in manifest["dependencies"].items():
        print(f"  [{'IN ' if status['included'] else 'OUT'}] {key}: {status['how']}")
    print(f"wrote {path} ({manifest['branch']} @ {manifest['head'][:8]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests.**

Run: `& $py -m pytest -q tests/test_build_manifest.py` → 4 passed. Then `& $py -m pytest -q` → **242 passed**, 38 deselected.

- [ ] **Step 5: Commit**

```powershell
git add src/armorpaint_mcp/build_manifest.py tests/test_build_manifest.py; git commit -m "feat: build-manifest writer records which upstream dependencies AP_BINARY contains" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `merge_mesh_pair` tool (mocked; runs on any build)

**Files:**
- Create: `src/armorpaint_mcp/merge_pair.py`
- Modify: `src/armorpaint_mcp/server.py`:
  - imports: add `from collections.abc import Callable` and `from armorpaint_mcp import merge_pair as mp`
  - `_run_mesh_edit`, lines 171-203
  - `merge_mesh_geometry`'s docstring, lines 344-348
  - add `merge_mesh_pair` after `mcp.tool()(merge_mesh_geometry)` (line 397)
- Modify: `src/armorpaint_mcp/catalog.py` (`EMITTED_MINIC_FUNCTIONS`, lines 137-158)
- Modify: `smoke/smoke.ps1` (after the Phase 6 block)
- Test: `tests/test_merge_pair.py` (new), `tests/test_server.py`, `tests/test_catalog.py`

**Interfaces:**
- Consumes: `server._resolve_edit_target`, `_save_script`, `_run_saving_script`, `_failure`, `run_api`, `catalog.scene_objects`, `script_gen.minic_string_literal`/`NodeSpecError` (all existing).
- Produces:
  - `merge_pair.ERROR_MARKER = "MERGE_ERR"`
  - `merge_pair.MergePairError(Exception)`
  - `merge_pair.build_merge_lines(keep: str, merge: str) -> list[str]`, which raises `MergePairError` (same name) or `NodeSpecError` (bad characters)
  - `merge_pair.check_pair(names: list[str], keep: str, merge: str) -> None`, which raises `MergePairError`
  - `merge_pair.marker_error(stdout: str) -> str | None`
  - `server._run_mesh_edit(project, minic_call: str | list[str], output_project, in_place, timeout_s, explain_abort: Callable[[str], str | None] | None = None) -> dict`. It is backward compatible.
  - `server.merge_mesh_pair(project: str, keep: str, merge: str, output_project: str | None = None, in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict`, which returns `{"ok", "output_project", "error"}`

- [ ] **Step 1: Write the failing pure tests.** Create `tests/test_merge_pair.py`:

```python
import pytest

from armorpaint_mcp import merge_pair as mp
from armorpaint_mcp.script_gen import NodeSpecError


def test_build_merge_lines_merges_merge_into_keep_and_verifies_the_result():
    lines = mp.build_merge_lines("Tessellated", "Cone")
    text = "\n".join(lines)

    assert 'object_t *keep_obj = script_get_object("Tessellated");' in lines
    assert 'object_t *merge_obj = script_get_object("Cone");' in lines
    assert "script_object_merge(merge_obj, keep_obj);" in lines
    # the in-script checks come after the merge, and nothing saves here:
    # server._save_script appends project_save LAST.
    assert text.index("script_object_merge(") < text.index("merge_did_nothing")
    assert text.index("script_object_merge(") < text.index("keep_lost")
    assert "project_save" not in text


def test_build_merge_lines_rejects_the_same_object_twice():
    with pytest.raises(mp.MergePairError, match="same object"):
        mp.build_merge_lines("Cone", "Cone")


@pytest.mark.parametrize("bad", ['Co"ne', "Co\\ne"])
def test_build_merge_lines_rejects_a_name_that_would_break_the_literal(bad):
    with pytest.raises(NodeSpecError):
        mp.build_merge_lines("Tessellated", bad)


def test_check_pair_accepts_two_distinct_existing_objects():
    mp.check_pair(["Tessellated", "Cone", "Torus"], "Tessellated", "Cone")


def test_check_pair_needs_two_objects():
    with pytest.raises(mp.MergePairError, match="only 1 object"):
        mp.check_pair(["Tessellated"], "Tessellated", "Cone")


def test_check_pair_names_the_missing_object_and_lists_the_real_ones():
    with pytest.raises(mp.MergePairError) as exc:
        mp.check_pair(["Tessellated", "Cone"], "Tessellated", "NoSuch")
    assert "NoSuch" in str(exc.value) and "Tessellated, Cone" in str(exc.value)


def test_check_pair_rejects_an_ambiguous_name():
    """Review Focus 1: script_get_object returns the FIRST match."""
    with pytest.raises(mp.MergePairError, match="matches 2 objects"):
        mp.check_pair(["Cone", "Cone", "Torus"], "Torus", "Cone")


def test_marker_error_explains_the_abort():
    why = mp.marker_error("Project loaded\nMERGE_ERR merge_did_nothing\n")
    assert why is not None and "merge_did_nothing" in why and "script_object_merge" in why


def test_marker_error_is_none_without_a_marker():
    assert mp.marker_error("Project saved\n") is None
```

- [ ] **Step 2: Run to verify they fail.**

Run: `& $py -m pytest -q tests/test_merge_pair.py`
Expected: FAIL at collection (`ImportError: cannot import name 'merge_pair'`).

- [ ] **Step 3: Implement** `src/armorpaint_mcp/merge_pair.py`:

```python
"""Pure-Python pieces of merge_mesh_pair (docs/PLAN.md Phase 7, item 9):
name checks, the minic lines, and abort markers. The merge itself is
ArmorPaint's own util_mesh_merge_geometry_down (util/util_mesh.c), reached
through script_object_merge (Phase 7 C change 3)."""

import re

from armorpaint_mcp.script_gen import minic_string_literal

ERROR_MARKER = "MERGE_ERR"

_REASONS = {
    "keep_not_found": "the keep object isn't in the project ArmorPaint opened",
    "merge_not_found": "the merge object isn't in the project ArmorPaint opened",
    "merge_did_nothing": ("script_object_merge left the merge object in place: this "
                          "build's script_object_merge refused the pair"),
    "keep_lost": "the keep object disappeared during the merge",
}


class MergePairError(Exception):
    """The merge can't be applied; the message is caller-facing."""


def build_merge_lines(keep: str, merge: str) -> list[str]:
    """The script body (no save; server._save_script appends it last): look
    up both objects, merge `merge` into `keep`, then prove it happened.
    `merge` must be gone and `keep` still there, otherwise print a marker
    and return before the save, so nothing is written."""
    if keep == merge:
        raise MergePairError(
            f"keep and merge name the same object ('{keep}'); name two different objects")
    k = minic_string_literal(keep, "keep")
    m = minic_string_literal(merge, "merge")
    err = ERROR_MARKER
    return [
        f"object_t *keep_obj = script_get_object({k});",
        f'if (keep_obj == NULL) {{ console_log("{err} keep_not_found"); return; }}',
        f"object_t *merge_obj = script_get_object({m});",
        f'if (merge_obj == NULL) {{ console_log("{err} merge_not_found"); return; }}',
        "script_object_merge(merge_obj, keep_obj);",
        f'if (script_get_object({m}) != NULL) {{ console_log("{err} merge_did_nothing"); return; }}',
        f'if (script_get_object({k}) == NULL) {{ console_log("{err} keep_lost"); return; }}',
    ]


def check_pair(names: list[str], keep: str, merge: str) -> None:
    """`names` are the project's object names (catalog.scene_objects, the
    same names script_get_object matches). Both must exist exactly once."""
    if len(names) < 2:
        raise MergePairError(f"project has only {len(names)} object(s); merge_mesh_pair "
                             f"needs at least 2")
    for role, name in (("keep", keep), ("merge", merge)):
        count = names.count(name)
        if count == 0:
            raise MergePairError(f"no object named '{name}' ({role}); objects: "
                                 f"{', '.join(names)}")
        if count > 1:
            raise MergePairError(f"'{name}' ({role}) matches {count} objects; rename the "
                                 f"duplicates so the merge can target one unambiguously")


_MARKER_RE = re.compile(rf"^{ERROR_MARKER} (\S+)", re.MULTILINE)


def marker_error(stdout: str) -> str | None:
    match = _MARKER_RE.search(stdout or "")
    if match is None:
        return None
    code = match.group(1)
    return f"merge aborted ({code}): {_REASONS.get(code, 'unexpected abort marker')}"
```

- [ ] **Step 4: Run** `& $py -m pytest -q tests/test_merge_pair.py` → 10 passed.

- [ ] **Step 5: Write the failing server tests.** In `tests/test_server.py`, add `merge_mesh_pair` to the `from armorpaint_mcp.server import (...)` list. Add this entry to `_NON_ASCII_CASES`:

```python
    "merge_mesh_pair": lambda p, m, t: merge_mesh_pair(p, "Tessellated", "Cone",
                                                       output_project=str(t / "o.arm")),
```

Then append:

```python
def _scene_api(*names):
    objects = "".join(f'"{n}": location (0.0, 0.0, 0.0), size (1.0, 1.0, 1.0)\n' for n in names)
    return "/* Current project state:\n{}\n\nScene objects in world space:\n" + objects


def _pair_call(tmp_path, run_side_effect, api_names=("Tessellated", "Cone", "Torus"),
               keep="Tessellated", merge="Cone", **kwargs):
    project = tmp_path / "project.arm"
    project.write_bytes(b"original")
    kwargs.setdefault("output_project", str(tmp_path / "out" / "merged.arm"))
    with patch("armorpaint_mcp.server._ensure_ready") as mock_cfg, \
         patch("armorpaint_mcp.server.run_api") as mock_api, \
         patch("armorpaint_mcp.server.run_minic_script", side_effect=run_side_effect) as mock_run:
        _cfg(mock_cfg)
        mock_api.return_value = ApiResult(ok=True, text=_scene_api(*api_names))
        result = merge_mesh_pair(project=str(project), keep=keep, merge=merge, **kwargs)
    return result, project, mock_api, mock_run


def test_merge_mesh_pair_merges_merge_into_keep_and_saves_a_fresh_sibling(tmp_path):
    result, project, mock_api, mock_run = _pair_call(tmp_path, _saving_run())

    output = tmp_path / "out" / "merged.arm"
    assert result == {"ok": True, "output_project": str(output), "error": None}
    assert output.read_bytes() == b"edited"
    assert project.read_bytes() == b"original"
    mock_api.assert_called_once()
    opened, script = mock_run.call_args[0][1], mock_run.call_args[0][2]
    assert opened == str(project)
    assert "script_object_merge(merge_obj, keep_obj);" in script
    assert script.index("script_object_merge(") < script.index("project_save(0);")
    assert script.rstrip().endswith("project_save(0);\n}")
    assert os.listdir(output.parent) == ["merged.arm"]


def test_merge_mesh_pair_in_place_replaces_the_project(tmp_path):
    result, project, _, _ = _pair_call(tmp_path, _saving_run(), output_project=None,
                                       in_place=True)

    assert result == {"ok": True, "output_project": str(project), "error": None}
    assert project.read_bytes() == b"edited"


def test_merge_mesh_pair_rejects_an_unknown_name_without_a_saving_launch(tmp_path):
    result, _, _, mock_run = _pair_call(tmp_path, _saving_run(), merge="NoSuch")

    assert result["ok"] is False and result["output_project"] is None
    assert "NoSuch" in result["error"] and "Tessellated, Cone, Torus" in result["error"]
    mock_run.assert_not_called()
    assert not (tmp_path / "out" / "merged.arm").exists()


def test_merge_mesh_pair_rejects_the_same_name_without_launching(tmp_path):
    """Review Focus 1."""
    result, _, mock_api, mock_run = _pair_call(tmp_path, _saving_run(), keep="Cone",
                                               merge="Cone")

    assert result["ok"] is False and "same object" in result["error"]
    mock_api.assert_not_called()
    mock_run.assert_not_called()


def test_merge_mesh_pair_checks_output_project_before_launching(tmp_path):
    """Review Focus 5: unlike merge_mesh_geometry, no --api launch first."""
    result, _, mock_api, mock_run = _pair_call(tmp_path, _saving_run(), output_project=None)

    assert result["ok"] is False and "output_project is required" in result["error"]
    mock_api.assert_not_called()
    mock_run.assert_not_called()


def test_merge_mesh_pair_reports_the_in_script_abort_marker(tmp_path):
    def aborts(binary, project, script, timeout_s):
        return ScriptResult(ok=True, stdout="MERGE_ERR merge_did_nothing\n", stderr="")

    result, _, _, _ = _pair_call(tmp_path, aborts)

    assert result["ok"] is False and result["output_project"] is None
    assert "merge_did_nothing" in result["error"]
    assert not (tmp_path / "out" / "merged.arm").exists()
    assert os.listdir(tmp_path / "out") == []


def test_merge_mesh_pair_on_a_build_without_script_object_merge_fails_cleanly(tmp_path):
    """Review Focus 2: a stock or pre-Phase-7 AP_BINARY."""
    line = "<script>:6: error: unknown function 'script_object_merge' (got '(')"

    def old_build(binary, project, script, timeout_s):
        return ScriptResult(ok=False, stdout=line + "\n", stderr="",
                            error=f"script error: {line}")

    result, _, _, _ = _pair_call(tmp_path, old_build)

    assert result["ok"] is False
    assert "unknown function 'script_object_merge'" in result["error"]
    assert not (tmp_path / "out" / "merged.arm").exists()


def test_merge_mesh_pair_is_registered_as_an_mcp_tool():
    tools = asyncio.run(mcp.list_tools())
    assert "merge_mesh_pair" in {t.name for t in tools}
```

In `tests/test_catalog.py`'s `_captured_scripts`, after the `scripts += captured + [server._save_script(["util_mesh_merge_geometry();"], ...)]` statement, add:

```python
    # merge_mesh_pair runs run_api first too; its body is merge_pair.build_merge_lines
    from armorpaint_mcp import merge_pair as mp
    scripts.append(server._save_script(mp.build_merge_lines("A", "B"), str(tmp_path / "f.arm")))
```

- [ ] **Step 6: Run to verify they fail.**

Run: `& $py -m pytest -q tests/test_server.py tests/test_catalog.py`
Expected: FAIL (`ImportError: cannot import name 'merge_mesh_pair'`).

- [ ] **Step 7: Implement in `server.py`.** Add the two imports. Replace `_run_mesh_edit` (lines 171-203) with:

```python
def _run_mesh_edit(project: str, minic_call: str | list[str], output_project: str | None,
                   in_place: bool, timeout_s: float,
                   explain_abort: Callable[[str], str | None] | None = None) -> dict:
    """Shared plumbing for every mesh-edit tool: open the caller's project
    (never writing it), run `minic_call` (one statement, or a list of lines),
    save to a fresh sibling of the target, then move that over the target. A
    failure at any point leaves the target untouched and no temp file behind.
    `explain_abort(stdout)` may turn a script's own abort marker into the
    error message (the script returned before saving on purpose).

    ok=True means ArmorPaint exited cleanly, printed no minic error, and
    saved the edited project -- not that the edit looks good.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    cfg = _ensure_ready()
    resolved = _resolve_edit_target(project, output_project, in_place, cfg)
    if isinstance(resolved, dict):
        return resolved
    project, target = resolved
    fresh = _fresh_sibling(target)
    body = [minic_call] if isinstance(minic_call, str) else list(minic_call)
    try:
        script = _save_script(body, fresh)
    except NodeSpecError as exc:
        return _failure(str(exc), "output_project")
    try:
        result = _run_saving_script(cfg, project, script, fresh, timeout_s)
        error = result.error
        if explain_abort is not None and (why := explain_abort(result.stdout or "")) is not None:
            error = why
        if result.ok and error is None:
            os.replace(fresh, target)
    except OSError as exc:
        error = f"could not write output_project: {exc}"
    finally:
        _remove_quietly(fresh)
    if error is not None:
        return _failure(error, "output_project")
    return {"ok": True, "output_project": target, "error": None}
```

In `merge_mesh_geometry`'s docstring, replace the `IMPORTANT:` paragraph (lines 344-348) with:

```
    IMPORTANT: this merges ALL objects in the project into the first one.
    To merge one chosen object into another and leave the rest alone, use
    merge_mesh_pair.
```

After `mcp.tool()(merge_mesh_geometry)` add:

```python
def merge_mesh_pair(project: str, keep: str, merge: str, output_project: str | None = None,
                    in_place: bool = False, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Merge the object named `merge` into the object named `keep` and leave
    every other object alone -- ArmorPaint's own "merge down"
    (util_mesh_merge_geometry_down), reached through script_object_merge.
    `keep` keeps its name, transform, parent and material; `merge`'s geometry
    is baked into `keep`'s local space and `merge` is removed, its children
    moved under `keep` with their world position kept. ArmorPaint remaps
    layer object masks itself. UVs are not re-unwrapped. To merge ALL objects
    into one, use merge_mesh_geometry.

    Both names must exist exactly once and differ (names as inspect_project
    reports them); this is checked through --api before the edit, which
    costs one extra ArmorPaint launch. Requires an AP_BINARY with
    script_object_merge (docs/PLAN.md Phase 7 change 3): `ap-mcp --check`'s
    "upstream dependency script-object-merge" row verifies it. On an older
    build this returns ok=False naming the unknown function.

    Writes the result to `output_project` by default (the caller's `project`
    is never modified) -- pass in_place=True to mutate `project` itself
    instead, in which case output_project must be omitted. Bounded by
    AP_ALLOWED_ROOTS when set.

    ok=True means ArmorPaint exited cleanly, printed no script error, the
    script confirmed `merge` is gone and `keep` still exists, and the result
    was saved.

    Returns {"ok": bool, "output_project": str | None, "error": str | None}."""
    cfg = _ensure_ready()
    resolved = _resolve_edit_target(project, output_project, in_place, cfg)
    if isinstance(resolved, dict):
        return resolved
    checked_project, _ = resolved
    try:
        lines = mp.build_merge_lines(keep, merge)
    except (NodeSpecError, mp.MergePairError) as exc:
        return _failure(str(exc), "output_project")
    api_result = run_api(cfg.binary, checked_project, timeout_s)
    if not api_result.ok:
        return _failure(api_result.error, "output_project")
    try:
        names = [o["name"] for o in scene_objects(api_result.text)]
        mp.check_pair(names, keep, merge)
    except (CatalogError, mp.MergePairError) as exc:
        return _failure(str(exc), "output_project")
    return _run_mesh_edit(project, lines, output_project, in_place, timeout_s,
                          explain_abort=mp.marker_error)


mcp.tool()(merge_mesh_pair)
```

- [ ] **Step 8: Register the minic name.** In `catalog.py`'s `EMITTED_MINIC_FUNCTIONS`, after the `"console_log",` entry add:

```python
    # merge_mesh_pair (merge_pair.build_merge_lines); Phase 7 change 3
    "script_object_merge",
```

- [ ] **Step 9: Smoke probe.** In `smoke/smoke.ps1`, after the Phase 6 probes add:

```powershell
# Phase 7: targeted 2-object merge, registered on the MCP server object.
Probe "merge_mesh_pair registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'merge_mesh_pair' in names, names; print(names)" }
```

- [ ] **Step 10: Run everything.**

- `& $py -m pytest -q` → **261 passed** (242 + 10 pure + 8 server + 1 non-ASCII case), 38 deselected. `test_every_emitted_minic_call_is_in_the_registry` passes only because of Step 8.
- `pwsh smoke/smoke.ps1` → `16 passed, 0 failed`, exit 0.

- [ ] **Step 11: Commit**

```powershell
git add src/armorpaint_mcp/merge_pair.py src/armorpaint_mcp/server.py src/armorpaint_mcp/catalog.py smoke/smoke.ps1 tests/test_merge_pair.py tests/test_server.py tests/test_catalog.py; git commit -m "feat: merge_mesh_pair merges one named object into another (needs script_object_merge)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: UV-less non-OBJ fixture and the texa-aware docstrings

**Files:**
- Create: `tests/fixtures/phase7/make_nouv_glb.py`, `tests/fixtures/phase7/repl_grid5_nouv.glb` (generated, committed), `tests/fixtures/phase7/.gitattributes`, `tests/fixtures/phase7/README.md`
- Modify: `src/armorpaint_mcp/replace.py` (`precheck_replacement` docstring, lines 27-33), `src/armorpaint_mcp/server.py` (`replace_mesh` docstring: the sentence "Either way the new mesh must have valid UVs.")
- Test: `tests/test_phase7_fixtures.py` (new)

**Interfaces:**
- Produces: `tests/fixtures/phase7/repl_grid5_nouv.glb`. It is `phase6/repl_grid5.glb` with `TEXCOORD_0` removed, and its node and mesh are named `ReplGridNoUV`. Task 10 appends it.
- Produces: `make_nouv_glb.strip_uvs(glb: bytes) -> bytes`, `SRC`, `OUT`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_phase7_fixtures.py`:

```python
import importlib.util
import json
import os
import struct

PHASE7 = os.path.join(os.path.dirname(__file__), "fixtures", "phase7")
NOUV_GLB = os.path.join(PHASE7, "repl_grid5_nouv.glb")


def _generator():
    spec = importlib.util.spec_from_file_location(
        "make_nouv_glb", os.path.join(PHASE7, "make_nouv_glb.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_chunk(glb: bytes) -> dict:
    length, _ = struct.unpack_from("<II", glb, 12)
    return json.loads(glb[20:20 + length])


def test_the_committed_glb_is_exactly_what_the_generator_writes():
    gen = _generator()
    with open(gen.SRC, "rb") as fh:
        expected = gen.strip_uvs(fh.read())
    with open(NOUV_GLB, "rb") as fh:
        assert fh.read() == expected


def test_the_glb_has_positions_and_indices_but_no_texcoords():
    with open(NOUV_GLB, "rb") as fh:
        glb = fh.read()
    assert struct.unpack_from("<I", glb, 8)[0] == len(glb)       # header length is right
    doc = _json_chunk(glb)
    prim = doc["meshes"][0]["primitives"][0]
    assert "TEXCOORD_0" not in prim["attributes"]
    assert "POSITION" in prim["attributes"] and "indices" in prim
    assert [n["name"] for n in doc["nodes"] if "mesh" in n] == ["ReplGridNoUV"]
```

- [ ] **Step 2: Run** `& $py -m pytest -q tests/test_phase7_fixtures.py` → FAIL (`FileNotFoundError` for `make_nouv_glb.py`).

- [ ] **Step 3: Write the generator.** Create `tests/fixtures/phase7/make_nouv_glb.py`:

```python
"""Writes repl_grid5_nouv.glb: ../phase6/repl_grid5.glb with its TEXCOORD_0
attribute removed and its node/mesh renamed ReplGridNoUV. The texcoord
accessor stays in the file, unused, which is valid glTF. The binary chunk is
copied unchanged. Deterministic; the output is committed.

    .venv\\Scripts\\python.exe tests\\fixtures\\phase7\\make_nouv_glb.py

ArmorPaint's glTF importer leaves raw->texa NULL when there is no
TEXCOORD_0 (paint/plugins/io_gltf/cgltf.c:190-204), so the mesh reaches
import_mesh_add_mesh's texa fallback (io/import_mesh.c:260-263): Phase 7
change 1's subject."""

import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "phase6", "repl_grid5.glb"))
OUT = os.path.join(HERE, "repl_grid5_nouv.glb")
NAME = "ReplGridNoUV"
_JSON_CHUNK = 0x4E4F534A


def strip_uvs(glb: bytes) -> bytes:
    magic, version, _ = struct.unpack_from("<4sII", glb, 0)
    if magic != b"glTF" or version != 2:
        raise ValueError("not a glTF 2.0 binary")
    json_len, json_type = struct.unpack_from("<II", glb, 12)
    if json_type != _JSON_CHUNK:
        raise ValueError("the first chunk is not JSON")
    doc = json.loads(glb[20:20 + json_len])
    rest = glb[20 + json_len:]                     # the BIN chunk, header included
    for mesh in doc["meshes"]:
        mesh["name"] = NAME
        for prim in mesh["primitives"]:
            prim["attributes"].pop("TEXCOORD_0", None)
    for node in doc["nodes"]:
        if "mesh" in node:
            node["name"] = NAME
    text = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    text += b" " * (-len(text) % 4)                # chunks stay 4-byte aligned
    body = struct.pack("<II", len(text), _JSON_CHUNK) + text + rest
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


if __name__ == "__main__":
    with open(SRC, "rb") as fh:
        data = strip_uvs(fh.read())
    with open(OUT, "wb") as fh:
        fh.write(data)
    print(f"wrote {OUT} ({len(data)} bytes)")
```

Create `tests/fixtures/phase7/.gitattributes` containing the single line `* -text`. Create `tests/fixtures/phase7/README.md`:

```markdown
# Phase 7 fixtures

- `repl_grid5_nouv.glb`: `../phase6/repl_grid5.glb` without `TEXCOORD_0`,
  node/mesh `ReplGridNoUV`. Regenerate with `make_nouv_glb.py`;
  `tests/test_phase7_fixtures.py` fails if the committed file drifts from it.
- `objects3_masked.arm` (optional, made by hand in the ArmorPaint GUI, see
  the Phase 7 plan's Task 11): `../phase6/objects3.arm` with one layer's
  object mask set to `Torus`. Its tests skip when it is absent.
```

- [ ] **Step 4: Generate and run.** `& $py tests\fixtures\phase7\make_nouv_glb.py` → `wrote ...repl_grid5_nouv.glb (<n> bytes)`. Then `& $py -m pytest -q tests/test_phase7_fixtures.py` → 2 passed.

- [ ] **Step 5: Docstrings.** In `replace.py`'s `precheck_replacement` docstring, replace `every face must have UVs (missing ones come out as uninitialized memory, io/import_mesh.c:260-263)` with:

```
    every face must have UVs (missing ones come out as all-(0,0) UVs on a
    build with Phase 7's texa zero-init, as uninitialized memory on one
    without it -- io/import_mesh.c:260-263)
```

In `server.replace_mesh`'s docstring, replace `Either way the new mesh must have valid UVs.` with:

```
    Either way the new mesh must have valid UVs. A UV-less OBJ is rejected
    before launch; a UV-less FBX/GLB/glTF is rejected reliably only on an
    AP_BINARY with the texa zero-init (`ap-mcp --check`'s "upstream
    dependency import-mesh-texa-zero-init" row) -- without it its UVs are
    uninitialized memory and might pass.
```

- [ ] **Step 6: Run** `& $py -m pytest -q` → **263 passed**, 38 deselected.

- [ ] **Step 7: Commit**

```powershell
git add tests/fixtures/phase7 tests/test_phase7_fixtures.py src/armorpaint_mcp/replace.py src/armorpaint_mcp/server.py; git commit -m "test: UV-less GLB fixture; document replace_mesh's texa dependency" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: C change 1 — `texa` zero-init (checkout, local commit only)

**Files:**
- Modify: `C:\Projects-local\z-Git\ArmorPaint\paint\sources\io\import_mesh.c` (lines 183-186 and 260-263 at `85f6cf1c`), on new branch `fix/import-mesh-texa-zero-init`

**Interfaces:**
- Consumes: nothing from Tasks 1-4.
- Produces: local branch `fix/import-mesh-texa-zero-init` (one commit on the fetched `origin/main`), and `UPSTREAM_BASE` = the fetched `origin/main` SHA, which goes in the task report. Tasks 6-8 and 13 use both.

- [ ] **Step 1: HUMAN GATE:** controller confirms Grayson's go for: "in `C:\Projects-local\z-Git\ArmorPaint`, run `git fetch origin`, create local branch `fix/import-mesh-texa-zero-init` from the fetched `origin/main` (this switches the checkout's working tree off `fix/mesh-accumulator-zero-init`), add 2 `memset` lines to `paint/sources/io/import_mesh.c`, and commit locally. No push, no build" before dispatch.

- [ ] **Step 2: Preflight and re-pin.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git status --porcelain --untracked-files=no; git rev-parse --abbrev-ref HEAD; git fetch origin; git rev-parse origin/main; git log --oneline 85f6cf1c..origin/main -- paint/sources; Pop-Location
```

Expected:
- `status` prints nothing (if it prints anything, stop and report).
- The branch is `fix/mesh-accumulator-zero-init`.
- `origin/main` prints `eec04adf...` or newer. Record the full SHA as `UPSTREAM_BASE`.
- The `paint/sources` log is empty as of 2026-09-27. If it isn't, list those commits in the report and re-verify every site in Steps 3 of Tasks 5-7 before editing.

- [ ] **Step 3: Verify the sites on `origin/main`.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git grep -n "mesh->texa = i16_array_create(verts \* 2);" origin/main -- paint/sources/io/import_mesh.c; Pop-Location
```

Expected: exactly two hits (`:185` and `:262` at `85f6cf1c`). Anything else: stop and report.

- [ ] **Step 4: Branch.** `git -C C:\Projects-local\z-Git\ArmorPaint switch -c fix/import-mesh-texa-zero-init origin/main`

- [ ] **Step 5: Edit.** In `paint\sources\io\import_mesh.c`, both blocks (in `import_mesh_make_mesh` and `import_mesh_add_mesh`) read:

```c
	if (mesh->texa == NULL) {
		i32 verts  = mesh->posa->length / 4;
		mesh->texa = i16_array_create(verts * 2);
	}
```

Make each one read:

```c
	if (mesh->texa == NULL) {
		i32 verts  = mesh->posa->length / 4;
		mesh->texa = i16_array_create(verts * 2);
		memset(mesh->texa->buffer, 0, mesh->texa->length * sizeof(i16));
	}
```

(`i16` is `int16_t`, `base/sources/iron_global.h:29`. `i16_array_create` → `i16_array_resize` is a plain `realloc`, `base/sources/iron_array.c:103`, `:552-559`.)

- [ ] **Step 6: Check the diff and the format.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git diff --stat; & "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\Llvm\x64\bin\clang-format.exe" --style=file --dry-run --lines=180:192 --lines=258:270 paint\sources\io\import_mesh.c; Pop-Location
```

Expected: `1 file changed, 2 insertions(+)`, and clang-format prints no warnings.

- [ ] **Step 7: Commit (local).**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git add paint/sources/io/import_mesh.c; git commit -m "paint: zero-init texcoords for meshes imported without UVs" -m "import_mesh_make_mesh and import_mesh_add_mesh create the texa array for a mesh without texture coordinates with i16_array_create, which never zeroes its buffer (i16_array_resize is a plain realloc). The mesh's UVs are then leftover heap contents and change run to run. make_mesh usually unwraps afterwards; add_mesh (appends, and every mesh after the first in a file) does not, so the garbage stays." -m "Zero the buffer right after creating it. A UV-less mesh now imports with every UV at (0, 0)." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; git log --oneline -2; Pop-Location
```

Report the new commit's SHA and `UPSTREAM_BASE`. Nothing is built here; Task 8 builds.

---

### Task 6: C change 2 — object-mask remap on delete (checkout, local commit only)

**Files:**
- Modify: `C:\Projects-local\z-Git\ArmorPaint\paint\sources\ui\tab_meshes.c` (`tab_meshes_draw_context_menu_delete`, `:443-476` at `85f6cf1c`, insert after `:465`), on new branch `fix/mesh-delete-object-mask-remap`

**Interfaces:**
- Consumes: the fetched `origin/main` from Task 5 (no second fetch).
- Produces: local branch `fix/mesh-delete-object-mask-remap` (one commit on `origin/main`).

- [ ] **Step 1: HUMAN GATE:** controller confirms Grayson's go for: "in `C:\Projects-local\z-Git\ArmorPaint`, create local branch `fix/mesh-delete-object-mask-remap` from `origin/main`, add a layer-object-mask remap (10 lines + 1 blank) to `tab_meshes_draw_context_menu_delete` in `paint/sources/ui/tab_meshes.c`, and commit locally. No push, no build" before dispatch.

- [ ] **Step 2: Preflight and verify the site.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git status --porcelain --untracked-files=no; git grep -n -A1 "array_remove(g_project->_->paint_objects, o);" origin/main -- paint/sources/ui/tab_meshes.c; git grep -n "tab_meshes_delete_index = array_index_of" origin/main -- paint/sources/ui/tab_meshes.c; Pop-Location
```

Expected: an empty status. One `array_remove` hit (`:464`), followed by `tab_timeline_on_mesh_deleted(mesh_name);`. One `tab_meshes_delete_index = array_index_of(...)` hit at the top of the same function (`:445`). Otherwise stop and report.

- [ ] **Step 3: Branch.** `git -C C:\Projects-local\z-Git\ArmorPaint switch -c fix/mesh-delete-object-mask-remap origin/main`

- [ ] **Step 4: Edit.** In `tab_meshes_draw_context_menu_delete`, the lines

```c
	array_remove(g_project->_->paint_objects, o);
	tab_timeline_on_mesh_deleted(mesh_name);

	object_t *new_root = g_project->_->paint_objects->buffer[0]->base;
```

become

```c
	array_remove(g_project->_->paint_objects, o);
	tab_timeline_on_mesh_deleted(mesh_name);

	i32 deleted_mask = tab_meshes_delete_index + 1;
	if (g_project->_->layers != NULL) {
		for (i32 i = 0; i < g_project->_->layers->length; ++i) {
			slot_layer_t *l = g_project->_->layers->buffer[i];
			l->object_mask  = l->object_mask == deleted_mask ? 0 : l->object_mask > deleted_mask ? l->object_mask - 1 : l->object_mask;
		}
	}
	g_context->layer_filter = g_context->layer_filter == deleted_mask  ? 0
	                          : g_context->layer_filter > deleted_mask ? g_context->layer_filter - 1
	                                                                   : g_context->layer_filter;

	object_t *new_root = g_project->_->paint_objects->buffer[0]->base;
```

A mask is the object's `paint_objects` index + 1, and 0 means all objects. This mirrors `util_mesh_merge_geometry_down`'s remap (`util/util_mesh.c:637-645`). A mask that pointed at the deleted object becomes 0, the value `util_mesh_merge_geometry` resets every mask to. The PR text leaves that choice to the maintainer. Don't touch the stage-shared branch above it: it returns early without removing anything from `paint_objects`.

- [ ] **Step 5: Check the diff and the format.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git diff --stat; & "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\Llvm\x64\bin\clang-format.exe" --style=file --dry-run --lines=462:480 paint\sources\ui\tab_meshes.c; Pop-Location
```

Expected: `1 file changed, 11 insertions(+)`. If clang-format warns about the inserted lines, apply exactly its suggestion to those lines only (`--lines=462:480 -i`), re-run `git diff`, and confirm that only the inserted lines changed.

- [ ] **Step 6: Commit (local).**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git add paint/sources/ui/tab_meshes.c; git commit -m "paint: remap layer object masks when deleting a mesh" -m "A layer's object_mask is its object's paint_objects index + 1. Deleting a mesh removed it from paint_objects but left every mask unchanged, so masks past the deleted slot pointed at the wrong object, and one on the deleted object pointed at whatever took its place. layer_filter had the same problem. tab_meshes_sort_hierarchy runs after the removal, so it can't see the shift." -m "Shift masks above the deleted slot down by one, as util_mesh_merge_geometry_down already does; a mask on the deleted object becomes 0 (all objects)." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; git log --oneline -2; Pop-Location
```

Report the commit SHA.

---

### Task 7: C change 3 — `script_object_merge` (checkout, local commit only)

**Files:**
- Modify, on new branch `feat/script-object-merge`:
  - `C:\Projects-local\z-Git\ArmorPaint\paint\sources\minic_impl.c` (after `script_object_remove`, which ends at `:838`)
  - `paint\sources\functions.h` (after `:523`)
  - `paint\sources\minic_api_list.h` (after `:500`)

**Interfaces:**
- Consumes: the fetched `origin/main` from Task 5.
- Produces: local branch `feat/script-object-merge` with the minic function `void script_object_merge(object_t *o, object_t *into)`, registered as `X2(script_object_merge, "v(p:object_t o,p:object_t into)", v, p, p)`. `o` is merged into `into`; `into` survives. Task 3's `build_merge_lines` calls `script_object_merge(merge_obj, keep_obj)`.

- [ ] **Step 1: HUMAN GATE:** controller confirms Grayson's go for: "in `C:\Projects-local\z-Git\ArmorPaint`, create local branch `feat/script-object-merge` from `origin/main`, add `script_object_merge` (23 added lines across `paint/sources/minic_impl.c`, `functions.h` and `minic_api_list.h`, in `c0df922d`'s shape), and commit locally. No push, no build" before dispatch.

- [ ] **Step 2: Preflight and verify the sites.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git status --porcelain --untracked-files=no; git grep -n "script_object_remove\|script_object_merge" origin/main -- paint/sources/minic_impl.c paint/sources/functions.h paint/sources/minic_api_list.h; git grep -n "void                      util_mesh_merge_geometry_down" origin/main -- paint/sources/functions.h; Pop-Location
```

Expected: an empty status. `script_object_remove` appears once in each of the three files. `script_object_merge` appears nowhere; if upstream already added it, stop and report, because this change becomes moot. `util_mesh_merge_geometry_down` is declared in `functions.h` (`:674`).

- [ ] **Step 3: Branch.** `git -C C:\Projects-local\z-Git\ArmorPaint switch -c feat/script-object-merge origin/main`

- [ ] **Step 4: Edit `minic_impl.c`.** Insert between `script_object_remove`'s closing `}` and `void script_object_set_name(`:

```c
void script_object_merge(object_t *o, object_t *into) {
	if (o == NULL || into == NULL || o == into) {
		return;
	}
	if (!string_equals(o->ext_type, "mesh_object_t") || !string_equals(into->ext_type, "mesh_object_t")) {
		return;
	}

	gpu_texture_t *current;
	bool           in_use;
	script_gpu_begin(&current, &in_use);
	util_mesh_merge_geometry_down(into->ext, o->ext);
	script_gpu_end(current, in_use);

	tab_meshes_reset_preview_map();
	g_context->ddirty = 2;
	if (ui_base_hwnds != NULL && ui_base_hwnds->length > TAB_AREA_SIDEBAR0) {
		ui_base_hwnds->buffer[TAB_AREA_SIDEBAR0]->redraws = 2;
	}
}

```

(`util_mesh_merge_geometry_down` itself returns unless both are in `paint_objects` and distinct, `util/util_mesh.c:610-615`. It moves `o`'s children to `into`, splices `o` out of `paint_objects` and `atlas_objects`, and remaps layer masks. The GUI calls it from `tab_meshes_merge_down_next_frame`, outside the render pass. The script path gets the same guarantee from `script_gpu_begin`/`_end`, as `script_object_remove` does.)

- [ ] **Step 5: Edit `functions.h`.** After `void                      script_object_remove(object_t *o);` add:

```c
void                      script_object_merge(object_t *o, object_t *into);
```

- [ ] **Step 6: Edit `minic_api_list.h`.** After `X1(script_object_remove, "v(p:object_t o)", v, p)` add:

```c
X2(script_object_merge, "v(p:object_t o,p:object_t into)", v, p, p)
```

- [ ] **Step 7: Check the diff and the format.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git diff --stat; $cf = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\Llvm\x64\bin\clang-format.exe"; $n = (Select-String -Path paint\sources\minic_impl.c -Pattern '^void script_object_merge').LineNumber; & $cf --style=file --dry-run "--lines=$($n):$($n + 20)" paint\sources\minic_impl.c; Pop-Location
```

Expected: `3 files changed, 23 insertions(+)` (21 in `minic_impl.c`, 1 each in the headers), and no clang-format warnings.

- [ ] **Step 8: Commit (local).**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git add paint/sources/minic_impl.c paint/sources/functions.h paint/sources/minic_api_list.h; git commit -m "paint: add script_object_merge" -m "Merges mesh object o into into, the scripted form of the Meshes tab's Merge Down: checks ext_type, wraps the GPU state and calls util_mesh_merge_geometry_down(into->ext, o->ext), like script_object_remove." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; git log --oneline -2; Pop-Location
```

Report the commit SHA.

---

### Task 8: Integration branch, `AP_BINARY` rebuild, build manifest

**Files:**
- Checkout: new local branch `integration/ap-mcp`; build outputs `paint\build\out\ArmorPaint.exe`, `paint\build\out\data\` and `paint\build\out\ap-mcp-build.json` (all git-ignored: `.gitignore:1` `**/build*/`)
- This repo: no file changes (the evidence goes in the report, and Task 12 records it)

**Interfaces:**
- Consumes: branches from Tasks 5-7 and `fix/mesh-accumulator-zero-init`, `build_manifest` (Task 2), `dependencies` (Task 1).
- Produces: `AP_BINARY` built from `integration/ap-mcp`, plus a manifest in which all four `UPSTREAM_DEPENDENCIES` are `included`. Tasks 9-12 rely on this. The report also records these for Tasks 12 and 13:
  - `INTEGRATION_HEAD`
  - `UPSTREAM_BASE`
  - the `--api` diff
  - whether `object_mask` appears in `--api` JSON

- [ ] **Step 1: HUMAN GATE:** controller confirms Grayson's go for all of the following in `C:\Projects-local\z-Git\ArmorPaint`, before dispatch:
  - (a) create local branch `integration/ap-mcp` from `origin/main` and `git merge --no-ff` into it `fix/mesh-accumulator-zero-init`, `fix/import-mesh-texa-zero-init`, `fix/mesh-delete-object-mask-remap` and `feat/script-object-merge`. The working tree switches to it.
  - (b) back up the current `paint\build\out\ArmorPaint.exe` to `paint\build\ArmorPaint-287e63f4.exe`, run `..\base\make.bat` from `paint\`, build `ArmorPaint.vcxproj` Release/x64 with VS2022 MSBuild, and copy the new exe over `paint\build\out\ArmorPaint.exe` (= `AP_BINARY`).
  - (c) write `paint\build\out\ap-mcp-build.json`.

- [ ] **Step 2: Capture the old binary's API and back it up.**

```powershell
$ap = 'C:\Projects-local\z-Git\ArmorPaint'; $bin = "$ap\paint\build\out\ArmorPaint.exe"; $work = "$env:TEMP\ap-mcp-phase7"; New-Item -ItemType Directory -Force $work | Out-Null; & $bin --api | Out-File -Encoding utf8 "$work\api-before.txt"; Copy-Item $bin "$ap\paint\build\ArmorPaint-287e63f4.exe"; (Get-Item "$work\api-before.txt").Length
```

Expected: a non-empty `api-before.txt`, and the backup exists.

- [ ] **Step 3: Build the integration branch.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git status --porcelain --untracked-files=no; git switch -c integration/ap-mcp origin/main; git merge --no-ff --no-edit fix/mesh-accumulator-zero-init; git merge --no-ff --no-edit fix/import-mesh-texa-zero-init; git merge --no-ff --no-edit fix/mesh-delete-object-mask-remap; git merge --no-ff --no-edit feat/script-object-merge; git log --oneline --graph -14; Pop-Location
```

Expected: an empty status, four merge commits, and no conflicts (the four changes touch disjoint files). On a conflict, `git merge --abort` and stop and report.

- [ ] **Step 4: Regenerate and compile.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint\paint; & ..\base\make.bat; $LASTEXITCODE; Pop-Location
& "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe" C:\Projects-local\z-Git\ArmorPaint\paint\build\ArmorPaint.vcxproj /p:Configuration=Release /p:Platform=x64 /m; $LASTEXITCODE
Copy-Item C:\Projects-local\z-Git\ArmorPaint\paint\build\x64\Release\ArmorPaint.exe C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe -Force
git -C C:\Projects-local\z-Git\ArmorPaint status --porcelain --untracked-files=no
```

Expected: both exit codes are 0, and the final `status` is empty. If `make.bat` modified tracked files, stop and report: don't commit or discard them in the checkout. A compile error means a change is wrong; stop and report the error and which branch's file it is in.

- [ ] **Step 5: Diff the API.**

```powershell
$work = "$env:TEMP\ap-mcp-phase7"; & C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe --api | Out-File -Encoding utf8 "$work\api-after.txt"; Compare-Object (Get-Content "$work\api-before.txt") (Get-Content "$work\api-after.txt")
```

Expected: **exactly one** difference, a `=>` line declaring `script_object_merge(...)`. Upstream's 4 new commits touch no `paint/sources` file, so nothing else may change. Any other added or removed line is a rename that could silently break a tool: stop and report it (memory: "diff `--api` after every rebuild").

- [ ] **Step 6: Confirm `object_mask` is readable** (Task 11 depends on it).

```powershell
& C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe C:\Projects-local\Tool-ArmorPaintMCP\tests\fixtures\phase6\objects3.arm --api | Select-String -SimpleMatch '"object_mask"' | Select-Object -First 1
```

Expected: one match. Record yes or no in the report. If there's no match, Task 11 is skipped and says so.

- [ ] **Step 7: Write the manifest and run `--check`** (worktree env, so the Task 1-2 code is used).

```powershell
Push-Location C:\Projects-local\Tool-ArmorPaintMCP\.claude\worktrees\phase7; $env:PYTHONPATH = "$PWD\src"; $env:AP_DOTENV = 'C:\Projects-local\Tool-ArmorPaintMCP\.env'; $py = 'C:\Projects-local\Tool-ArmorPaintMCP\.venv\Scripts\python.exe'; & $py -m armorpaint_mcp.build_manifest --checkout C:\Projects-local\z-Git\ArmorPaint --binary C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe; & $py -m armorpaint_mcp.server --check; $LASTEXITCODE; Pop-Location
```

Expected:
- The writer prints `[IN ]` for all four dependencies (`how`: `ancestor`) and `wrote ...ap-mcp-build.json (integration/ap-mcp @ <sha>)`.
- `--check` prints every row `[PASS]`, including `minic API` and all four `upstream dependency` rows, and exits 0. If Task 3 hasn't landed yet, `minic API` still passes; it just doesn't list `script_object_merge`.

- [ ] **Step 8: Sanity run on the new binary** (serially; the first call may hit the cold-start case, so rerun that test once). Shell variables don't survive between tool calls, so this starts with the same env prefix as Step 7.

```powershell
Push-Location C:\Projects-local\Tool-ArmorPaintMCP\.claude\worktrees\phase7; $env:PYTHONPATH = "$PWD\src"; $env:AP_DOTENV = 'C:\Projects-local\Tool-ArmorPaintMCP\.env'; $py = 'C:\Projects-local\Tool-ArmorPaintMCP\.venv\Scripts\python.exe'; & $py -m pytest -q -m integration tests/test_run_script_integration.py tests/test_merge_mesh_geometry_integration.py tests/test_smooth_mesh_integration.py tests/test_bevel_mesh_integration.py; Pop-Location
```

Expected: all pass. The smooth and bevel tests re-prove that #2148 is still in the build.

- [ ] **Step 9: Report** `INTEGRATION_HEAD` (`git -C C:\Projects-local\z-Git\ArmorPaint rev-parse HEAD`), `UPSTREAM_BASE`, the Step 5 diff line, the Step 6 answer, and the `--check` output. There's no commit in this repo.

Rollback: if Steps 4-8 can't be made green, don't improvise. Report it. Restoring the old build means switching back to `fix/mesh-accumulator-zero-init` and re-running make + MSBuild (the backup exe alone doesn't match the regenerated `data\`), and that is a checkout change that needs its own go.

---

### Task 9: `merge_mesh_pair` integration tests (item 9's gate)

**Files:**
- Create: `tests/test_merge_mesh_pair_integration.py`

**Interfaces:**
- Consumes: `merge_mesh_pair` (Task 3); `AP_BINARY` with `script_object_merge` (Task 8); `tests._mesh_edit_test_helpers.export_obj`; `uv_analysis.parse_obj`/`groups_by_name`/`group_signature`; `replace.object_names`/`local_transform`/`parent_name`/`material_override_name`; fixtures `phase6/objects3_v2.arm` (Tessellated at identity; Cone transformed with material `MatB`; Torus) and `phase6/objects3_v4_parented.arm` (v2 with Cone under Tessellated).

- [ ] **Step 1: Write the tests.** Create `tests/test_merge_mesh_pair_integration.py`:

```python
"""Real ArmorPaint required, on an AP_BINARY with script_object_merge (Phase 7
Task 8). Item 9's gate (docs/PLAN.md 7.1):
    .venv\\Scripts\\python.exe -m pytest tests/test_merge_mesh_pair_integration.py -v -m integration

Vertex counts come from script_export_mesh, which merges vertices sharing a
quantized position within one object (io/export_obj.c). The kept object in
the gate test is Tessellated, at identity, and the merged Cone is moved and
scaled (objects3_v2), so no vertex of one can land on a vertex of the other.
If the vertex sum ever fails while the face sum holds, check for exactly
that collapse before touching the assertion."""
import os

import pytest

from armorpaint_mcp import replace as rp
from armorpaint_mcp import uv_analysis as ua
from armorpaint_mcp.catalog import extract_project_state
from armorpaint_mcp.config import load_config
from armorpaint_mcp.runner import run_api
from armorpaint_mcp.server import inspect_project, merge_mesh_pair
from tests._mesh_edit_test_helpers import export_obj

PHASE6 = os.path.join(os.path.dirname(__file__), "fixtures", "phase6")
V2 = os.path.join(PHASE6, "objects3_v2.arm")
V4 = os.path.join(PHASE6, "objects3_v4_parented.arm")


def _names(project):
    result = inspect_project(project)
    assert result["ok"], result["error"]
    return sorted(o["name"] for o in result["objects"])


def _state(project):
    return extract_project_state(run_api(load_config().binary, project).text)


def _groups(project, obj_path):
    obj = ua.parse_obj(export_obj(project, str(obj_path)))
    return obj, ua.groups_by_name(obj)


def _vertices(group):
    return len({i for tri in group.tri_v for i in tri})


@pytest.mark.integration
def test_merge_pair_merges_exactly_two_objects_and_leaves_the_third_alone(tmp_path):
    before_obj, before = _groups(V2, tmp_path / "before.obj")
    out = tmp_path / "merged.arm"

    result = merge_mesh_pair(project=V2, keep="Tessellated", merge="Cone",
                             output_project=str(out))

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    # N objects become N-1; keep's name survives, merge's is gone
    assert _names(str(out)) == ["Tessellated", "Torus"]
    after_obj, after = _groups(str(out), tmp_path / "after.obj")
    # the merged object's geometry is the sum of the two
    assert after["Tessellated"].faces == before["Tessellated"].faces + before["Cone"].faces
    assert _vertices(after["Tessellated"]) == (_vertices(before["Tessellated"])
                                               + _vertices(before["Cone"]))
    # a third object is untouched
    assert (ua.group_signature(after_obj, after["Torus"])
            == ua.group_signature(before_obj, before["Torus"]))


@pytest.mark.integration
def test_the_kept_object_keeps_its_transform_and_material(tmp_path):
    before = _state(V2)
    out = tmp_path / "merged.arm"

    result = merge_mesh_pair(project=V2, keep="Cone", merge="Torus", output_project=str(out))

    assert result["ok"] is True, result["error"]
    assert _names(str(out)) == ["Cone", "Tessellated"]
    after = _state(str(out))
    assert rp.local_transform(after, "Cone") == pytest.approx(
        rp.local_transform(before, "Cone"), abs=1e-5)
    assert rp.material_override_name(after, "Cone") == "MatB"
    assert len(after["layer_datas"]) == len(before["layer_datas"])


@pytest.mark.integration
def test_merging_a_parent_into_its_child_keeps_the_child_in_place(tmp_path):
    """Review Focus 3. util_mesh_merge_geometry_down re-parents the kept
    child to the merged parent's parent (none), keeping its world pose.
    Tessellated's world is identity in this fixture (tests/fixtures/phase6/
    README.md), so Cone's local transform before equals its world transform,
    and it must equal its (now root) local transform after."""
    before_state = _state(V4)
    _, before = _groups(V4, tmp_path / "before.obj")
    out = tmp_path / "merged.arm"

    result = merge_mesh_pair(project=V4, keep="Cone", merge="Tessellated",
                             output_project=str(out))

    assert result["ok"] is True, result["error"]
    assert _names(str(out)) == ["Cone", "Torus"]
    after_state = _state(str(out))
    assert rp.parent_name(after_state, "Cone") is None
    assert rp.local_transform(after_state, "Cone") == pytest.approx(
        rp.local_transform(before_state, "Cone"), abs=1e-4)
    _, after = _groups(str(out), tmp_path / "after.obj")
    assert after["Cone"].faces == before["Cone"].faces + before["Tessellated"].faces


@pytest.mark.integration
def test_an_unknown_name_fails_and_writes_nothing(tmp_path):
    out = tmp_path / "merged.arm"

    result = merge_mesh_pair(project=V2, keep="Tessellated", merge="NoSuchObject",
                             output_project=str(out))

    assert result["ok"] is False and "NoSuchObject" in result["error"]
    assert not out.exists()
```

- [ ] **Step 2: Run** (serially; after a rebuild the first call may cold-start, so rerun it once per Global Constraints).

Run: `& $py -m pytest -q -m integration tests/test_merge_mesh_pair_integration.py`
Expected: 4 passed.

Triage. Fix this project's Python, never the tests. The transform, material and parent-into-child assertions exercise **upstream** behaviour (`util_mesh_merge_geometry_down`, its `world`/`world_unpack` handling). If one of them fails for a reason other than the cases below, stop and report it as a finding: don't loosen the assertion, and never touch the ArmorPaint checkout outside a gated task. The only fixes allowed here are:
- If `merge_did_nothing` appears, the build's `script_object_merge` refused the pair. Check `--check` and the Task 8 diff.
- If a minic parse error points at the `!= NULL` line, rewrite that check in `merge_pair.build_merge_lines` as `object_t *left = script_get_object(<merge>); if (left == NULL) { } else { console_log(...); return; }`, rerun Task 3's unit tests, then this.
- If only the vertex sum fails, see the module docstring.
- If the material assertion fails, remove "and material" from `merge_mesh_pair`'s docstring claim and report it. Don't drop the assertion silently.

- [ ] **Step 3: Commit**

```powershell
git add tests/test_merge_mesh_pair_integration.py src/armorpaint_mcp/merge_pair.py src/armorpaint_mcp/server.py tests/test_merge_pair.py; git commit -m "test: merge_mesh_pair integration gate (N-1 objects, name, vertex/face sums, third object untouched)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: UV-less non-OBJ is rejected deterministically (texa gate)

**Files:**
- Create: `tests/test_phase7_texa_integration.py`

**Interfaces:**
- Consumes: `dependencies.load_manifest` (Task 1); `repl_grid5_nouv.glb` (Task 4); an `AP_BINARY` whose manifest shows `import-mesh-texa-zero-init` included (Task 8); `replace_mesh`, `run_script`; `tests._mesh_edit_test_helpers.export_obj`.

- [ ] **Step 1: Write the tests.** A lucky zero page makes an unfixed binary pass these tests too, so each test first **requires** the manifest to list the texa fix. It fails (it doesn't skip) when the fix isn't there, so a green run always means "on a fixed build".

```python
"""Real ArmorPaint required, on an AP_BINARY with Phase 7 change 1 (texa
zero-init). docs/PLAN.md Phase 7 gate: "a UV-less non-OBJ replacement is
rejected deterministically once the texa fix is in AP_BINARY".
    .venv\\Scripts\\python.exe -m pytest tests/test_phase7_texa_integration.py -v -m integration

Without the fix these UVs are uninitialized heap memory, which often reads
as zero anyway, so passing on its own proves nothing about the fix. Each
test therefore first requires the build manifest to list the fix."""
import os

import pytest

from armorpaint_mcp import uv_analysis as ua
from armorpaint_mcp.config import load_config
from armorpaint_mcp.dependencies import load_manifest
from armorpaint_mcp.server import replace_mesh, run_script
from tests._mesh_edit_test_helpers import export_obj

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
NOUV_GLB = os.path.join(FIXTURES, "phase7", "repl_grid5_nouv.glb")
OBJECTS3 = os.path.join(FIXTURES, "phase6", "objects3.arm")
SAMPLE = os.path.join(FIXTURES, "sample_project.arm")


def _require_texa_fix():
    manifest, error = load_manifest(load_config().binary)
    assert error is None, error
    status = manifest["dependencies"].get("import-mesh-texa-zero-init")
    assert status and status["included"], f"AP_BINARY lacks the texa fix: {status}"


@pytest.mark.integration
def test_a_uv_less_glb_imports_with_every_uv_at_zero(tmp_path):
    _require_texa_fix()
    glb = os.path.abspath(NOUV_GLB).replace("\\", "\\\\")
    saved = tmp_path / "appended.arm"
    script = ("void main() {\n"
              f'\tscript_append_mesh("{glb}");\n'
              f'\tproject_filepath_set("{str(saved).replace(os.sep, "/")}");\n'
              "\tproject_save(0);\n}\n")

    result = run_script(project=SAMPLE, script=script)

    assert result["ok"], result["error"]
    obj = ua.parse_obj(export_obj(str(saved), str(tmp_path / "export.obj")))
    group = ua.groups_by_name(obj)["ReplGridNoUV"]
    assert group.tri_vt, "the appended object has no UV'd triangles in the export"
    assert {obj.vt[t] for tri in group.tri_vt for t in tri} == {(0.0, 0.0)}


@pytest.mark.integration
def test_a_uv_less_glb_replacement_is_rejected_every_time(tmp_path):
    _require_texa_fix()
    for run in range(3):
        out = tmp_path / f"out{run}.arm"

        result = replace_mesh(project=OBJECTS3, old_object="Cone", new_mesh=NOUV_GLB,
                              mode="swap", output_project=str(out))

        assert result["ok"] is False, f"run {run}: accepted a UV-less replacement"
        assert "the replacement's UVs are invalid" in result["error"], result["error"]
        assert "UV-degenerate triangles cover" in result["error"], result["error"]
        assert not out.exists()
```

- [ ] **Step 2: Run** (serially): `& $py -m pytest -q -m integration tests/test_phase7_texa_integration.py` → 2 passed. The second test makes up to 15 ArmorPaint launches, about a minute.

- [ ] **Step 3: Commit**

```powershell
git add tests/test_phase7_texa_integration.py; git commit -m "test: UV-less GLB replacement is rejected deterministically on the texa-fixed build" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Object-mask remap evidence (optional; host-made fixture; not a gate item)

**Files:**
- Create: `tests/test_phase7_object_mask_integration.py`
- Create (only if Grayson makes it): `tests/fixtures/phase7/objects3_masked.arm`

**Interfaces:**
- Consumes: Task 8's answer to "does `object_mask` appear in `--api` JSON" (if no, skip this task and say so in the report); `replace_mesh`, `merge_mesh_pair`; `replace.object_names` (`mesh_datas` order is `paint_objects` order, the order masks index).

- [ ] **Step 1: HOST (Grayson, optional, non-blocking):** controller asks Grayson whether he wants to make the masked fixture. It needs the GUI because minic can't set a mask (there's no `slot_layer_t` registration). The steps:
  1. Open `C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ArmorPaint.exe`.
  2. Open `C:\Projects-local\Tool-ArmorPaintMCP\.claude\worktrees\phase7\tests\fixtures\phase6\objects3.arm`.
  3. In the Layers panel, set the layer's object mask to **Torus**, and only Torus.
  4. Save As `C:\Projects-local\Tool-ArmorPaintMCP\.claude\worktrees\phase7\tests\fixtures\phase7\objects3_masked.arm`.

  If he declines, commit the test file anyway: it skips cleanly, and Task 13 uses the "no fixture" Testing text for PR 2.

- [ ] **Step 2: Write the tests.**

```python
"""Real ArmorPaint + an optional hand-made fixture (Phase 7 plan, Task 11).
Phase 7 change 2: a layer masked to one object keeps pointing at that object
when another object is deleted. replace_mesh deletes the old object through
script_object_remove -> tab_meshes_draw_context_menu_delete. Not a Phase 7
gate item (docs/PLAN.md: "not headless-testable" -- only SETTING a mask is;
reading it back through --api works). Skips when the fixture is absent.
    .venv\\Scripts\\python.exe -m pytest tests/test_phase7_object_mask_integration.py -v -m integration
"""
import os

import pytest

from armorpaint_mcp import replace as rp
from armorpaint_mcp.catalog import extract_project_state
from armorpaint_mcp.config import load_config
from armorpaint_mcp.runner import run_api
from armorpaint_mcp.server import merge_mesh_pair, replace_mesh

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
MASKED = os.path.join(FIXTURES, "phase7", "objects3_masked.arm")
REPL = os.path.join(FIXTURES, "phase6", "repl_grid5.obj")


def _mask_owners(project):
    """Per layer: the name of the object its mask points at, or None (0 = all)."""
    state = extract_project_state(run_api(load_config().binary, project).text)
    names = rp.object_names(state)
    return [None if not l.get("object_mask") else names[l["object_mask"] - 1]
            for l in state["layer_datas"]]


@pytest.fixture
def masked():
    if not os.path.isfile(MASKED):
        pytest.skip("tests/fixtures/phase7/objects3_masked.arm not made (optional, Task 11)")
    owners = _mask_owners(MASKED)
    assert "Torus" in owners and set(owners) <= {None, "Torus"}, owners
    return MASKED


@pytest.mark.integration
def test_replace_leaves_a_torus_mask_on_the_torus(masked, tmp_path):
    before = _mask_owners(masked)
    out = tmp_path / "replaced.arm"

    result = replace_mesh(project=masked, old_object="Cone", new_mesh=REPL, mode="swap",
                          output_project=str(out))

    assert result["ok"] is True, result["error"]
    assert _mask_owners(str(out)) == before


@pytest.mark.integration
def test_merge_pair_leaves_a_torus_mask_on_the_torus(masked, tmp_path):
    before = _mask_owners(masked)
    out = tmp_path / "merged.arm"

    result = merge_mesh_pair(project=masked, keep="Tessellated", merge="Cone",
                             output_project=str(out))

    assert result["ok"] is True, result["error"]
    assert _mask_owners(str(out)) == before
```

- [ ] **Step 3: Run** `& $py -m pytest -q -m integration tests/test_phase7_object_mask_integration.py`. With the fixture, expect 2 passed. Without it, expect 2 skipped. Record which in the report (Task 13 picks PR 2's Testing text from it).

- [ ] **Step 4: Commit**

```powershell
git add tests/test_phase7_object_mask_integration.py tests/fixtures/phase7; git commit -m "test: layer object masks follow their object through replace_mesh and merge_mesh_pair (optional fixture)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Full regression, docs, Phase 7 gate record

**Files:**
- Modify: `README.md`, `CLAUDE.md` (project), `STATUS.md`, `docs/PLAN.md`, `ROADMAP.md`, `HANDOFF.md`

**Interfaces:**
- Consumes: Task 8's `INTEGRATION_HEAD`/`UPSTREAM_BASE`/`--check` output; Tasks 9-11's results.

- [ ] **Step 1: Full regression** (serially, same binary):
  - `& $py -m pytest -q` → **263 passed**, 46 deselected (38 + 4 from Task 9 + 2 from Task 10 + 2 from Task 11, which are collected whether or not the fixture exists). Record the numbers.
  - `& $py -m pytest -q -m integration` → all pass (Task 11's 2 may skip). Record passed and skipped.
  - `pwsh smoke/smoke.ps1` → `16 passed, 0 failed`, exit 0.
  - `& $py -m armorpaint_mcp.server --check` → exit 0, all rows `[PASS]`, including the four `upstream dependency` rows. Paste the output into STATUS.md.

- [ ] **Step 2: README.md.**
  - Add `merge_mesh_pair` to the tool list: one paragraph paraphrasing its docstring (merge `merge` into `keep`, everything else untouched, keep's name/transform/parent/material kept, needs `script_object_merge`).
  - In `merge_mesh_geometry`'s entry, point to `merge_mesh_pair` for pairs.
  - Replace the "Known upstream bug … build that branch" sub-bullet with a **"Building AP_BINARY"** subsection covering, in order:
    1. `AP_BINARY` is built from the checkout's local `integration/ap-mcp` branch = upstream `main` + a `--no-ff` merge of each open dependency branch (list the four with their PR numbers or "not yet opened").
    2. The build commands: `..\base\make.bat` from `paint\`, then the VS2022 MSBuild line and the copy into `paint\build\out\`, copied from Global Constraints.
    3. `& $py -m armorpaint_mcp.build_manifest --checkout <checkout> --binary <exe>` after every build.
    4. `ap-mcp --check` shows one row per upstream dependency and fails on a missing or stale manifest.
    5. When a PR merges upstream, rebuild the integration branch without it and set the registry entry's `upstream_commit` if the merge changed the SHA.

- [ ] **Step 3: CLAUDE.md (project).**
  - In "Environment (this machine)", rewrite the ArmorPaint checkout paragraph: the checkout is on `integration/ap-mcp` @ `<INTEGRATION_HEAD>` = upstream `main` `<UPSTREAM_BASE>` + #2148's branch + the three Phase 7 branches, and `AP_BINARY` was built from it on `<date>`, with `ap-mcp-build.json` next to it. Keep the sentence "Changing this checkout counts as changing something outside this project: ask Grayson first."
  - In the Commands table, add a row `| Build manifest | python -m armorpaint_mcp.build_manifest --checkout <ArmorPaint> --binary <AP_BINARY> |`.

- [ ] **Step 4: STATUS.md.**
  - Phase Gates table: add row `| 7 | ArmorPaint C changes (texa zero-init, object-mask remap on delete, script_object_merge) on an integration build + --check dependency rows; merge_mesh_pair | ✅ <date> | <pytest counts>; <integration counts>; smoke 16/16; --check green (4 upstream-dependency rows); --api diff = +script_object_merge only; merge gate tests 4/4; texa gate 2/2; object-mask tests <2 passed | 2 skipped (no fixture)> |`.
  - Add a "Current Phase Detail (Phase 7)" table: one ✅ row per new or changed file with its test evidence.
  - Update the "Known risks" and Known Issues entries:
    - "A UV-less non-OBJ replacement is caught probabilistically" → closed on the integration build (Task 10).
    - "Object-mask remap on delete" → fixed in the integration build, with the Task 11 evidence or "no fixture".
  - Add an "Open upstream PRs" line listing #2148 and the three branches (PR numbers filled in by Tasks 14-16).
  - Update the "Open phase" line: Phase 7 gate green.

- [ ] **Step 5: docs/PLAN.md, ROADMAP.md, HANDOFF.md.**
  - PLAN.md:
    - change the heading to `## Phase 7 (APPROVED 2026-09-27, ✅ GATE GREEN <date>)`;
    - add a short "Done" note under it pointing at STATUS.md;
    - correct change 2's citation to `ui/tab_meshes.c:443-476` (the delete path; `:128-134` is the reorder remap);
    - under "Further upstream candidates", add: "the delete path doesn't splice `g_project->atlas_objects`, which `util_mesh_merge_geometry_down` does (`util/util_mesh.c:626-628`)".
  - ROADMAP.md: item 9 `✅ shipped (Phase 7, merge_mesh_pair)`.
  - HANDOFF.md: a new baton with the phase state, the integration-build facts, which PRs are still to open (Tasks 14-16), and the next step.

- [ ] **Step 6: Commit**

```powershell
git add README.md CLAUDE.md STATUS.md docs/PLAN.md ROADMAP.md HANDOFF.md; git commit -m "docs: record Phase 7 gate (integration build, --check dependency rows, merge_mesh_pair)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

After this task the branch is ready for superpowers:finishing-a-development-branch. Tasks 14-16 can run before or after the merge to main. Once merged, retire `.claude\worktrees\phase7` per root rule 10: `& C:\Projects-local\_agent-commons\tools\Clear-MergedWorktrees.ps1 -Repo C:\Projects-local\Tool-ArmorPaintMCP -Only phase7 -Execute`.

---

### Task 13: Upstream PR texts, for Grayson to approve

**Files:**
- Create: `docs/upstream/2026-09-27-pr-texa-zero-init.md`, `docs/upstream/2026-09-27-pr-object-mask-remap.md`, `docs/upstream/2026-09-27-pr-script-object-merge.md`

**Interfaces:**
- Consumes: `UPSTREAM_BASE` (Task 8 manifest's `upstream_base`), Task 11's outcome.
- Produces: three body files (first line `Title: <title>`, then a blank line, then the body). Tasks 14-16 pass the body to `gh pr create --body-file` without the title line.

Shape, per the upstream-precedent memory note and #2148's body: problem → cause → fix with the diff inline → **Compatibility** → **Testing** with concrete evidence. Keep each small and single-purpose.

- [ ] **Step 1: Write `docs/upstream/2026-09-27-pr-texa-zero-init.md`:**

````markdown
Title: Zero-init texcoords for meshes imported without UVs

When an imported mesh has no texture coordinates, `import_mesh_make_mesh` and `import_mesh_add_mesh` create its `texa` array with `i16_array_create`, which doesn't zero the buffer (`i16_array_resize` is a plain `realloc`). The mesh's UVs are then whatever was already in that heap memory, so the same file can import with different UVs from run to run. Same class of bug as #2148.

`import_mesh_make_mesh` usually hides it, because `import_mesh_needs_unwrap` unwraps the mesh afterwards. `import_mesh_add_mesh` (appending, and every mesh after the first in a multi-mesh file) doesn't unwrap, so the garbage UVs stay.

**Fix:** zero the buffer right after creating it, in both functions. A mesh without UVs then imports with every UV at (0, 0), every time.

```c
if (mesh->texa == NULL) {
	i32 verts  = mesh->posa->length / 4;
	mesh->texa = i16_array_create(verts * 2);
	memset(mesh->texa->buffer, 0, mesh->texa->length * sizeof(i16));
}
```

**Compatibility:** no API change. Only meshes without UVs are affected: their UVs go from undefined to (0, 0). 2 added lines, one file.

**Testing:** appended a glTF that has positions and indices but no `TEXCOORD_0` via `script_append_mesh` in a headless `--script` run, then exported it with `script_export_mesh`: every exported UV is (0, 0). A check that rejects zero-area UV layouts rejected the same file on 3 of 3 repeated runs. Tested on Windows x64 in an integration build of current `main` ({UPSTREAM_BASE}) that also carries #2148 and two other small fixes in unrelated files; this branch itself is a single commit on `main`. Formatting checked against the repo's own `.clang-format`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
````

- [ ] **Step 2: Write `docs/upstream/2026-09-27-pr-object-mask-remap.md`.** Use Testing text **A** if Task 11 passed with the fixture, **B** if it skipped:

````markdown
Title: Remap layer object masks when deleting a mesh

A layer's `object_mask` stores its object's index in `paint_objects` plus one (0 means all objects). Deleting a mesh (`tab_meshes_draw_context_menu_delete`, also reached from `script_object_remove`) removes it from `paint_objects` but leaves every mask unchanged. Masks that pointed past the deleted object now point one object further along, and a mask on the deleted object points at whatever took its slot. `layer_filter` has the same problem. The `tab_meshes_sort_hierarchy()` call that follows snapshots its "old order" after the removal, so it can't see the shift.

`util_mesh_merge_geometry_down` already remaps masks this way when it removes the merged object; the delete path just doesn't.

**Fix:** right after `array_remove`, shift masks above the deleted slot down by one. A mask on the deleted object becomes 0 (all objects), the same value `util_mesh_merge_geometry` resets masks to. If you'd rather handle that case differently, happy to change it.

```c
i32 deleted_mask = tab_meshes_delete_index + 1;
if (g_project->_->layers != NULL) {
	for (i32 i = 0; i < g_project->_->layers->length; ++i) {
		slot_layer_t *l = g_project->_->layers->buffer[i];
		l->object_mask  = l->object_mask == deleted_mask ? 0 : l->object_mask > deleted_mask ? l->object_mask - 1 : l->object_mask;
	}
}
g_context->layer_filter = g_context->layer_filter == deleted_mask  ? 0
                          : g_context->layer_filter > deleted_mask ? g_context->layer_filter - 1
                                                                   : g_context->layer_filter;
```

**Compatibility:** no API change. Only projects with a masked layer and more than one mesh behave differently: the mask keeps following its object. 11 added lines, one file.

**Testing:** TESTING_TEXT

🤖 Generated with [Claude Code](https://claude.com/claude-code)
````

Replace `TESTING_TEXT` with exactly one of:
- **A:** `On a 3-object project (default mesh, cone, torus) with a layer masked to the torus, removing the cone via script_object_remove in a headless --script run (and saving) leaves the mask on the torus, read back from the saved project with --api. Tested on Windows x64 in an integration build of current main ({UPSTREAM_BASE}) that also carries #2148 and two other small fixes in unrelated files; this branch itself is a single commit on main. Formatting checked against the repo's own .clang-format.` Wrap the identifiers in backticks when pasting.
- **B:** `A layer's mask can't be set from a headless script, so the masked case was checked by reading the change against util_mesh_merge_geometry_down's remap; the headless suite that deletes meshes through script_object_remove passes unchanged. Built on Windows x64 in an integration build of current main ({UPSTREAM_BASE}) that also carries #2148 and two other small fixes in unrelated files; this branch itself is a single commit on main. Formatting checked against the repo's own .clang-format.` Wrap the identifiers in backticks when pasting.

- [ ] **Step 3: Write `docs/upstream/2026-09-27-pr-script-object-merge.md`:**

````markdown
Title: Add script_object_merge

Adds `script_object_merge(object_t *o, object_t *into)`, which merges one mesh object into another: the scripted form of the Meshes tab's Merge Down. It follows `script_object_remove`'s shape. It takes `object_t*`, checks `ext_type`, wraps the GPU state, and calls the existing `util_mesh_merge_geometry_down(into->ext, o->ext)`. That function already checks that both are paint objects and distinct, moves `o`'s children to `into`, and remaps layer masks.

Scripts can merge every object (`util_mesh_merge_geometry`) but not a chosen pair, since `util_mesh_merge_geometry_down` takes `mesh_object_t*`.

```c
void script_object_merge(object_t *o, object_t *into) {
	if (o == NULL || into == NULL || o == into) {
		return;
	}
	if (!string_equals(o->ext_type, "mesh_object_t") || !string_equals(into->ext_type, "mesh_object_t")) {
		return;
	}

	gpu_texture_t *current;
	bool           in_use;
	script_gpu_begin(&current, &in_use);
	util_mesh_merge_geometry_down(into->ext, o->ext);
	script_gpu_end(current, in_use);

	tab_meshes_reset_preview_map();
	g_context->ddirty = 2;
	if (ui_base_hwnds != NULL && ui_base_hwnds->length > TAB_AREA_SIDEBAR0) {
		ui_base_hwnds->buffer[TAB_AREA_SIDEBAR0]->redraws = 2;
	}
}
```

plus `X2(script_object_merge, "v(p:object_t o,p:object_t into)", v, p, p)` in `minic_api_list.h` and the declaration in `functions.h`.

**Compatibility:** purely additive: one new script function, no change to existing ones. 23 added lines, 3 files.

**Testing:** headless `--script` runs on a 3-object project (default mesh, a transformed cone, a torus):
- Merging the cone into the default mesh leaves 2 objects, keeps the default mesh's name, and gives it the sum of both objects' faces and vertices. The torus exports the same geometry as before.
- Merging the torus into the transformed cone keeps the cone's transform and material.
- Merging a parent into its own child leaves the child at the root in the same place.

`--api` lists `script_object_merge`, and nothing else in it changed. Tested on Windows x64 in an integration build of current `main` ({UPSTREAM_BASE}) that also carries #2148 and two other small fixes in unrelated files; this branch itself is a single commit on `main`. Formatting checked against the repo's own `.clang-format`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
````

- [ ] **Step 4: Substitute the base SHA and verify.**

```powershell
$m = Get-Content C:\Projects-local\z-Git\ArmorPaint\paint\build\out\ap-mcp-build.json -Raw | ConvertFrom-Json; $base = $m.upstream_base.Substring(0, 8); Get-ChildItem docs\upstream\2026-09-27-pr-*.md | ForEach-Object { [IO.File]::WriteAllText($_.FullName, [IO.File]::ReadAllText($_.FullName).Replace('{UPSTREAM_BASE}', $base)) }; Select-String -Encoding UTF8 -Path docs\upstream\*.md -Pattern '\{UPSTREAM_BASE\}|TESTING_TEXT'
```

(Use `[IO.File]` rather than `Get-Content`/`Set-Content`. PowerShell 5.1 reads a BOM-less file as ANSI, which garbles the 🤖 line, and its `-Encoding utf8` writes a BOM, which would end up at the start of the PR body.)

Expected: the last command prints nothing. Also confirm each "N added lines" claim against the checkout: `git -C C:\Projects-local\z-Git\ArmorPaint diff --shortstat origin/main...<branch>` for each branch. Expect 2, 11 and 23 insertions. Fix the text if one differs.

- [ ] **Step 5: Commit**

```powershell
git add docs/upstream; git commit -m "docs: upstream PR texts for the three Phase 7 ArmorPaint changes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Then the controller sends Grayson the three files (`SendUserFile`) and asks for the Task 14-16 go-aheads.

---

### Task 14: Upstream PR — texa zero-init

**Files:**
- Modify: `src/armorpaint_mcp/dependencies.py` (the `import-mesh-texa-zero-init` entry: `pr=`), `STATUS.md` (open PRs line), `README.md` (the Building AP_BINARY list)

**Interfaces:**
- Consumes: branch `fix/import-mesh-texa-zero-init` (Task 5), `docs/upstream/2026-09-27-pr-texa-zero-init.md` (Task 13).
- Produces: armory3d/armorpaint PR number `$pr` in the registry, so the `--check` row name becomes `upstream dependency import-mesh-texa-zero-init (#<n>)`.

- [ ] **Step 1: HUMAN GATE:** controller confirms Grayson's go for: "push local branch `fix/import-mesh-texa-zero-init` from `C:\Projects-local\z-Git\ArmorPaint` to remote `gc-fork` (`git@github.com:graysonchalmers/armorpaint.git`)" before dispatch.

- [ ] **Step 2: Push and verify.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git push gc-fork fix/import-mesh-texa-zero-init; git rev-parse fix/import-mesh-texa-zero-init; git ls-remote gc-fork refs/heads/fix/import-mesh-texa-zero-init; Pop-Location
```

Expected: the two SHAs match. If SSH auth fails, stop and report; don't try other credentials.

- [ ] **Step 3: HUMAN GATE:** controller confirms Grayson's go for: "open a PR on armory3d/armorpaint, base `main`, head `graysonchalmers:fix/import-mesh-texa-zero-init`, title `Zero-init texcoords for meshes imported without UVs`, body = `docs/upstream/2026-09-27-pr-texa-zero-init.md` minus its Title line (which he has read)" before running Step 4.

- [ ] **Step 4: Open the PR.**

```powershell
$src = 'C:\Projects-local\Tool-ArmorPaintMCP\.claude\worktrees\phase7\docs\upstream\2026-09-27-pr-texa-zero-init.md'; $body = "$env:TEMP\ap-mcp-phase7\pr-texa-body.md"; New-Item -ItemType Directory -Force "$env:TEMP\ap-mcp-phase7" | Out-Null; [IO.File]::WriteAllText($body, (([IO.File]::ReadAllLines($src) | Select-Object -Skip 2) -join "`n")); $url = gh pr create -R armory3d/armorpaint --base main --head graysonchalmers:fix/import-mesh-texa-zero-init --title "Zero-init texcoords for meshes imported without UVs" --body-file $body; $url; $pr = [int]($url.Trim() -split '/')[-1]; $pr
```

Expected: a `https://github.com/armory3d/armorpaint/pull/<n>` URL, and `$pr` = `<n>`.

- [ ] **Step 5: Record it.** In `dependencies.py`, change the entry's line `"probably rejects it"),` to `"probably rejects it", pr=<n>),`, with `<n>` = `$pr`. Add `#<n>` to STATUS.md's open-PRs line and README's dependency list. Run `& $py -m pytest -q` (all pass) and `& $py -m armorpaint_mcp.server --check` (the row now reads `(#<n>)`, still PASS).

- [ ] **Step 6: Commit** (type the PR number for `<n>`: shell variables such as `$pr` don't survive between tool calls)

```powershell
git add src/armorpaint_mcp/dependencies.py STATUS.md README.md; git commit -m "docs: texa zero-init opened upstream as armory3d/armorpaint#<n>" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Upstream PR — object-mask remap on delete

**Files:**
- Modify: `src/armorpaint_mcp/dependencies.py` (the `delete-object-mask-remap` entry), `STATUS.md`, `README.md`

**Interfaces:**
- Consumes: branch `fix/mesh-delete-object-mask-remap` (Task 6), `docs/upstream/2026-09-27-pr-object-mask-remap.md` (Task 13).
- Produces: `pr=<n>` on the `delete-object-mask-remap` registry entry.

- [ ] **Step 1: HUMAN GATE:** controller confirms Grayson's go for: "push local branch `fix/mesh-delete-object-mask-remap` from `C:\Projects-local\z-Git\ArmorPaint` to remote `gc-fork`" before dispatch.

- [ ] **Step 2: Push and verify.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git push gc-fork fix/mesh-delete-object-mask-remap; git rev-parse fix/mesh-delete-object-mask-remap; git ls-remote gc-fork refs/heads/fix/mesh-delete-object-mask-remap; Pop-Location
```

Expected: the two SHAs match.

- [ ] **Step 3: HUMAN GATE:** controller confirms Grayson's go for: "open a PR on armory3d/armorpaint, base `main`, head `graysonchalmers:fix/mesh-delete-object-mask-remap`, title `Remap layer object masks when deleting a mesh`, body = `docs/upstream/2026-09-27-pr-object-mask-remap.md` minus its Title line" before running Step 4.

- [ ] **Step 4: Open the PR.**

```powershell
$src = 'C:\Projects-local\Tool-ArmorPaintMCP\.claude\worktrees\phase7\docs\upstream\2026-09-27-pr-object-mask-remap.md'; $body = "$env:TEMP\ap-mcp-phase7\pr-mask-body.md"; New-Item -ItemType Directory -Force "$env:TEMP\ap-mcp-phase7" | Out-Null; [IO.File]::WriteAllText($body, (([IO.File]::ReadAllLines($src) | Select-Object -Skip 2) -join "`n")); $url = gh pr create -R armory3d/armorpaint --base main --head graysonchalmers:fix/mesh-delete-object-mask-remap --title "Remap layer object masks when deleting a mesh" --body-file $body; $url; $pr = [int]($url.Trim() -split '/')[-1]; $pr
```

- [ ] **Step 5: Record it.** In `dependencies.py`, change `"the old object"),` (the end of the `delete-object-mask-remap` summary) to `"the old object", pr=<n>),`. Update STATUS.md and README. Run `& $py -m pytest -q` and `--check` (PASS, `(#<n>)`).

- [ ] **Step 6: Commit** (type the PR number for `<n>`: shell variables such as `$pr` don't survive between tool calls)

```powershell
git add src/armorpaint_mcp/dependencies.py STATUS.md README.md; git commit -m "docs: object-mask remap opened upstream as armory3d/armorpaint#<n>" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Upstream PR — `script_object_merge`

**Files:**
- Modify: `src/armorpaint_mcp/dependencies.py` (the `script-object-merge` entry), `STATUS.md`, `README.md`

**Interfaces:**
- Consumes: branch `feat/script-object-merge` (Task 7), `docs/upstream/2026-09-27-pr-script-object-merge.md` (Task 13).
- Produces: `pr=<n>` on the `script-object-merge` registry entry.

- [ ] **Step 1: HUMAN GATE:** controller confirms Grayson's go for: "push local branch `feat/script-object-merge` from `C:\Projects-local\z-Git\ArmorPaint` to remote `gc-fork`" before dispatch.

- [ ] **Step 2: Push and verify.**

```powershell
Push-Location C:\Projects-local\z-Git\ArmorPaint; git push gc-fork feat/script-object-merge; git rev-parse feat/script-object-merge; git ls-remote gc-fork refs/heads/feat/script-object-merge; Pop-Location
```

Expected: the two SHAs match.

- [ ] **Step 3: HUMAN GATE:** controller confirms Grayson's go for: "open a PR on armory3d/armorpaint, base `main`, head `graysonchalmers:feat/script-object-merge`, title `Add script_object_merge`, body = `docs/upstream/2026-09-27-pr-script-object-merge.md` minus its Title line" before running Step 4.

- [ ] **Step 4: Open the PR.**

```powershell
$src = 'C:\Projects-local\Tool-ArmorPaintMCP\.claude\worktrees\phase7\docs\upstream\2026-09-27-pr-script-object-merge.md'; $body = "$env:TEMP\ap-mcp-phase7\pr-merge-body.md"; New-Item -ItemType Directory -Force "$env:TEMP\ap-mcp-phase7" | Out-Null; [IO.File]::WriteAllText($body, (([IO.File]::ReadAllLines($src) | Select-Object -Skip 2) -join "`n")); $url = gh pr create -R armory3d/armorpaint --base main --head graysonchalmers:feat/script-object-merge --title "Add script_object_merge" --body-file $body; $url; $pr = [int]($url.Trim() -split '/')[-1]; $pr
```

- [ ] **Step 5: Record it.** In `dependencies.py`, change `minic_names=("script_object_merge",)),` to `minic_names=("script_object_merge",), pr=<n>),`. Update STATUS.md and README. Run `& $py -m pytest -q` and `--check` (PASS, `(#<n>)`).

- [ ] **Step 6: Commit** (type the PR number for `<n>`: shell variables such as `$pr` don't survive between tool calls)

```powershell
git add src/armorpaint_mcp/dependencies.py STATUS.md README.md; git commit -m "docs: script_object_merge opened upstream as armory3d/armorpaint#<n>" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

When any of the four PRs merges upstream, follow README "Building AP_BINARY": rebuild `integration/ap-mcp` from the new `main` without that branch (a checkout change, so it needs Grayson's go), set the entry's `upstream_commit` if the merged SHA differs, rewrite the manifest, and re-run `--check`.

---

## Self-review

**1. Spec coverage.**
- C change 1 (texa zero-init at `import_mesh.c:183-186`/`:260-263`) → Task 5; its PR → Tasks 13/14.
- C change 2 (mask remap on delete) → Task 6, at the corrected site; evidence → Task 11 (optional, as the spec says it isn't gated); PR → Tasks 13/15.
- C change 3 (`script_object_merge` in `c0df922d`'s shape, 3 files) → Task 7; PR → Tasks 13/16.
- D3 route:
  - integration branch = upstream `main` + every open PR → Task 8;
  - `AP_BINARY` built from it → Task 8;
  - `--check` detects each dependency → Tasks 1, 2 and 8;
  - drop a PR when it merges → Task 16's closing note and README (Task 12);
  - each checkout change and PR on Grayson's explicit go → the HUMAN GATE steps in Tasks 5-8 and 14-16.
- D2 (the wrapper, no `->ext` spike) → Task 7; no spike task exists.
- D5 → Task 6.
- Item 9's `merge_mesh_pair` on `_run_mesh_edit`, pre-checking both names and N ≥ 2 → Task 3. Its gate → Task 9:
  - N → N-1, keep survives and merge is gone, and the vertex sum → `test_merge_pair_merges_exactly_two_objects_and_leaves_the_third_alone`;
  - the third object untouched → same test (`group_signature`);
  - the smoke probe → Task 3 Step 9.
- Phase 7 gate extras:
  - UV-less non-OBJ rejected deterministically, gated on the texa fix being in the build → Task 10 (it requires the manifest);
  - `--check` reports every open-PR dependency → Tasks 1 and 8 Step 7, recorded in Task 12.
- The Phase 6 texa risk is closed in STATUS.md and the docstrings → Tasks 4 and 12.
- Not in scope, as instructed: `__wargv` and non-ASCII `%TEMP%` (listed under "Not in this plan").

**2. Placeholder scan.** No TBD or "similar to Task N". Runtime values the plan can't know ahead of time are produced by a named command and substituted by one:
- `UPSTREAM_BASE` and `INTEGRATION_HEAD` (Task 8's report and manifest);
- PR numbers (`$pr` from `gh pr create`);
- `{UPSTREAM_BASE}`/`TESTING_TEXT` in the PR bodies (Task 13 Step 4 substitutes them, then fails the check if either remains);
- the date and test counts in STATUS.md (recorded from Step 1's output).

**3. Type consistency.**
- `UpstreamDependency`, `UPSTREAM_DEPENDENCIES`, `MANIFEST_NAME`, `MANIFEST_SCHEMA`, `load_manifest`, `manifest_path`, `binary_sha256` and `dependency_checks` are defined in Task 1 and used unchanged in Tasks 2, 10 and 11.
- The dependency keys (`mesh-accumulator-zero-init`, `import-mesh-texa-zero-init`, `delete-object-mask-remap`, `script-object-merge`) and branch names match across Tasks 1, 5-8, 10 and 14-16.
- `build_merge_lines`, `check_pair`, `marker_error`, `MergePairError` and `ERROR_MARKER` are defined in Task 3.
- `script_object_merge(merge_obj, keep_obj)` (Task 3) matches the C signature `(object_t *o, object_t *into)` with `into` surviving (Task 7).
- `_run_mesh_edit`'s new `explain_abort` keyword is optional, so the seven existing callers are unchanged.

**4. Review Focus.** Each of the five lines has its test in the owning task: 1 → Task 3 (three tests); 2 → Tasks 3 and 1; 3 → Task 9; 4 → Task 1; 5 → Task 3.
