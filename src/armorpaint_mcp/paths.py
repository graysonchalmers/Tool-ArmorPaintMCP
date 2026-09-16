"""Client-facing path guards for the MCP tools.

Two shapes:
  * ensure_within_roots  -- bounds a whole client-supplied path to
    AP_ALLOWED_ROOTS. Opt-in: empty roots means passthrough.
  * reject_path_fragment -- rejects traversal in a client-supplied *name*
    (e.g. an export preset) that gets joined onto a trusted dir. Always on.
"""

import os


class PathNotAllowed(Exception):
    """A client-supplied path or fragment is not permitted."""


def ensure_within_roots(path: str, roots: list[str]) -> str:
    """Return realpath(path). If roots is non-empty, require the realpath to
    lie within one of them (else raise PathNotAllowed). Empty roots is
    passthrough. realpath resolves symlinks before comparison, so a link
    inside a root cannot point outside it."""
    resolved = os.path.realpath(path)
    if not roots:
        return resolved
    cand = os.path.normcase(resolved)
    for root in roots:
        root_norm = os.path.normcase(os.path.realpath(root))
        if cand == root_norm or cand.startswith(root_norm + os.sep):
            return resolved
    raise PathNotAllowed(
        f"path '{path}' is outside the allowed roots "
        f"(AP_ALLOWED_ROOTS): {roots}")


def reject_path_fragment(name: str) -> str:
    """Return name if it is a bare path component. Raise PathNotAllowed if it
    contains a path separator or equals '..'. Always enforced, independent of
    AP_ALLOWED_ROOTS: a separator or '..' in a 'name' (e.g. an export preset)
    is never legitimate."""
    seps = [s for s in (os.sep, os.altsep) if s]
    if any(s in name for s in seps):
        raise PathNotAllowed(
            f"'{name}' must be a bare name with no path separators")
    if name == "..":
        raise PathNotAllowed(f"'{name}' is not a valid name")
    return name
