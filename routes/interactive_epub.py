"""Interactive EPUB export — EPUB with embedded character cards and map references."""
from __future__ import annotations
import io, zipfile, os
from flask import Blueprint, render_template, jsonify, request, send_file
from services import chapter_service, character_service

bp = Blueprint("interactive_epub", __name__, url_prefix="/interactive-epub")


@bp.route("/")
def index():
    chapters, total = chapter_service.list_chapters(per_page=10000)
    characters = character_service.list_characters()
    return render_template("interactive_epub/index.html", active_nav="interactive_epub",
                           chapters=chapters, total=total, characters=characters)


@bp.route("/download")
def download():
    chapters, _ = chapter_service.list_chapters(per_page=10000)
    characters = character_service.list_characters()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # mimetype (must be first, uncompressed)
        zf.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)

        # META-INF/container.xml
        zf.writestr("META-INF/container.xml", '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>''')

        # Content OPF
        manifest_items = ""
        spine_items = ""
        for i, ch in enumerate(chapters, 1):
            manifest_items += f'<item id="ch{i}" href="chapter{i}.xhtml" media-type="application/xhtml+xml"/>\n'
            spine_items += f'<itemref idref="ch{i}"/>'

        # Character cards
        char_manifest = ""
        char_html = ""
        for i, c in enumerate(characters, 1):
            char_manifest += f'<item id="char{i}" href="character{i}.xhtml" media-type="application/xhtml+xml"/>\n'
            char_html += f'''<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{c.name}</title></head>
<body><h1>{c.name}</h1><p><strong>Role:</strong> {c.role or 'Unknown'}</p>
<p><strong>Background:</strong> {c.background or 'N/A'}</p>
<p><strong>Personality:</strong> {c.psychology or 'N/A'}</p></body></html>'''
            zf.writestr(f"OEBPS/character{i}.xhtml", char_html)

        opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Interactive Manuscript</dc:title>
    <dc:language>en</dc:language>
    <dc:identifier id="bookid">asm-interactive-{int(__import__("time").time())}</dc:identifier>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    {manifest_items}
    {char_manifest}
  </manifest>
  <spine toc="ncx">
    <itemref idref="nav"/>
    {spine_items}
  </spine>
</package>'''
        zf.writestr("OEBPS/content.opf", opf)

        # Navigation
        nav_html = '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Contents</title></head><body><h1>Table of Contents</h1><nav><ol>'
        for i, ch in enumerate(chapters, 1):
            nav_html += f'<li><a href="chapter{i}.xhtml">{ch.title}</a></li>'
        nav_html += '</ol></nav></body></html>'
        zf.writestr("OEBPS/nav.xhtml", nav_html)

        # TOC NCX
        nav_points = ""
        for i, ch in enumerate(chapters, 1):
            nav_points += f'<navPoint id="ch{i}" playOrder="{i}"><navLabel><text>{ch.title}</text></navLabel><content src="chapter{i}.xhtml"/></navPoint>'
        ncx = f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="asm-interactive"/></head>
  <docTitle><text>Manuscript</text></docTitle>
  <navMap>{nav_points}</navMap>
</ncx>'''
        zf.writestr("OEBPS/toc.ncx", ncx)

        # Chapters
        for i, ch in enumerate(chapters, 1):
            content = (ch.content or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n\n", "</p><p>")
            html = f'''<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{ch.title}</title></head>
<body><h1>{ch.title}</h1><p>{content}</p></body></html>'''
            zf.writestr(f"OEBPS/chapter{i}.xhtml", html)

    buf.seek(0)
    return send_file(buf, mimetype="application/epub+zip", as_attachment=True, download_name="interactive_manuscript.epub")
