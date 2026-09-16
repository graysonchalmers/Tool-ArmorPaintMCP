"""ArmorPaint MCP server package.

Drives ArmorPaint's own native CLI flags and minic scripting engine to batch
re-export/rebake existing .arm projects -- no source patching, no custom
rebuild. See docs/superpowers/specs/2026-09-15-armorpaint-mcp-design.md for
the full design and why the reference implementation's patch-and-rebuild
approach was deliberately not followed.

Units (grown in as each phase lands -- see docs/PLAN.md):
  config.py   env/.env-driven configuration (AP_BINARY, AP_OUTPUT_DIR, AP_ALLOWED_ROOTS)
  doctor.py   --check preflight (green/red checklist, never raises)
  server.py   the MCP server + console entry point (ap-mcp)
"""

from importlib.metadata import version as _pkg_version, PackageNotFoundError

try:
    __version__ = _pkg_version("ap-mcp")
except PackageNotFoundError:  # not pip-installed (tests import via pythonpath=src)
    __version__ = "0.0.0+unknown"
