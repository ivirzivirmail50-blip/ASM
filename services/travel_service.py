"""Travel route service — character journeys on the world map."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select

from core.db import read_session, write_transaction
from models.travel_route import TravelRoute
from services._common import current_project_id, dump_json, load_json, new_uuid

log = logging.getLogger("asm.routes.travel")


def list_routes() -> list[TravelRoute]:
    with read_session() as s:
        return list(s.scalars(
            select(TravelRoute).where(
                TravelRoute.project_id == current_project_id(s)
            ).order_by(TravelRoute.created_at.asc())
        ).all())


def create_route(character_id: str, name: str, color: str = "#6366f1",
                 waypoints: list[dict] | None = None) -> TravelRoute:
    rid = new_uuid()
    with write_transaction() as s:
        r = TravelRoute(
            id=rid, project_id=current_project_id(s),
            character_id=character_id, name=name, color=color,
            waypoints=dump_json(waypoints or []),
        )
        s.add(r)
        s.flush()
        return r


def update_route(route_id: str, **fields) -> TravelRoute:
    with write_transaction() as s:
        r = s.get(TravelRoute, route_id)
        if not r:
            return None
        for k in ("name", "color", "character_id"):
            if k in fields and fields[k] is not None:
                setattr(r, k, fields[k])
        if "waypoints" in fields:
            r.waypoints = dump_json(fields["waypoints"])
        s.flush()
        return r


def delete_route(route_id: str) -> None:
    with write_transaction() as s:
        r = s.get(TravelRoute, route_id)
        if r:
            s.delete(r)


def get_routes_json() -> list[dict]:
    routes = list_routes()
    return [{
        "id": r.id, "character_id": r.character_id,
        "name": r.name, "color": r.color,
        "waypoints": load_json(r.waypoints, []),
    } for r in routes]
