"""Tests for export_service: all export formats."""
import io
import json
import pytest

from services import export_service, chapter_service, character_service, world_service


class TestChapterExport:
    def test_export_txt(self):
        ch = chapter_service.create_chapter(title="Export Test", content="Hello world content.")
        content, mime, filename = export_service.export_chapter(ch.id, "txt")
        assert b"Hello world" in content
        assert filename.endswith(".txt")
        assert "text" in mime

    def test_export_md(self):
        ch = chapter_service.create_chapter(title="MD Test", content="Content here.")
        content, mime, filename = export_service.export_chapter(ch.id, "md")
        assert b"# MD Test" in content
        assert filename.endswith(".md")

    def test_export_html(self):
        ch = chapter_service.create_chapter(title="HTML Test", content="Some content.")
        content, mime, filename = export_service.export_chapter(ch.id, "html")
        assert b"<!DOCTYPE html>" in content
        assert b"HTML Test" in content
        assert filename.endswith(".html")

    def test_export_docx(self):
        ch = chapter_service.create_chapter(title="DOCX Test", content="Doc content.")
        content, mime, filename = export_service.export_chapter(ch.id, "docx")
        assert filename.endswith(".docx")
        assert len(content) > 1000  # DOCX has minimum size

    def test_export_pdf(self):
        ch = chapter_service.create_chapter(title="PDF Test", content="PDF content here.")
        content, mime, filename = export_service.export_chapter(ch.id, "pdf")
        assert filename.endswith(".pdf")
        assert content.startswith(b"%PDF")

    def test_export_json(self):
        ch = chapter_service.create_chapter(title="JSON Test", content="JSON content.")
        content, mime, filename = export_service.export_chapter(ch.id, "json")
        data = json.loads(content)
        assert data["title"] == "JSON Test"
        assert data["content"] == "JSON content."

    def test_export_unknown_format(self):
        ch = chapter_service.create_chapter(title="X", content="x")
        from core.errors import NotFoundError
        with pytest.raises(NotFoundError):
            export_service.export_chapter(ch.id, "xyz")


class TestManuscriptExport:
    def test_manuscript_txt(self):
        chapter_service.create_chapter(title="Ch 1", content="First chapter.")
        chapter_service.create_chapter(title="Ch 2", content="Second chapter.")
        content, mime, filename = export_service.export_manuscript("txt")
        assert b"First chapter" in content
        assert b"Second chapter" in content

    def test_manuscript_pdf(self):
        chapter_service.create_chapter(title="PDF Ch", content="Content.")
        content, mime, filename = export_service.export_manuscript("pdf")
        assert content.startswith(b"%PDF")

    def test_manuscript_epub(self):
        chapter_service.create_chapter(title="EPUB Ch", content="Content.")
        content, mime, filename = export_service.export_manuscript("epub")
        assert filename.endswith(".epub")
        # EPUB is a ZIP — starts with PK
        assert content.startswith(b"PK")

    def test_manuscript_docx(self):
        chapter_service.create_chapter(title="DOCX Ch", content="Content.")
        content, mime, filename = export_service.export_manuscript("docx")
        assert filename.endswith(".docx")


class TestCharacterSheetExport:
    def test_character_sheet_txt(self):
        ch = character_service.create_character(name="Hero", role="protagonist")
        content, mime, filename = export_service.export_character_sheet(ch.id, "txt")
        assert b"Hero" in content

    def test_character_sheet_pdf(self):
        ch = character_service.create_character(name="PDF Hero", role="minor")
        content, mime, filename = export_service.export_character_sheet(ch.id, "pdf")
        assert content.startswith(b"%PDF")

    def test_character_sheet_docx(self):
        ch = character_service.create_character(name="DOCX Hero", role="minor")
        content, mime, filename = export_service.export_character_sheet(ch.id, "docx")
        assert filename.endswith(".docx")

    def test_character_sheet_json(self):
        ch = character_service.create_character(
            name="JSON Hero", role="protagonist",
            physical="Tall and strong",
        )
        content, mime, filename = export_service.export_character_sheet(ch.id, "json")
        data = json.loads(content)
        assert data["name"] == "JSON Hero"
        assert data["physical"] == "Tall and strong"


class TestWorldBibleExport:
    def test_world_bible_txt(self):
        world_service.create_entry(type_="location", name="City", content="A city.")
        world_service.create_entry(type_="lore", name="Myth", content="A myth.")
        content, mime, filename = export_service.export_world_bible("txt")
        assert b"City" in content
        assert b"Myth" in content

    def test_world_bible_pdf(self):
        world_service.create_entry(type_="location", name="PDF Place", content="x")
        content, mime, filename = export_service.export_world_bible("pdf")
        assert content.startswith(b"%PDF")

    def test_world_bible_docx(self):
        world_service.create_entry(type_="faction", name="Guild", content="x")
        content, mime, filename = export_service.export_world_bible("docx")
        assert filename.endswith(".docx")

    def test_world_bible_json(self):
        world_service.create_entry(type_="location", name="JSON Place", content="x")
        content, mime, filename = export_service.export_world_bible("json")
        data = json.loads(content)
        assert "entries" in data


class TestFullProjectExport:
    def test_full_project_pdf(self):
        chapter_service.create_chapter(title="Full Ch", content="x")
        character_service.create_character(name="Full Char", role="minor")
        world_service.create_entry(type_="location", name="Full Place", content="x")
        content, mime, filename = export_service.export_full_project("pdf")
        assert content.startswith(b"%PDF")

    def test_full_project_docx(self):
        chapter_service.create_chapter(title="Full Ch 2", content="x")
        content, mime, filename = export_service.export_full_project("docx")
        assert filename.endswith(".docx")
