"""Setup preflight for the ArmorPaint MCP server.

`require_valid` in config.py fails fast at the first missing prerequisite,
which is right for server startup but unhelpful when someone is getting set
up. `check_setup` runs every check and returns them all as data (never
raising) so `ap-mcp --check` can print one green/red checklist.
"""

import os
import subprocess
from dataclasses import dataclass

from armorpaint_mcp.catalog import mesh_edit_patch_missing
from armorpaint_mcp.config import Config, load_config


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def check_setup(cfg: Config) -> list[Check]:
    """Run every setup check against a resolved Config. Never raises."""
    checks: list[Check] = []

    if not cfg.binary:
        checks.append(Check("AP_BINARY", False,
                            "not set. Point AP_BINARY at ArmorPaint.exe."))
    elif os.path.isfile(cfg.binary):
        checks.append(Check("AP_BINARY", True, cfg.binary))
    else:
        checks.append(Check("AP_BINARY", False, f"does not exist: '{cfg.binary}'"))

    if cfg.binary and os.path.isfile(cfg.binary):
        data_dir = os.path.join(os.path.dirname(cfg.binary), "data")
        if os.path.isdir(data_dir):
            checks.append(Check("data dir next to binary", True, data_dir))
        else:
            checks.append(Check("data dir next to binary", False,
                                f"missing: '{data_dir}'. ArmorPaint access-violates on "
                                "launch with no log output if data\\ isn't next to the "
                                "exe -- see README \"Build gotcha\"."))

    if cfg.binary and os.path.isfile(cfg.binary):
        try:
            out = subprocess.run([cfg.binary, "--help"], capture_output=True,
                                  text=True, timeout=15)
            checks.append(Check("binary launches", out.returncode == 1,
                                "printed --help and exited" if out.returncode == 1
                                else f"unexpected exit code {out.returncode}"))
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append(Check("binary launches", False, str(exc)))

    if cfg.binary and os.path.isfile(cfg.binary):
        try:
            out = subprocess.run([cfg.binary, "--api"], capture_output=True,
                                  text=True, timeout=15)
            missing = mesh_edit_patch_missing(out.stdout) if out.returncode == 0 else None
            if missing is None:
                checks.append(Check("mesh-edit patch", False,
                                    f"'--api' exited {out.returncode}, could not check"))
            elif missing:
                checks.append(Check("mesh-edit patch", False,
                                    f"missing minic registration(s): {', '.join(missing)} "
                                    "-- this AP_BINARY is running stock ArmorPaint. Phase 5's "
                                    "mesh-edit tools (decimate_mesh, etc.) need the scoped "
                                    "local patch built -- see ROADMAP.md's \"Patch policy\"."))
            else:
                checks.append(Check("mesh-edit patch", True,
                                    "all 7 mesh-edit functions registered"))
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append(Check("mesh-edit patch", False, str(exc)))

    # Check writability without creating anything: walk up to the nearest
    # existing ancestor and test that. The server makedirs the output dir at
    # export time; a preflight shouldn't have that side effect.
    probe = cfg.output_dir
    while probe and not os.path.isdir(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    if probe and os.path.isdir(probe) and os.access(probe, os.W_OK):
        checks.append(Check("output dir", True, cfg.output_dir))
    else:
        checks.append(Check("output dir", False, f"not writable: '{cfg.output_dir}'"))

    if cfg.allowed_roots:
        checks.append(Check("AP_ALLOWED_ROOTS", True, os.pathsep.join(cfg.allowed_roots)))
    else:
        checks.append(Check("AP_ALLOWED_ROOTS", True,
                            "unset. Reads and writes are unrestricted; set it "
                            "(os.pathsep-separated dirs) to bound client paths."))

    return checks


def all_ok(checks: list[Check]) -> bool:
    return all(c.ok for c in checks)


def format_report(checks: list[Check]) -> str:
    lines = ["ArmorPaint MCP setup check", ""]
    for c in checks:
        lines.append(f"  [{'PASS' if c.ok else 'FAIL'}] {c.name}: {c.detail}")
    lines.append("")
    if all_ok(checks):
        lines.append("All checks passed. ap-mcp is ready.")
    else:
        n = sum(1 for c in checks if not c.ok)
        lines.append(f"{n} check(s) failed. Fix the above and re-run `ap-mcp --check`.")
    return "\n".join(lines)


def run_check(cfg: Config | None = None) -> int:
    """Print the preflight report. Returns 0 if all checks pass, else 1."""
    if cfg is None:
        cfg = load_config()
    checks = check_setup(cfg)
    print(format_report(checks))
    return 0 if all_ok(checks) else 1
