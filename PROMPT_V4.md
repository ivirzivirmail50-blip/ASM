# Absolute Story Manager v4.0 — Build Prompt

> A local-first writing management tool for long-form fiction. Build from scratch. No references to any existing codebase.
>
> **v4 focus vs v3:** offline-guaranteed assets, hardened security, WAL-based concurrency, cost-aware versioning, structured logging, FTS5 search, future-proof multi-book schema, and an *optional, opt-in* hybrid AI layer. Everything below supersedes v3 where they conflict.

---

## 1. What This App Is

**Absolute Story Manager (ASM)** is a local-first, single-user creative writing tool for managing a long-form fiction project. It runs on `localhost` — no cloud, no auth, no SaaS.

Core capabilities:
- Upload, version, diff, and reorder chapters
- Build rich character profiles with relationship graphs
- Plan stories with Kanban boards, timelines, and outlines
- Maintain a world-building reference library (locations, lore, factions, glossary + custom types)
- Export manuscripts and project documents (PDF, DOCX, EPUB, Markdown, HTML, TXT)
- Track writing goals, streaks, and activity on a dashboard
- **(Optional)** AI assistance via a local model (Ollama) **or** an OpenAI-compatible API — disabled by default, surfaced only in Settings

---

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Web framework | Flask 3.x with **Blueprints** |
| Database | SQLite via **SQLAlchemy** ORM + **Alembic** migrations, **WAL mode**, **FTS5** for full-text search |
| Templating | Jinja2 |
| Forms / CSRF | **Flask-WTF** (CSRF on all POST/PUT/DELETE) |
| CSS | Tailwind CSS — **served locally** (precompiled CLI build, not CDN) |
| Client-side JS | Alpine.js — **local** |
| Drag-and-drop | SortableJS — **local** |
| Graph visualization | vis-network — **local** |
| Rich-text editor | EasyMDE or Tiptap — **local** |
| Charts | Chart.js — **local** |
| Fonts | Bundled locally (Inter, Noto Serif, JetBrains Mono) via `@font-face`; **no Google Fonts requests** |
| Logging | Python `logging` + `RotatingFileHandler` → `data/logs/asm.log` |
| Testing | pytest, pytest-cov |
| PDF generation | ReportLab |
| EPUB generation | ebooklib |
| File parsing | python-docx, pypdf, chardet, striprtf, odfpy, beautifulsoup4, markdown |
| AI (optional) | `requests`/`httpx` to Ollama (`localhost:11434`) **or** OpenAI-compatible endpoint; **no SDK hard dependency** |
| Backup | ZIP-based auto-backup (background thread) |

> **Offline guarantee:** *Every* frontend dependency lives under `static/vendor/`. The app must work fully with the network cable unplugged. See §19 for the vendor setup. A `scripts/fetch_vendor.py` downloads/refreshes these assets and records their SHA-256 in `static/vendor/MANIFEST.txt`.

---

## 3. Project Structure

```
absolute-story-manager/
├── app.py                      # Flask app factory + blueprint registration (< 120 lines)
├── config.py                   # Config class with env vars, defaults, path resolution
├── requirements.txt
├── start.bat                   # Windows launcher: venv check + flask run
├── .env.example                # Documented env keys (no secrets shipped)
│
├── models/                     # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── project.py              # NEW: future-proof multi-book root
│   ├── chapter.py
│   ├── character.py
│   ├── plan.py
│   ├── world.py
│   ├── activity.py
│   ├── settings.py
│   └── search.py               # NEW: FTS5 virtual tables + triggers
│
├── services/                   # Business logic (no route/UI code)
│   ├── chapter_service.py
│   ├── character_service.py
│   ├── plan_service.py
│   ├── world_service.py
│   ├── export_service.py
│   ├── search_service.py       # FTS5-backed
│   ├── stats_service.py
│   ├── backup_service.py
│   ├── diff_service.py
│   ├── versioning_service.py   # NEW: cost-aware snapshot policy
│   ├── validate_service.py     # NEW: data health + reference integrity
│   └── ai_service.py           # NEW: optional hybrid AI (opt-in)
│
├── routes/                     # Flask Blueprints
│   ├── __init__.py
│   ├── dashboard.py
│   ├── chapters.py
│   ├── characters.py
│   ├── plans.py
│   ├── world.py
│   ├── export.py
│   ├── search.py
│   ├── ai.py                   # NEW: /ai/* endpoints (404 when disabled)
│   └── settings.py
│
├── templates/
│   ├── base.html               # App shell: sidebar + main area + undo toolbar
│   ├── components/             # Reusable: cards, modals, badges, buttons, toasts
│   ├── dashboard.html
│   ├── search.html
│   ├── settings.html
│   ├── settings_ai.html        # NEW: optional AI configuration
│   ├── settings_validate.html  # Data health check results page
│   ├── 404.html
│   ├── 500.html
│   ├── chapters/               # list, upload, detail, edit, compare, versions, versions_compare
│   ├── characters/             # list, detail, edit, graph, timeline, compare
│   ├── plans/                  # board, timeline, outline, edit
│   └── world/                  # index, edit, versions, map
│
├── static/
│   ├── css/main.css
│   ├── vendor/                 # NEW: all third-party JS/CSS/fonts, offline
│   │   ├── MANIFEST.txt        # name, version, source URL, sha256
│   │   ├── tailwind/
│   │   ├── alpine/
│   │   ├── sortablejs/
│   │   ├── vis-network/
│   │   ├── easymde/ (or tiptap/)
│   │   ├── chartjs/
│   │   └── fonts/
│   └── js/
│       ├── app.js              # CSRF, keyboard shortcuts, undo/redo, toasts, cycleStatus()
│       ├── editor.js           # Rich-text editor init + autosave
│       ├── kanban.js
│       ├── chapter_reorder.js
│       ├── outline_dnd.js
│       ├── graph.js
│       ├── world_map.js
│       ├── charts.js
│       ├── diff.js
│       └── ai.js               # NEW: only loaded when AI enabled
│
├── security/                   # NEW
│   ├── upload.py               # MIME sniff, magic-byte check, size cap, sanitized names
│   └── limits.py               # centralized field/size limits
│
├── core/                       # NEW: cross-cutting infra
│   ├── db.py                   # engine, scoped_session, WAL pragmas, locks
│   ├── logging.py              # RotatingFileHandler config
│   ├── errors.py               # typed exceptions + error codes
│   └── csrf.py                 # Flask-WTF setup
│
├── tests/
│   ├── conftest.py
│   ├── test_chapter_service.py
│   ├── test_character_service.py
│   ├── test_plan_service.py
│   ├── test_world_service.py
│   ├── test_export_service.py
│   ├── test_stats_service.py
│   ├── test_search_service.py
│   ├── test_versioning_service.py
│   ├── test_ai_service.py
│   ├── test_security_upload.py
│   └── test_routes/
│
├── scripts/
│   ├── seed_data.py
│   ├── fetch_vendor.py         # NEW: download + verify vendor assets
│   └── init_db.py              # creates tables, FTS, default project + settings
│
└── data/                       # .gitignore'd runtime data
    ├── asm.db
    ├── logs/                   # NEW: asm.log + rotated logs
    ├── raw/                    # {entity_type}/{uuid}/{filename} original uploads
    ├── media/                  # NEW: avatars, map images, mood board
    ├── backups/                # ZIP backups
    └── exports/                # Generated files
```

### Rules

1. Routes in `routes/` are Flask Blueprints. One file per module.
2. All business logic in `services/`. Routes only parse HTTP requests, validate with Flask-WTF forms, and call services.
3. Models in `models/` define schema via SQLAlchemy. **No raw SQL except FTS5 DDL/triggers** (in `models/search.py`, guarded by idempotent `IF NOT EXISTS`).
4. `app.py` is under 120 lines — app factory and blueprint/error-handler registration only.
5. Type hints on all public methods. Docstrings on all service methods.
6. **Concurrency**: SQLite in **WAL mode** (`PRAGMA journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`). All writes go through `core/db.py` with a module-level `threading.Lock` **plus** `busy_timeout` — never rely on the lock alone. Background threads (backup, AI) use a **separate** scoped session.
7. **Raw file storage**: Preserve original uploaded files in `data/raw/{entity_type}/{uuid}/` with a sanitized filename. No client-supplied path segments ever reach disk (see §11).
8. **Activity log cap**: Limit `activity_log` to **2000** entries (raised from v3's 200 — required for streaks/heatmap). On insert, delete oldest beyond cap in the same transaction.
9. **Input validation**: All fields validated/sanitized via `security/limits.py` on save. Limits: title 500, name 200, tags ≤ 100 items, `character_ids` ≤ 200, query ≤ 200 chars, **upload ≤ 25 MB**, **single upload request body ≤ 30 MB**. Reject over-length rather than silently truncate; truncate only for freeform display fields.
10. **Logging**: every service write and every caught exception logs at appropriate level. No secrets (API keys) ever logged.
11. **Cost-aware versioning**: see §5.2 — snapshots are taken on explicit save, status change, or re-upload — **not** on every autosave tick.
12. **AI is opt-in**: `ai_service` returns a clear "disabled" state unless `ai.enabled = true` in settings. AI routes return `404` (not 500) when disabled, so they're invisible to the default user.

---

## 4. Database Schema

> **Future-proofing (multi-book):** a `projects` table is the root. All top-level content tables carry `project_id TEXT FK → projects.id` defaulting to the seeded `'default'` project. Today only one project is used; tomorrow multi-book is a UI feature, not a painful migration. **Never write a query that omits `project_id` filtering on these tables** (a helper `current_project_id()` returns the active project).

### projects  *(NEW)*

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | 'default' seeded |
| name | TEXT NOT NULL | "My Story" |
| subtitle | TEXT | e.g. "Book One of the trilogy" |
| created_at | DATETIME | |

### chapters

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| project_id | TEXT FK → projects.id | DEFAULT 'default' |
| title | TEXT NOT NULL | Max 500 chars |
| content | TEXT | Full chapter text |
| synopsis | TEXT | Dedicated field, separate from content |
| status | TEXT DEFAULT 'draft' | draft / revised / final |
| word_count | INTEGER DEFAULT 0 | Computed on save |
| target_word_count | INTEGER | Per-chapter word goal |
| sort_order | INTEGER DEFAULT 0 | For drag-and-drop reorder |
| character_ids | TEXT | JSON array of linked character UUIDs, max 200 items |
| tags | TEXT | JSON array of tag strings, max 100 items |
| raw_file_path | TEXT | Path to original uploaded file (preserved for re-download) |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### chapter_versions

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| chapter_id | TEXT FK → chapters.id | |
| version_number | INTEGER | |
| content | TEXT | Snapshot of chapter content |
| word_count | INTEGER | |
| source | TEXT | manual / reupload / status_change / split / merge |
| uploaded_at | DATETIME | |
| notes | TEXT | Version-specific notes |

### characters

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| project_id | TEXT FK → projects.id | DEFAULT 'default' |
| name | TEXT NOT NULL | Max 200 chars |
| age | TEXT | e.g. "35", "Unknown", "Centuries old" |
| gender | TEXT | e.g. "Male", "Female", "Non-binary", "Unknown" |
| aliases | TEXT | JSON array of alternative names / nicknames |
| role | TEXT | protagonist / antagonist / supporting / minor |
| avatar_color | TEXT | Hex color for avatar circle |
| avatar_path | TEXT | NEW: optional uploaded avatar image |
| physical | TEXT | Physical description |
| psychology | TEXT | Personality, traits, fears, motivations |
| background | TEXT | Origin, history, education |
| philosophy | TEXT | Beliefs, values, moral code |
| philosophy_quotes | TEXT | JSON array of notable quotes by this character |
| story_role | TEXT | Function in the story |
| story_role_chapters | TEXT | JSON array of chapter IDs where character plays key role |
| voice | TEXT | How they speak: dialect, vocabulary, verbal tics |
| notes | TEXT | Freeform notes |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### character_groups

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| project_id | TEXT FK → projects.id | DEFAULT 'default' |
| name | TEXT NOT NULL | e.g. "Royal Family", "The Resistance" |
| description | TEXT | |
| color | TEXT | Hex color for graph nodes |

### character_group_members

| Column | Type | Notes |
|--------|------|-------|
| character_id | TEXT FK → characters.id | |
| group_id | TEXT FK → character_groups.id | |

### character_relationships

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| from_character_id | TEXT FK → characters.id | |
| to_character_id | TEXT FK → characters.id | |
| relationship_type | TEXT | married_to, rival_of, parent_of, friend_of, enemy_of, serves, mentors, loves, betrayed_by, custom |
| description | TEXT | |
| is_bidirectional | BOOLEAN DEFAULT 0 | |
| created_at | DATETIME | |

### character_arcs

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| character_id | TEXT FK → characters.id | |
| arc_name | TEXT NOT NULL | e.g. "Redemption Arc" |
| description | TEXT | |
| stages | TEXT (JSON) | [{name, description, status, chapter_ids}] |
| created_at | DATETIME | |

Stages example:
```json
[
  {"name": "Innocence", "description": "...", "status": "completed", "chapter_ids": ["ch1","ch2"]},
  {"name": "Rising Conflict", "description": "...", "status": "in_progress", "chapter_ids": ["ch3"]},
  {"name": "Climax", "description": "...", "status": "planned", "chapter_ids": []},
  {"name": "Resolution", "description": "...", "status": "planned", "chapter_ids": []}
]
```

### plans

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| project_id | TEXT FK → projects.id | DEFAULT 'default' |
| title | TEXT NOT NULL | |
| description | TEXT | |
| status | TEXT DEFAULT 'idea' | idea / planned / writing / draft_done / revised / final |
| column | TEXT | Same as status, used for Kanban positioning |
| sort_order | INTEGER DEFAULT 0 | |
| chapter_id | TEXT FK → chapters.id | Nullable, linked chapter |
| parent_id | TEXT FK → plans.id | Nullable, for nesting in outline |
| depends_on_id | TEXT FK → plans.id | Nullable, dependency |
| story_date | TEXT | In-story date for timeline (e.g. "Day 1", "Year 321") |
| event_type | TEXT | plot_point / character_moment / climax / resolution / custom |
| track | TEXT | Timeline lane name (e.g. "Main Plot", "Romance Subplot") |
| characters_involved | TEXT | JSON array of character UUIDs |
| deadline | DATE | Nullable |
| effort_estimate | INTEGER | Nullable, estimated word count |
| tags | TEXT (JSON) | |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### plan_subtasks

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| plan_id | TEXT FK → plans.id | |
| title | TEXT NOT NULL | |
| is_completed | BOOLEAN DEFAULT 0 | |
| sort_order | INTEGER DEFAULT 0 | |
| created_at | DATETIME | |

### world_entries

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| project_id | TEXT FK → projects.id | DEFAULT 'default' |
| type | TEXT NOT NULL | location / lore / faction / glossary / magic_system / species / culture / technology |
| name | TEXT NOT NULL | Max 300 chars |
| category | TEXT | User-defined category within type |
| description | TEXT | Short summary |
| content | TEXT | Full entry content |
| notes | TEXT | Freeform scratchpad notes |
| metadata | TEXT (JSON) | Type-specific structured fields (see below) |
| parent_id | TEXT FK → world_entries.id | Nullable, for hierarchy |
| map_pin_x | FLOAT | Nullable, position on world map |
| map_pin_y | FLOAT | Nullable, position on world map |
| map_pin_label | TEXT | |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### world_entry_versions

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| entry_id | TEXT FK → world_entries.id | |
| version_number | INTEGER | |
| snapshot | TEXT (JSON) | Full entry state |
| source | TEXT | manual / autosave_interval / status_change |
| created_at | DATETIME | |
| notes | TEXT | |

### world_entry_relations

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| from_entry_id | TEXT FK → world_entries.id | |
| to_entry_id | TEXT FK → world_entries.id | |
| relation_type | TEXT | located_in, governed_by, allied_with, part_of, etc. |
| description | TEXT | |

### activity_log

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| project_id | TEXT FK → projects.id | DEFAULT 'default' |
| entity_type | TEXT | chapter / character / plan / world_entry / ai_action |
| entity_id | TEXT | |
| entity_title | TEXT | Denormalized for display |
| action | TEXT | created / updated / deleted / uploaded / reordered / status_changed |
| word_count_delta | INTEGER | |
| details | TEXT (JSON) | |
| timestamp | DATETIME | |

### settings

| Column | Type | Notes |
|--------|------|-------|
| key | TEXT PK | |
| value | TEXT | JSON-encoded |

### Settings Keys

| Key | Type | Default |
|-----|------|---------|
| active_project_id | string | "default" |
| story_title | string | "My Story" |
| story_author | string | "Author" |
| story_genre | string | "" |
| story_description | string | "" |
| daily_word_goal | int | 500 |
| total_word_goal | int | 80000 |
| manuscript_font | string | "Courier" |
| manuscript_font_size | int | 12 |
| manuscript_line_spacing | float | 2.0 |
| manuscript_margins | float | 1.0 |
| autosave_interval_seconds | int | 3 |
| version_snapshot_interval_minutes | int | 15 |
| auto_backup_enabled | bool | true |
| auto_backup_interval_hours | int | 6 |
| theme | string | "dark" |
| sidebar_collapsed | bool | false |
| editor_font | string | "serif" |
| editor_font_size | int | 16 |
| chapter_viewer_font | string | "serif" |
| chapter_viewer_font_size | int | 16 |
| chapter_sort_default | string | "sort_order" |
| character_sort_default | string | "name" |
| default_chapter_status | string | "draft" |
| world_types | JSON array | ["location","lore","faction","glossary"] |
| **ai.enabled** | bool | **false** |
| **ai.provider** | string | "ollama" |
| **ai.api_base** | string | "http://localhost:11434" |
| **ai.api_key** | string | "" |
| **ai.model** | string | "" |
| **ai.timeout_seconds** | int | 60 |

> **Secrets handling:** `ai.api_key` (if any) is stored in the DB but **never** rendered in templates, never logged, and never included in JSON project export unless an explicit "include secrets" checkbox is checked at export time.

### FTS5 full-text index  *(NEW)*

External-content FTS5 tables mirroring searchable text, kept in sync via triggers:
- `chapters_fts(chapters)` over `title, synopsis, content`
- `characters_fts(characters)` over `name, aliases, physical, psychology, background, philosophy, voice, notes`
- `world_fts(world_entries)` over `name, description, content, notes`

Triggers: `AFTER INSERT/UPDATE/DELETE` keep FTS in sync. Querying uses `MATCH` with snippet/column highlighting. Falls back to `LIKE` only if FTS5 is unavailable on the SQLite build.

---

## 5. Features — Full Specification

### 5.1 Dashboard ("Story Cockpit")

- **Story Health Bar**: Progress bar showing total words vs. total_word_goal
- **Daily Word Goal Ring Chart**: Circular progress of today's words vs. daily_word_goal
- **Writing Streak**: Consecutive days with activity computed from activity_log, flame icon
- **Word-Count History Chart**: Line/sparkline of daily word counts over past 30 days (activity_log grouped by date, sum word_count_delta)
- **Annual Heatmap** *(NEW)*: GitHub-style 365-day contribution grid; click a day → that day's activity
- **Stats Grid**: Total Chapters, Total Characters, Total World Entries, Total Words, Last Edit
- **Writing This Period**:
  - Words Today: sum word_count_delta where timestamp >= today midnight
  - Words This Week: where timestamp >= Monday of current week
  - Words This Month: where timestamp >= 1st of current month
- **Character Appearance Heatmap**: Table showing each character's appearance count across chapters (chapters.character_ids)
- **Recent Activity Feed**: Last 10 actions from activity_log with entity links and undo buttons
- **Upcoming Deadlines**: Plan items with deadlines in the next 7 days
- **Quick-Add Buttons**: New Chapter, New Character, New Plan Item

### 5.2 Chapters

**Upload**
- Drag-and-drop file upload zone supporting TXT, DOCX, PDF, MD, RTF, ODT, HTML, CSV
- File is parsed, text extracted, metadata generated, initial version created
- Original file stored for reference under `data/raw/chapter/{uuid}/{safe_name}`
- **Validation**: MIME + magic-byte check, ≤ 25 MB, allowed extensions only, sanitized filename (§11)

**Chapter List**
- Grid of chapter cards with status badges, tags, word count, reading time estimates, version count, synopsis preview
- Filter by status, search by title/content (FTS5)
- Sort by: title, status, word count, date created, date modified, sort order
- **Pagination**: server-side, **30 cards/page** default (configurable in settings)
- **Drag-and-drop reorder**: SortableJS with grab handle on each card. On drop, POST to /chapters/reorder with new order array. Ghost card placeholder, cursor change to grabbing, toast "Chapters reordered".
- **Bulk status change**: Checkbox on each card + "Change Status" dropdown in toolbar

**Chapter Detail**
- Full content display
- Metadata panel: word count, reading time, status, tags, version count, linked characters
- Synopsis display
- **Previous/Next navigation** buttons in header
- Quick Edit toggle: inline editing without leaving page
- Version sparkline showing version history
- Character list with links to character profiles

**Rich-Text Markdown Editor**
- EasyMDE or Tiptap (local), replacing plain textarea
- Toolbar: bold, italic, headings, lists, blockquotes, code blocks, links, images
- **Autosave**: Debounced (configurable, default 3s). Visual indicator: "Saving..." then "Saved checkmark". Autosave updates `chapters.content` **only** — it does **not** create a version row.
- Keyboard shortcut Ctrl+S to save immediately (this *does* create a version snapshot)

**Cost-aware Versioning** *(revised from v3)*
Snapshots are written to `chapter_versions` only on:
1. Explicit **Save** (Ctrl+S or Save button)
2. **Status change** (draft → revised → final)
3. **Re-upload** of a file
4. **Split / Merge** operations
5. **Time-based**: if the chapter has changed since its last snapshot by more than `version_snapshot_interval_minutes` (default 15), the next save creates a snapshot
This keeps the DB lean while preserving recoverable history.

**Distraction-Free Mode**
- F11 fullscreen, minimal UI
- Only: editor content, word counter, status indicator, exit button
- Escape to exit

**Version Tracking**
- Upload new version from file: POST /chapters/{id}/reupload — parses file, creates new version entry, updates chapter content and word count
- Or save current state as new version: POST /chapters/{id}/versions/save
- Version history list with timestamps, word counts, and **source** label

**Side-by-Side Diff**
- Compare any two versions of the same chapter: GET /chapters/{id}/versions/compare?v1=X&v2=Y
- Compare any two different chapters: GET /chapters/compare?ch1=X&ch2=Y
- Line-level comparison with word-level highlighting within changed lines (green additions, red deletions)
- Navigate between hunks
- Export diff as TXT or HTML: POST /chapters/{id}/diff/export with format parameter

**Chapter Split/Merge**
- Split at a paragraph boundary: choose split point, create new chapter from second half
- Merge two adjacent chapters: combine content, keep higher sort order

**Word Count Target**
- Per-chapter target word count
- Progress bar on chapter card showing current/target
- Color: red when < 25%, yellow when < 75%, green when >= 75%

### 5.3 Characters

**Character List**
- Avatar initials (colored circle based on avatar_color or name hash), or uploaded avatar image
- Name, role badge, age, appearance count
- Filter by role, search by name/aliases/notes (FTS5)
- Extended search: searches name, aliases, notes, psychology, background
- Sort by: name, date created, appearance count (first chapter they appear in)

**Rich Profile Sections**
- Age, Gender, Aliases (list of alternative names)
- Physical: height, build, hair, eyes, distinguishing marks, clothing style
- Psychology: personality traits, fears, motivations, strengths, weaknesses
- Background: origin, education, key events, family
- Philosophy: beliefs, values, moral code, notable quotes (list)
- Story Role: function in story, arc summary, key decisions, linked chapter IDs
- Voice/Dialogue Style: dialect, vocabulary, verbal tics, speech patterns
- Notes: freeform text

**Character Groups**
- Create named groups (e.g., "Royal Family", "The Resistance")
- Assign characters to multiple groups simultaneously
- Each group has a color for graph visualization
- Edit group name, description, color

**Drag-and-Drop Group Management**
- Reorder characters within a group (SortableJS)
- Drag characters between groups (SortableJS with group: 'groups')
- Visual feedback: ghost card, group highlight

**Relationship Mapping**
- Create typed relationships between characters
- Relationship types: married_to, rival_of, parent_of, friend_of, enemy_of, serves, mentors, loves, betrayed_by, custom
- Bidirectional option (married_to is mutual by default)
- Description field for context
- Delete relationships from either character's profile

**Interactive Relationship Graph**
- Library: vis-network (local)
- Nodes = characters, colored by group or name hash
- Edges = relationships:
  - Solid lines for person-to-person relationships
  - Dashed red lines for group-to-group relationships
  - Dashed orange lines for group-to-person relationships
- Interactions:
  - Click node → navigate to character detail
  - Click edge → show relationship details in popup with Delete button
  - Drag nodes → reposition for better layout
  - Mouse wheel → zoom in/out
  - Drag background → pan
  - Double-click background → reset view
- Delete relationships from graph (click edge → popup → Delete → confirm → toast)
- Click-to-create relationships (add mode → click two nodes → choose type/description → confirm)
- Relationship type filter tabs (pill buttons: All, each type, Group-Group, Group-Person)
- Group highlighting (legend with colors; click → highlight members, dim others)
- Physics simulation with stabilization
- Save node positions to database on drag end

**Character Arc Tracking**
- Create named arcs per character
- Define stages (default: setup, rising, climax, resolution — customizable)
- Each stage: name, description, status (planned/in_progress/completed), linked chapter IDs
- Visual timeline showing arc progression with stage markers
- Click stage → show details, link/unlink chapters

**Character Timeline**
- Vertical timeline of character appearances across chapters
- Each entry: chapter number, chapter title, brief context
- Arc stage markers overlaid on timeline
- Click entry → navigate to chapter

**Character Comparison**
- Select two characters from dropdowns
- Side-by-side attribute comparison: all profile sections
- Highlight differences
- Export comparison as text

**Formatted Character Sheet PDF Export**
- Styled like a D&D character sheet
- Sections with tables and styled fields
- Avatar circle with initials (or uploaded avatar image)
- Consistent formatting: headers, labels, values

### 5.4 Story Planning

**Kanban Board**
- 6 columns: Idea → Planned → Writing → Draft Done → Revised → Final
- **Drag-and-drop between columns**: SortableJS with group: 'plans'
  - On drop: POST /plans/{id}/status with new status
  - Toast "Plan item moved"
- **Drag-and-drop within columns**: SortableJS sort: true
  - On drop: POST /plans/reorder with new order per column
  - Toast "Plan items reordered"
- Visual feedback: ghost card, chosen highlight, smooth animation
- Cards show: title, description snippet, subtask progress bar, linked chapter badge, deadline, estimated vs actual word count
- Quick status change via card context menu

**Plan Item Subtasks/Checklists**
- Add subtasks to any plan item
- **Drag-and-drop reorder subtasks** (SortableJS)
- Checkbox to mark complete
- Progress bar on card showing completion percentage
- Edit subtask title inline

**Corkboard / Index Card View** *(NEW, optional)*
- Scrivener-style card grid; each plan item or chapter = one index card
- Cards show title + synopsis snippet + status pin color
- Rearrange via drag-and-drop; reorder persists to sort_order

**Nested Outline View**
- Chapters → Scenes → Beats hierarchy
- Expand/collapse sections
- **Drag-and-drop reorder**: Reorder plan items, nest/unnest by dragging
  - Drag item onto another item to make it a child
  - Drag item to top level to un-nest
- Show word count per act/section
- Status indicators (colored dots)
- Link plan items to chapters

**Multi-Track Timeline**
- Parallel lanes for: Main Plot, Subplot 1, Subplot 2, Character Arc, etc.
- **Drag-and-drop track reordering** (SortableJS)
- Event pins colored by type: plot_point, character_moment, climax, resolution
- **Zoom controls**: Switch between per-day, per-week, per-month granularity
- Click event → show details or navigate to linked plan/chapter
- Add new event by clicking on timeline
- Edit event: title, description, type, linked plan/chapter, date

**Dependencies**
- depends_on field on plan items
- Visual arrows between dependent items on Kanban board
- Warn on status conflicts (e.g., dependent is "idea" but blocker is "writing")

**Effort Estimation**
- Estimated word count field on plan item
- Actual word count computed from linked chapter
- Show estimated vs actual on card

**Deadline Tracking**
- Date picker for plan item deadlines
- Overdue warnings on Kanban board (red border)
- Upcoming deadlines widget on dashboard

### 5.5 World Building

**Tab-Based Library**
- Tabs: Locations, Lore & Rules, Factions, Glossary + Custom Types
- Custom types configurable in settings (add/remove types)
- Each tab shows entries in card or list view

**Search and Filter** (FTS5)
- Search box per sub-tab (searches name and content)
- Filter by category within type
- Filter by type-dependent field: region (locations), era (lore), allegiance (factions)
- Filter by date range

**Sort Options**
- By name (A-Z, Z-A)
- By category
- By date created
- By last modified

**CRUD Operations**
- Create: name, type, category, description, content, notes, metadata fields
- Edit: all fields
- Delete: with confirmation dialog
- Duplicate: clone entry with "(copy)" suffix

**Type-Specific Metadata Fields** (stored in metadata JSON):
- Location: region, atmosphere, population, key_events, climate, culture
- Lore: origin_era, source, significance, related_locations
- Faction: allegiance, members_count, territory, leader, values
- Glossary: term, definition, pronunciation, related_terms
- Magic System: source, rules, limitations, known_users
- Species: habitat, lifespan, abilities, society_structure

**Cross-Referencing**
- Link world entries to each other (e.g., a location linked to a faction)
- Link types: located_in, governed_by, allied_with, part_of, custom
- Show clickable references in entry detail
- Click reference → navigate to linked entry
- Back-references: show which entries link to this one

**Location Hierarchy**
- parent_id field for nesting (continent > region > city > building)
- Tree view showing hierarchy
- Click node → expand/collapse children
- Click leaf → navigate to entry

**World Entry Versioning**
- Auto-snapshot on **explicit save** (cost-aware, same policy as chapters)
- Version history page: GET /world/{id}/versions (dedicated template world/versions.html)
- Compare any two versions (side-by-side diff)
- Restore previous version

**Interactive World Map**
- Upload a map image as background (stored under `data/media/maps/`)
- Place clickable pins linking to location entries
- Drag pins to reposition
- Click pin → popup with location name + "View" link
- Zoom/pan the map (mouse wheel + drag)
- Pin color matches location category
- Add pin mode: click on map → select location entry or create new
- Delete pin: right-click → remove (does not delete the location entry)
- Save pin positions to database

**World Bible Export**
- Combined formatted reference document (PDF/DOCX)
- Table of contents
- Sections organized by type (Locations, Lore, Factions, Glossary)
- Each entry formatted with name, description, content

**Drag-and-Drop Reorder**
- Reorder world entries within a type via drag handle
- SortableJS with handle
- POST /world/reorder with new order
- Ghost card, grab handle cursor

### 5.6 Export Engine

**Single Entity Export**
- Any chapter, character, or world entry
- Formats: TXT, MD, DOCX, PDF, JSON, HTML
- Each format properly styled
- Character comparison export: GET /characters/compare?ch1=X&ch2=Y&export=txt (or pdf)

**Full Manuscript Export**
- Concatenated chapters in order
- Formats: TXT, MD, DOCX, PDF, EPUB, HTML
- Table of contents generated from chapter titles

**Print-Ready Manuscript**
- Industry Standard Manuscript Format:
  - 12pt Courier New
  - 1-inch margins all around
  - Double-spaced lines
  - First-line indent (0.5 inch)
  - Chapter headings centered
  - Page breaks between chapters
  - Title page with story title, author name, word count

**Full Project Export**
- DOCX or PDF containing:
  - Title page
  - Table of contents
  - Full manuscript
  - Character sheets (formatted)
  - World bible (formatted)

**DOCX Quality**
- Proper paragraph formatting (not splitting on line breaks)
- Heading levels (Heading 1 for chapters, Heading 2 for sections)
- Page breaks between chapters
- Consistent font and spacing

**HTML Export**
- Styled HTML for browser reading
- Print stylesheet for clean printing
- Chapter navigation sidebar

**EPUB Export**
- Valid EPUB with table of contents
- Chapter navigation
- Metadata (title, author, description)
- Proper encoding

**Character Sheet PDF**
- Visually formatted like a D&D character sheet
- Styled sections with tables
- Avatar circle with initials (or uploaded avatar image)
- Consistent formatting

**Export Configuration**
- Configurable in settings: font, font size, line spacing, margins
- Chapter heading style options
- Page break behavior

### 5.7 Search

- **Full-Text Search**: FTS5 across chapters, characters, world entries
- **Module Filtering**: Search within specific modules or all
- **Case Sensitivity Toggle**
- **Regex Support** (post-filter on FTS results; clearly bounded)
- **Query Length Limit**: Max 200 characters
- **Highlighted results**: `<mark>` around matches with context snippets (FTS `snippet()`)
- **Recent Searches**: Saved in localStorage
- **Keyboard shortcut**: `/` to focus search from anywhere
- **Result cap**: 50 results/module, paginated

### 5.8 Settings

- **Appearance**: Theme (dark/light), chapter viewer font (serif/mono/sans), font size slider
- **Story Metadata**: Title, author, genre, description (used in exports)
- **Writing Goals**: Daily word goal, total word goal
- **Auto-Backup**: Enable/disable, configurable interval hours (default 6), manual backup download, restore from backup
- **Versioning Policy** *(NEW)*: snapshot interval minutes, manual-only mode toggle
- **JSON Import/Export**: Export entire project as JSON, import from JSON (secrets excluded unless explicitly chosen)
- **Manuscript Formatting Defaults**: Font, font size, line spacing, margins
- **Chapter Viewer**: Font family (serif/mono/sans), font size
- **Editor Settings**: Autosave interval, editor theme
- **Session Preferences**: Sidebar collapsed, default sort orders
- **Custom World Entity Types**: Add/remove world entry types
- **Data Health Check**: Validate all references, find orphans, fix word count mismatches — dedicated results page (settings_validate.html)
- **AI (optional)** *(NEW)*: see §8 — enable toggle, provider, base URL, key (masked), model, timeout. Hidden behind a collapsed "Advanced" section so it's out of the default user's way.

---

## 6. Drag-and-Drop — Complete Reference

Every drag-and-drop interaction in the application:

| Location | What is Dragged | Library | Backend Endpoint | Visual Feedback |
|----------|-----------------|---------|-----------------|-----------------|
| Chapter list | Chapter cards for reordering | SortableJS | POST /chapters/reorder | Ghost card, grab handle, toast "Chapters reordered" |
| Kanban board | Plan cards between columns | SortableJS group: 'plans' | POST /plans/{id}/status | Ghost card, column highlight, toast "Plan item moved" |
| Kanban board | Plan cards within column | SortableJS sort: true | POST /plans/reorder | Ghost card, toast "Plan items reordered" |
| Corkboard | Index cards | SortableJS | POST /chapters/reorder (or /plans/reorder) | Ghost card, smooth animation |
| Chapter upload | File into dropzone | Native HTML5 drag-and-drop | File upload handler | Dashed border highlight, file preview |
| Outline view | Plan items for reorder/nest | SortableJS nested groups | POST /plans/reorder | Ghost card, indent feedback |
| Plan subtasks | Subtask items for reorder | SortableJS | POST /plans/{id}/subtasks/reorder | Ghost card |
| Character groups | Characters between groups | SortableJS group: 'groups' | POST /characters/groups/reassign | Ghost card, group highlight |
| World entries | Entries within type for reorder | SortableJS with handle | POST /world/reorder | Ghost card, grab handle |
| Timeline tracks | Track lanes for reorder | SortableJS | POST /plans/timeline/reorder | Ghost card |
| World map | Map pins for repositioning | Custom drag | POST /world/{id}/map-pin | Pin follows cursor |
| Character graph | Graph nodes for repositioning | vis-network built-in | Save position to DB | Node follows cursor |

### SortableJS Configuration

```javascript
new Sortable(element, {
  group: 'unique-group-name',
  animation: 150,
  ghostClass: 'sortable-ghost',
  chosenClass: 'sortable-chosen',
  dragClass: 'sortable-drag',
  handle: '.drag-handle',
  filter: '.no-drag',
  onEnd: function(evt) {
    var ids = Array.from(evt.to.children).map(function(el) { return el.dataset.id; });
    fetch('/endpoint', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ order: ids })
    }).then(function(r) { return r.json(); }).then(function(data) {
      if (data.ok) showToast('Reordered', 'success');
    });
  }
});
```

### CSS for Drag States

```css
.sortable-ghost { opacity: 0.4; background: var(--accent-light); }
.sortable-chosen { box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.sortable-drag { transform: rotate(2deg); }
.drag-handle { cursor: grab; }
.drag-handle:active { cursor: grabbing; }
```

---

## 7. UI/UX

### Layout
- Persistent left sidebar (224px, collapsible): Logo, nav links, version label
- Main content area: scrollable, responsive
- Floating undo/redo toolbar: bottom-right, always visible
- Toast notification area: bottom-center, auto-dismiss after 3s

### Responsive Design
- Desktop: full sidebar + main content
- Tablet: sidebar collapses to icons
- Mobile: sidebar becomes hamburger menu, panels stack, cards go single-column

### Themes
- Dark theme (default): deep navy/slate background, indigo accent
- Light theme: white/gray palette
- CSS variables for all colors, switchable via `data-theme` attribute

### Reusable Components
- Card: rounded, shadow, hover state, optional drag handle
- Badge: status indicator (colored dot + text)
- Button: primary, secondary, ghost, danger variants
- Modal: confirmation dialogs, form overlays
- Toast: success/error/info notifications, auto-dismiss
- Form inputs: text, textarea, select, checkbox, date picker
- Progress bar: linear and circular
- Tabs: horizontal tab navigation
- Dropdown: context menus, action menus

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| Ctrl+N | New chapter |
| Ctrl+Shift+N | New character |
| Ctrl+S | Save current form/editor (creates version snapshot) |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z | Redo |
| `/` | Focus global search |
| F11 | Toggle distraction-free mode |
| Escape | Close modal / exit distraction-free |
| Ctrl+E | Toggle edit mode on detail pages |

### Breadcrumbs
On all sub-pages: Dashboard > Chapters > Chapter Title

### Undo System
- Command-pattern undo/redo (100 operations)
- Persistent in database
- Undo toast after delete: "Item deleted. Undo?" with 10-second window

### Error Pages
- Custom 404.html: "Page not found" with link to dashboard
- Custom 500.html: "Something went wrong" with retry button
- Registered via Flask error handlers in app.py; all 500s are logged with a request-id shown to the user

### Client-Side Interactions
- `cycleStatus()`: Click status badge on chapter card to cycle draft → revised → final
- `exportDiff()`: Export visible diff as TXT or HTML file (client-side download)

---

## 8. AI Layer (Optional, Hybrid, Opt-In) — NEW

> Design principle: **the app is fully usable and complete without AI.** AI is a power-user add-on, kept behind a Settings toggle, never in the default UI flow. No AI calls happen unless `ai.enabled = true`. When disabled, `/ai/*` routes return `404` and the `ai.js` bundle is not loaded.

### Providers (hybrid)
- **Local (preferred):** Ollama at `http://localhost:11434` — zero data leaves the machine. Compatible with local-first philosophy.
- **API:** any OpenAI-compatible endpoint (`/v1/chat/completions`) with a user-supplied base URL + key.

`ai_service.py` is a thin adapter: `generate(prompt, *, max_tokens, temperature)` → returns text or a typed error. It detects Ollama vs OpenAI-compat by `ai.provider`. No heavy SDK is a hard dependency; plain `requests`/`httpx` only.

### Capabilities (all opt-in per call, never automatic)
- **Continue writing**: given the end of a chapter, suggest the next paragraph(s)
- **Summarize**: chapter → synopsis; character → one-line summary
- **Rewrite / tone shift**: rewrite a selection in a chosen tone
- **Consistency check** *(high-value)*: scan chapters for contradictions against the character/world DB (e.g., eye color differs across chapters) — returns a findings list, user reviews before any change
- **Name generator**: culture-style names for characters/locations
- **Tag/synopsis suggestion**: propose tags or a synopsis for an untagged chapter

### UX placement
- A subtle "✨ Assist" button appears in the editor toolbar **only when AI is enabled**.
- Findings from the consistency check open in a review modal — **nothing is edited without explicit accept**.
- Every AI action is logged to `activity_log` with `entity_type='ai_action'` (prompt text is **not** stored; only action type + entity id + timestamp, to avoid retaining possibly-sensitive prose).
- Streaming responses render token-by-token with a Stop button.

### Safety / privacy
- API key never logged, never templated, never exported unless explicitly chosen.
- On first enable, show a one-time disclosure: which provider, where data goes (local vs external), and that prose is sent only for the chosen provider.
- Rate-limit per session (e.g., max 30 requests/min) to avoid runaway costs.

---

## 9. Security  *(NEW section, hardens v3)*

### CSRF
- Flask-WTF `CSRFProtect` enabled app-wide. Every state-changing request (POST/PUT/PATCH/DELETE) requires a valid token. JS reads token from a meta tag (`getCsrfToken()`).

### File Upload Hardening (`security/upload.py`)
- **Allow-list extensions**: txt, md, docx, pdf, rtf, odt, html, htm, csv.
- **Size cap**: 25 MB per file, 30 MB per request body. Enforced before reading the whole file (stream + early abort).
- **Magic-byte check**: verify the claimed type against file signature (e.g., `%PDF-`, ZIP/DOCX `PK\x03\x04`), not just the extension/MIME header.
- **Filename sanitization**: strip path components, replace dangerous chars, force a safe extension, store under `data/raw/{type}/{uuid}/{safe}`. Client-supplied filenames **never** determine the on-disk path.
- **Scan content** for embedded scripts when importing HTML (strip `<script>`, `on*=` handlers) before display/export.

### Input Limits (`security/limits.py`)
- Centralized constants (see §3 Rule 9). Single source of truth imported by services and forms.

### Path Safety
- All file reads/writes resolve through a `safe_join(root, *parts)` helper that rejects traversal (`..`, absolute paths, drive letters on Windows).
- `send_from_directory` with explicit allowed roots only.

### Local Threat Model
- Even on localhost, another browser tab/extension can issue CSRF — hence CSRF is mandatory, not optional.
- No `eval`, no `innerHTML` of untrusted content; render user content via Jinja autoescape + a sanitization step for imported HTML.

---

## 10. Error Handling & Logging  *(NEW section)*

- **Typed exceptions** in `core/errors.py`: `NotFoundError`, `ValidationError`, `UploadError`, `ConflictError`, `AiDisabledError`, `AiProviderError`. Each maps to an HTTP status + user message.
- **Global handlers** in `app.py` render 404/500 pages and log 500s with a generated `request_id` (shown to the user for support).
- **Logging**: `RotatingFileHandler` → `data/logs/asm.log` (10 MB × 5 files). Format includes timestamp, level, module, request_id. Service writes log at INFO; caught-but-handled errors at WARNING; unhandled at ERROR.
- **Never log**: API keys, full prompt bodies, raw file contents, personal prose beyond a short excerpt.
- Background threads (backup, AI) attach their own logger names so their output is distinguishable.

---

## 11. Testing

### Unit Tests (pytest)
- Service tests for each service method with in-memory SQLite (WAL still set pragmatically where supported)
- Model tests for relationships, constraints, computed fields
- **FTS5 search tests**: index sync via triggers, MATCH queries, snippet highlighting
- Diff engine tests for line-level and word-level diffing
- Export tests for each format
- Stats tests for streak calculation, word counts, activity, annual heatmap
- **Versioning policy tests**: confirm snapshots are created on save/status/reupload but NOT on every autosave
- **AI service tests**: mocked HTTP; `AiDisabledError` when disabled; provider routing
- **Upload security tests**: oversize reject, bad extension reject, magic-byte mismatch reject, path-traversal filename sanitize

### Integration Tests (pytest + Flask test client)
- Route tests for each Blueprint (CSRF enforced — missing token ⇒ 400)
- CRUD flows: create, read, update, delete for each entity type
- Drag-and-drop: reorder endpoints accept and persist correct order
- Export flows: correct content types and file content
- Search: correct results with highlighting
- **AI routes return 404 when disabled, 200 when enabled+mocked**

### Fixtures

```python
import pytest
from app import create_app
from core.db import init_db

@pytest.fixture
def client():
    app = create_app(testing=True)
    init_db(seed_defaults=True)
    with app.test_client() as client:
        yield client

@pytest.fixture
def seed_data():
    # 3 chapters, 2 characters, 1 plan, 1 world entry
    pass

@pytest.fixture
def ai_enabled(client):
    # flips settings.ai.enabled = true with a mocked provider
    pass
```

### Commands

```
pytest
pytest -v
pytest --cov=services --cov=routes
pytest -x
pytest tests/test_security_upload.py
```

---

## 12. Performance Budget  *(quantified, revises v3)*

1. SQLite indexes on `sort_order`, `status`, `entity_type`, `timestamp`, `project_id`, and FK columns.
2. **WAL mode** for concurrent reader/writer throughput; `busy_timeout=5000`.
3. In-memory caching for stats and entity lists with TTL (invalidate on write). Stats cache TTL 60s.
4. Lazy loading: don't load all relationships in list views (use `select`/column queries, not full ORM graphs).
5. **Pagination thresholds (server-side)**: chapters 30/page, world entries 40/page, search results 50/module. Anything exceeding is paginated, never all-loaded.
6. Debounced autosave (default 3s) — updates content only, no version row.
7. Background exports with progress indicator; large exports streamed, not held in memory.
8. **FTS5** for search instead of `LIKE '%...%'` on large text columns.
9. Query budgets: list pages ≤ 5 DB round-trips; dashboard ≤ 8. Asserted in integration tests via a query-count fixture (warn, not fail, to avoid brittleness).

---

## 13. What NOT to Build

- No real-time collaboration
- No plugin/extension system
- **No multi-project UI in v4** (schema is ready; UI/switcher is a future extension — see §20)
- No Gantt chart
- No authentication
- No cloud sync
- **No AI by default** — AI is strictly opt-in and optional (see §8)

---

## 14. Seed Data

Script that creates:
- 1 default project
- 5 sample chapters (varying statuses, 1000–3000 words each)
- 8 sample characters (with groups and relationships)
- 6 sample plan items (spread across Kanban columns, with subtasks)
- 10 sample world entries (locations, lore, factions, glossary)
- 2 sample character arcs
- Realistic activity log for past **60 days** (enough for the annual heatmap + streaks)
- Pre-configured settings (AI disabled)

---

## 15. File Naming

- Python: `snake_case.py`
- Templates: `snake_case.html` in module directories
- Static JS/CSS: `kebab-case`
- Blueprints: named after module (chapters, characters, plans, world, export, settings, dashboard, search, ai)
- URLs: kebab-case (`/chapter-list` not `/chapterList`)
- CSS: Tailwind utilities + custom classes in kebab-case

---

## 16. Development Order

### Phase 1 — Foundation & Hardening
1. Project structure, `core/db.py` (WAL, scoped sessions, locks), `core/logging.py`, `core/errors.py`, Flask-WTF CSRF
2. SQLAlchemy models **incl. `projects`, FTS5 virtual tables + triggers**
3. Alembic migrations
4. `security/upload.py` + `security/limits.py`
5. Chapter service (CRUD, cost-aware versioning, reorder)
6. Chapter routes and templates
7. Drag-and-drop chapter reorder
8. Chapter + versioning + upload-security tests

### Phase 2 — Characters
1. Character service (CRUD, groups, relationships)
2. Character routes and templates
3. Relationship graph with vis-network (local)
4. Character arc tracking
5. Character comparison
6. Tests

### Phase 3 — Plans
1. Plan service (CRUD, subtasks, status)
2. Kanban board with drag-and-drop
3. Outline view with nested drag-and-drop
4. Corkboard view (optional)
5. Multi-track timeline with zoom
6. Tests

### Phase 4 — World Building
1. World entry service (CRUD, versioning, hierarchy)
2. World entry templates with FTS5 search/filter
3. Cross-referencing
4. Interactive world map
5. Tests

### Phase 5 — Dashboard + Stats
1. Stats service (writing history, streaks, word counts, annual heatmap)
2. Dashboard with all widgets
3. Word-count history chart
4. Character appearance heatmap
5. Tests

### Phase 6 — Export + Search
1. Export service for all formats
2. Print-ready manuscript formatting
3. FTS5-backed full-text search UI
4. Tests

### Phase 7 — Settings + Polish
1. Settings page (incl. versioning policy, pagination defaults)
2. Auto-backup and restore
3. JSON import/export (secrets excluded unless chosen)
4. Keyboard shortcuts
5. Light theme
6. Responsive design
7. Final testing

### Phase 8 — Optional AI Layer
1. `ai_service.py` adapter (Ollama + OpenAI-compatible)
2. `/ai/*` routes (404 when disabled)
3. `settings_ai.html` (collapsed "Advanced" section)
4. Editor "✨ Assist" button (conditional load of `ai.js`)
5. Consistency-check review modal
6. Mocked provider tests + `AiDisabledError` tests

---

## 17. Settings Keys — Quick Reference

See §4 "Settings Keys" table. Note the new keys: `active_project_id`, `version_snapshot_interval_minutes`, `ai.*`.

---

## 18. Concurrency Model (summary)

- Single writer lock (`core/db.py`) guards write transactions; combined with SQLite `busy_timeout=5000` + WAL for reader concurrency.
- Background threads (backup, AI streaming) open **their own** scoped session and never share the request session.
- All multi-step writes (e.g., reorder + activity_log insert) occur inside one transaction; on any exception the whole transaction rolls back.

---

## 19. Local Vendor Setup (Offline Guarantee) — NEW

The app must run with no internet. All third-party assets are vendored:

1. `scripts/fetch_vendor.py` downloads each asset, writes it under `static/vendor/<pkg>/`, and appends a line to `static/vendor/MANIFEST.txt`:
   `name | version | source_url | local_path | sha256`
2. On startup, `app.py` (or a `core/vendor.py` check) verifies the manifest exists and warns (does not crash) if an entry is missing — pointing the user to `python scripts/fetch_vendor.py`.
3. Fonts (Inter, Noto Serif, JetBrains Mono) are bundled as `.woff2` under `static/vendor/fonts/` and declared via `@font-face` in `main.css`. **No `<link>` to Google Fonts.**
4. Tailwind is a **precompiled** local CSS (`static/vendor/tailwind/tailwind.min.css`) — not the CDN JIT script.
5. `base.html` references every asset via `{{ url_for('static', filename='vendor/...') }}`, never an `https://` URL.

Assets to vendor: Tailwind (compiled), Alpine.js, SortableJS, vis-network, EasyMDE (or Tiptap), Chart.js, and the three font families.

---

## 20. Future Extensions (not built in v4, but schema-ready)

- **Multi-book / series UI**: `projects` table + `project_id` already exist. A future project switcher + per-project settings is a UI-only addition; no content-table migration needed. `active_project_id` setting already selects the active one.
- **Git-style local version control** (commit/branch/rollback) on top of `*_versions` tables.
- **Optional cloud backup** (Dropbox/Google Drive) as an additional backup target.
- **Obsidian/Markdown vault** two-way sync.
- **Consistency checker** expanding into a fuller "story lint" (timeline conflicts, pacing).

---

Build this app from scratch. Every feature listed above must be implemented. Do not skip any drag-and-drop interaction. Do not enable AI by default. Do not reference any existing code.
