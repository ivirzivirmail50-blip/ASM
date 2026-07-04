"""Scrivener-style compile presets — different export configurations.

Each preset defines font, size, spacing, margins, title page, page breaks,
heading style, etc. Users can select a preset before exporting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompilePreset:
    """A single compile preset configuration."""
    key: str
    name: str
    description: str
    font: str = "Courier"
    font_size: int = 12
    line_spacing: float = 2.0
    margins: float = 1.0
    title_page: bool = True
    page_breaks_between_chapters: bool = True
    chapter_heading_centered: bool = True
    first_line_indent: float = 0.5
    include_synopsis: bool = False
    include_word_count: bool = True
    toc: bool = False
    header_text: str = ""
    footer_text: str = ""
    chapter_prefix: str = "Chapter"
    color_scheme: str = "dark"  # for HTML exports


PRESETS: list[CompilePreset] = [
    CompilePreset(
        key="manuscript",
        name="Industry Standard Manuscript",
        description="12pt Courier, double-spaced, 1-inch margins. For submissions to publishers.",
        font="Courier", font_size=12, line_spacing=2.0, margins=1.0,
        title_page=True, page_breaks_between_chapters=True,
        chapter_heading_centered=True, first_line_indent=0.5,
        include_word_count=True, toc=False,
    ),
    CompilePreset(
        key="beta_reader",
        name="Beta Reader Copy",
        description="Readable font, 1.5 spacing, no title page. Easy to read for feedback.",
        font="Times-Roman", font_size=12, line_spacing=1.5, margins=1.0,
        title_page=False, page_breaks_between_chapters=True,
        chapter_heading_centered=False, first_line_indent=0.3,
        include_synopsis=True, include_word_count=False, toc=False,
        header_text="{author} — {title} — Chapter {n}",
    ),
    CompilePreset(
        key="ebook",
        name="E-book Ready",
        description="Clean formatting for EPUB conversion. Minimal styling, flowing text.",
        font="Times-Roman", font_size=11, line_spacing=1.15, margins=0.75,
        title_page=True, page_breaks_between_chapters=True,
        chapter_heading_centered=True, first_line_indent=0.25,
        include_word_count=False, toc=True,
    ),
    CompilePreset(
        key="pdf_book",
        name="PDF Book (Print Ready)",
        description="Professional book layout with TOC, page numbers, headers.",
        font="Times-Roman", font_size=11, line_spacing=1.4, margins=0.9,
        title_page=True, page_breaks_between_chapters=True,
        chapter_heading_centered=True, first_line_indent=0.3,
        include_word_count=False, toc=True,
        header_text="{title}",
        footer_text="{page}",
    ),
    CompilePreset(
        key="blog_post",
        name="Blog Post (HTML)",
        description="Web-optimized HTML with CSS styling, no page breaks.",
        font="Helvetica", font_size=14, line_spacing=1.6, margins=0.5,
        title_page=False, page_breaks_between_chapters=False,
        chapter_heading_centered=True, first_line_indent=0,
        include_word_count=False, toc=False,
        color_scheme="light",
    ),
    CompilePreset(
        key="workshop",
        name="Workshop / Critique Copy",
        description="Double-spaced, numbered lines, wide margins for annotations.",
        font="Courier", font_size=11, line_spacing=2.0, margins=1.25,
        title_page=False, page_breaks_between_chapters=False,
        chapter_heading_centered=True, first_line_indent=0.5,
        include_synopsis=True, include_word_count=True, toc=False,
    ),
]


def get_all_presets() -> list[dict[str, Any]]:
    """Return all presets as a list of dicts."""
    return [
        {
            "key": p.key, "name": p.name, "description": p.description,
            "font": p.font, "font_size": p.font_size,
            "line_spacing": p.line_spacing, "margins": p.margins,
            "title_page": p.title_page,
            "page_breaks": p.page_breaks_between_chapters,
            "toc": p.toc,
        }
        for p in PRESETS
    ]


def get_preset(key: str) -> CompilePreset | None:
    """Get a preset by key."""
    for p in PRESETS:
        if p.key == key:
            return p
    return None


def apply_preset_to_settings(preset_key: str) -> dict[str, Any]:
    """Convert a preset to settings dict that can be saved to DB.

    Returns settings keys: manuscript_font, manuscript_font_size,
    manuscript_line_spacing, manuscript_margins.
    """
    p = get_preset(preset_key)
    if not p:
        return {}
    return {
        "manuscript_font": p.font,
        "manuscript_font_size": str(p.font_size),
        "manuscript_line_spacing": str(p.line_spacing),
        "manuscript_margins": str(p.margins),
    }
