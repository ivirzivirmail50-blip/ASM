"""Beta reader comment service."""
from __future__ import annotations

import logging

from sqlalchemy import select

from core.db import read_session, write_transaction
from models.beta_comment import BetaComment

log = logging.getLogger("asm.beta")


def list_comments(chapter_id: str) -> list[BetaComment]:
    with read_session() as s:
        return list(s.scalars(
            select(BetaComment).where(BetaComment.chapter_id == chapter_id)
            .order_by(BetaComment.position.asc())
        ).all())


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


def resolve_comment(comment_id: int) -> None:
    with write_transaction() as s:
        c = s.get(BetaComment, comment_id)
        if c:
            c.status = "resolved"


def delete_comment(comment_id: int) -> None:
    with write_transaction() as s:
        c = s.get(BetaComment, comment_id)
        if c:
            s.delete(c)


def count_open(chapter_id: str) -> int:
    with read_session() as s:
        return s.query(BetaComment).filter_by(
            chapter_id=chapter_id, status="open"
        ).count()
