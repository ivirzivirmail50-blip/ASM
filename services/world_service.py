"""World entry service: CRUD, versioning, hierarchy, relations, map."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.world import WorldEntry, WorldEntryRelation, WorldEntryVersion
from security import limits
from services._common import (
    current_project_id, dump_json, load_json, log_activity, new_uuid, now_utc,
)

log = logging.getLogger("asm.world")

DEFAULT_TYPES = ("location", "lore", "faction", "glossary",
                 "magic_system", "species", "culture", "technology")


def get_all_types() -> list[str]:
    """Return all configured world types (defaults + user-added)."""
    from core.db import read_session
    from models.settings import Setting
    with read_session() as s:
        types = Setting.get(s, "world_types", list(DEFAULT_TYPES))
        if isinstance(types, str):
            try:
                import json
                types = json.loads(types)
            except (json.JSONDecodeError, TypeError):
                types = list(DEFAULT_TYPES)
        # Always ensure defaults are present
        merged = list(DEFAULT_TYPES) + [t for t in types if t not in DEFAULT_TYPES]
        return merged


def add_custom_type(name: str) -> list[str]:
    """Add a custom world entry type. Returns updated types list."""
    import re
    cleaned = re.sub(r"[^a-z0-9_]+", "_", name.lower().strip())
    if not cleaned:
        raise ValidationError("Invalid type name.")
    types = get_all_types()
    if cleaned in types:
        raise ValidationError(f"Type '{cleaned}' already exists.")
    types.append(cleaned)
    from core.db import write_transaction
    from models.settings import Setting
    with write_transaction() as s:
        Setting.set(s, "world_types", types)
    return types


def remove_custom_type(name: str) -> list[str]:
    """Remove a custom world entry type (defaults cannot be removed)."""
    if name in DEFAULT_TYPES:
        raise ValidationError(f"Default type '{name}' cannot be removed.")
    types = get_all_types()
    if name in types:
        types.remove(name)
        from core.db import write_transaction
        from models.settings import Setting
        with write_transaction() as s:
            Setting.set(s, "world_types", types)
    return types


# Type-specific metadata field templates.
METADATA_FIELDS: dict[str, list[str]] = {
    "location": ["region", "atmosphere", "population", "key_events",
                 "climate", "culture"],
    "lore": ["origin_era", "source", "significance", "related_locations"],
    "faction": ["allegiance", "members_count", "territory", "leader", "values"],
    "glossary": ["term", "definition", "pronunciation", "related_terms"],
    "magic_system": ["source", "rules", "limitations", "known_users"],
    "species": ["habitat", "lifespan", "abilities", "society_structure"],
    "culture": ["language", "traditions", "religion", "economy"],
    "technology": ["era", "inventor", "impact", "limitations"],
}


def list_entries(
    *, type_: str | None = None, search: str | None = None,
    category: str | None = None, sort: str = "name",
    page: int = 1, per_page: int | None = None,
) -> tuple[list[WorldEntry], int]:
    """Return (entries, total_count) with optional pagination.

    If per_page is None, reads from settings (world_per_page).
    """
    if per_page is None:
        from core.db import read_session as _rs
        from models.settings import Setting
        with _rs() as s:
            per_page = int(Setting.get(s, "world_per_page", 40))
        if not per_page or per_page < 1:
            per_page = 40
    with read_session() as s:
        q = select(WorldEntry).where(
            WorldEntry.project_id == current_project_id(s)
        )
        if type_ and type_ != "all":
            q = q.where(WorldEntry.type == type_)
        if category:
            q = q.where(WorldEntry.category == category)
        if search:
            like = f"%{search}%"
            q = q.where(
                (WorldEntry.name.ilike(like))
                | (WorldEntry.description.ilike(like))
            )
        sort_col = {
            "name": WorldEntry.name,
            "category": WorldEntry.category,
            "created_at": WorldEntry.created_at,
            "updated_at": WorldEntry.updated_at,
            "sort_order": WorldEntry.sort_order,
        }.get(sort, WorldEntry.name)
        q = q.order_by(sort_col.asc())
        # Count
        from sqlalchemy import func
        count_q = select(func.count()).select_from(q.subquery())
        total = s.scalar(count_q) or 0
        # Paginate
        page = max(1, page)
        q = q.offset((page - 1) * per_page).limit(per_page)
        entries = list(s.scalars(q).all())
        return entries, total


def get_entry(entry_id: str) -> WorldEntry:
    with read_session() as s:
        e = s.get(WorldEntry, entry_id)
        if not e:
            raise NotFoundError("World entry not found.")
        return e


def create_entry(
    *, type_: str, name: str, category: str | None = None,
    description: str | None = None, content: str | None = None,
    notes: str | None = None, metadata: dict | None = None,
    parent_id: str | None = None,
    map_pin_x: float | None = None, map_pin_y: float | None = None,
    map_pin_label: str | None = None,
) -> WorldEntry:
    if not name or len(name) > 300:
        raise ValidationError("Name required, ≤ 300 chars.")
    if not type_:
        raise ValidationError("Type required.")
    eid = new_uuid()
    with write_transaction() as s:
        from sqlalchemy import func
        max_order = s.scalar(
            select(func.max(WorldEntry.sort_order)).where(
                WorldEntry.project_id == current_project_id(s),
                WorldEntry.type == type_,
            )
        ) or 0
        e = WorldEntry(
            id=eid,
            project_id=current_project_id(s),
            type=type_,
            name=name,
            category=category,
            description=description,
            content=content,
            notes=notes,
            metadata_=dump_json(metadata or {}),
            parent_id=parent_id,
            map_pin_x=map_pin_x,
            map_pin_y=map_pin_y,
            map_pin_label=map_pin_label,
            sort_order=max_order + 1,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(e)
        # Version 1
        snapshot = {
            "type": type_, "name": name, "category": category,
            "description": description, "content": content, "notes": notes,
            "metadata": metadata or {},
        }
        s.add(WorldEntryVersion(
            id=new_uuid(), entry_id=eid, version_number=1,
            snapshot=dump_json(snapshot), source="manual",
            created_at=now_utc(), notes="Initial version",
        ))
        log_activity(
            s, entity_type="world_entry", entity_id=eid, entity_title=name,
            action="created",
        )
        s.flush()
        return e


def update_entry(
    entry_id: str, *, create_version: bool = True, **fields: Any
) -> WorldEntry:
    with write_transaction() as s:
        e = s.get(WorldEntry, entry_id)
        if not e:
            raise NotFoundError("World entry not found.")
        for k in ("name", "category", "description", "content", "notes",
                  "parent_id", "map_pin_x", "map_pin_y", "map_pin_label",
                  "map_image_path"):
            if k in fields and fields[k] is not None:
                setattr(e, k, fields[k])
        if "metadata" in fields:
            e.metadata_ = dump_json(fields["metadata"] or {})
        if "type" in fields and fields["type"]:
            e.type = fields["type"]
        e.updated_at = now_utc()
        if create_version:
            last_v = s.scalar(
                select(WorldEntryVersion)
                .where(WorldEntryVersion.entry_id == entry_id)
                .order_by(WorldEntryVersion.version_number.desc())
            )
            vnum = (last_v.version_number + 1) if last_v else 1
            snapshot = {
                "type": e.type, "name": e.name, "category": e.category,
                "description": e.description, "content": e.content,
                "notes": e.notes, "metadata": load_json(e.metadata_, {}) or {},
            }
            s.add(WorldEntryVersion(
                id=new_uuid(), entry_id=entry_id, version_number=vnum,
                snapshot=dump_json(snapshot), source="manual",
                created_at=now_utc(), notes="Manual save",
            ))
        log_activity(
            s, entity_type="world_entry", entity_id=entry_id,
            entity_title=e.name, action="updated",
        )
        s.flush()
        return e


def delete_entry(entry_id: str) -> str:
    """Delete a world entry. Records undo snapshot. Returns label."""
    from models.undo import snapshot_world_entry, record_delete
    e = get_entry(entry_id)
    snapshot = snapshot_world_entry(e)
    label = f"Delete world entry '{e.name}'"
    record_delete("world_entry", entry_id, label, snapshot)
    with write_transaction() as s:
        e = s.get(WorldEntry, entry_id)
        if not e:
            raise NotFoundError("World entry not found.")
        name = e.name
        s.query(WorldEntryVersion).filter_by(entry_id=entry_id).delete()
        s.query(WorldEntryRelation).filter(
            (WorldEntryRelation.from_entry_id == entry_id)
            | (WorldEntryRelation.to_entry_id == entry_id)
        ).delete()
        # Detach children
        s.query(WorldEntry).filter(WorldEntry.parent_id == entry_id).update(
            {WorldEntry.parent_id: None}
        )
        s.delete(e)
        log_activity(
            s, entity_type="world_entry", entity_id=entry_id,
            entity_title=name, action="deleted",
        )
    return label


def duplicate_entry(entry_id: str) -> WorldEntry:
    with write_transaction() as s:
        src = s.get(WorldEntry, entry_id)
        if not src:
            raise NotFoundError("World entry not found.")
        new_id = new_uuid()
        from sqlalchemy import func
        max_order = s.scalar(
            select(func.max(WorldEntry.sort_order)).where(
                WorldEntry.project_id == src.project_id,
                WorldEntry.type == src.type,
            )
        ) or 0
        e = WorldEntry(
            id=new_id, project_id=src.project_id, type=src.type,
            name=f"{src.name} (copy)", category=src.category,
            description=src.description, content=src.content,
            notes=src.notes, metadata_=src.metadata_,
            parent_id=src.parent_id, sort_order=max_order + 1,
            created_at=now_utc(), updated_at=now_utc(),
        )
        s.add(e)
        s.flush()
        return e


def reorder_entries(type_: str, ordered_ids: list[str]) -> None:
    with write_transaction() as s:
        for idx, eid in enumerate(ordered_ids):
            e = s.get(WorldEntry, eid)
            if e:
                e.sort_order = idx + 1
        log_activity(
            s, entity_type="world_entry", entity_id="batch",
            entity_title=type_, action="reordered",
        )


# ---- Relations ----

def list_relations() -> list[WorldEntryRelation]:
    with read_session() as s:
        return list(s.scalars(
            select(WorldEntryRelation).order_by(
                WorldEntryRelation.relation_type.asc()
            )
        ).all())


def relations_for(entry_id: str) -> tuple[list[WorldEntryRelation], list[WorldEntryRelation]]:
    """Returns (outgoing, incoming) for the entry."""
    with read_session() as s:
        out = list(s.scalars(
            select(WorldEntryRelation).where(
                WorldEntryRelation.from_entry_id == entry_id
            )
        ).all())
        inc = list(s.scalars(
            select(WorldEntryRelation).where(
                WorldEntryRelation.to_entry_id == entry_id
            )
        ).all())
        return out, inc


def create_relation(*, from_id: str, to_id: str, rel_type: str,
                    description: str | None = None) -> WorldEntryRelation:
    if from_id == to_id:
        raise ValidationError("Cannot relate an entry to itself.")
    rid = new_uuid()
    with write_transaction() as s:
        if not s.get(WorldEntry, from_id) or not s.get(WorldEntry, to_id):
            raise NotFoundError("Entry not found.")
        rel = WorldEntryRelation(
            id=rid, from_entry_id=from_id, to_entry_id=to_id,
            relation_type=rel_type, description=description,
        )
        s.add(rel)
        s.flush()
        return rel


def delete_relation(relation_id: str) -> None:
    with write_transaction() as s:
        rel = s.get(WorldEntryRelation, relation_id)
        if rel:
            s.delete(rel)


# ---- Versions ----

def list_versions(entry_id: str) -> list[WorldEntryVersion]:
    with read_session() as s:
        return list(s.scalars(
            select(WorldEntryVersion)
            .where(WorldEntryVersion.entry_id == entry_id)
            .order_by(WorldEntryVersion.version_number.desc())
        ).all())


def restore_version(entry_id: str, version_id: str) -> WorldEntry:
    with write_transaction() as s:
        e = s.get(WorldEntry, entry_id)
        v = s.get(WorldEntryVersion, version_id)
        if not e or not v or v.entry_id != entry_id:
            raise NotFoundError("Entry or version not found.")
        snap = load_json(v.snapshot, {}) or {}
        if "type" in snap:
            e.type = snap["type"]
        if "name" in snap:
            e.name = snap["name"]
        if "category" in snap:
            e.category = snap["category"]
        if "description" in snap:
            e.description = snap["description"]
        if "content" in snap:
            e.content = snap["content"]
        if "notes" in snap:
            e.notes = snap["notes"]
        if "metadata" in snap:
            e.metadata_ = dump_json(snap["metadata"] or {})
        e.updated_at = now_utc()
        # Snapshot the restored state
        last_v = s.scalar(
            select(WorldEntryVersion)
            .where(WorldEntryVersion.entry_id == entry_id)
            .order_by(WorldEntryVersion.version_number.desc())
        )
        vnum = (last_v.version_number + 1) if last_v else 1
        s.add(WorldEntryVersion(
            id=new_uuid(), entry_id=entry_id, version_number=vnum,
            snapshot=v.snapshot, source="manual",
            created_at=now_utc(), notes=f"Restored from v{v.version_number}",
        ))
        s.flush()
        return e


# ---- Map ----

def get_map_entries() -> list[WorldEntry]:
    """Return all location-type entries (with optional pin coords)."""
    with read_session() as s:
        return list(s.scalars(
            select(WorldEntry).where(
                WorldEntry.project_id == current_project_id(s),
                WorldEntry.type == "location",
            ).order_by(WorldEntry.name.asc())
        ).all())


def update_pin(entry_id: str, x: float | None, y: float | None,
               label: str | None = None) -> None:
    """Set or remove a map pin. Pass x=None, y=None to remove the pin."""
    with write_transaction() as s:
        e = s.get(WorldEntry, entry_id)
        if not e:
            raise NotFoundError("Entry not found.")
        if x is None or y is None:
            e.map_pin_x = None
            e.map_pin_y = None
        else:
            try:
                e.map_pin_x = float(x)
                e.map_pin_y = float(y)
            except (TypeError, ValueError):
                raise ValidationError("Invalid pin coordinates.")
        if label is not None:
            e.map_pin_label = label


def get_hierarchy(parent_id: str | None = None) -> list[dict]:
    """Return tree of location entries under parent_id."""
    with read_session() as s:
        rows = s.scalars(
            select(WorldEntry).where(
                WorldEntry.project_id == current_project_id(s),
                WorldEntry.type == "location",
            ).order_by(WorldEntry.name.asc())
        ).all()
        # Build tree
        nodes = {r.id: {"entry": r, "children": []} for r in rows}
        roots = []
        for r in rows:
            if r.parent_id and r.parent_id in nodes:
                nodes[r.parent_id]["children"].append(nodes[r.id])
            else:
                roots.append(nodes[r.id])
        return roots
