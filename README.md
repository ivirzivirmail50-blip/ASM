# Absolute Story Manager v5.0

> **Local-first, single-user creative writing management tool.** Works completely offline — no CDN, no cloud, no account required.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

### 📝 Writing & Editing
- **Chapter Management** — CRUD, drag-reorder, file upload (TXT/DOCX/PDF/RTF/ODT/HTML), EasyMDE editor, version control, diff, split/merge
- **Focus Mode Pro** — Full-screen distraction-free writing with Pomodoro timer, auto-save, customizable background/font/width
- **Reading Mode** — Continuous scroll across chapters, font/size/line-height controls, 4 themes, auto-resume
- **Scene Cards** — Auto-extract scenes from chapters, corkboard view, drag-drop reorder, mood/status/location metadata
- **Quick Capture** — Dashboard widget for instant notes, chapters, journal entries, or snippets

### 🧠 AI Features (Optional — Disable in Settings)
- **AI Editor Copilot** — Continue, expand, shorten, or generate dialogue from your text
- **Character AI Chat** — Talk to your characters using their voice profile and background
- **AI Assistant** — Context-aware continuation, consistency check, name generator, streaming chat
- **Character Generator** — Random or AI-powered character creation with full backstories

### 🎭 Characters & World
- **Character Profiles** — Rich profiles with physical, psychological, background, philosophy, voice
- **Voice Profiles** — Define speech patterns, catchphrases, vocabulary; scan dialogue for consistency
- **Character Arcs** — Track development stages with progress bars and chapter links
- **Mood Tracker** — Per-chapter emotional state timeline (8 moods, 3 intensities)
- **Relationship Graph** — Interactive vis-network graph with group support, drag-save positions
- **Relationship Timeline** — Character×character relationship matrix
- **Family Tree** — Visual family tree with parent/marriage relations
- **World Library** — Typed entries (location/lore/faction/glossary), hierarchy tree, versioning
- **Interactive World Map** — Upload images, place colored pins, **nested sub-maps** (Galaxy → Planet → City → Street), travel routes

### 📊 Analysis & Tracking
- **Writing Analytics** — Per-chapter: word count, dialogue ratio, lexical diversity, reading time
- **Word Frequency Analyzer** — Overused words, repeated phrases, character mention counts
- **Pacing Analysis** — Tension curve, word distribution, dialogue vs narration
- **Story Lint** — 7 automated checks (repeated words, sentence length, adverbs, passive voice, etc.)
- **Glossary & Style Sheet** — Term consistency with Levenshtein near-miss detection
- **Spell Check** — English dictionary + custom words, disable for non-English writers
- **Manuscript Forecast** — Completion date prediction based on writing pace
- **Writing Habits** — 7×24 heatmap, best day/hour, streak tracking

### 📅 Planning & Motivation
- **Kanban Board** — 6-column (idea→final), subtasks, dependencies, deadlines
- **Plot Structure Templates** — 11 structures (Hero's Journey, Save the Cat, Three-Act, Seven-Point, Freytag, Kishōtenketsu, Fichtean Curve, Heroine's Journey, Tragedy, Voyage & Return, Comedy)
- **Timeline** — Vertical/horizontal, zoom, colored pins, event CRUD
- **Timeline Audit** — Detects ordering violations, cycles, gaps, character double-booking
- **Goals Calendar** — Monthly heatmap, year overview, daily/weekly/monthly progress
- **Achievements** — 18 badges across 5 categories (streak/words/chapters/cast/consistency)
- **Milestones** — 12 word-count milestones (1K → 1M) with one-time celebrations
- **Session Timer** — Pomodoro-style focused sessions with WPM tracking
- **Writing Journal** — Daily mood, energy, wins, struggles, gratitude
- **Prompt Calendar** — Daily writing prompts in calendar view
- **Inspiration Hub** — 70+ curated prompts, scenario generator, daily prompt
- **Chapter Dependencies** — DAG with cycle detection and topological sort

### 📦 Export & Publish
- **Export** — TXT/MD/HTML/DOCX/PDF/EPUB/JSON, async progress, Scrivener compile presets
- **Compile Wizard** — Publication-ready manuscript with front matter, TOC, back matter
- **Scrivener Export** — .scriv-compatible ZIP package
- **Interactive EPUB** — EPUB 3 with embedded character cards and navigable TOC
- **Serial Reader** — Clean web-based reading interface with prev/next navigation
- **Story Bible** — Auto-generated reference document (characters, world, timeline, glossary)
- **Manuscript Diff** — Compare manuscript state between two dates
- **Find & Replace** — Regex-supported bulk search with preview
- **Submission Tracker** — Track markets, response times, acceptance rate

### 🎨 Customization
- **Theme Editor** — 7 preset themes (dark/light/sepia/forest/ocean/sunset/midnight), 13 CSS variable overrides, custom CSS
- **Multi-language UI** — English, Türkçe, Español, Français, Deutsch
- **Snippets & Templates** — Reusable text blocks and chapter templates
- **Notes & Ideas** — Quick-capture inbox with 6 categories, cross-references, promote to chapter/snippet/plan
- **Research & References** — Track books, articles, websites with quotes and ratings
- **Music Player** — Upload and play local audio files with custom progress bar
- **Keyboard Shortcuts** — `?` for cheatsheet, `g` chord navigation, `t` theme, `b` sidebar

## Quick Start

```bash
# Clone
git clone https://github.com/yourusername/absolute-story-manager.git
cd absolute-story-manager

# Install dependencies
pip install -r requirements.txt

# Run
python app.py
# → Opens at http://localhost:3000/
```

**Windows:** Double-click `start.bat`

## Configuration

### AI (Optional)
1. Settings → AI → Enable
2. Choose provider: Ollama (local) or OpenAI-compatible (Groq, OpenRouter)
3. Enter API base URL and key
4. Click ↻ to fetch model list

### Interface Language
Settings → Appearance → Interface Language → English / Türkçe / Español / Français / Deutsch

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+, Flask 3.x, SQLAlchemy 2.x |
| Database | SQLite (WAL mode + FTS5 full-text search) |
| Frontend | Tailwind CSS, Alpine.js, SortableJS, vis-network, EasyMDE, Chart.js |
| AI (optional) | Ollama / OpenAI-compatible API |
| Assets | All vendor files bundled locally (no CDN) |

## Project Structure

```
absolute-story-manager/
├── app.py                 # Flask app factory + main entry
├── config.py              # Configuration
├── requirements.txt
├── start.bat              # Windows launcher
├── core/                  # DB, CSRF, errors, logging, cache
├── models/                # 26 SQLAlchemy models
├── routes/                # 60+ blueprints (one per feature)
├── services/              # 51 service modules
├── templates/             # 100+ Jinja2 templates
├── static/                # CSS, JS, vendor assets
├── tests/                 # 870+ tests
├── data/                  # SQLite DB, media, backups (gitignored)
└── scripts/               # Vendor fetch, seed data, init
```

## Statistics

| Metric | Value |
|--------|-------|
| Python files | 195+ |
| HTML templates | 105+ |
| Blueprints | 60+ |
| Test count | 870+ |
| Plot templates | 11 |
| Languages | 5 (EN/TR/ES/FR/DE) |
| Export formats | 30+ combinations |

## License

MIT — See LICENSE file for details.
