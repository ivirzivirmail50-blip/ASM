"""Tests for the Submission Tracker feature (v4.2)."""
from __future__ import annotations

from datetime import date

import pytest

from services import submission_service as svc


def test_create_submission_minimal():
    sub = svc.create_submission(title="Test Story", market_name="Test Mag")
    assert sub.id
    assert sub.title == "Test Story"
    assert sub.market_name == "Test Mag"
    assert sub.status == "drafting"
    assert sub.market_type == "magazine"


def test_create_submission_invalid_status():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_submission(title="x", market_name="y", status="bogus")


def test_create_submission_invalid_market_type():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_submission(title="x", market_name="y", market_type="bogus")


def test_create_submission_empty_title():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_submission(title="", market_name="y")


def test_create_submission_empty_market():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_submission(title="x", market_name="")


def test_create_submission_with_dates():
    sub = svc.create_submission(
        title="Test", market_name="Mag",
        submitted_date=date(2026, 7, 1),
        response_date=date(2026, 7, 15),
        status="rejected",
    )
    assert sub.days_to_respond == 14
    assert sub.status == "rejected"


def test_days_to_respond_none_when_missing_date():
    sub = svc.create_submission(
        title="Test", market_name="Mag",
        submitted_date=date(2026, 7, 1),
        status="submitted",
    )
    assert sub.days_to_respond is None


def test_list_submissions():
    svc.create_submission(title="A", market_name="M1")
    svc.create_submission(title="B", market_name="M2")
    subs = svc.list_submissions()
    assert len(subs) >= 2


def test_list_submissions_filter_by_status():
    svc.create_submission(title="A", market_name="M1", status="submitted")
    svc.create_submission(title="B", market_name="M2", status="rejected")
    submitted = svc.list_submissions(status="submitted")
    assert all(s.status == "submitted" for s in submitted)
    rejected = svc.list_submissions(status="rejected")
    assert all(s.status == "rejected" for s in rejected)


def test_list_submissions_filter_by_market_type():
    svc.create_submission(title="A", market_name="M1", market_type="magazine")
    svc.create_submission(title="B", market_name="M2", market_type="agent")
    mags = svc.list_submissions(market_type="magazine")
    assert all(s.market_type == "magazine" for s in mags)


def test_update_submission():
    sub = svc.create_submission(title="Old", market_name="M")
    updated = svc.update_submission(sub.id, title="New", status="accepted")
    assert updated.title == "New"
    assert updated.status == "accepted"


def test_update_submission_recomputes_days():
    sub = svc.create_submission(
        title="T", market_name="M",
        submitted_date=date(2026, 7, 1),
    )
    assert sub.days_to_respond is None
    updated = svc.update_submission(sub.id, response_date=date(2026, 7, 8))
    assert updated.days_to_respond == 7


def test_delete_submission():
    sub = svc.create_submission(title="x", market_name="y")
    svc.delete_submission(sub.id)
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.get_submission(sub.id)


def test_to_dict_shape():
    sub = svc.create_submission(
        title="T", market_name="M", market_type="agent",
        status="submitted",
        submitted_date=date(2026, 7, 1),
    )
    d = svc.to_dict(sub)
    assert d["title"] == "T"
    assert d["market_name"] == "M"
    assert d["market_type"] == "agent"
    assert d["market_type_label"] == "Agent"
    assert d["market_icon"] == "🤝"
    assert d["status"] == "submitted"
    assert d["status_label"] == "Submitted"
    assert d["status_icon"] == "📤"
    assert d["submitted_date"] == "2026-07-01"


def test_stats_with_no_submissions():
    s = svc.stats()
    assert s["total"] == 0
    assert s["acceptance_rate"] == 0
    assert s["avg_response_days"] == 0


def test_stats_counts():
    svc.create_submission(title="A", market_name="M1", status="submitted")
    svc.create_submission(title="B", market_name="M2", status="accepted")
    svc.create_submission(title="C", market_name="M3", status="rejected")
    svc.create_submission(
        title="D", market_name="M4", status="rejected",
        submitted_date=date(2026, 7, 1), response_date=date(2026, 7, 11),
    )
    s = svc.stats()
    assert s["total"] >= 4
    assert s["pending"] >= 1
    assert s["accepted"] >= 1
    assert s["rejected"] >= 2
    # Acceptance rate is at least 1/4 = 25%
    assert s["acceptance_rate"] > 0


def test_stats_avg_response_days():
    svc.create_submission(
        title="A", market_name="M1", status="rejected",
        submitted_date=date(2026, 7, 1), response_date=date(2026, 7, 11),
    )  # 10 days
    svc.create_submission(
        title="B", market_name="M2", status="rejected",
        submitted_date=date(2026, 7, 1), response_date=date(2026, 7, 21),
    )  # 20 days
    s = svc.stats()
    assert s["avg_response_days"] == 15.0
    assert s["median_response_days"] in (10, 20)  # one of them


def test_list_markets():
    svc.create_submission(title="A", market_name="Mag X", status="accepted")
    svc.create_submission(title="B", market_name="Mag X", status="rejected")
    svc.create_submission(title="C", market_name="Mag Y", status="submitted")
    markets = svc.list_markets()
    names = {m["name"] for m in markets}
    assert "Mag X" in names
    assert "Mag Y" in names
    mag_x = next(m for m in markets if m["name"] == "Mag X")
    assert mag_x["submissions"] >= 2
    assert mag_x["accepted"] >= 1
    assert mag_x["rejected"] >= 1
