"""Tests for Theme & CSS Editor (v4.4)."""
from __future__ import annotations

import pytest

from services import theme_service as svc


def test_get_config_returns_defaults():
    config = svc.get_config()
    assert config["preset"] == "dark"
    assert config["overrides"] == {}
    assert config["font_family"] == ""
    assert config["custom_css"] == ""


def test_save_config_persists():
    saved = svc.save_config({
        "preset": "sepia",
        "font_family": "Georgia, serif",
    })
    assert saved["preset"] == "sepia"
    assert saved["font_family"] == "Georgia, serif"
    # Verify loaded back
    loaded = svc.get_config()
    assert loaded["preset"] == "sepia"
    assert loaded["font_family"] == "Georgia, serif"


def test_save_config_invalid_preset():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.save_config({"preset": "bogus"})


def test_save_config_invalid_overrides():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.save_config({"overrides": "not a dict"})


def test_save_config_custom_css_too_long():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.save_config({"custom_css": "x" * 10001})


def test_reset_config():
    svc.save_config({"preset": "sepia"})
    svc.reset_config()
    config = svc.get_config()
    assert config["preset"] == "dark"


def test_generate_css_empty_for_defaults():
    config = dict(svc.DEFAULT_THEME_CONFIG)
    css = svc.generate_css(config)
    assert css == ""


def test_generate_css_with_preset():
    config = {"preset": "sepia", "overrides": {}, "font_family": "", "base_font_size": "", "custom_css": ""}
    css = svc.generate_css(config)
    assert "--bg: #f4ecd8" in css  # sepia bg


def test_generate_css_with_font_override():
    config = {
        "preset": "dark", "overrides": {},
        "font_family": "Georgia, serif",
        "base_font_size": "", "custom_css": "",
    }
    css = svc.generate_css(config)
    assert "Georgia, serif" in css
    assert "font-family" in css


def test_generate_css_with_base_font_size():
    config = {
        "preset": "dark", "overrides": {},
        "font_family": "", "base_font_size": "18px",
        "custom_css": "",
    }
    css = svc.generate_css(config)
    assert "font-size: 18px" in css


def test_generate_css_with_custom_css():
    config = {
        "preset": "dark", "overrides": {},
        "font_family": "", "base_font_size": "",
        "custom_css": ".card { border-radius: 12px; }",
    }
    css = svc.generate_css(config)
    assert ".card { border-radius: 12px; }" in css


def test_generate_css_with_color_override():
    config = {
        "preset": "dark",
        "overrides": {"--accent": "#ff0000"},
        "font_family": "", "base_font_size": "", "custom_css": "",
    }
    css = svc.generate_css(config)
    assert "--accent: #ff0000" in css


def test_get_preset_list():
    presets = svc.get_preset_list()
    assert len(presets) >= 6  # dark, light, sepia, forest, ocean, sunset, midnight
    keys = {p["key"] for p in presets}
    assert "dark" in keys
    assert "light" in keys
    assert "sepia" in keys


def test_each_preset_has_required_vars():
    for key, preset in svc.PRESET_THEMES.items():
        assert "label" in preset
        assert "icon" in preset
        assert "vars" in preset
        vars_ = preset["vars"]
        # Must have core color vars
        assert "--bg" in vars_
        assert "--text" in vars_
        assert "--accent" in vars_
        assert "--border" in vars_


def test_save_and_generate_css_roundtrip():
    svc.save_config({
        "preset": "forest",
        "font_family": "Inter, sans-serif",
        "custom_css": ".test { color: red; }",
    })
    config = svc.get_config()
    css = svc.generate_css(config)
    assert "--bg: #0f1f15" in css  # forest bg
    assert "Inter, sans-serif" in css
    assert ".test { color: red; }" in css
