import os
import pytest

from armorpaint_mcp.paths import ensure_within_roots, reject_path_fragment, PathNotAllowed


def test_ensure_within_roots_passthrough_when_empty(tmp_path):
    p = tmp_path / "anywhere.arm"
    assert ensure_within_roots(str(p), []) == os.path.realpath(str(p))


def test_ensure_within_roots_allows_path_inside_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    p = root / "project.arm"
    assert ensure_within_roots(str(p), [str(root)]) == os.path.realpath(str(p))


def test_ensure_within_roots_rejects_path_outside_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.arm"
    with pytest.raises(PathNotAllowed):
        ensure_within_roots(str(outside), [str(root)])


def test_reject_path_fragment_allows_bare_name():
    assert reject_path_fragment("generic") == "generic"


def test_reject_path_fragment_rejects_separator():
    with pytest.raises(PathNotAllowed):
        reject_path_fragment("../generic")


def test_reject_path_fragment_rejects_dotdot():
    with pytest.raises(PathNotAllowed):
        reject_path_fragment("..")
