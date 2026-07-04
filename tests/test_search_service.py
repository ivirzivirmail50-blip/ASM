"""Tests for search_service: FTS5 + LIKE fallback."""
import pytest

from services import chapter_service, character_service, world_service, search_service


def test_search_chapters_by_title():
    chapter_service.create_chapter(title="Unique Chapter Title XYZ", content="content")
    results = search_service.search_chapters("Unique")
    assert any("Unique" in r["title"] for r in results)


def test_search_chapters_by_content():
    chapter_service.create_chapter(title="Random", content="This contains specialtoken foobar.")
    results = search_service.search_chapters("specialtoken")
    assert any("Random" in r["title"] for r in results)


def test_search_characters_by_name():
    character_service.create_character(name="ZarathanSpecialist", role="minor")
    results = search_service.search_characters("ZarathanSpecialist")
    assert any("ZarathanSpecialist" in r["title"] for r in results)


def test_search_world_entries():
    world_service.create_entry(type_="location", name="Special City Name", content="content")
    results = search_service.search_world("Special City")
    assert any("Special City" in r["title"] for r in results)


def test_search_all_returns_three_modules():
    chapter_service.create_chapter(title="SearchAll Chapter", content="content")
    results = search_service.search_all("SearchAll")
    assert "chapters" in results
    assert "characters" in results
    assert "world" in results


def test_search_empty_query_returns_empty():
    results = search_service.search_all("")
    assert results == {"chapters": [], "characters": [], "world": []}


def test_search_no_matches_returns_empty():
    results = search_service.search_chapters("this-should-not-match-anything-xyz123")
    assert results == []
