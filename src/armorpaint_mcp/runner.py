"""Drives the real ArmorPaint binary as a subprocess.

--background is deliberately NEVER passed for --export-textures: that
combination is broken on this build (iron_stop() fires before the scheduled
export runs, producing zero output at exit code 0 -- confirmed empirically,
see docs/PLAN.md's Phase 1 section and the design spec's amendment). Instead
this launches the normal GUI process, polls the output directory for new
files, and terminates the process once export is detected complete.
"""

import glob
import os
import subprocess
import time
from dataclasses import dataclass

DEFAULT_TIMEOUT_S = 30.0
POLL_INTERVAL_S = 0.25
SETTLE_S = 0.5  # grace period after the first new file appears, so a
                # multi-file export (5 PNGs for "generic") finishes writing
                # before we terminate the process.


@dataclass
class ExportResult:
    ok: bool
    files: list[str]
    error: str | None = None


def list_export_presets(binary: str) -> list[str]:
    """Preset names discoverable from the ArmorPaint install next to
    `binary` (<binary_dir>/data/export_presets/*.json) -- read from disk,
    never hardcoded, so this can't silently go stale the way the reference
    project's hardcoded bake-type/blend-mode constants can."""
    presets_dir = os.path.join(os.path.dirname(binary), "data", "export_presets")
    return sorted(
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(presets_dir, "*.json"))
    )


def export_textures(binary: str, project: str, texture_type: str, preset: str,
                     output_dir: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> ExportResult:
    """Launch ArmorPaint against `project` and export textures at `preset`.
    Returns ExportResult(ok, files, error). Never raises for a normal
    export-didn't-happen failure -- that's ExportResult(ok=False, ...)."""
    os.makedirs(output_dir, exist_ok=True)
    before = set(os.listdir(output_dir))

    proc = subprocess.Popen(
        [binary, project, "--export-textures", texture_type, preset, output_dir],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )

    deadline = time.monotonic() + timeout_s
    new_files: list[str] = []
    while time.monotonic() < deadline:
        after = set(os.listdir(output_dir))
        new_files = sorted(after - before)
        if new_files:
            time.sleep(SETTLE_S)
            after = set(os.listdir(output_dir))
            new_files = sorted(after - before)
            break
        time.sleep(POLL_INTERVAL_S)

    proc.terminate()
    try:
        _, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        _, stderr = proc.communicate(timeout=5)

    if not new_files:
        detail = f": {stderr.strip()}" if stderr and stderr.strip() else ""
        return ExportResult(ok=False, files=[], error=(
            f"no new files appeared in '{output_dir}' within {timeout_s}s{detail}"))
    return ExportResult(ok=True, files=[os.path.join(output_dir, f) for f in new_files])
