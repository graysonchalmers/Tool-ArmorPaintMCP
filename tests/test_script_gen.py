import pytest

from armorpaint_mcp.script_gen import generate_script, NodeSpecError


def test_generate_script_checker_includes_expected_calls():
    script = generate_script(
        {"type": "checker", "params": {"scale": 8.0,
                                        "color1": [1.0, 0.0, 0.0],
                                        "color2": [0.0, 0.0, 1.0]}},
        "C:/out/dir",
    )

    assert "void main() {" in script
    assert script.rstrip().endswith("}")
    assert 'script_material_create_node_at("TEX_CHECKER", -400.0, 0.0)' in script
    assert 'script_material_get_node("OUTPUT_MATERIAL_PBR")' in script
    assert "script_material_set_color(src, 1, 1, 1.0, 0.0, 0.0, 1.0);" in script
    assert "script_material_set_color(src, 1, 2, 0.0, 0.0, 1.0, 1.0);" in script
    assert "script_material_set_float(src, 1, 3, 8.0);" in script
    assert "script_material_connect(src, 0, out, 0);" in script
    assert "script_fill_layer();" in script
    assert 'export_texture_run("C:/out/dir", 0);' in script
    # fill must happen before export, and node setup before the connect
    assert script.index("script_fill_layer();") < script.index("export_texture_run")
    assert script.index("script_material_connect") < script.index("script_fill_layer();")


def test_generate_script_checker_uses_defaults_when_params_omitted():
    script = generate_script({"type": "checker"}, "C:/out")

    assert "script_material_set_float(src, 1, 3, 5.0);" in script
    assert "script_material_set_color(src, 1, 1, 0.8, 0.8, 0.8, 1.0);" in script
    assert "script_material_set_color(src, 1, 2, 0.2, 0.2, 0.2, 1.0);" in script


def test_generate_script_solid_includes_expected_calls():
    script = generate_script(
        {"type": "solid", "params": {"color": [0.1, 0.2, 0.3]}}, "C:/out")

    assert 'script_material_create_node_at("RGB", -400.0, 0.0)' in script
    assert "script_material_set_color(src, 0, 0, 0.1, 0.2, 0.3, 1.0);" in script
    assert "script_material_connect(src, 0, out, 0);" in script
    assert "script_fill_layer();" in script
    assert 'export_texture_run("C:/out", 0);' in script


def test_generate_script_solid_uses_default_color_when_omitted():
    script = generate_script({"type": "solid"}, "C:/out")

    assert "script_material_set_color(src, 0, 0, 0.8, 0.8, 0.8, 1.0);" in script


def test_generate_script_rejects_unknown_node_type():
    with pytest.raises(NodeSpecError, match="unsupported node_spec type 'glow'"):
        generate_script({"type": "glow"}, "C:/out")


def test_generate_script_rejects_missing_type_key():
    with pytest.raises(NodeSpecError, match="must be a dict with a 'type' key"):
        generate_script({"params": {}}, "C:/out")


def test_generate_script_rejects_non_dict_node_spec():
    with pytest.raises(NodeSpecError, match="must be a dict"):
        generate_script("checker", "C:/out")


def test_generate_script_rejects_bad_color_shape():
    with pytest.raises(NodeSpecError, match="color1.*3 numbers"):
        generate_script({"type": "checker", "params": {"color1": [1.0, 0.0]}},
                         "C:/out")


def test_generate_script_rejects_non_numeric_scale():
    with pytest.raises(NodeSpecError, match="scale must be a number"):
        generate_script({"type": "checker", "params": {"scale": "big"}}, "C:/out")


def test_generate_script_normalizes_windows_backslashes():
    script = generate_script({"type": "solid"}, r"C:\out\dir")

    assert 'export_texture_run("C:/out/dir", 0);' in script
    assert "\\o" not in script  # no literal backslash made it into the script


def test_generate_script_rejects_path_containing_double_quote():
    with pytest.raises(NodeSpecError, match="double-quote"):
        generate_script({"type": "solid"}, 'C:/out/"; system("evil"); //')
