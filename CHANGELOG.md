# Absolute Story Manager — Changelog

> Tüm sürüm geçmişi: eklenen özellikler, düzeltmeler ve iyileştirmeler.

---

## v4.0.0 — Final (2026-07-03)

### Temel Sürüm (İlk Kurulum)
- Flask 3.x + SQLAlchemy + Jinja2 + Tailwind + Alpine.js + SortableJS + vis-network + EasyMDE + Chart.js
- Tüm vendor asset'leri offline (CDN yok)
- SQLite WAL mode + FTS5 full-text search
- Dark/Light tema, responsive design
- 9 Blueprint: dashboard, chapters, characters, plans, world, search, export, settings, ai

### Modüller
- **Dashboard**: Story cockpit, ring chart, 30-gün word chart, 365-gün heatmap, streak, karakter appearance heatmap
- **Chapters**: CRUD, drag-reorder, upload (TXT/MD/DOCX/PDF/RTF/ODT/HTML/CSV), EasyMDE editor, cost-aware versioning, split/merge, diff
- **Characters**: Rich profiles, groups, relationships, vis-network graph (drag-save-position, click-to-create, filters), arcs, timeline, compare
- **Plans**: Kanban (SortableJS), outline (nested DnD), timeline (multi-track), subtasks, dependencies, deadlines
- **World**: Tab library, type-specific metadata, cross-references, hierarchy tree, interactive map, versioning
- **Search**: FTS5 + LIKE fallback, case-sensitive, regex, recent searches (localStorage)
- **Export**: TXT/MD/HTML/DOCX/PDF/EPUB/JSON, async progress, Scrivener compile presets
- **Settings**: Appearance, story metadata, goals, versioning, pagination, backup, import/export, AI, data health
- **AI (opt-in)**: Ollama/OpenAI-compatible, continue/summarize/tags/consistency-check/name-generator/dialogue/streaming

---

## Düzeltmeler ve Eklemeler (Kronolojik)

### Tur 1: İlk Sürüm
- Temel proje yapısı oluşturuldu (models/, services/, routes/, templates/, static/)
- Tüm modeller: projects, chapters, chapter_versions, characters, character_groups, character_relationships, character_arcs, plans, plan_subtasks, world_entries, world_entry_versions, world_entry_relations, activity_log, settings
- FTS5 virtual tables + sync triggers
- Tüm servisler: chapter, character, plan, world, stats, search, export, diff, versioning, validate, backup, ai
- Tüm route'lar (80+ URL)
- Tüm template'ler (36 HTML)
- Vendor script (offline asset indirme)
- Seed data (8 karakter, 5 bölüm, 6 plan, 10 world entry)

### Tur 2: Test ve Düzeltmeler
- **Düzeltme**: `cycleStatus` JS chapter'ı bozuyordu → ayrı endpoint eklendi
- **Düzeltme**: World map pin kaldırma çalışmıyordu → null koordinatlar desteklendi
- **Düzeltme**: Chapter service empty title koruması eklendi
- **Düzeltme**: Activity log dashboard linkleri düzeltildi
- **Düzeltme**: Cost-aware versioning mantığı düzeltildi (status change artık snapshot oluşturuyor)
- **Ekleme**: Character Timeline page
- **Ekleme**: Kanban subtask progress bar
- **Ekleme**: Outline nested reorder persist
- **Ekleme**: AI "✨ Assist" editor toolbar butonları
- **Ekleme**: AI activity log entegrasyonu
- **Test**: 129 pytest + 91 integration test = 220 test

### Tur 3: PROMPT_V4 Eksik Giderme
- **Ekleme**: Persistent undo sistemi (DB-backed, 100 entry cap, delete-with-undo)
- **Ekleme**: Chapter `versions/save`, `diff/export` endpoint'leri
- **Ekleme**: Character compare export (TXT + PDF)
- **Ekleme**: World version compare
- **Ekleme**: Custom world types CRUD
- **Ekleme**: JSON import/export (tam DB round-trip)
- **Ekleme**: Search case-sensitive + regex
- **Ekleme**: AI consistency check, streaming, rate limit (30/dk)
- **Ekleme**: AI first-enable disclosure modal
- **Ekleme**: Plan dependency warnings + overdue display + effort vs actual
- **Ekleme**: Character Groups page (drag-drop between groups)
- **Ekleme**: Corkboard view
- **Ekleme**: World Hierarchy tree
- **Ekleme**: Word-level diff highlighting + hunk navigation
- **Ekleme**: World map image upload + zoom/pan
- **Ekleme**: Timeline zoom controls (Day/Week/Month)
- **Ekleme**: Mobile responsive (tablet icon-only, mobile hamburger)
- **Ekleme**: Distraction-free editor mode
- **Ekleme**: Ctrl+E edit mode toggle
- **Ekleme**: Subtask inline edit
- **Ekleme**: Manuscript formatting settings
- **Test**: 181 pytest

### Tur 4: Altyapı Eksikleri
- **Ekleme**: `start.bat` Windows launcher (venv + requirements + flask run)
- **Ekleme**: 9 reusable component template (card, modal, badge, button, toast, progress_bar, form_input, tabs, dropdown)
- **Ekleme**: Vendor manifest startup kontrolü
- **Ekleme**: Ayrı JS dosyaları (world_map.js, charts.js, diff.js)
- **Ekleme**: Kanban dependency arrows (SVG overlay)
- **Ekleme**: Timeline event add/edit popup
- **Ekleme**: Search pagination
- **Ekleme**: 4 yeni test dosyası (export, diff, validate, backup)
- **Test**: 245 pytest

### Tur 5: AI + Cache + Pagination
- **Ekleme**: `ai.disclosure_accepted` setting (bir kez göster, sonra kaydet)
- **Ekleme**: `core/cache.py` — thread-safe in-memory cache (TTL + invalidate)
- **Ekleme**: Stats cache (11 fonksiyon, 60s TTL, write'da invalidate)
- **Ekleme**: Background export progress (async_export + status/download)
- **Ekleme**: Timeline track reorder (SortableJS + persist)
- **Ekleme**: Configurable pagination (chapters_per_page, world_per_page, search_results_per_module)
- **Ekleme**: World pagination
- **Düzeltme**: Manuscript line spacing 24pt (double-spaced) — settings'den okur
- **Test**: 272 pytest

### Tur 6: Kritik Bug Düzeltmeleri
- **Düzeltme**: `start.bat` NameError — `_verify_vendor_manifest` create_app'den önce taşındı
- **Ekleme**: Browser otomatik açılış (webbrowser.open + threading)
- **Ekleme**: `tests/test_versioning_service.py` (16 test)
- **Ekleme**: Toplu drag-drop import (çoklu TXT/PDF → chapters veya world entries)
- **Düzeltme**: Karakter "Invalid Response" — tüm form JS'leri FormData gönderiyor (JSON değil)
- **Ekleme**: `submitForm()` yardımcı fonksiyonu app.js'ye eklendi
- **Düzeltme**: 8 form template'inin JS'i sıfırdan yeniden yazıldı
- **Test**: 288 pytest

### Tur 7: CSRF Düzeltmesi
- **Düzeltme**: Tüm Blueprint'ler CSRF'den muaf tutuldu (local-first app)
- **Düzeltme**: 10 form template'ine CSRF hidden field eklendi
- **Düzeltme**: Browser double açma sorunu (use_reloader=False)
- **Düzeltme**: Bulk import FormData'ya csrf_token eklendi
- **Test**: 288 pytest

### Tur 8: P0/P1 Özellikler
- **Ekleme**: Quick Switch (Ctrl+P) — global command palette
- **Ekleme**: Canlı kelime sayacı + Writing Sprint Timer (25dk, WPM, pause/resume)
- **Ekleme**: Version diff live preview (toggle, canlı diff)
- **Ekleme**: Story Lint Engine (AI-free) — 7 kontrol: repeated words, name typos, sentence length, adverb overuse, passive voice, dialogue tags, attribute consistency
- **Test**: 288 pytest

### Tur 9: AI Context + Pacing
- **Ekleme**: AI Context-Aware Continuation (karakter+dünya+plot context ile)
- **Ekleme**: Pacing Analysis — tension curve, word count distribution, dialogue vs narration, rhythm assessment
- **Test**: 288 pytest

### Tur 10: Compile Presets + Horizontal Timeline
- **Ekleme**: Scrivener Compile Presets — 6 profil (Manuscript, Beta Reader, E-book, PDF Book, Blog, Workshop)
- **Ekleme**: Interactive Horizontal Timeline — vertical/horizontal toggle, zoom, renkli pin'ler
- **Test**: 288 pytest

### Tur 11: AI Dialogue + Multi-Book
- **Ekleme**: AI Dialogue Generator — karakter voice/psychology ile diyalog üret (8 duygu seçeneği)
- **Ekleme**: Series/Multi-Book UI — project switcher, create/edit/delete, per-book stats
- **Test**: 288 pytest

### Tur 12: Son Özellikler (Bu Sürüm)
- **Ekleme**: World Map Travel Routes — karakter seyahat rotaları (SVG overlay, create/update/delete)
- **Ekleme**: Beta Reader Mode — read-only chapter + yorum (text selection, resolve/delete)
- **Ekleme**: Composition Mode — tam ekran yazma + arka plan rengi, font boyutu, genişlik ayarı
- **Ekleme**: Scene/Beat Editing — bölüm içinde sahne tespiti ve önizleme (otomatik \n\n\n bölme)
- **Test**: 288 pytest

---

## İstatistikler

| Metric | Value |
|--------|-------|
| Python dosyası | 72 |
| HTML template | 54 |
| JS dosyası | 15 |
| CSS dosyası | 4 |
| Vendor asset | 13 |
| Test sayısı | 288 |
| URL endpoint | 90+ |
| Blueprint | 15 |
| AI özelliği | 9 |
| Export format | 30+ kombinasyon |
| Toplam dosya | 195+ |

## Çalıştırma
```bash
# Windows: start.bat (browser otomatik açılır)
# Linux/Mac: python app.py
# Test: PYTHONPATH=. python -m pytest tests/ -v
```
