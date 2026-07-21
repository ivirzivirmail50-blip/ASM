"""Theme & CSS Editor service — let writers customize colors, fonts, spacing.

The theme config is persisted as a Setting ('custom_theme') and injected
as a <style> tag in base.html. The writer can:
- Pick from preset themes (dark, light, sepia, forest, ocean, sunset)
- Override individual CSS variables (accent color, background, text, fonts)
- Adjust global font family and base font size
- Add custom CSS overrides (freeform textarea)

Preset themes are bundled; the writer's customizations layer on top.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from core.db import read_session, write_transaction
from core.errors import ValidationError
from models.settings import Setting

log = logging.getLogger("asm.theme")


# ---------------------------------------------------------------------------
# Preset themes
# ---------------------------------------------------------------------------

PRESET_THEMES: dict[str, dict[str, Any]] = {
    "dark": {
        "label": "Dark (default)",
        "icon": "🌙",
        "vars": {
            "--bg": "#0b1020",
            "--bg-elev-1": "#131a30",
            "--bg-elev-2": "#1a2240",
            "--bg-elev-3": "#232c52",
            "--border": "#2c365d",
            "--text": "#e6e9f5",
            "--text-dim": "#9aa3c7",
            "--text-mute": "#6b7299",
            "--accent": "#6366f1",
            "--accent-hover": "#818cf8",
            "--success": "#22c55e",
            "--warning": "#f59e0b",
            "--danger": "#ef4444",
        },
    },
    "light": {
        "label": "Light",
        "icon": "☀",
        "vars": {
            "--bg": "#f7f8fb",
            "--bg-elev-1": "#ffffff",
            "--bg-elev-2": "#f1f3f9",
            "--bg-elev-3": "#e6e9f5",
            "--border": "#e0e4ee",
            "--text": "#1a2030",
            "--text-dim": "#4b5575",
            "--text-mute": "#7a8398",
            "--accent": "#4f46e5",
            "--accent-hover": "#6366f1",
            "--success": "#16a34a",
            "--warning": "#d97706",
            "--danger": "#dc2626",
        },
    },
    "sepia": {
        "label": "Sepia",
        "icon": "📜",
        "vars": {
            "--bg": "#f4ecd8",
            "--bg-elev-1": "#faf3e0",
            "--bg-elev-2": "#ede0c8",
            "--bg-elev-3": "#e0d4b8",
            "--border": "#c9b890",
            "--text": "#3a2f1a",
            "--text-dim": "#5e4f30",
            "--text-mute": "#8a7a55",
            "--accent": "#a16207",
            "--accent-hover": "#c2740a",
            "--success": "#5a7a3a",
            "--warning": "#b8860b",
            "--danger": "#a0522d",
        },
    },
    "forest": {
        "label": "Forest",
        "icon": "🌲",
        "vars": {
            "--bg": "#0f1f15",
            "--bg-elev-1": "#16291e",
            "--bg-elev-2": "#1d3526",
            "--bg-elev-3": "#264532",
            "--border": "#2f5a3f",
            "--text": "#d4e8d8",
            "--text-dim": "#9ab8a2",
            "--text-mute": "#6a8a73",
            "--accent": "#10b981",
            "--accent-hover": "#34d399",
            "--success": "#22c55e",
            "--warning": "#f59e0b",
            "--danger": "#ef4444",
        },
    },
    "ocean": {
        "label": "Ocean",
        "icon": "🌊",
        "vars": {
            "--bg": "#0a1929",
            "--bg-elev-1": "#0f2438",
            "--bg-elev-2": "#152e48",
            "--bg-elev-3": "#1c3a58",
            "--border": "#244a6e",
            "--text": "#d6e4f0",
            "--text-dim": "#9ab4ca",
            "--text-mute": "#6a8aa5",
            "--accent": "#0ea5e9",
            "--accent-hover": "#38bdf8",
            "--success": "#14b8a6",
            "--warning": "#f59e0b",
            "--danger": "#ef4444",
        },
    },
    "sunset": {
        "label": "Sunset",
        "icon": "🌅",
        "vars": {
            "--bg": "#1a0f1f",
            "--bg-elev-1": "#271628",
            "--bg-elev-2": "#361c38",
            "--bg-elev-3": "#472349",
            "--border": "#5a2d5d",
            "--text": "#f5e6f0",
            "--text-dim": "#c7a8c0",
            "--text-mute": "#9a7a95",
            "--accent": "#ec4899",
            "--accent-hover": "#f472b6",
            "--success": "#22c55e",
            "--warning": "#f59e0b",
            "--danger": "#ef4444",
        },
    },
    "midnight": {
        "label": "Midnight (OLED black)",
        "icon": "🌑",
        "vars": {
            "--bg": "#000000",
            "--bg-elev-1": "#0a0a0a",
            "--bg-elev-2": "#141414",
            "--bg-elev-3": "#1f1f1f",
            "--border": "#2a2a2a",
            "--text": "#e0e0e0",
            "--text-dim": "#a0a0a0",
            "--text-mute": "#707070",
            "--accent": "#6366f1",
            "--accent-hover": "#818cf8",
            "--success": "#22c55e",
            "--warning": "#f59e0b",
            "--danger": "#ef4444",
        },
    },
}

DEFAULT_THEME_CONFIG: dict[str, Any] = {
    "preset": "dark",
    "overrides": {},        # CSS variable overrides on top of preset
    "font_family": "",      # empty = use default
    "base_font_size": "",   # empty = use default (16px)
    "custom_css": "",       # freeform CSS
}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def get_config() -> dict[str, Any]:
    with read_session() as s:
        raw = Setting.get(s, "custom_theme", "")
    if not raw:
        return dict(DEFAULT_THEME_CONFIG)
    # Setting.get already parses JSON, so raw is usually a dict.
    # Handle both dict and string for safety.
    if isinstance(raw, str):
        try:
            saved = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return dict(DEFAULT_THEME_CONFIG)
    elif isinstance(raw, dict):
        saved = raw
    else:
        return dict(DEFAULT_THEME_CONFIG)
    merged = dict(DEFAULT_THEME_CONFIG)
    merged.update(saved)
    return merged


def save_config(config: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_THEME_CONFIG)
    merged.update(config)
    if merged["preset"] not in PRESET_THEMES:
        raise ValidationError(f"preset must be one of {list(PRESET_THEMES)}")
    if not isinstance(merged["overrides"], dict):
        raise ValidationError("overrides must be an object")
    if len(merged.get("custom_css") or "") > 10000:
        raise ValidationError("custom_css must be ≤ 10000 chars")
    with write_transaction() as s:
        existing = s.query(Setting).filter_by(key="custom_theme").first()
        if existing:
            existing.value = json.dumps(merged, ensure_ascii=False)
        else:
            s.add(Setting(key="custom_theme", value=json.dumps(merged, ensure_ascii=False)))
    return merged


def reset_config() -> dict[str, Any]:
    """Reset to defaults."""
    with write_transaction() as s:
        existing = s.query(Setting).filter_by(key="custom_theme").first()
        if existing:
            s.delete(existing)
    return dict(DEFAULT_THEME_CONFIG)


# ---------------------------------------------------------------------------
# CSS generation
# ---------------------------------------------------------------------------

def generate_css(config: dict[str, Any] | None = None) -> str:
    """Generate the CSS to inject into base.html.

    Output is a <style> block (or empty string if no customizations).
    """
    config = config or get_config()
    if not config:
        return ""
    # Only skip if truly default (dark preset, no overrides, no custom CSS, no font changes)
    if (config.get("preset", "dark") == "dark"
        and not config.get("overrides")
        and not config.get("font_family")
        and not config.get("base_font_size")
        and not config.get("custom_css")):
        return ""
    parts: list[str] = []
    # Apply preset (overrides the data-theme attribute's variables)
    preset_key = config.get("preset", "dark")
    preset = PRESET_THEMES.get(preset_key, PRESET_THEMES["dark"])
    vars_css: list[str] = []
    for k, v in preset["vars"].items():
        vars_css.append(f"  {k}: {v};")
    # Apply overrides on top
    for k, v in (config.get("overrides") or {}).items():
        if k.startswith("--"):
            vars_css.append(f"  {k}: {v};")
    if vars_css:
        parts.append(f":root, [data-theme='dark'], [data-theme='light'] {{\n" + "\n".join(vars_css) + "\n}")
    # Font family override
    if config.get("font_family"):
        ff = config["font_family"]
        parts.append(f"body, .content, .card, .form-input, .form-select, .form-textarea {{ font-family: {ff} !important; }}")
    # Base font size override
    if config.get("base_font_size"):
        parts.append(f"html {{ font-size: {config['base_font_size']} !important; }}")
    # Custom CSS
    if config.get("custom_css"):
        parts.append(config["custom_css"])
    if not parts:
        return ""
    return "\n".join(parts)


def get_preset_list() -> list[dict[str, Any]]:
    return [
        {"key": k, "label": v["label"], "icon": v["icon"]}
        for k, v in PRESET_THEMES.items()
    ]
