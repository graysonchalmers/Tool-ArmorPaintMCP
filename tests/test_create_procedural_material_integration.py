# tests/test_create_procedural_material_integration.py
"""Real ArmorPaint required. Run with:
    .venv\\Scripts\\python.exe -m pytest tests/test_create_procedural_material_integration.py -v
(needs AP_BINARY set to a working build -- see .env.example)
"""
import pytest
from PIL import Image

from armorpaint_mcp.server import create_procedural_material


@pytest.mark.integration
def test_checker_material_produces_a_genuinely_painted_texture(tmp_path):
    output_dir = tmp_path / "out"

    result = create_procedural_material(
        node_spec={"type": "checker", "params": {"scale": 8.0}},
        output_dir=str(output_dir),
        preset="generic",
    )

    assert result["error"] is None, result["error"]
    assert result["ok"] is True
    assert len(result["files"]) == 5  # base, nor, occ, rough, metal

    base_color_file = next(f for f in result["files"] if f.endswith("_base.png"))
    image = Image.open(base_color_file).convert("RGB")
    sampled_colors = {
        image.getpixel((x, y))
        for x in (0, image.width // 4, image.width // 2, image.width - 1)
        for y in (0, image.height // 4, image.height // 2, image.height - 1)
    }
    # A checker pattern samples to at least two distinct colors across the
    # image (some sample points may land on transparent/unpainted UV gaps,
    # which is expected -- the point is proving it's not a single flat
    # color everywhere, the exact failure mode this phase spent a session
    # debugging).
    assert len(sampled_colors) > 1, (
        f"expected a genuinely painted checker pattern, got a single "
        f"uniform color across all sample points: {sampled_colors}")
