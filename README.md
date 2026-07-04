# Absolute Story Manager v4.0

> Local-first, single-user creative writing tool for managing long-form fiction. Built with Flask + SQLAlchemy + Jinja2, all assets vendored offline.

## Quick Start

```bash
cd /home/z/my-project/absolute-story-manager
pip install -r requirements.txt
python scripts/init_db.py        # Create tables + default settings
python scripts/seed_data.py      # Optional: load sample project
python app.py                    # Run on http://127.0.0.1:5555
```

Open http://127.0.0.1:5555/ in your browser.

## What's Built

### Foundation
- Flask 3.x app factory with Blueprints (one per module)
- SQLAlchemy ORM with **WAL mode** + write-lock + scoped sessions
- **FTS5 full-text search** with sync triggers across chapters / characters / world
- Flask-WTF **CSRF** on every POST/PUT/DELETE
- Rotating file logger (`data/logs/asm.log`) with request_id correlation
- Typed errors → mapped to HTTP status + custom 404/500 pages
- Hardened uploads: extension allow-list, magic-byte check, 25 MB cap, filename sanitization, `safe_join` path traversal protection

### Modules
- **Dashboard (Story Cockpit)**: stat cards, story-health bar, daily ring chart, 30-day word chart (Chart.js), annual GitHub-style heatmap, writing streak, character appearance heatmap, recent activity feed, upcoming deadlines
- **Chapters**: list with drag-reorder (SortableJS) + pagination + status filter, drag-drop file upload (TXT/MD/DOCX/PDF/RTF/ODT/HTML/CSV), EasyMDE rich-text editor with debounced autosave (no version spam), cost-aware version snapshots, side-by-side diff, version restore, split/merge, compare two chapters
- **Characters**: rich profiles (physical/psychology/background/philosophy/voice/notes), groups with drag-reorder, **interactive vis-network relationship graph** (physics simulation, drag nodes → save positions, click edge → popup with delete, click-to-create relationship mode, filter pills, group highlight legend), character arcs with stages, timeline of appearances, side-by-side compare, PDF/DOCX character sheet export
- **Plans**: 6-column **Kanban board** with cross-column drag-and-drop (SortableJS), nested outline with drag-reorder, multi-track timeline, subtasks with checkbox + drag-reorder + progress bar, deadlines, effort estimates, quick status change
- **World**: tabbed library (location/lore/faction/glossary + custom types), type-specific metadata fields, cross-references with back-references, location hierarchy, **interactive world map** with draggable pins (right-click to remove), version history + restore, FTS5 search
- **Search**: FTS5-backed full-text search across all modules with `<mark>` highlighted snippets and module filtering
- **Export**: TXT/MD/HTML/DOCX/PDF/EPUB for manuscripts, character sheets (D&D-style PDF), world bibles, full project (combined)
- **Settings**: appearance (theme/font/size), story metadata, writing goals, versioning policy, auto-backup, data health check (find dangling references + fix word counts), JSON project export (secrets stripped), AI configuration
- **Backup**: timestamped ZIP auto-backup + manual restore
- **AI (optional, opt-in)**: hybrid adapter for Ollama (local) or OpenAI-compatible endpoints; `/ai/*` routes return 404 when disabled; continue writing, summarize, rewrite, suggest tags/synopsis, name generator

### UI/UX
- Dark theme (default) + Light theme, switchable, persisted
- Sidebar (240px, collapsible to 64px), breadcrumbs, topbar with global search
- Custom design system in `static/css/main.css`: cards, badges, buttons, modals, toasts, progress bars, ring charts, heatmaps, tabs, filter pills, diff view, drag-and-drop states
- Reusable toasts, undo/redo toolbar, confirm dialogs
- Keyboard shortcuts: `/` (search), `Ctrl+N` (new chapter), `Ctrl+Shift+N` (new character), `Ctrl+S` (save version), `Ctrl+Z` / `Ctrl+Shift+Z` (undo/redo), `F11` (distraction-free), `Esc` (close modal)
- All third-party assets vendored offline (`static/vendor/`): Tailwind, Alpine.js, SortableJS, vis-network, EasyMDE, Chart.js, Inter/Noto Serif/JetBrains Mono fonts. **No CDN calls.**

## Project Structure

```
absolute-story-manager/
├── app.py                  # App factory (< 120 lines)
├── config.py               # Config + path resolution
├── requirements.txt
├── core/                   # Cross-cutting infra
│   ├── db.py               # Engine, scoped_session, WAL, write lock
│   ├── logging.py          # RotatingFileHandler + request_id
│   ├── errors.py           # Typed exceptions
│   └── csrf.py             # Flask-WTF setup
├── security/               # Hardening
│   ├── upload.py           # MIME + magic-byte + size + sanitize
│   └── limits.py           # Centralized field/size limits
├── models/                 # SQLAlchemy ORM
│   ├── project.py          # Multi-book root
│   ├── chapter.py
│   ├── character.py
│   ├── plan.py
│   ├── world.py
│   ├── activity.py
│   ├── settings.py
│   └── search.py           # FTS5 virtual tables + triggers
├── services/               # Business logic (no routes)
│   ├── chapter_service.py
│   ├── character_service.py
│   ├── plan_service.py
│   ├── world_service.py
│   ├── stats_service.py
│   ├── search_service.py
│   ├── export_service.py
│   ├── diff_service.py
│   ├── versioning_service.py
│   ├── validate_service.py
│   ├── backup_service.py
│   └── ai_service.py
├── routes/                 # Flask Blueprints
│   ├── dashboard.py
│   ├── chapters.py
│   ├── characters.py
│   ├── plans.py
│   ├── world.py
│   ├── search.py
│   ├── export.py
│   ├── settings.py
│   └── ai.py
├── templates/              # Jinja2 (base + components + per-module)
├── static/
│   ├── css/main.css
│   ├── js/                 # app, editor, graph, kanban, reorder, outline_dnd
│   └── vendor/             # All third-party assets (offline)
├── scripts/
│   ├── init_db.py
│   ├── seed_data.py        # Realistic demo project
│   └── fetch_vendor.py     # Download + verify offline assets
└── data/                   # Runtime (gitignored)
    ├── asm.db
    ├── logs/
    ├── raw/                # Original uploads preserved
    ├── media/              # Avatars, map images
    ├── backups/            # ZIP backups
    └── exports/            # Generated files
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Web framework | Flask 3.x with Blueprints |
| Database | SQLite (WAL mode) via SQLAlchemy ORM |
| Search | FTS5 with sync triggers |
| Templating | Jinja2 |
| Forms/CSRF | Flask-WTF |
| CSS | Tailwind (precompiled) + custom CSS variables |
| Client JS | Alpine.js, SortableJS, vis-network, EasyMDE, Chart.js — all local |
| PDF | ReportLab |
| DOCX | python-docx |
| EPUB | ebooklib |
| Fonts | Inter, Noto Serif, JetBrains Mono (woff2, local) |

## Design Priorities

Per user request, **graph and UI are the priority**:
- The relationship graph (vis-network) supports drag-to-save positions, click-to-create-relationship mode, filter pills, group-highlight legend, bidirectional arrows, dashed lines for hostile relations, physics simulation with stabilization
- The dashboard features a Chart.js 30-day word-count line chart with gradient fill, a circular daily-goal ring chart with animated count-up, and a GitHub-style 365-day annual heatmap with 4 intensity levels
- The Kanban board supports cross-column drag-and-drop with optimistic reordering, count badges, and column highlighting on drop
- Every interaction has toast feedback, undo/redo toolbar, and keyboard shortcuts
