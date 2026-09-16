"""Drives the real ArmorPaint binary as a subprocess.

--background is deliberately NEVER passed for --export-textures: that
combination is broken on this build (iron_stop() fires before the scheduled
export runs, producing zero output at exit code 0 -- confirmed empirically,
see docs/PLAN.md's Phase 1 section and the design spec's amendment). Instead
this launches the normal GUI process, polls the output directory until every
file the chosen preset says it will write has been written with a stable,
non-empty size, and terminates the process once that's true.

Completion is decided against the *expected* filenames (derived from the
preset's own JSON definition), never against "filenames that are new since
we started": ArmorPaint overwrites existing files rather than creating
uniquely-named ones, so a set difference goes blind the moment the output
directory is not empty (a re-export would report a false failure, and a
second preset sharing filenames with the first would report a partial file
list as if it were the whole export).

Expected-and-present isn't enough on its own either, for the same reason in
reverse: into a reused output directory, run 1's leftovers would satisfy it
instantly even if run 2's process died on launch. So each expected file is
fingerprinted (size + mtime) before launch and must *change* to count.
"""

import glob
import json
import os
import subprocess
import time
from dataclasses import dataclass

DEFAULT_TIMEOUT_S = 30.0
POLL_INTERVAL_S = 0.25

# ArmorPaint maps the --export-textures <type> argument onto bit depth +
# LDR format in args.c, and export_texture.c turns that into the extension:
# 8-bit png/jpg keep their own extension, exr16/exr32 both write .exr.
_TEXTURE_TYPE_EXTENSIONS = {
    "png": ".png",
    "jpg": ".jpg",
    "exr16": ".exr",
    "exr32": ".exr",
}


@dataclass
class ExportResult:
    ok: bool
    files: list[str]
    error: str | None = None


def _presets_dir(binary: str) -> str:
    """The ArmorPaint install's export-preset directory, next to `binary`.
    Single source of truth for both listing presets and reading one, so the
    two can't drift apart."""
    return os.path.join(os.path.dirname(binary), "data", "export_presets")


def list_export_presets(binary: str) -> list[str]:
    """Preset names discoverable from the ArmorPaint install next to
    `binary` (<binary_dir>/data/export_presets/*.json) -- read from disk,
    never hardcoded, so this can't silently go stale the way the reference
    project's hardcoded bake-type/blend-mode constants can."""
    return sorted(
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(_presets_dir(binary), "*.json"))
    )


def preset_texture_names(binary: str, preset: str) -> list[str]:
    """The texture names `preset` writes, in the preset's own definition
    order, read from <binary_dir>/data/export_presets/<preset>.json (whose
    shape is {"textures": [{"name": "base", ...}, ...]}).

    Raises OSError if the preset file is unreadable, and ValueError/KeyError/
    TypeError if its JSON isn't the expected shape -- callers treat any of
    those as "can't tell what this export should produce"."""
    path = os.path.join(_presets_dir(binary), f"{preset}.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return [texture.get("name", "") for texture in data["textures"]]


def expected_output_files(binary: str, project: str, texture_type: str,
                          preset: str, output_dir: str) -> list[str]:
    """The exact files ArmorPaint will write for this project + preset, in
    preset order.

    Mirrors ArmorPaint's own naming (paint/sources/io/export_texture.c
    builds out_path this way in its preset-texture loop): the stem is the
    opened project's basename without its extension (import_arm.c sets
    ui_files_filename that way), each preset texture appends "_<name>", and
    a preset texture with an empty name (minecraft_mer's first entry)
    appends nothing at all. So sample_project.arm + "generic" as png gives
    sample_project_base.png ... sample_project_metal.png."""
    ext = _TEXTURE_TYPE_EXTENSIONS.get(texture_type)
    if ext is None:
        raise ValueError(
            f"unknown texture type '{texture_type}'; expected one of "
            f"{', '.join(sorted(_TEXTURE_TYPE_EXTENSIONS))}")
    stem = os.path.splitext(os.path.basename(project))[0]
    return [
        os.path.join(output_dir, f"{stem}_{name}{ext}" if name else f"{stem}{ext}")
        for name in preset_texture_names(binary, preset)
    ]


def _fingerprint(path: str) -> tuple[int, int] | None:
    """(size, mtime_ns) of `path`, or None if it's missing or still empty (a
    file ArmorPaint has created but not yet filled reads as 0 bytes)."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return None if st.st_size == 0 else (st.st_size, st.st_mtime_ns)


def _snapshot(paths: list[str]) -> dict[str, tuple[int, int]]:
    """Fingerprints of whichever of `paths` already exist. Taken before the
    export launches: output dirs get reused, and an export that never runs
    must not be judged complete on the *previous* run's leftovers."""
    return {p: fp for p in paths if (fp := _fingerprint(p)) is not None}


def _written_by_this_run(paths: list[str],
                         before: dict[str, tuple[int, int]]) -> dict[str, tuple[int, int]] | None:
    """Fingerprints of every path, but only if all of them were written by
    this run -- present, non-empty, and changed from the pre-launch
    snapshot. None means "not all there yet"."""
    fresh: dict[str, tuple[int, int]] = {}
    for path in paths:
        fp = _fingerprint(path)
        if fp is None or before.get(path) == fp:
            return None
        fresh[path] = fp
    return fresh


def _terminate(proc) -> str:
    """Stop the GUI process (it does not self-exit) and return its stderr.
    Always runs, including when the poll loop raised or was interrupted."""
    proc.terminate()
    try:
        _, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        _, stderr = proc.communicate(timeout=5)
    return stderr or ""


def export_textures(binary: str, project: str, texture_type: str, preset: str,
                     output_dir: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> ExportResult:
    """Launch ArmorPaint against `project` and export textures at `preset`.
    Returns ExportResult(ok, files, error). Never raises for a normal
    export-didn't-happen failure -- that's ExportResult(ok=False, ...)."""
    os.makedirs(output_dir, exist_ok=True)

    try:
        expected = expected_output_files(binary, project, texture_type, preset,
                                          output_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Fail before spawning a GUI process we'd have no way to judge.
        return ExportResult(ok=False, files=[], error=(
            f"could not determine which files preset '{preset}' exports: {exc}"))

    before = _snapshot(expected)
    proc = subprocess.Popen(
        [binary, project, "--export-textures", texture_type, preset, output_dir],
        # stdout is never read during the poll; an unread PIPE could fill the
        # OS buffer and deadlock a long export. stderr IS read and reported.
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )

    deadline = time.monotonic() + timeout_s
    complete = False
    try:
        while time.monotonic() < deadline:
            fresh = _written_by_this_run(expected, before)
            if fresh is None:
                time.sleep(POLL_INTERVAL_S)
                continue
            # Every expected file has been (re)written and is non-empty.
            # Confirm the last writes have landed by re-reading once.
            time.sleep(POLL_INTERVAL_S)
            if _written_by_this_run(expected, before) == fresh:
                complete = True
                break
    finally:
        stderr = _terminate(proc)

    if not complete:
        written = [p for p in expected
                   if _fingerprint(p) not in (None, before.get(p))]
        unwritten = [p for p in expected if p not in written]
        detail = f": {stderr.strip()}" if stderr and stderr.strip() else ""
        return ExportResult(ok=False, files=written, error=(
            f"export outcome uncertain: after {timeout_s}s, "
            f"{len(unwritten)} of {len(expected)} file(s) preset '{preset}' should "
            f"write were not written by this run (missing, empty, or unchanged) "
            f"in '{output_dir}': "
            f"{', '.join(os.path.basename(p) for p in unwritten) or 'none'}"
            f"{detail}"))
    return ExportResult(ok=True, files=expected)
