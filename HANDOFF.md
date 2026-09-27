# 🧭 Session Handoff — Tool-ArmorPaintMCP

_Last updated: 2026-09-27 08:30 CDT (wrap-up: upstream sync session)_

> The baton. Written by `wrap-up` at session end, read by `pickup` at session start.

## 🎯 Current state

v1 (5 tools) + Phase 5 (7 mesh/UV editing tools) shipped and green on a
build of **current upstream ArmorPaint**:
- The 7-function registration patch is upstream, merged 2026-09-17 as
  [armory3d/armorpaint#2139](https://github.com/armory3d/armorpaint/pull/2139)
  (`ee2f3635`).
- Upstream then renamed `plugin_uv_unwrap_button` to `util_mesh_uv_unwrap`
  (`01bae6c5`). The project now calls the new name (STATUS.md Known Issue #6,
  closed), so it **requires a build from `01bae6c5` on**.
- The smooth/bevel/normals zero-init fix is open upstream as
  [armory3d/armorpaint#2148](https://github.com/armory3d/armorpaint/pull/2148):
  11 `memset` lines, one file. 10-run repro on upstream `main` `85f6cf1c`:
  stock 3/10 smooth + 9/10 bevel corrupted, fixed 0/10 + 0/10.
- The ArmorPaint checkout is on `fix/mesh-accumulator-zero-init` at
  `287e63f4` (upstream `main` `85f6cf1c` + that fix), pushed to `gc-fork`.
  `AP_BINARY` was built from it 2026-09-27.
- On that build: `pytest -q` 122 passed, `-m integration` 18 passed, smoke
  13/13, `--check` green. `spike/minic-decimate` is superseded.

Phase 6 (ROADMAP items 8-10) is in `docs/PLAN.md` as **DRAFT, not approved**,
source-read only. Its 6.0 prerequisite (re-baseline) is done.

## 📌 Where we stopped

Session's commits merged (fast-forward) into `main` and pushed; `origin/main`
in sync. Nothing mid-flight. The `pickup-4c87f9` worktree (the session's own,
app-owned) is fully merged and can be retired once the session closes.

## ▶️ Next concrete step

1. Watch #2148. When it merges, rebuild `AP_BINARY` from plain upstream
   `main` and retire the local `fix/mesh-accumulator-zero-init` branch.
2. Grayson answers Phase 6 decisions D2-D5 in `docs/PLAN.md`, then approve
   or trim the draft before any Phase 6 work.

## ❓ Open questions

- Phase 6 decisions:
  - D2: item 9's C change, upstream-first or local.
  - D3: future registrations straight upstream by default?
  - D4: item 8 replace semantics.
  - D5: upstream the layer-mask remap on delete.
- D1 was pinned for now; the maintainer warned of more script-API renames.
  After any `AP_BINARY` rebuild, diff `--api` and run `--check` +
  integration. An undefined minic call still exits 0 with `ok=True`.
- ~~`decimate_mesh`'s gallery symptom~~: closed 2026-09-27 as STATUS.md
  Known Issue #7 (fixture-scale effect, not a bug).
- Parked small items:
  - the `_failure()` key-set assertion gap (2 of 10 call sites);
  - spec Amendment 3's "6 of 7 functions patched" prose;
  - `merge_mesh_geometry`'s docstring still lacks the "ok=True proves only
    completion" caveat.
- Live mode: deferred, unchanged.

## 🗂️ Changed this session

- `a27eb28`: doc drift fixed (#2139 merged, not open). Known Issue #6
  logged. `doctor.py`'s mesh-edit message no longer claims "stock
  ArmorPaint".
- `dd84a32`: switched to `util_mesh_uv_unwrap`. Phase 6 draft added.
  ROADMAP rows 8-10 + STATUS open-phase point at it.
- ArmorPaint checkout: new branch `fix/mesh-accumulator-zero-init`
  (`287e63f4`), pushed to `gc-fork`, PR #2148 opened. Rebuilt `AP_BINARY`
  (old exe + `data\` backed up in the session scratchpad only).
- Deleted the merged remote branch `origin/claude/mystifying-banach-e42a6d`.
  Moved the empty stuck `.claude\worktrees\mesh-uv-visual-gallery` to
  `_to_delete\worktrees\`.

---
📜 Full session history: `handoff-log/` (one dated file per session, oldest to newest)
