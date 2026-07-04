"""Hardened upload validation: extension, magic-bytes, size, filename sanitization."""
from __future__ import annotations

import os
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Tuple

from core.errors import UploadError, ValidationError
from security import limits

# (extension, magic-bytes-prefix, friendly-name)
_MAGIC_SIGNATURES = [
    ("pdf", b"%PDF-", "PDF"),
    ("docx", b"PK\x03\x04", "DOCX (ZIP)"),
    ("odt", b"PK\x03\x04", "ODT (ZIP)"),
    ("rtf", b"{\\rtf", "RTF"),
    # text-like formats have no universal magic; we accept them by extension
    # but still strip control chars before display.
]


def allowed_extension(filename: str | None) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in limits.ALLOWED_UPLOAD_EXTS


def get_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def check_size(size: int) -> None:
    """Reject early if file exceeds the per-file cap."""
    if size <= 0:
        raise UploadError("Empty file.", code="empty_file")
    if size > limits.UPLOAD_MAX_BYTES:
        raise UploadError(
            f"File too large: {size} bytes (max {limits.UPLOAD_MAX_BYTES}).",
            code="too_large",
        )


def check_magic_bytes(content: bytes, ext: str) -> None:
    """For binary formats, verify magic bytes match the claimed extension.

    Text formats (txt, md, html, csv) are accepted based on extension; we
    still strip control characters / scripts before display.
    """
    ext = ext.lower()
    expected = {
        "pdf": b"%PDF-",
        "docx": b"PK\x03\x04",
        "odt": b"PK\x03\x04",
        "rtf": b"{\\rtf",
    }
    if ext not in expected:
        return  # text-like
    sig = expected[ext]
    if not content.startswith(sig):
        raise UploadError(
            f"File content does not match its extension '{ext}'.",
            code="magic_mismatch",
        )


def sanitize_filename(filename: str) -> str:
    """Strip path components + dangerous chars; force a safe basename.

    The client-supplied filename NEVER determines the on-disk path beyond
    the basename. UUID-based directories prevent collisions.
    """
    if not filename:
        return "upload"
    # Drop any path separators / drive letters / parent refs.
    base = os.path.basename(filename.replace("\\", "/"))
    base = base.lstrip(".")  # no hidden-file tricks
    # Normalize unicode + replace dangerous chars.
    base = unicodedata.normalize("NFKC", base)
    base = re.sub(r"[^\w.\- ]+", "_", base)
    base = base.strip().rstrip(".")
    if not base:
        base = "upload"
    # Cap length.
    return base[:180]


def safe_storage_path(root: Path, entity_type: str, ent_id: str,
                      filename: str) -> Path:
    """Build a safe on-disk path under data/raw/{entity_type}/{uuid}/{safe}.

    The UUID makes path traversal impossible. The basename is sanitized.
    """
    if not ent_id:
        ent_id = uuid.uuid4().hex
    safe_name = sanitize_filename(filename)
    target_dir = (root / entity_type / ent_id).resolve()
    # Ensure target stays under root.
    root_resolved = root.resolve()
    if not str(target_dir).startswith(str(root_resolved)):
        raise ValidationError("Invalid storage path.", code="path_escape")
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / safe_name


def safe_join(root: Path, *parts: str) -> Path:
    """Reject path traversal; return a resolved path guaranteed under root."""
    root_resolved = root.resolve()
    candidate = (root_resolved.joinpath(*parts)).resolve()
    if not str(candidate).startswith(str(root_resolved)):
        raise ValidationError("Invalid path.", code="path_escape")
    return candidate


def strip_unsafe_html(html: str) -> str:
    """Strip <script>, on*= handlers, javascript: URLs from imported HTML."""
    import re
    if not html:
        return ""
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.I | re.S)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.I | re.S)
    html = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", html, flags=re.I)
    html = re.sub(r"\son\w+\s*=\s*'[^']*'", "", html, flags=re.I)
    html = re.sub(r"\son\w+\s*=\s*[^\s>]+", "", html, flags=re.I)
    html = re.sub(r"javascript:", "", html, flags=re.I)
    return html


def parse_uploaded_file(filename: str, content: bytes) -> Tuple[str, str]:
    """Parse an uploaded file into plain text.

    Returns (text, source_format). Raises UploadError on parse failure.
    """
    ext = get_extension(filename)
    check_magic_bytes(content, ext)
    try:
        if ext in ("txt", "md", "markdown", "csv"):
            text = _decode_text(content)
            return text, ext
        if ext == "html" or ext == "htm":
            text = _decode_text(content)
            cleaned = strip_unsafe_html(text)
            # Convert to plain text via bs4
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(cleaned, "html.parser")
            return soup.get_text(separator="\n"), ext
        if ext == "docx":
            from docx import Document
            import io
            doc = Document(io.BytesIO(content))
            return "\n\n".join(p.text for p in doc.paragraphs), ext
        if ext == "odt":
            from odf.opendocument import load
            from odf.text import P
            import io
            doc = load(io.BytesIO(content))
            paragraphs = [str(p).strip() for p in doc.getElementsByType(P)]
            return "\n\n".join(paragraphs), ext
        if ext == "pdf":
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(content))
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
            return "\n\n".join(parts), ext
        if ext == "rtf":
            try:
                from striprtf.striprtf import rtf_to_text
            except ImportError:
                from striprtf import striprtf as _mod
                rtf_to_text = _mod.rtf_to_text
            text = _decode_text(content)
            return rtf_to_text(text), ext
    except UploadError:
        raise
    except Exception as exc:
        raise UploadError(f"Failed to parse {ext}: {exc}", code="parse_failed") from exc

    raise UploadError(f"Unsupported extension: {ext}", code="bad_ext")


def _decode_text(content: bytes) -> str:
    """Decode bytes to text using chardet when needed."""
    if not content:
        return ""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        import chardet
        guess = chardet.detect(content)
        encoding = guess.get("encoding") or "utf-8"
        try:
            return content.decode(encoding, errors="replace")
        except (LookupError, TypeError):
            return content.decode("utf-8", errors="replace")
