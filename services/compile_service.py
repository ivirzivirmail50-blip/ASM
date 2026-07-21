"""Manuscript Compile Wizard — build a publication-ready manuscript with front matter.

Distinct from export_service.export_manuscript() (which is a simple
chapter concatenation). The Compile Wizard lets the writer configure:

- Front matter: title page, copyright notice, dedication, epigraph,
  acknowledgments, table of contents
- Chapter formatting: include chapter numbers, scene break markers,
  drop caps, chapter separators
- Back matter: author note, about the author, other books
- Output format: txt, md, html, docx (pdf/epub reuses existing infrastructure)

The compile config is persisted as a Setting so the writer doesn't have
to re-configure each time.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.chapter import Chapter
from models.settings import Setting
from services._common import current_project_id, dump_json, load_json

log = logging.getLogger("asm.compile")


DEFAULT_COMPILE_CONFIG: dict[str, Any] = {
    # Front matter
    "include_title_page": True,
    "include_copyright": True,
    "copyright_text": "© 2026 by Author Name. All rights reserved.",
    "include_dedication": False,
    "dedication_text": "For those who believed in this story before it existed.",
    "include_epigraph": False,
    "epigraph_text": "",
    "epigraph_attribution": "",
    "include_acknowledgments": False,
    "acknowledgments_text": "",
    "include_toc": True,
    # Chapter formatting
    "chapter_number_format": "chapter",  # none / chapter / number / chapter_number
    "chapter_title_prefix": "",
    "scene_break_marker": "* * *",
    "include_synopsis": False,  # only for writer reference, not publication
    # Back matter
    "include_author_note": False,
    "author_note_text": "",
    "include_about_author": False,
    "about_author_text": "",
    "include_other_books": False,
    "other_books_text": "",
    # Chapter selection
    "chapter_status_filter": "all",  # all / draft / revised / final
    # Output
    "format": "html",  # txt / md / html / docx
}


def get_config() -> dict[str, Any]:
    """Load the compile config from settings, merged with defaults."""
    with read_session() as s:
        raw = Setting.get(s, "compile_config", "")
    if not raw:
        return dict(DEFAULT_COMPILE_CONFIG)
    # Setting.get already parses JSON, so raw is usually a dict.
    # Handle both dict and string for safety.
    if isinstance(raw, str):
        try:
            saved = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return dict(DEFAULT_COMPILE_CONFIG)
    elif isinstance(raw, dict):
        saved = raw
    else:
        return dict(DEFAULT_COMPILE_CONFIG)
    merged = dict(DEFAULT_COMPILE_CONFIG)
    merged.update(saved)
    return merged


def save_config(config: dict[str, Any]) -> dict[str, Any]:
    """Persist the compile config."""
    merged = dict(DEFAULT_COMPILE_CONFIG)
    merged.update(config)
    # Validate
    if merged["chapter_number_format"] not in ("none", "chapter", "number", "chapter_number"):
        raise ValidationError("chapter_number_format must be none/chapter/number/chapter_number")
    if merged["format"] not in ("txt", "md", "html", "docx", "pdf", "epub"):
        raise ValidationError("format must be txt/md/html/docx/pdf/epub")
    if merged["chapter_status_filter"] not in ("all", "draft", "revised", "final"):
        raise ValidationError("chapter_status_filter must be all/draft/revised/final")
    with write_transaction() as s:
        existing = s.query(Setting).filter_by(key="compile_config").first()
        if existing:
            existing.value = json.dumps(merged, ensure_ascii=False)
        else:
            s.add(Setting(key="compile_config", value=json.dumps(merged, ensure_ascii=False)))
    return merged


def _filter_chapters(config: dict[str, Any]) -> list[Chapter]:
    """Return chapters matching the status filter, in sort order."""
    status_filter = config.get("chapter_status_filter", "all")
    with read_session() as s:
        q = select(Chapter).where(Chapter.project_id == current_project_id(s))
        if status_filter != "all":
            q = q.where(Chapter.status == status_filter)
        chapters = list(s.scalars(q.order_by(Chapter.sort_order.asc())))
        return chapters


def _format_chapter_title(ch: Chapter, idx: int, config: dict[str, Any]) -> str:
    """Format the chapter title according to config."""
    fmt = config.get("chapter_number_format", "chapter")
    prefix = config.get("chapter_title_prefix", "")
    parts: list[str] = []
    if fmt == "chapter":
        parts.append(f"Chapter {idx}")
        if ch.title:
            parts.append(ch.title)
    elif fmt == "number":
        parts.append(str(idx))
        if ch.title:
            parts.append(ch.title)
    elif fmt == "chapter_number":
        parts.append(f"Chapter {idx}: {ch.title}" if ch.title else f"Chapter {idx}")
    else:  # none
        if ch.title:
            parts.append(ch.title)
    title = " — ".join(parts) if fmt == "chapter" and len(parts) > 1 else " — ".join(parts)
    if prefix and fmt != "none":
        return f"{prefix}{title}"
    return title


def compile_manuscript(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compile the manuscript with front matter.

    Returns a dict with: title, author, sections (list of {type, heading, body, html}),
    total_words, chapter_count.
    """
    config = config or get_config()
    chapters = _filter_chapters(config)
    with read_session() as s:
        title = Setting.get(s, "story_title", "My Story")
        author = Setting.get(s, "story_author", "Author")
    sections: list[dict[str, Any]] = []

    # ---- Front matter ----
    if config.get("include_title_page"):
        sections.append({
            "type": "title_page",
            "heading": "",
            "body": f"{title}\nby {author}",
            "html": f"<div class='title-page'><h1>{_esc(title)}</h1><p class='author'>by {_esc(author)}</p></div>",
        })
    if config.get("include_copyright"):
        ct = config.get("copyright_text", "")
        sections.append({
            "type": "copyright",
            "heading": "",
            "body": ct,
            "html": f"<div class='copyright'><p>{_esc(ct).replace(chr(10), '<br>')}</p></div>",
        })
    if config.get("include_dedication"):
        dt = config.get("dedication_text", "")
        sections.append({
            "type": "dedication",
            "heading": "",
            "body": dt,
            "html": f"<div class='dedication'><p><em>{_esc(dt).replace(chr(10), '<br>')}</em></p></div>",
        })
    if config.get("include_epigraph"):
        et = config.get("epigraph_text", "")
        ea = config.get("epigraph_attribution", "")
        body = et + (f"\n— {ea}" if ea else "")
        sections.append({
            "type": "epigraph",
            "heading": "",
            "body": body,
            "html": f"<div class='epigraph'><blockquote>{_esc(et).replace(chr(10), '<br>')}</blockquote>{f'<p>— {_esc(ea)}</p>' if ea else ''}</div>",
        })
    if config.get("include_toc"):
        toc_lines: list[str] = []
        toc_html: list[str] = ["<ul class='toc'>"]
        for i, ch in enumerate(chapters, start=1):
            ct = _format_chapter_title(ch, i, config)
            toc_lines.append(f"{ct}")
            toc_html.append(f"<li>{_esc(ct)}</li>")
        toc_html.append("</ul>")
        sections.append({
            "type": "toc",
            "heading": "Table of Contents",
            "body": "\n".join(toc_lines),
            "html": "".join(toc_html),
        })
    if config.get("include_acknowledgments"):
        at = config.get("acknowledgments_text", "")
        sections.append({
            "type": "acknowledgments",
            "heading": "Acknowledgments",
            "body": at,
            "html": f"<div class='acknowledgments'><h2>Acknowledgments</h2><p>{_esc(at).replace(chr(10), '<br>')}</p></div>",
        })

    # ---- Chapters ----
    total_words = 0
    for i, ch in enumerate(chapters, start=1):
        ct = _format_chapter_title(ch, i, config)
        content = ch.content or ""
        # Apply scene break marker if set
        marker = config.get("scene_break_marker", "")
        if marker:
            # Replace 3+ newlines with the marker
            import re
            content = re.sub(r"\n{3,}", f"\n\n{marker}\n\n", content)
        wc = len(content.split()) if content else 0
        total_words += wc
        sections.append({
            "type": "chapter",
            "heading": ct,
            "body": content,
            "html": f"<div class='chapter'><h2>{_esc(ct)}</h2><div class='chapter-content'>{_md_to_html(content)}</div></div>",
            "word_count": wc,
            "chapter_id": ch.id,
        })

    # ---- Back matter ----
    if config.get("include_author_note"):
        an = config.get("author_note_text", "")
        sections.append({
            "type": "author_note",
            "heading": "Author's Note",
            "body": an,
            "html": f"<div class='author-note'><h2>Author's Note</h2><p>{_esc(an).replace(chr(10), '<br>')}</p></div>",
        })
    if config.get("include_about_author"):
        aa = config.get("about_author_text", "")
        sections.append({
            "type": "about_author",
            "heading": "About the Author",
            "body": aa,
            "html": f"<div class='about-author'><h2>About the Author</h2><p>{_esc(aa).replace(chr(10), '<br>')}</p></div>",
        })
    if config.get("include_other_books"):
        ob = config.get("other_books_text", "")
        sections.append({
            "type": "other_books",
            "heading": "Other Books by the Author",
            "body": ob,
            "html": f"<div class='other-books'><h2>Other Books</h2><p>{_esc(ob).replace(chr(10), '<br>')}</p></div>",
        })

    return {
        "title": title,
        "author": author,
        "sections": sections,
        "total_words": total_words,
        "chapter_count": len(chapters),
        "config": config,
    }


def render_compiled(compiled: dict[str, Any], fmt: str | None = None) -> tuple[bytes, str, str]:
    """Render the compiled manuscript into the requested format.

    Returns (content_bytes, mime_type, filename).
    """
    fmt = (fmt or compiled["config"].get("format", "html")).lower()
    title = compiled["title"]
    author = compiled["author"]
    sections = compiled["sections"]
    safe_title = _safe_filename(title)

    if fmt == "txt":
        parts: list[str] = []
        for sec in sections:
            if sec["heading"]:
                parts.append(f"\n{'=' * 60}\n{sec['heading']}\n{'=' * 60}\n\n")
            else:
                parts.append(f"\n{sec['body']}\n\n")
        return "".join(parts).encode("utf-8"), "text/plain", f"{safe_title}.txt"

    if fmt == "md":
        parts = [f"# {title}\n\n*by {author}*\n\n"]
        for sec in sections:
            if sec["heading"]:
                parts.append(f"\n## {sec['heading']}\n\n")
            parts.append(f"{sec['body']}\n\n---\n")
        return "".join(parts).encode("utf-8"), "text/markdown", f"{safe_title}.md"

    if fmt == "html":
        css = """
        body { font-family: Georgia, serif; max-width: 720px; margin: 2rem auto; padding: 1rem; line-height: 1.7; color: #1a1a1a; }
        .title-page { text-align: center; padding: 6rem 0; page-break-after: always; }
        .title-page h1 { font-size: 2.5rem; margin-bottom: 1rem; }
        .title-page .author { font-size: 1.2rem; color: #555; }
        .copyright { text-align: center; font-size: 0.85rem; color: #555; page-break-after: always; padding: 4rem 0; }
        .dedication { text-align: center; font-style: italic; padding: 4rem 0; page-break-after: always; }
        .epigraph { text-align: center; padding: 3rem 0; page-break-after: always; }
        .epigraph blockquote { font-style: italic; }
        .toc { page-break-after: always; }
        .toc li { margin: 0.5rem 0; }
        .chapter { page-break-before: always; }
        .chapter h2 { text-align: center; border-bottom: 1px solid #ccc; padding-bottom: 0.5rem; margin-bottom: 2rem; }
        .acknowledgments, .author-note, .about-author, .other-books { page-break-before: always; }
        """
        parts = [f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{_esc(title)}</title>
<style>{css}</style></head><body>"""]
        for sec in sections:
            parts.append(sec["html"])
        parts.append("</body></html>")
        return "".join(parts).encode("utf-8"), "text/html", f"{safe_title}.html"

    if fmt == "docx":
        return _compiled_to_docx(compiled), \
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", \
            f"{safe_title}.docx"

    raise ValidationError(f"Compile format '{fmt}' not supported. Use txt/md/html/docx.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    """HTML-escape a string."""
    if not s:
        return ""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&#39;"))


def _md_to_html(text: str) -> str:
    """Minimal markdown to HTML (paragraphs + line breaks)."""
    if not text:
        return ""
    # Escape HTML first
    s = _esc(text)
    # Bold
    s = s.replace("**", "<strong>", 1) if "**" in s else s
    # Italic
    s = s.replace("*", "<em>", 1) if "*" in s else s
    # Paragraphs
    paras = s.split("\n\n")
    return "".join(f"<p>{p.strip().replace(chr(10), '<br>')}</p>" for p in paras if p.strip())


def _safe_filename(s: str) -> str:
    """Make a string safe for use as a filename."""
    if not s:
        return "manuscript"
    import re
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    s = re.sub(r"[-\s]+", "-", s)
    return s[:60] or "manuscript"


def _compiled_to_docx(compiled: dict[str, Any]) -> bytes:
    """Convert the compiled manuscript to a DOCX file."""
    try:
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        raise NotFoundError("python-docx not installed. Run: pip install python-docx")

    doc = Document()
    # Set default style
    style = doc.styles["Normal"]
    style.font.name = "Georgia"
    style.font.size = Pt(12)

    for sec in compiled["sections"]:
        stype = sec["type"]
        if stype == "title_page":
            doc.add_paragraph()
            doc.add_paragraph()
            h = doc.add_paragraph(compiled["title"])
            h.alignment = WD_ALIGN_PARAGRAPH.CENTER
            h.runs[0].font.size = Pt(28)
            a = doc.add_paragraph(f"by {compiled['author']}")
            a.alignment = WD_ALIGN_PARAGRAPH.CENTER
            a.runs[0].font.size = Pt(14)
            doc.add_page_break()
        elif stype == "copyright":
            p = doc.add_paragraph(sec["body"])
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.runs[0].font.size = Pt(9)
            doc.add_page_break()
        elif stype == "dedication":
            p = doc.add_paragraph(sec["body"])
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.runs[0].font.italic = True
            doc.add_page_break()
        elif stype == "epigraph":
            p = doc.add_paragraph(sec["body"])
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.runs[0].font.italic = True
            doc.add_page_break()
        elif stype == "toc":
            doc.add_heading("Table of Contents", level=1)
            for line in sec["body"].split("\n"):
                if line.strip():
                    doc.add_paragraph(line.strip())
            doc.add_page_break()
        elif stype == "acknowledgments":
            doc.add_heading("Acknowledgments", level=1)
            doc.add_paragraph(sec["body"])
            doc.add_page_break()
        elif stype == "chapter":
            h = doc.add_heading(sec["heading"], level=1)
            h.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for para in sec["body"].split("\n\n"):
                if para.strip():
                    doc.add_paragraph(para.strip())
            doc.add_page_break()
        elif stype == "author_note":
            doc.add_heading("Author's Note", level=1)
            doc.add_paragraph(sec["body"])
            doc.add_page_break()
        elif stype == "about_author":
            doc.add_heading("About the Author", level=1)
            doc.add_paragraph(sec["body"])
            doc.add_page_break()
        elif stype == "other_books":
            doc.add_heading("Other Books by the Author", level=1)
            doc.add_paragraph(sec["body"])

    import io
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
