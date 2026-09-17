# 2026-09-16 (later same day) — upstream PR to armory3d/armorpaint

- Picked up right after the Phase 5 wrap-up — same calendar day, separate
  session. Grayson's pickup request named the exact next step already
  recorded in HANDOFF: start the upstream PR, check armory3d/armorpaint's
  contribution guidelines.
- Checked the guidelines: no `CONTRIBUTING.md` exists. Pulled the repo's
  actual recent PR history instead — found two small, single-purpose PRs
  merged that same week (#2117, #2136) with a consistent
  Problem/Compatibility/Testing body shape, and, more valuably, three much
  larger unrelated "Feat/mcp-*" PRs (500-1700 lines, 8-9 files each) from a
  different contributor, all closed unread within 20-45 minutes with zero
  comments. Surfaced this as a real finding, not a guess: size/scope, not
  the "mcp" framing, is almost certainly what gets a PR rejected on sight —
  our patch (19 lines, 1 file) is well inside the size band that merged
  twice that week.
- Presented the finding and a 4-option "choose your next move" rather than
  unilaterally deciding PR shape (single PR vs. split into 7, more research
  first, or park it) — publishing to a third-party public repo is
  explicit-permission territory. Grayson picked "prep the PR" (single PR,
  matching the merged precedent's size and shape).
- Cleaned the patch's comments in `spike/minic-decimate`
  (`C:\Projects-local\z-Git\ArmorPaint`) — the original spike comments
  referenced internal session artifacts ("see spike report for details"),
  rewritten to be self-contained for an outside reviewer. Amended the
  branch's single unpushed commit with the cleaned diff and a repo-style
  message (`paint: expose util_mesh + uv-unwrap operators to minic
  scripts`, `2b528475`) — no functional change, same 7 registrations.
  Drafted the PR title/body in the same session, modeled on #2117's shape.
- Confirmed no existing fork on Grayson's GitHub account, then stopped and
  asked before any GitHub-facing action (fork/push/PR-open all touch his
  public account). Grayson confirmed "run all three."
- Forked `armory3d/armorpaint` → `graysonchalmers/armorpaint` (GitHub API).
  Found `gh` already authenticated as `graysonchalmers` locally with SSH —
  used that to push the branch directly (`git push gc-fork
  spike/minic-decimate:expose-util-mesh-uv-unwrap-to-minic`) rather than the
  GitHub API's file-based push, so the real local commit and Grayson's own
  authorship reached the fork unchanged instead of being re-created via API.
  Opened the PR: **armory3d/armorpaint#2139**, Grayson's first open-source
  contribution.
- Wrote two commons log entries (prep, then PR-opened) and updated HANDOFF's
  "Next concrete step" mid-session so a cold pickup wouldn't see stale
  next-steps if the session had ended right after opening the PR.
