"""Beta reader comment service — with threaded replies."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.beta_comment import BetaComment

log = logging.getLogger("asm.beta")


def list_comments(chapter_id: str) -> list[BetaComment]:
    with read_session() as s:
        return list(s.scalars(
            select(BetaComment).where(BetaComment.chapter_id == chapter_id)
            .order_by(BetaComment.position.asc(), BetaComment.created_at.asc())
        ).all())


def list_top_level(chapter_id: str) -> list[BetaComment]:
    """Return only top-level comments (no parent), ordered by position."""
    with read_session() as s:
        return list(s.scalars(
            select(BetaComment).where(
                BetaComment.chapter_id == chapter_id,
                BetaComment.parent_id.is_(None),
            ).order_by(BetaComment.position.asc(), BetaComment.created_at.asc())
        ).all())


def list_replies(parent_id: int) -> list[BetaComment]:
    """Return all replies to a given comment, ordered chronologically."""
    with read_session() as s:
        return list(s.scalars(
            select(BetaComment).where(BetaComment.parent_id == parent_id)
            .order_by(BetaComment.created_at.asc())
        ).all())


def get_comment(comment_id: int) -> BetaComment:
    with read_session() as s:
        c = s.get(BetaComment, comment_id)
        if not c:
            raise NotFoundError("Comment not found.")
        return c


def add_comment(chapter_id: str, comment: str, *, reader_name: str = "Beta Reader",
                selected_text: str = "", position: int = 0) -> BetaComment:
    with write_transaction() as s:
        c = BetaComment(
            chapter_id=chapter_id, reader_name=reader_name,
            comment=comment, selected_text=selected_text,
            position=position, status="open",
        )
        s.add(c)
        s.flush()
        return c


def add_reply(parent_id: int, comment: str, *, reader_name: str = "Author",
              is_author_reply: bool = True) -> BetaComment:
    """Add a reply to an existing comment."""
    if not comment.strip():
        raise ValidationError("Reply text required.")
    with write_transaction() as s:
        parent = s.get(BetaComment, parent_id)
        if not parent:
            raise NotFoundError("Parent comment not found.")
        reply = BetaComment(
            chapter_id=parent.chapter_id,
            reader_name=reader_name,
            comment=comment,
            selected_text="",  # replies don't have their own selection
            position=parent.position,  # inherit parent's position
            status="open",
            parent_id=parent_id,
            is_author_reply=is_author_reply,
        )
        s.add(reply)
        s.flush()
        return reply


def resolve_comment(comment_id: int) -> BetaComment:
    """Resolve a comment and all its replies."""
    with write_transaction() as s:
        c = s.get(BetaComment, comment_id)
        if not c:
            raise NotFoundError("Comment not found.")
        c.status = "resolved"
        # Also resolve all replies
        replies = list(s.scalars(
            select(BetaComment).where(BetaComment.parent_id == comment_id)
        ))
        for r in replies:
            r.status = "resolved"
        s.flush()
        return c


def reopen_comment(comment_id: int) -> BetaComment:
    """Reopen a resolved comment."""
    with write_transaction() as s:
        c = s.get(BetaComment, comment_id)
        if not c:
            raise NotFoundError("Comment not found.")
        c.status = "open"
        s.flush()
        return c


def delete_comment(comment_id: int) -> None:
    """Delete a comment and all its replies."""
    with write_transaction() as s:
        c = s.get(BetaComment, comment_id)
        if c:
            # Delete all replies first (flush to avoid FK constraint issues)
            replies = list(s.scalars(
                select(BetaComment).where(BetaComment.parent_id == comment_id)
            ))
            for r in replies:
                s.delete(r)
            s.flush()  # ensure replies are deleted before parent
            s.delete(c)


def count_open(chapter_id: str) -> int:
    with read_session() as s:
        return s.query(BetaComment).filter_by(
            chapter_id=chapter_id, status="open"
        ).count()


def count_all(chapter_id: str) -> int:
    with read_session() as s:
        return s.query(BetaComment).filter_by(
            chapter_id=chapter_id
        ).count()


def to_dict(c: BetaComment, *, include_replies: bool = False) -> dict[str, Any]:
    d = {
        "id": c.id,
        "chapter_id": c.chapter_id,
        "reader_name": c.reader_name,
        "selected_text": c.selected_text or "",
        "comment": c.comment,
        "position": c.position or 0,
        "status": c.status,
        "parent_id": c.parent_id,
        "is_author_reply": bool(c.is_author_reply),
        "is_top_level": c.parent_id is None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
    if include_replies and c.parent_id is None:
        replies = list_replies(c.id)
        d["replies"] = [to_dict(r) for r in replies]
        d["reply_count"] = len(replies)
    return d


def get_threaded(chapter_id: str) -> list[dict[str, Any]]:
    """Return comments as threaded structure: top-level comments with nested replies."""
    top_level = list_top_level(chapter_id)
    return [to_dict(c, include_replies=True) for c in top_level]


def stats(chapter_id: str) -> dict[str, Any]:
    """Aggregate stats for a chapter's comments."""
    all_comments = list_comments(chapter_id)
    top_level = [c for c in all_comments if c.parent_id is None]
    replies = [c for c in all_comments if c.parent_id is not None]
    open_count = sum(1 for c in all_comments if c.status == "open")
    resolved_count = sum(1 for c in all_comments if c.status == "resolved")
    author_replies = sum(1 for c in all_comments if c.is_author_reply)
    return {
        "total": len(all_comments),
        "top_level": len(top_level),
        "replies": len(replies),
        "open": open_count,
        "resolved": resolved_count,
        "author_replies": author_replies,
    }
