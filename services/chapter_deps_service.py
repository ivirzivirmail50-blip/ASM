"""Chapter Dependency Tracker — visualize and validate chapter ordering.

Lets the writer define dependencies between chapters: "Chapter 5 depends on
Chapter 3" (Chapter 3 must come before Chapter 5). The tracker:
- Detects cycles (Chapter A depends on B which depends on A)
- Detects ordering violations (Chapter 5 depends on Chapter 7 but 7 comes after 5)
- Computes topological order (correct writing/reading order)
- Renders as a dependency graph (vis-network)
- Shows which chapters are "blocked" (have unmet dependencies)

Dependencies are stored in a simple model: (from_chapter_id, to_chapter_id)
meaning "from depends on to" (to must come before from).
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.chapter_deps import ChapterDependency
from models.chapter import Chapter
from services._common import current_project_id, new_uuid

log = logging.getLogger("asm.chapter_deps")


def list_dependencies() -> list[ChapterDependency]:
    with read_session() as s:
        return list(s.scalars(
            select(ChapterDependency).where(
                ChapterDependency.project_id == current_project_id(s)
            )
        ))


def add_dependency(from_chapter_id: str, to_chapter_id: str) -> ChapterDependency:
    """Declare that from_chapter depends on to_chapter."""
    if from_chapter_id == to_chapter_id:
        raise ValidationError("A chapter cannot depend on itself.")
    with write_transaction() as s:
        # Verify both chapters exist
        ch1 = s.get(Chapter, from_chapter_id)
        ch2 = s.get(Chapter, to_chapter_id)
        if not ch1 or not ch2:
            raise NotFoundError("One or both chapters not found.")
        # Check for duplicate
        existing = s.scalar(
            select(ChapterDependency).where(
                ChapterDependency.from_chapter_id == from_chapter_id,
                ChapterDependency.to_chapter_id == to_chapter_id,
            )
        )
        if existing:
            return existing  # idempotent
        # Check for reverse dependency (would create a 2-cycle)
        reverse = s.scalar(
            select(ChapterDependency).where(
                ChapterDependency.from_chapter_id == to_chapter_id,
                ChapterDependency.to_chapter_id == from_chapter_id,
            )
        )
        if reverse:
            raise ValidationError("Reverse dependency already exists — would create a cycle.")
        dep = ChapterDependency(
            id=new_uuid(),
            project_id=current_project_id(s),
            from_chapter_id=from_chapter_id,
            to_chapter_id=to_chapter_id,
        )
        s.add(dep)
        s.flush()
        return dep


def remove_dependency(from_chapter_id: str, to_chapter_id: str) -> None:
    with write_transaction() as s:
        dep = s.scalar(
            select(ChapterDependency).where(
                ChapterDependency.from_chapter_id == from_chapter_id,
                ChapterDependency.to_chapter_id == to_chapter_id,
            )
        )
        if dep:
            s.delete(dep)


def get_dependency_graph() -> dict[str, Any]:
    """Build the full dependency graph for visualization and analysis."""
    deps = list_dependencies()
    with read_session() as s:
        chapters = list(s.scalars(
            select(Chapter).where(Chapter.project_id == current_project_id(s))
            .order_by(Chapter.sort_order.asc())
        ))
    ch_map = {ch.id: ch for ch in chapters}

    # Build adjacency: for each chapter, what does it depend on?
    depends_on: dict[str, list[str]] = {ch.id: [] for ch in chapters}
    depended_by: dict[str, list[str]] = {ch.id: [] for ch in chapters}
    for d in deps:
        if d.from_chapter_id in depends_on:
            depends_on[d.from_chapter_id].append(d.to_chapter_id)
        if d.to_chapter_id in depended_by:
            depended_by[d.to_chapter_id].append(d.from_chapter_id)

    # Detect cycles using DFS
    cycles = _detect_cycles(depends_on)

    # Detect ordering violations: chapter A depends on B, but A.sort_order < B.sort_order
    violations: list[dict[str, Any]] = []
    for d in deps:
        ch_from = ch_map.get(d.from_chapter_id)
        ch_to = ch_map.get(d.to_chapter_id)
        if ch_from and ch_to:
            if (ch_from.sort_order or 0) < (ch_to.sort_order or 0):
                violations.append({
                    "from_chapter_id": d.from_chapter_id,
                    "from_title": ch_from.title,
                    "from_sort_order": ch_from.sort_order,
                    "to_chapter_id": d.to_chapter_id,
                    "to_title": ch_to.title,
                    "to_sort_order": ch_to.sort_order,
                    "message": f"'{ch_from.title}' (#{ch_from.sort_order}) depends on '{ch_to.title}' (#{ch_to.sort_order}) but appears earlier in the manuscript.",
                })

    # Compute blocked chapters (have unmet dependencies = dependency comes later in sort order)
    blocked: list[dict[str, Any]] = []
    for ch in chapters:
        deps_for_ch = depends_on.get(ch.id, [])
        unmet = []
        for dep_id in deps_for_ch:
            dep_ch = ch_map.get(dep_id)
            if dep_ch and (dep_ch.sort_order or 0) > (ch.sort_order or 0):
                unmet.append({"id": dep_id, "title": dep_ch.title, "sort_order": dep_ch.sort_order})
        if unmet:
            blocked.append({
                "chapter_id": ch.id,
                "title": ch.title,
                "sort_order": ch.sort_order,
                "unmet_deps": unmet,
            })

    # Topological order (if no cycles)
    topo_order: list[str] = []
    if not cycles:
        topo_order = _topological_sort(chapters, depends_on)

    return {
        "chapters": [{
            "id": ch.id,
            "title": ch.title,
            "sort_order": ch.sort_order,
            "status": ch.status,
        } for ch in chapters],
        "dependencies": [{
            "from": d.from_chapter_id,
            "to": d.to_chapter_id,
        } for d in deps],
        "cycles": cycles,
        "violations": violations,
        "blocked": blocked,
        "topological_order": topo_order,
        "total_chapters": len(chapters),
        "total_dependencies": len(deps),
    }


def _detect_cycles(depends_on: dict[str, list[str]]) -> list[list[str]]:
    """Detect cycles using DFS. Returns list of cycles (each is a list of chapter IDs)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in depends_on}
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in depends_on.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                # Found a cycle — extract it
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
            elif color[neighbor] == WHITE:
                dfs(neighbor, path)
        path.pop()
        color[node] = BLACK

    for node in depends_on:
        if color[node] == WHITE:
            dfs(node, [])
    return cycles


def _topological_sort(chapters: list, depends_on: dict[str, list[str]]) -> list[str]:
    """Kahn's algorithm for topological sort."""
    # Build in-degree map
    in_degree: dict[str, int] = {ch.id: 0 for ch in chapters}
    for node, deps in depends_on.items():
        # depends_on[node] = list of chapters that node depends on
        # So node has in-edges from its dependencies
        for dep in deps:
            if dep in in_degree:
                in_degree[node] = in_degree.get(node, 0) + 1

    # Start with nodes that have no dependencies
    queue = [ch.id for ch in chapters if in_degree.get(ch.id, 0) == 0]
    # Sort queue by sort_order for deterministic output
    ch_sort = {ch.id: ch.sort_order or 0 for ch in chapters}
    queue.sort(key=lambda x: ch_sort.get(x, 0))

    result: list[str] = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        # Find all chapters that depend on this node and decrement their in-degree
        for ch_id, deps in depends_on.items():
            if node in deps:
                in_degree[ch_id] -= 1
                if in_degree[ch_id] == 0:
                    # Insert in sorted position
                    inserted = False
                    for i, existing in enumerate(queue):
                        if ch_sort.get(ch_id, 0) < ch_sort.get(existing, 0):
                            queue.insert(i, ch_id)
                            inserted = True
                            break
                    if not inserted:
                        queue.append(ch_id)
    return result
