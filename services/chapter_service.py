"""Chapter service: CRUD, cost-aware versioning, reorder, upload, split, merge."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.chapter import Chapter, ChapterVersion
from models.settings import Setting
from security import limits
from security.upload import parse_uploaded_file, safe_storage_path
from services._common import (
    current_project_id, dump_json, load_json, log_activity, new_uuid, now_utc,
)

log = logging.getLogger("asm.chapter")


def count_words(text: str | None) -> int:
    if not text:
        return 0
    # Word count: split on whitespace; for CJK count characters.
    import re
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return 0
    # Heuristic: if mostly CJK, count chars; else count words.
    cjk = sum(1 for c in cleaned if "\u4e00" <= c <= "\u9fff")
    if cjk > len(cleaned) * 0.3:
        return cjk
    return len(cleaned.split())


def list_chapters(
    *,
    status: str | None = None,
    sort: str = "sort_order",
    search: str | None = None,
    page: int = 1,
    per_page: int | None = None,
) -> tuple[list[Chapter], int]:
    """Return (chapters, total_count) for the current project."""
    if per_page is None:
        # Read from settings
        from core.db import read_session
        from models.settings import Setting
        with read_session() as s:
            per_page = int(Setting.get(s, "chapters_per_page", limits.CHAPTERS_PER_PAGE))
        if not per_page or per_page < 1:
            per_page = limits.CHAPTERS_PER_PAGE
    with read_session() as s:
        q = select(Chapter).where(
            Chapter.project_id == current_project_id(s)
        )
        if status and status != "all":
            q = q.where(Chapter.status == status)
        if search:
            like = f"%{search}%"
            q = q.where(Chapter.title.ilike(like))
        # Sort
        sort_col = {
            "title": Chapter.title,
            "status": Chapter.status,
            "word_count": Chapter.word_count,
            "created_at": Chapter.created_at,
            "updated_at": Chapter.updated_at,
            "sort_order": Chapter.sort_order,
        }.get(sort, Chapter.sort_order)
        q = q.order_by(sort_col.asc())
        # Count
        from sqlalchemy import func
        count_q = select(func.count()).select_from(q.subquery())
        total = s.scalar(count_q) or 0
        # Paginate
        page = max(1, page)
        q = q.offset((page - 1) * per_page).limit(per_page)
        chapters = list(s.scalars(q).all())
        return chapters, total


def get_chapter(chapter_id: str) -> Chapter:
    with read_session() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            raise NotFoundError("Chapter not found.")
        return ch


def get_chapter_with_versions(chapter_id: str) -> tuple[Chapter, list[ChapterVersion]]:
    with read_session() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            raise NotFoundError("Chapter not found.")
        versions = list(
            s.scalars(
                select(ChapterVersion)
                .where(ChapterVersion.chapter_id == chapter_id)
                .order_by(ChapterVersion.version_number.desc())
            ).all()
        )
        return ch, versions


def create_chapter(
    *, title: str, content: str | None = None, synopsis: str | None = None,
    status: str = "draft", target_word_count: int | None = None,
    tags: list[str] | None = None, character_ids: list[str] | None = None,
    notes: str | None = None,  # ignored, kept for API compat
) -> Chapter:
    if not title or len(title) > limits.TITLE_MAX:
        raise ValidationError(
            f"Title required and must be ≤ {limits.TITLE_MAX} chars."
        )
    cid = new_uuid()
    wc = count_words(content)
    with write_transaction() as s:
        # Determine sort_order: highest + 1
        from sqlalchemy import func
        max_order = s.scalar(
            select(func.max(Chapter.sort_order)).where(
                Chapter.project_id == current_project_id(s)
            )
        ) or 0
        ch = Chapter(
            id=cid,
            project_id=current_project_id(s),
            title=title,
            content=content or "",
            synopsis=synopsis or "",
            status=status,
            word_count=wc,
            target_word_count=target_word_count,
            sort_order=max_order + 1,
            character_ids=dump_json(character_ids or []),
            tags=dump_json(tags or []),
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(ch)
        s.flush()
        # First version (manual)
        v = ChapterVersion(
            id=new_uuid(),
            chapter_id=cid,
            version_number=1,
            content=content or "",
            word_count=wc,
            source="manual",
            uploaded_at=now_utc(),
            notes="Initial version",
        )
        s.add(v)
        log_activity(
            s, entity_type="chapter", entity_id=cid, entity_title=title,
            action="created", word_count_delta=wc,
            details={"status": status},
        )
        s.flush()
        return ch


def update_chapter(
    chapter_id: str, *,
    title: str | None = None,
    content: str | None = None,
    synopsis: str | None = None,
    status: str | None = None,
    target_word_count: int | None = None,
    tags: list[str] | None = None,
    character_ids: list[str] | None = None,
    create_version: bool = True,
    version_source: str = "manual",
    version_notes: str | None = None,
) -> Chapter:
    """Update a chapter. If create_version=True, snapshot the previous content."""
    with write_transaction() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            raise NotFoundError("Chapter not found.")
        old_wc = ch.word_count or 0
        delta = 0
        snapshot_interval = int(
            Setting.get(s, "version_snapshot_interval_minutes", 15) or 15
        )

        if title is not None:
            # Treat empty string as "no change" to be safe (cycleStatus used to send "")
            title_stripped = title.strip() if isinstance(title, str) else title
            if title_stripped == "":
                pass  # no-op; keep existing title
            elif len(title_stripped) > limits.TITLE_MAX:
                raise ValidationError(f"Title must be ≤ {limits.TITLE_MAX} chars.")
            else:
                ch.title = title_stripped
        if content is not None:
            new_wc = count_words(content)
            ch.content = content
            ch.word_count = new_wc
            delta = new_wc - old_wc
        if synopsis is not None:
            ch.synopsis = synopsis
        if status is not None and status != ch.status:
            # Status change → always snapshot
            create_version = True
            version_source = "status_change"
            version_notes = f"Status: {ch.status} → {status}"
            ch.status = status
        if target_word_count is not None:
            ch.target_word_count = target_word_count
        if tags is not None:
            if len(tags) > limits.TAGS_MAX:
                raise ValidationError(f"Tags ≤ {limits.TAGS_MAX} items.")
            ch.tags = dump_json(tags)
        if character_ids is not None:
            if len(character_ids) > limits.CHARACTER_IDS_MAX:
                raise ValidationError(f"character_ids ≤ {limits.CHARACTER_IDS_MAX}.")
            ch.character_ids = dump_json(character_ids)
        ch.updated_at = now_utc()

        # Cost-aware versioning.
        # Snapshot the chapter's *current* state when:
        # - create_version=True AND
        # - (it's a status_change/reupload/split/merge source) OR content was updated
        should_snapshot = False
        snapshot_content = ch.content  # use whatever the chapter now has
        if create_version:
            if version_source in ("status_change", "reupload", "split", "merge"):
                should_snapshot = True
            elif content is not None:
                # manual save with content change → check time-based policy
                last_v = s.scalar(
                    select(ChapterVersion)
                    .where(ChapterVersion.chapter_id == chapter_id)
                    .order_by(ChapterVersion.version_number.desc())
                )
                if last_v is None:
                    should_snapshot = True
                elif last_v.content != content:
                    # Content differs from last snapshot
                    if last_v.uploaded_at:
                        elapsed = datetime.now(timezone.utc) - last_v.uploaded_at.replace(tzinfo=timezone.utc)
                        if elapsed >= timedelta(minutes=snapshot_interval):
                            should_snapshot = True
                        else:
                            # Within the interval: only snapshot if substantially different
                            should_snapshot = True  # explicit save always snapshots when content differs
                    else:
                        should_snapshot = True
        if should_snapshot:
            last_v = s.scalar(
                select(ChapterVersion)
                .where(ChapterVersion.chapter_id == chapter_id)
                .order_by(ChapterVersion.version_number.desc())
            )
            vnum = (last_v.version_number + 1) if last_v else 1
            v = ChapterVersion(
                id=new_uuid(),
                chapter_id=chapter_id,
                version_number=vnum,
                content=snapshot_content,
                word_count=ch.word_count,
                source=version_source,
                uploaded_at=now_utc(),
                notes=version_notes,
            )
            s.add(v)

        log_activity(
            s, entity_type="chapter", entity_id=chapter_id,
            entity_title=ch.title, action="updated",
            word_count_delta=delta,
        )
        s.flush()
        return ch


def delete_chapter(chapter_id: str) -> str:
    """Delete a chapter. Records undo snapshot BEFORE delete.
    Returns the human-readable label for the undo toast."""
    from models.undo import snapshot_chapter, record_delete
    # Capture snapshot BEFORE delete (need a read session for related rows)
    ch = get_chapter(chapter_id)
    snapshot = snapshot_chapter(ch)
    label = f"Delete chapter '{ch.title}'"
    record_delete("chapter", chapter_id, label, snapshot)
    with write_transaction() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            raise NotFoundError("Chapter not found.")
        title = ch.title
        wc = ch.word_count or 0
        # Delete versions first
        s.query(ChapterVersion).filter_by(chapter_id=chapter_id).delete()
        s.delete(ch)
        log_activity(
            s, entity_type="chapter", entity_id=chapter_id,
            entity_title=title, action="deleted",
            word_count_delta=-wc,
        )
    return label


def reorder_chapters(ordered_ids: list[str]) -> None:
    """Persist new sort_order for the given chapter id list."""
    if not ordered_ids:
        return
    with write_transaction() as s:
        for idx, cid in enumerate(ordered_ids):
            ch = s.get(Chapter, cid)
            if ch:
                ch.sort_order = idx + 1
        log_activity(
            s, entity_type="chapter", entity_id="batch",
            entity_title="Chapters", action="reordered",
        )


def bulk_status(chapter_ids: list[str], new_status: str) -> None:
    if new_status not in {"draft", "revised", "final"}:
        raise ValidationError("Invalid status.")
    with write_transaction() as s:
        for cid in chapter_ids:
            ch = s.get(Chapter, cid)
            if ch:
                ch.status = new_status
                ch.updated_at = now_utc()
        log_activity(
            s, entity_type="chapter", entity_id="batch",
            entity_title="Chapters", action="status_changed",
            details={"status": new_status, "count": len(chapter_ids)},
        )


def upload_new_chapter(
    *, filename: str, content: bytes, title: str | None = None,
    status: str = "draft", tags: list[str] | None = None,
) -> Chapter:
    """Parse uploaded file → create chapter with reupload-preserved original."""
    if len(content) > limits.UPLOAD_MAX_BYTES:
        from core.errors import UploadError
        raise UploadError("File too large.")
    text, fmt = parse_uploaded_file(filename, content)
    if not title:
        # Use filename without extension
        import os
        title = os.path.splitext(filename)[0][: limits.TITLE_MAX] or "Untitled"
    if len(title) > limits.TITLE_MAX:
        title = title[: limits.TITLE_MAX]

    cid = new_uuid()
    wc = count_words(text)
    # Save raw original
    from config import Config
    raw_path = safe_storage_path(Config.RAW_DIR, "chapter", cid, filename)
    raw_path.write_bytes(content)

    with write_transaction() as s:
        from sqlalchemy import func
        max_order = s.scalar(
            select(func.max(Chapter.sort_order)).where(
                Chapter.project_id == current_project_id(s)
            )
        ) or 0
        ch = Chapter(
            id=cid,
            project_id=current_project_id(s),
            title=title,
            content=text,
            status=status,
            word_count=wc,
            sort_order=max_order + 1,
            tags=dump_json(tags or []),
            raw_file_path=str(raw_path.relative_to(Config.DATA_DIR.parent)),
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(ch)
        s.flush()
        v = ChapterVersion(
            id=new_uuid(), chapter_id=cid, version_number=1,
            content=text, word_count=wc, source="reupload",
            uploaded_at=now_utc(), notes=f"Imported from {filename}",
        )
        s.add(v)
        log_activity(
            s, entity_type="chapter", entity_id=cid, entity_title=title,
            action="uploaded", word_count_delta=wc,
            details={"filename": filename, "format": fmt},
        )
        s.flush()
        return ch


def reupload_chapter(chapter_id: str, *, filename: str, content: bytes) -> Chapter:
    """Replace chapter content from a new upload; create a new version row."""
    from core.errors import UploadError
    if len(content) > limits.UPLOAD_MAX_BYTES:
        raise UploadError("File too large.")
    text, fmt = parse_uploaded_file(filename, content)
    from config import Config
    raw_path = safe_storage_path(Config.RAW_DIR, "chapter", chapter_id, filename)
    raw_path.write_bytes(content)

    with write_transaction() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            raise NotFoundError("Chapter not found.")
        old_wc = ch.word_count or 0
        new_wc = count_words(text)
        ch.content = text
        ch.word_count = new_wc
        ch.raw_file_path = str(raw_path.relative_to(Config.DATA_DIR.parent))
        ch.updated_at = now_utc()
        last_v = s.scalar(
            select(ChapterVersion)
            .where(ChapterVersion.chapter_id == chapter_id)
            .order_by(ChapterVersion.version_number.desc())
        )
        vnum = (last_v.version_number + 1) if last_v else 1
        v = ChapterVersion(
            id=new_uuid(), chapter_id=chapter_id, version_number=vnum,
            content=text, word_count=new_wc, source="reupload",
            uploaded_at=now_utc(), notes=f"Re-uploaded from {filename}",
        )
        s.add(v)
        log_activity(
            s, entity_type="chapter", entity_id=chapter_id,
            entity_title=ch.title, action="uploaded",
            word_count_delta=new_wc - old_wc,
            details={"filename": filename, "format": fmt, "reupload": True},
        )
        s.flush()
        return ch


def split_chapter(chapter_id: str, split_at_paragraph: int) -> tuple[Chapter, Chapter]:
    """Split a chapter at the Nth paragraph (1-indexed). Returns (original, new)."""
    with write_transaction() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            raise NotFoundError("Chapter not found.")
        paragraphs = (ch.content or "").split("\n\n")
        if split_at_paragraph < 1 or split_at_paragraph >= len(paragraphs):
            raise ValidationError("Invalid split position.")
        first = "\n\n".join(paragraphs[:split_at_paragraph])
        second = "\n\n".join(paragraphs[split_at_paragraph:])
        ch.content = first
        ch.word_count = count_words(first)
        ch.updated_at = now_utc()
        # New chapter
        new_id = new_uuid()
        new_ch = Chapter(
            id=new_id,
            project_id=current_project_id(s),
            title=f"{ch.title} (Split)",
            content=second,
            status=ch.status,
            word_count=count_words(second),
            sort_order=ch.sort_order + 1,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(new_ch)
        # Bump subsequent chapters' sort_order
        s.query(Chapter).filter(
            Chapter.project_id == current_project_id(s),
            Chapter.sort_order > ch.sort_order,
        ).update({Chapter.sort_order: Chapter.sort_order + 1})
        # Versions for both
        last_v = s.scalar(
            select(ChapterVersion)
            .where(ChapterVersion.chapter_id == chapter_id)
            .order_by(ChapterVersion.version_number.desc())
        )
        vnum = (last_v.version_number + 1) if last_v else 1
        s.add(ChapterVersion(
            id=new_uuid(), chapter_id=chapter_id, version_number=vnum,
            content=first, word_count=ch.word_count, source="split",
            uploaded_at=now_utc(), notes=f"Split at paragraph {split_at_paragraph}",
        ))
        s.add(ChapterVersion(
            id=new_uuid(), chapter_id=new_id, version_number=1,
            content=second, word_count=new_ch.word_count, source="split",
            uploaded_at=now_utc(), notes="Created by split",
        ))
        log_activity(
            s, entity_type="chapter", entity_id=new_id,
            entity_title=new_ch.title, action="created",
            word_count_delta=new_ch.word_count,
            details={"split_from": chapter_id},
        )
        s.flush()
        return ch, new_ch


def merge_chapters(first_id: str, second_id: str) -> Chapter:
    """Merge two chapters; the second is deleted, content combined into the first."""
    with write_transaction() as s:
        first = s.get(Chapter, first_id)
        second = s.get(Chapter, second_id)
        if not first or not second:
            raise NotFoundError("Chapter not found.")
        merged = f"{first.content or ''}\n\n{second.content or ''}".strip()
        first.content = merged
        first.word_count = count_words(merged)
        first.updated_at = now_utc()
        # Snapshot
        last_v = s.scalar(
            select(ChapterVersion)
            .where(ChapterVersion.chapter_id == first_id)
            .order_by(ChapterVersion.version_number.desc())
        )
        vnum = (last_v.version_number + 1) if last_v else 1
        s.add(ChapterVersion(
            id=new_uuid(), chapter_id=first_id, version_number=vnum,
            content=merged, word_count=first.word_count, source="merge",
            uploaded_at=now_utc(), notes=f"Merged with {second.title}",
        ))
        # Delete second
        s.query(ChapterVersion).filter_by(chapter_id=second_id).delete()
        s.delete(second)
        log_activity(
            s, entity_type="chapter", entity_id=first_id,
            entity_title=first.title, action="updated",
            details={"merged_with": second_id, "merged_title": second.title},
        )
        s.flush()
        return first


def get_version(version_id: str) -> ChapterVersion:
    with read_session() as s:
        v = s.get(ChapterVersion, version_id)
        if not v:
            raise NotFoundError("Version not found.")
        return v


def restore_version(chapter_id: str, version_id: str) -> Chapter:
    with write_transaction() as s:
        ch = s.get(Chapter, chapter_id)
        v = s.get(ChapterVersion, version_id)
        if not ch or not v or v.chapter_id != chapter_id:
            raise NotFoundError("Chapter or version not found.")
        old_wc = ch.word_count or 0
        ch.content = v.content
        ch.word_count = v.word_count
        ch.updated_at = now_utc()
        # Snapshot of restored state
        last_v = s.scalar(
            select(ChapterVersion)
            .where(ChapterVersion.chapter_id == chapter_id)
            .order_by(ChapterVersion.version_number.desc())
        )
        vnum = (last_v.version_number + 1) if last_v else 1
        s.add(ChapterVersion(
            id=new_uuid(), chapter_id=chapter_id, version_number=vnum,
            content=v.content, word_count=v.word_count, source="manual",
            uploaded_at=now_utc(), notes=f"Restored from v{v.version_number}",
        ))
        log_activity(
            s, entity_type="chapter", entity_id=chapter_id,
            entity_title=ch.title, action="updated",
            word_count_delta=v.word_count - old_wc,
            details={"restored_from_version": v.version_number},
        )
        s.flush()
        return ch


def get_neighbors(chapter_id: str) -> tuple[Chapter | None, Chapter | None]:
    """Return (prev, next) chapters by sort_order."""
    with read_session() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            raise NotFoundError("Chapter not found.")
        pid = current_project_id(s)
        prev = s.scalar(
            select(Chapter).where(
                Chapter.project_id == pid,
                Chapter.sort_order < ch.sort_order,
            ).order_by(Chapter.sort_order.desc())
        )
        nxt = s.scalar(
            select(Chapter).where(
                Chapter.project_id == pid,
                Chapter.sort_order > ch.sort_order,
            ).order_by(Chapter.sort_order.asc())
        )
        return prev, nxt
