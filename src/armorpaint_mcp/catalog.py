"""Parses ArmorPaint's own `--api` output (paint/sources/args.c's args_api,
paint/sources/nodes_neural/text_to_text_node.c's text_to_text_node_reference)
into structured data. No hardcoded bake-type/blend-mode magic numbers --
everything here is read from the app's own text output, confirmed
empirically against the real local build (2026-09-16, see
docs/PLAN.md Phase 3). Bake types are deliberately NOT parsed here: the only
bake-adjacent node type, TEX_BAKE, exposes its bake-type selector as a
CUSTOM button widget (not an ENUM), so no option list is text-exposed --
and since mesh-detail baking is already confirmed structurally unreachable
from any script/CLI path (STATUS.md Known Issue #1), a bake-type catalog
would have no consumer anyway.
"""

import json
import re

_STATE_START = "/* Current project state:\n"
_STATE_END = "\n\nScene objects in world space"


class CatalogError(Exception):
    """`api_text` doesn't contain the section being parsed, or it's malformed."""


def extract_project_state(api_text: str) -> dict:
    """The `/* Current project state: <JSON> ... */` block's JSON, decoded.
    Anchored on the literal marker text and the following section header
    (rather than searching for a bare '*/', which the JSON payload could in
    principle contain inside a string value)."""
    start = api_text.find(_STATE_START)
    if start == -1:
        raise CatalogError(
            "'--api' output has no 'Current project state' block -- "
            "was a project path passed to ArmorPaint.exe, not just --api?")
    start += len(_STATE_START)
    end = api_text.find(_STATE_END, start)
    if end == -1:
        raise CatalogError(
            "'--api' output's project state block has no terminating "
            "'Scene objects in world space' section -- unexpected output shape")
    try:
        return json.loads(api_text[start:end])
    except json.JSONDecodeError as exc:
        raise CatalogError(f"project state block is not valid JSON: {exc}") from exc


def blend_modes(api_text: str) -> list[str]:
    """Blend mode names, in index order, from the MIX_RGB node's blend_type
    ENUM button in the material node-type reference. layer_datas[].blending
    is an integer index into this same list. Specifically anchored to
    MIX_RGB (not just any 'blend_type' button) because MIX_NORMAL_MAP has
    its own, differently-sized blend_type ENUM."""
    match = re.search(
        r'// MIX_RGB \|.*?\n//\s+button \d+ blend_type ENUM: (.+)',
        api_text)
    if match is None:
        raise CatalogError(
            "'--api' output has no MIX_RGB blend_type ENUM button -- "
            "unexpected material node reference shape")
    options = match.group(1).split(", ")
    # Each option is "<index> <name>"; keep the name, drop the index (the
    # list's own position is the index).
    return [re.sub(r'^\d+\s+', '', opt) for opt in options]


def scene_objects(api_text: str) -> list[dict]:
    """Every object in the 'Scene objects in world space' section: name,
    location, and size, already in world space (no matrix decoding needed --
    unlike mesh_transforms in the JSON state block, which is column-major
    4x4 and not worth parsing when this text section already has the
    answer)."""
    pattern = re.compile(
        r'"([^"]+)": location \(([^)]+)\), size \(([^)]+)\)')
    return [
        {
            "name": name,
            "location": [float(v) for v in loc.split(", ")],
            "size": [float(v) for v in size.split(", ")],
        }
        for name, loc, size in pattern.findall(api_text)
    ]
