"""Search routes — FTS5-backed."""
from __future__ import annotations

import logging

from flask import Blueprint, render_template, request

from core.db import read_session
from models.settings import Setting
from services import search_service

log = logging.getLogger("asm.routes.search")
bp = Blueprint("search", __name__, url_prefix="/search")


def _get_per_page() -> int:
    """Read search results per page from settings."""
    with read_session() as s:
        val = int(Setting.get(s, "search_results_per_module", 50))
    return val if val > 0 else 50


@bp.route("/")
def index():
    q = request.args.get("q", "").strip()[:200]
    module = request.args.get("module", "all")
    case_sensitive = request.args.get("case") == "1"
    regex = request.args.get("regex") == "1"
    page = max(1, request.args.get("page", 1, type=int))
    per_page = _get_per_page()

    results = {"chapters": [], "characters": [], "world": []}
    if q:
        if module == "all":
            results = search_service.search_all(q, case_sensitive=case_sensitive,
                                                regex=regex)
        elif module == "chapters":
            results["chapters"] = search_service.search_chapters(
                q, case_sensitive=case_sensitive, regex=regex)
        elif module == "characters":
            results["characters"] = search_service.search_characters(
                q, case_sensitive=case_sensitive, regex=regex)
        elif module == "world":
            results["world"] = search_service.search_world(
                q, case_sensitive=case_sensitive, regex=regex)

    # Paginate each module independently
    total_counts = {k: len(v) for k, v in results.items()}
    paginated = {}
    for mod, items in results.items():
        start = (page - 1) * per_page
        paginated[mod] = items[start:start + per_page]
    results = paginated

    # Determine if there's a next page (any module has more results)
    has_next = any(total > page * per_page for total in total_counts.values())
    has_prev = page > 1

    return render_template("search.html", q=q, module=module,
                           case_sensitive=case_sensitive, regex=regex,
                           results=results, counts=total_counts,
                           page=page, per_page=per_page,
                           has_next=has_next, has_prev=has_prev,
                           active_nav="search")
