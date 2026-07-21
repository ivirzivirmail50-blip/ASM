"""Tests for Manuscript Compile Wizard (v4.4)."""
from __future__ import annotations

import pytest

from services import compile_service as svc


def test_get_config_returns_defaults():
    config = svc.get_config()
    assert config["include_title_page"] is True
    assert config["chapter_number_format"] == "chapter"
    assert config["format"] == "html"


def test_save_config_persists():
    saved = svc.save_config({
        "preset": "dark",
        "include_dedication": True,
        "dedication_text": "For my cat",
        "format": "docx",
    })
    assert saved["include_dedication"] is True
    assert saved["dedication_text"] == "For my cat"
    # Verify it's loaded back
    loaded = svc.get_config()
    assert loaded["include_dedication"] is True
    assert loaded["dedication_text"] == "For my cat"


def test_save_config_invalid_format():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.save_config({"format": "bogus"})


def test_save_config_invalid_chapter_number_format():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.save_config({"chapter_number_format": "bogus"})


def test_save_config_invalid_status_filter():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.save_config({"chapter_status_filter": "bogus"})


def test_compile_manuscript_with_defaults():
    from services.chapter_service import create_chapter
    create_chapter(title="Test", content="Some content for testing.")
    compiled = svc.compile_manuscript()
    assert compiled["chapter_count"] >= 1
    assert compiled["total_words"] > 0
    assert len(compiled["sections"]) > 0
    # Should have title page + chapters at minimum
    section_types = [s["type"] for s in compiled["sections"]]
    assert "title_page" in section_types
    assert "chapter" in section_types


def test_compile_with_dedication():
    from services.chapter_service import create_chapter
    create_chapter(title="Ded Test", content="Content.")
    config = svc.get_config()
    config["include_dedication"] = True
    config["dedication_text"] = "For my readers"
    compiled = svc.compile_manuscript(config)
    section_types = [s["type"] for s in compiled["sections"]]
    assert "dedication" in section_types


def test_compile_with_toc():
    from services.chapter_service import create_chapter
    create_chapter(title="TOC Test 1", content="Content 1.")
    create_chapter(title="TOC Test 2", content="Content 2.")
    config = svc.get_config()
    config["include_toc"] = True
    compiled = svc.compile_manuscript(config)
    toc_section = next(s for s in compiled["sections"] if s["type"] == "toc")
    assert "TOC Test 1" in toc_section["body"]
    assert "TOC Test 2" in toc_section["body"]


def test_compile_with_back_matter():
    from services.chapter_service import create_chapter
    create_chapter(title="BM Test", content="Content.")
    config = svc.get_config()
    config["include_author_note"] = True
    config["author_note_text"] = "Thanks for reading"
    config["include_about_author"] = True
    config["about_author_text"] = "The author lives somewhere"
    compiled = svc.compile_manuscript(config)
    section_types = [s["type"] for s in compiled["sections"]]
    assert "author_note" in section_types
    assert "about_author" in section_types


def test_compile_chapter_number_format_none():
    from services.chapter_service import create_chapter
    create_chapter(title="No Num", content="Content.")
    config = svc.get_config()
    config["chapter_number_format"] = "none"
    compiled = svc.compile_manuscript(config)
    chapter_section = next(s for s in compiled["sections"] if s["type"] == "chapter")
    assert "Chapter 1" not in chapter_section["heading"]
    assert "No Num" in chapter_section["heading"]


def test_compile_chapter_number_format_chapter():
    from services.chapter_service import create_chapter
    create_chapter(title="With Num", content="Content.")
    config = svc.get_config()
    config["chapter_number_format"] = "chapter"
    compiled = svc.compile_manuscript(config)
    chapter_section = next(s for s in compiled["sections"] if s["type"] == "chapter")
    assert "Chapter 1" in chapter_section["heading"]


def test_compile_status_filter():
    from services.chapter_service import create_chapter
    create_chapter(title="Draft", content="Draft content.", status="draft")
    create_chapter(title="Final", content="Final content.", status="final")
    config = svc.get_config()
    config["chapter_status_filter"] = "final"
    compiled = svc.compile_manuscript(config)
    assert compiled["chapter_count"] == 1
    chapter_section = next(s for s in compiled["sections"] if s["type"] == "chapter")
    assert "Final" in chapter_section["heading"]


def test_render_compiled_html():
    from services.chapter_service import create_chapter
    create_chapter(title="Render Test", content="Some content.")
    compiled = svc.compile_manuscript()
    content, mime, filename = svc.render_compiled(compiled, "html")
    assert mime == "text/html"
    assert filename.endswith(".html")
    assert b"<html" in content
    assert b"Render Test" in content


def test_render_compiled_txt():
    from services.chapter_service import create_chapter
    create_chapter(title="TXT Test", content="Some text content.")
    compiled = svc.compile_manuscript()
    content, mime, filename = svc.render_compiled(compiled, "txt")
    assert mime == "text/plain"
    assert filename.endswith(".txt")
    assert b"TXT Test" in content


def test_render_compiled_md():
    from services.chapter_service import create_chapter
    create_chapter(title="MD Test", content="Some markdown content.")
    compiled = svc.compile_manuscript()
    content, mime, filename = svc.render_compiled(compiled, "md")
    assert mime == "text/markdown"
    assert filename.endswith(".md")
    assert b"# " in content  # title heading


def test_render_compiled_invalid_format():
    from core.errors import ValidationError
    compiled = svc.compile_manuscript()
    with pytest.raises(ValidationError):
        svc.render_compiled(compiled, "bogus")


def test_scene_break_marker_applied():
    from services.chapter_service import create_chapter
    create_chapter(title="Marker Test", content="Scene 1.\n\n\nScene 2.")
    config = svc.get_config()
    config["scene_break_marker"] = "---"
    compiled = svc.compile_manuscript(config)
    chapter_section = next(s for s in compiled["sections"] if s["type"] == "chapter")
    assert "---" in chapter_section["body"]


def test_format_chapter_title():
    from models.chapter import Chapter
    from services.chapter_service import create_chapter
    ch = create_chapter(title="My Title", content="x")
    config = {"chapter_number_format": "chapter_number"}
    title = svc._format_chapter_title(ch, 1, config)
    assert "Chapter 1" in title
    assert "My Title" in title


def test_safe_filename():
    assert svc._safe_filename("My Story!!!") == "my-story"
    assert svc._safe_filename("") == "manuscript"
