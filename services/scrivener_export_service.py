"""Export to Scrivener — generate a .scriv-compatible package.

Scrivener projects are actually folders (bundles) with a specific structure:
  MyProject.scriv/
    Files/
      Docs/
        000001.scrtext    (RTF or text content per document)
        000002.scrtext
        ...
      Binder/
        binder.xml        (project structure — which docs exist and their order)
    Settings/
      projectsettings.xml
    Searches/
    Snapshots/

This service generates a simplified version:
- Each chapter becomes a .scrtext file (plain text with Scrivener-style header)
- A binder.xml that lists all chapters in order
- A projectsettings.xml with basic project metadata

The output is a ZIP file with .scriv extension that Scrivener can import.
"""
from __future__ import annotations

import io
import logging
import os
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from core.db import read_session
from core.errors import ValidationError
from models.chapter import Chapter
from models.settings import Setting
from services._common import current_project_id, load_json

log = logging.getLogger("asm.scrivener_export")


def _safe_filename(s: str) -> str:
    import re
    s = re.sub(r"[^\w\s-]", "", s or "").strip()
    s = re.sub(r"[-\s]+", "_", s)
    return s[:60] or "untitled"


def generate_scriv_package(*, include_synopsis: bool = True,
                           include_tags: bool = True,
                           status_filter: str = "all") -> tuple[bytes, str]:
    """Generate a .scriv package as ZIP bytes.

    Returns (zip_bytes, filename).
    """
    with read_session() as s:
        pid = current_project_id(s)
        title = Setting.get(s, "story_title", "My Story")
        author = Setting.get(s, "story_author", "Author")
        q = select(Chapter).where(Chapter.project_id == pid)
        if status_filter != "all":
            q = q.where(Chapter.status == status_filter)
        chapters = list(s.scalars(q.order_by(Chapter.sort_order.asc())))

    safe_title = _safe_filename(title)
    scriv_name = f"{safe_title}.scriv"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Binder XML (project structure)
        binder_xml = _generate_binder_xml(title, chapters)
        zf.writestr(f"{scriv_name}/Files/Binder/binder.xml", binder_xml)

        # Project settings XML
        settings_xml = _generate_settings_xml(title, author)
        zf.writestr(f"{scriv_name}/Settings/projectsettings.xml", settings_xml)

        # Each chapter as a .scrtext file
        for i, ch in enumerate(chapters, start=1):
            doc_id = f"{i:06d}"
            content = ch.content or ""
            # Prepend Scrivener-style metadata header
            header_parts = [f"Title: {ch.title}"]
            if include_synopsis and ch.synopsis:
                header_parts.append(f"Synopsis: {ch.synopsis}")
            if include_tags:
                tags = load_json(ch.tags, [])
                if tags:
                    header_parts.append(f"Keywords: {', '.join(tags)}")
            header_parts.append(f"Status: {ch.status}")
            header_parts.append(f"Words: {ch.word_count or 0}")
            header_parts.append("")  # blank line before content
            scrtext = "\n".join(header_parts) + "\n" + content
            zf.writestr(f"{scriv_name}/Files/Docs/{doc_id}.scrtext", scrtext)

        # A simple notes file
        notes_content = f"Exported from Absolute Story Manager on {datetime.now(timezone.utc).isoformat()}\n"
        notes_content += f"Title: {title}\nAuthor: {author}\nChapters: {len(chapters)}\n"
        zf.writestr(f"{scriv_name}/Files/Docs/notes.txt", notes_content)

    return buf.getvalue(), f"{scriv_name}.zip"


def _generate_binder_xml(title: str, chapters: list) -> str:
    """Generate a simplified binder.xml for Scrivener compatibility."""
    import xml.etree.ElementTree as ET
    from xml.dom import minidom

    root = ET.Element("ScrivenerProject")
    root.set("Version", "1.0")

    binder = ET.SubElement(root, "Binder")

    # Draft folder (manuscript)
    draft = ET.SubElement(binder, "BinderItem")
    draft.set("ID", "draft")
    draft.set("Type", "Folder")
    title_el = ET.SubElement(draft, "Title")
    title_el.text = "Draft"
    children = ET.SubElement(draft, "Children")

    for i, ch in enumerate(chapters, start=1):
        doc_id = f"{i:06d}"
        item = ET.SubElement(children, "BinderItem")
        item.set("ID", doc_id)
        item.set("Type", "Text")
        t = ET.SubElement(item, "Title")
        t.text = ch.title

    # Research folder (empty)
    research = ET.SubElement(binder, "BinderItem")
    research.set("ID", "research")
    research.set("Type", "Folder")
    rt = ET.SubElement(research, "Title")
    rt.text = "Research"

    # Pretty-print
    rough = ET.tostring(root, encoding="unicode")
    parsed = minidom.parseString(rough)
    return parsed.toprettyxml(indent="  ")


def _generate_settings_xml(title: str, author: str) -> str:
    """Generate a minimal projectsettings.xml."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ProjectSettings>
  <ProjectTitle>{_xml_escape(title)}</ProjectTitle>
  <Author>{_xml_escape(author)}</Author>
  <Language>en</Language>
  <Created>{datetime.now(timezone.utc).isoformat()}</Created>
  <LastModified>{datetime.now(timezone.utc).isoformat()}</LastModified>
</ProjectSettings>
"""


def _xml_escape(s: str) -> str:
    if not s:
        return ""
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))
