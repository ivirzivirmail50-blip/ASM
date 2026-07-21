"""Submission Tracker service — where you sent your work, what came back."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.submission import (
    Submission, SUBMISSION_STATUSES, MARKET_TYPES,
)
from services._common import current_project_id, log_activity, new_uuid, now_utc

log = logging.getLogger("asm.submissions")


def list_submissions(
    *, status: str | None = None, market_type: str | None = None,
) -> list[Submission]:
    with read_session() as s:
        q = s.query(Submission).filter_by(project_id=current_project_id(s))
        if status and status != "all":
            q = q.filter_by(status=status)
        if market_type and market_type != "all":
            q = q.filter_by(market_type=market_type)
        return list(q.order_by(
            Submission.submitted_date.desc().nullslast(),
            Submission.created_at.desc(),
        ).all())


def get_submission(submission_id: str) -> Submission:
    with read_session() as s:
        sub = s.get(Submission, submission_id)
        if not sub:
            raise NotFoundError("Submission not found.")
        return sub


def create_submission(
    *, title: str, market_name: str, market_type: str = "magazine",
    chapter_id: str | None = None, status: str = "drafting",
    submitted_date: date | None = None, response_date: date | None = None,
    response_type: str | None = None, cover_letter: str = "", notes: str = "",
) -> Submission:
    if not title or len(title) > 500:
        raise ValidationError("Title required, ≤ 500 chars.")
    if not market_name or len(market_name) > 300:
        raise ValidationError("Market name required, ≤ 300 chars.")
    if status not in SUBMISSION_STATUSES:
        raise ValidationError(f"Status must be one of {list(SUBMISSION_STATUSES)}.")
    if market_type not in MARKET_TYPES:
        raise ValidationError(f"Market type must be one of {list(MARKET_TYPES)}.")
    sid = new_uuid()
    days_to_respond = _compute_days(submitted_date, response_date)
    with write_transaction() as s:
        sub = Submission(
            id=sid,
            project_id=current_project_id(s),
            title=title.strip(),
            market_name=market_name.strip(),
            market_type=market_type,
            chapter_id=chapter_id,
            status=status,
            submitted_date=submitted_date,
            response_date=response_date,
            days_to_respond=days_to_respond,
            response_type=response_type,
            cover_letter=cover_letter or "",
            notes=notes or "",
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(sub)
        log_activity(
            s, entity_type="submission", entity_id=sid,
            entity_title=f"{title} → {market_name}", action="created",
        )
        s.flush()
        return sub


def update_submission(submission_id: str, **fields: Any) -> Submission:
    with write_transaction() as s:
        sub = s.get(Submission, submission_id)
        if not sub:
            raise NotFoundError("Submission not found.")
        for k in ("title", "market_name", "market_type", "chapter_id", "status",
                  "submitted_date", "response_date", "response_type",
                  "cover_letter", "notes"):
            if k in fields and fields[k] is not None:
                setattr(sub, k, fields[k])
        # Recompute days_to_respond if either date changed
        sub.days_to_respond = _compute_days(sub.submitted_date, sub.response_date)
        sub.updated_at = now_utc()
        s.flush()
        return sub


def delete_submission(submission_id: str) -> None:
    with write_transaction() as s:
        sub = s.get(Submission, submission_id)
        if sub:
            s.delete(sub)


def _compute_days(submitted: date | None, responded: date | None) -> int | None:
    if submitted and responded:
        return (responded - submitted).days
    return None


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def stats() -> dict[str, Any]:
    """Aggregate stats for the dashboard view."""
    subs = list_submissions()
    by_status: dict[str, int] = {s: 0 for s in SUBMISSION_STATUSES}
    by_market: dict[str, int] = {m: 0 for m in MARKET_TYPES}
    response_times: list[int] = []
    for sub in subs:
        by_status[sub.status] = by_status.get(sub.status, 0) + 1
        by_market[sub.market_type] = by_market.get(sub.market_type, 0) + 1
        if sub.days_to_respond is not None:
            response_times.append(sub.days_to_respond)
    avg_response = sum(response_times) / len(response_times) if response_times else 0
    median_response = sorted(response_times)[len(response_times) // 2] if response_times else 0
    return {
        "total": len(subs),
        "by_status": by_status,
        "by_market": by_market,
        "accepted": by_status.get("accepted", 0) + by_status.get("published", 0),
        "rejected": by_status.get("rejected", 0),
        "pending": by_status.get("submitted", 0) + by_status.get("in_review", 0),
        "avg_response_days": round(avg_response, 1),
        "median_response_days": median_response,
        "acceptance_rate": (
            round((by_status.get("accepted", 0) + by_status.get("published", 0))
                  / len(subs) * 100, 1) if subs else 0
        ),
    }


def to_dict(sub: Submission) -> dict[str, Any]:
    return {
        "id": sub.id,
        "title": sub.title,
        "market_name": sub.market_name,
        "market_type": sub.market_type,
        "market_type_label": MARKET_TYPES.get(sub.market_type, {}).get("label", sub.market_type),
        "market_icon": MARKET_TYPES.get(sub.market_type, {}).get("icon", "📝"),
        "chapter_id": sub.chapter_id,
        "status": sub.status,
        "status_label": SUBMISSION_STATUSES.get(sub.status, {}).get("label", sub.status),
        "status_icon": SUBMISSION_STATUSES.get(sub.status, {}).get("icon", "📝"),
        "status_color": SUBMISSION_STATUSES.get(sub.status, {}).get("color", "#94a3b8"),
        "submitted_date": sub.submitted_date.isoformat() if sub.submitted_date else None,
        "response_date": sub.response_date.isoformat() if sub.response_date else None,
        "days_to_respond": sub.days_to_respond,
        "response_type": sub.response_type,
        "cover_letter": sub.cover_letter or "",
        "notes": sub.notes or "",
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
    }


def list_markets() -> list[dict[str, Any]]:
    """Distinct market names with submission counts (for reuse / tracking)."""
    subs = list_submissions()
    markets: dict[str, dict[str, Any]] = {}
    for s in subs:
        key = s.market_name
        if key not in markets:
            markets[key] = {
                "name": key,
                "market_type": s.market_type,
                "icon": MARKET_TYPES.get(s.market_type, {}).get("icon", "📝"),
                "submissions": 0,
                "accepted": 0,
                "rejected": 0,
                "pending": 0,
            }
        markets[key]["submissions"] += 1
        if s.status in ("accepted", "published"):
            markets[key]["accepted"] += 1
        elif s.status == "rejected":
            markets[key]["rejected"] += 1
        elif s.status in ("submitted", "in_review"):
            markets[key]["pending"] += 1
    return sorted(markets.values(), key=lambda m: m["submissions"], reverse=True)
