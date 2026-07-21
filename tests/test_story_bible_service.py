"""Tests for Story Bible Auto-Generator (v4.5)."""
from __future__ import annotations

import json

import pytest

from services import story_bible_service as svc


def test_gather_data_returns_structure():
    data = svc.gather_data()
    assert "title" in data
    assert "author" in data
    assert "chapters" in data
    assert "characters" in data
    assert "relationships" in data
    assert "world_entries" in data
    assert "timeline" in data
    assert "glossary" in data
    assert "stats" in data


def test_gather_data_stats():
    data = svc.gather_data()
    st = data["stats"]
    assert "chapter_count" in st
    assert "character_count" in st
    assert "world_count" in st
    assert "total_words" in st


def test_gather_data_includes_chapters():
    from services.chapter_service import create_chapter
    create_chapter(title="Bible Test", content="Content here.")
    data = svc.gather_data()
    assert any(c["title"] == "Bible Test" for c in data["chapters"])


def test_gather_data_includes_characters():
    from services.character_service import create_character
    create_character(name="Bible Hero", role="protagonist")
    data = svc.gather_data()
    assert any(c["name"] == "Bible Hero" for c in data["characters"])


def test_gather_data_includes_world():
    from services import world_service
    world_service.create_entry(type_="location", name="Bible City")
    data = svc.gather_data()
    assert any(e["name"] == "Bible City" for e in data["world_entries"])


def test_render_html():
    data = svc.gather_data()
    html = svc.render_html(data)
    assert "<html" in html
    assert data["title"] in html
    assert "Plot Summary" in html
    assert "Characters" in html


def test_render_txt():
    data = svc.gather_data()
    txt = svc.render_txt(data)
    assert data["title"] in txt
    assert "PLOT SUMMARY" in txt
    assert "CHARACTERS" in txt


def test_render_md():
    data = svc.gather_data()
    md = svc.render_md(data)
    assert f"# {data['title']}" in md
    assert "## Plot Summary" in md
    assert "## Characters" in md


def test_render_html_with_data():
    from services.chapter_service import create_chapter
    from services.character_service import create_character
    create_chapter(title="Render Test Ch", content="Content with words.")
    create_character(name="Render Hero", role="protagonist")
    data = svc.gather_data()
    html = svc.render_html(data)
    assert "Render Test Ch" in html
    assert "Render Hero" in html


def test_render_returns_tuple():
    data = svc.gather_data()
    for fmt in ["html", "txt", "md", "json"]:
        content, mime, filename = svc.render(data, fmt)
        assert isinstance(content, bytes)
        assert isinstance(mime, str)
        assert isinstance(filename, str)
        assert filename


def test_render_invalid_format():
    data = svc.gather_data()
    with pytest.raises(ValueError):
        svc.render(data, "bogus")


def test_render_json_valid():
    data = svc.gather_data()
    content, _, _ = svc.render(data, "json")
    parsed = json.loads(content.decode("utf-8"))
    assert parsed["title"] == data["title"]


def test_esc_escapes_html():
    assert svc._esc("<script>") == "&lt;script&gt;"
    assert svc._esc("") == ""
    assert svc._esc("plain") == "plain"


def test_render_html_contains_glossary_section():
    data = svc.gather_data()
    html = svc.render_html(data)
    assert "Glossary" in html


def test_render_html_contains_timeline_section():
    data = svc.gather_data()
    html = svc.render_html(data)
    assert "Timeline" in html


def test_render_html_contains_relationships_section():
    data = svc.gather_data()
    html = svc.render_html(data)
    assert "Relationships" in html
