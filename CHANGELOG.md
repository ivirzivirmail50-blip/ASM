# Absolute Story Manager — Changelog

> Tüm sürüm geçmişi: eklenen özellikler, düzeltmeler ve iyileştirmeler.

---

## v5.1.0 — New Tools & Bug Fixes (2026-07-21)

### Yeni Özellikler
- **Focus Mode Pro** (`/focus/`): Tam ekran yazma + Pomodoro timer + auto-save + özelleştirilebilir background/font/width
- **AI Editor Copilot** (`/ai-copilot/`): AI ile devam etme, genişletme, kısaltma, diyalog üretme. AI disabled iken gizlenir
- **Character AI Chat** (`/character-chat/`): Karakterinizle ses profilini kullanarak sohbet. AI disabled iken gizlenir
- **Character Generator** (`/character-generator/`): Rastgele karakter üretimi (fantasy/modern/scifi). AI opsiyonel (checkbox AI disabled iken disabled)
- **Family Tree Builder** (`/family-tree/`): vis-network ile aile ağacı. Parent/married relations
- **Web Serial Platform** (`/serial/`): Bölümleri seri olarak okuma. Temiz reader view, prev/next nav
- **Interactive EPUB** (`/interactive-epub/`): EPUB 3 export, gömülü karakter kartları, navigable TOC
- **Nested Sub-Maps**: Hiyerarşik haritalar (Galaksi → Güneş Sistemi → Dünya → Şehir). Breadcrumb navigation, per-level map images
- **i18n Çoklu Dil**: 5 dil (EN/TR/ES/FR/DE). Client-side JS ile sidebar çevirisi. Settings'den dil seçimi
- **World Map Pin Colors**: Pin koyarken 8 renk seçeneği
- **11 Plot Structure Templates**: Hero's Journey, Save the Cat, Three-Act, Seven-Point, Freytag, Kishōtenketsu + 5 yeni (Fichtean Curve, Heroine's Journey, Tragedy, Voyage & Return, Comedy)

### Düzeltmeler
- **Character Arc / Relationship Timeline 500 hatası**: Character nesneleri JSON serializable değildi — plain dict'e çevrildi
- **Word Frequency 500 hatası**: Jinja2'de `max()` fonksiyonu kullanılmış — Jinja2 filter ile değiştirildi
- **Session Timer 180dk başlama**: UTC timezone parsing hatası — ISO string'e `Z` eklenerek düzeltildi
- **Session Timer pause/resume**: Pause sırasında geçen süre de sayılıyordu — `started_at` resume'da sıfırlanıyor, `elapsed_seconds` accumulate ediliyor
- **Dashboard grafik**: Line chart → Bar chart, `max-height: 200px`, `max: Math.ceil(maxValue * 1.2)` ile sabit sınırlar
- **Scene Cards etkileşim**: `onclick` attribute JSON bozuyordu — `data-action` + `addEventListener` ile güvenli handling
- **Music Player seek**: Tıklanınca başa sarıyordu — `getBoundingClientRect` ile düzeltildi
- **Prompt Calendar tıklama**: `onclick` attribute JSON bozuyordu — `data-day` + `addEventListener` ile düzeltildi
- **Sidebar scroll**: CSS'de `overflow-y: auto` yoktu — eklendi, `sessionStorage` ile scroll position hatırlama
- **Spell Check dil seçeneği**: "Disabled — I write in another language" seçeneği eklendi
- **Theme Editor**: Preset değişince CSS üretilmiyordu — default config karşılaştırma düzeltildi
- **Sub-world map pin**: Alt haritada location yoksa "Create New Location" butonu eklendi
- **Port 3000**: Caddy reverse proxy 3000 bekliyordu, Flask 5555'te çalışıyordu — düzeltildi
- **Static file cache**: `SEND_FILE_MAX_AGE_DEFAULT = 0` ile cache devre dışı
- **Map inline JS**: `world_map.js` ayrı dosyada Jinja syntax içeriyordu — template içine inline taşındı
- **Graph group-char**: Group node ID'leri `g-` prefix ile — backend FK constraint kaldırıldı
- **Graph popup**: Draggable + smart positioning + Escape ile kapatma

### GitHub Hazırlık
- `.gitignore` eklendi (Python, venv, DB, backups, media, IDE, OS)
- `README.md` tamamen yeniden yazıldı (özellikler, quick start, tech stack, project structure)
- `CHANGELOG.md` güncellendi

---

## v5.0.0 — Analysis, Moods & Music (2026-07-15)

🎉 **v5.0 Milestone Release** — 51 blueprint, 872 test, 95+ HTML template

### Yeni Modüller
- **Word Frequency Analyzer** (`/word-freq/`): Kelime tekrar analizi. Top N words (stopwords excluded). **Overused words** tespiti (threshold: 1 per 200 words). Repeated 2-word ve 3-word phrases (3+ occurrences). **Character mention count** (name + aliases). Per-chapter breakdown (top 5 words per chapter). Lexical diversity (unique/total ratio). 120s cache.
- **Character Mood Tracker** (`/char-mood/`): Bölüm bazlı karakter duygu durumu. 8 mood (joyful/hopeful/neutral/determined/anxious/afraid/angry/sad) with score 1-5. 3 intensity (low/medium/high). Per-character horizontal mood timeline across chapters. Set/update/delete mood (upsert — bir karakter+bölüm için tek mood). Note per entry. Mood legend.
- **Writing Music Player** (`/music/`): Local audio file player. Upload MP3/OGG/WAV/M4A/FLAC to `data/media/music/`. HTML5 audio player (sticky). Track library with play/delete. File size display. No new model — files on disk only.

### İyileştirmeler
- `models/char_mood.py` — CharacterMood ORM modeli (models/ altında, dairesel import önlemek için)
- Sidebar'a 3 yeni link: Word Frequency (📊), Mood Tracker (😊), Music Player (🎵)

### Mimari
- 3 yeni blueprint: `word_freq`, `char_mood`, `music`
- 1 yeni model: `models/char_mood.py` (CharacterMood)
- 3 yeni service: `word_freq_service`, `char_mood_service`, `music_service`
- Toplam blueprint sayısı: 48 → 51

### Test
- 21 yeni odaklı test (851 → 872)
- tests/test_v50_focused.py — word freq (6), char mood (6), music (6), sidebar (3)
- Kritik yollar: analysis with content, repeated phrases, set/update/delete mood, upload audio, invalid extension, delete track

---

## v4.9.0 — Milestones, Relationships & Scrivener (2026-07-15)

### Yeni Modüller
- **Word Count Milestone Celebrations** (`/milestones/`): 12 word count milestone (1K → 1M). Her milestone: threshold, name, icon, description. Reached/locked status + progress bar. **One-time celebration** (persisted — yeni ulaşılan milestone'lar "newly_celebrated" olarak işaretlenir, tekrar kutlanmaz). Next milestone tracker with progress % ve words remaining. Celebration animation (CSS pulse).
- **Character Relationship Timeline** (`/rel-timeline/`): Karakter ilişkilerini takip et. Mevcut CharacterRelationship modelini kullanır. Relationship matrix (character×character grid). Add/remove relationship (from→to, type, description, bidirectional). Stats (total, bidirectional, types breakdown). Events list. 12 common relationship type suggestion datalist.
- **Export to Scrivener** (`/scrivener/`): `.scriv` format export. ZIP package: `Files/Binder/binder.xml` (project structure), `Files/Docs/*.scrtext` (per-chapter content with metadata headers), `Settings/projectsettings.xml`. Options: include synopsis, include tags, status filter. Her chapter .scrtext dosyası: Title/Synopsis/Keywords/Status/Words header + content. Scrivener import instructions.

### İyileştirmeler
- `models/milestone.py` — MilestoneCelebration ORM modeli (models/ altında, dairesel import önlemek için)
- Sidebar'a 3 yeni link: Milestones (🎉), Relationship Timeline (🕸), Scrivener Export (📦)

### Mimari
- 3 yeni blueprint: `milestones`, `rel_timeline`, `scrivener`
- 1 yeni model: `models/milestone.py` (MilestoneCelebration)
- 3 yeni service: `milestone_service`, `rel_timeline_service`, `scrivener_export_service`
- Toplam blueprint sayısı: 45 → 48

### Test
- 20 yeni odaklı test (831 → 851)
- tests/test_v49_focused.py — milestones (6), rel_timeline (6), scrivener (5), sidebar (3)
- Kritik yollar: milestone reached with words, celebration persists, add relationship, self-rel rejected, matrix, ZIP contains .scrtext + binder.xml

---

## v4.8.0 — Arcs, Forecast & Habits (2026-07-15)

### Yeni Modüller
- **Character Arc Tracker** (`/character-arcs/`): Karakter gelişim yayları. Her karakter için çoklu arc. Her arc'ta stages (JSON: name/description/status/chapter_ids). 4 stage status (planned/active/completed/skipped). Progress %, current stage, overall status. Stage CRUD (add/update/remove). Aggregate stats (total/completed/active/planned arcs + stages). Progress bar per arc.
- **Manuscript Forecast** (`/forecast/`): Tamamlanma tarihi tahmini. 3 pace window (7d/30d/90d): avg words/day, writing days, est. completion date. Daily goal pace ayrı hesaplanır. Milestone projections (30/60/90/180 gün sonra projected words + %). On-track indicator (50%+ complete AND pace ≥ daily goal). 120s cache.
- **Writing Habit Insights** (`/habits/`): En verimli gün/saat analizi. activity_log timestamp'lerinden: best day of week, best hour, day-of-week productivity ranking, hour ranking (top 8), **7×24 heatmap** (day×hour grid, 5 intensity level). Frequency: writing days vs skipped days, % writing days. Longest streak + current streak. 30/90/365 gün seçilebilir.

### İyileştirmeler
- `services/habits_service.py` — empty state için 7×24 heatmap döndürür (always consistent shape)
- Sidebar'a 3 yeni link: Character Arcs, Manuscript Forecast, Writing Habits

### Mimari
- 3 yeni blueprint: `character_arcs`, `forecast`, `habits`
- 0 yeni model (CharacterArc zaten v4.0'dan var, service yeni)
- 3 yeni service: `character_arc_service`, `forecast_service`, `habits_service`
- Toplam blueprint sayısı: 42 → 45

### Test
- 21 yeni odaklı test (810 → 831)
- tests/test_v48_focused.py — character arcs (8), forecast (5), habits (5), sidebar (3)
- Kritik yollar: create arc, add/update stage, progress calc, overall status, forecast paces, heatmap 7×24, insights with activity

---

## v4.7.0 — Threads, Prompts & Dependencies (2026-07-15)

### Yeni Modüller
- **Beta Reader Comment Threads** (`/beta/`): Yorumlara yanıt (reply) desteği. BetaComment modeline `parent_id` + `is_author_reply` alanları eklendi. Top-level comments + nested replies. resolve/reopen lifecycle (cascades to replies). `get_threaded()` dict yapısı. `stats()` aggregate (total/top_level/replies/open/resolved/author_replies). Author vs reader ayrımı.
- **Writing Prompts Calendar** (`/prompt-calendar/`): inspiration_service'deki deterministik günlük prompt'ları takvim görünümünde. Her gün için prompt category + text. Month grid (Mon-Sun). Prev/next navigation. Today's prompt highlight. Day click → modal with full prompt → save veya new chapter. inspiration_service'i reuse eder (no new model).
- **Chapter Dependency Tracker** (`/chapter-deps/`): Bölümler arası bağımlılık grafiği. "Chapter A depends on Chapter B" = B before A. Cycle detection (DFS). Ordering violation detection (dependent before prerequisite). Blocked chapters (unmet deps). Topological sort (Kahn's algorithm). vis-network graph (hierarchical LR layout). Add/remove dependency UI.

### İyileştirmeler
- `models/beta_comment.py` — parent_id + is_author_reply alanları eklendi (migration: DB silinip yeniden oluşturulmalı)
- `services/beta_service.py` — delete_comment artık flush yaparak FK constraint hatasını önler
- Sidebar'a 2 yeni link: Prompt Calendar, Chapter Deps

### Mimari
- 3 yeni blueprint: `prompt_calendar`, `chapter_deps` (beta threads mevcut beta blueprint'e eklendi)
- 1 yeni model: `models/chapter_deps.py` (ChapterDependency)
- 2 yeni service: `chapter_deps_service` (prompt_calendar mevcut inspiration_service'i reuse eder)
- Toplam blueprint sayısı: 40 → 42

### Test
- 17 yeni odaklı test (793 → 810)
- tests/test_v47_focused.py — beta threads (5), prompt calendar (5), chapter deps (5), sidebar (2)
- Kritik yollar: add/reply/resolve/reopen/delete cascade, month/day API, add/remove dep, self-dep rejected, reverse-dep rejected

---

## v4.6.0 — Focus & History (2026-07-15)

### Yeni Modüller
- **Writing Session Timer** (`/sessions/`): Pomodoro-style odaklı yazım oturumları. 5 session type (pomodoro 25min, short_focus 15min, long_focus 50min, sprint 10min, custom). Start/pause/resume/complete/abandon lifecycle. Otomatik word count delta (start vs end). Live timer (JS setInterval). WPM hesaplama. 30-day aggregate stats (total sessions, minutes, words, avg WPM). Tek active session constraint.
- **Manuscript Snapshot Diff** (`/snapshot-diff/`): İki tarih arası manuscript değişikliklerini karşılaştır. chapter_versions kullanarak geçmiş state'i reconstruct eder. Added/removed/modified chapters tespiti. Per-chapter word count delta + first differing line preview. Net word change. HTML download (styled). Date picker (available snapshot dates).
- **Quick Capture Widget** (dashboard): Tek widget'tan 4 tür hızlı yakalama — note, chapter, journal, snippet. Type selector + title + body + Ctrl+Enter. AJAX submit, toast feedback. Mevcut servisleri (note_service, chapter_service, journal_service, snippet_service) reuse eder — duplicate code yok.

### İyileştirmeler
- Dashboard'a Quick Capture widget'ı eklendi — açılışta hızlı fikir yakalama
- Sidebar'a 2 yeni link: Session Timer, Manuscript Diff
- **Test stratejisi değişikliği**: Bu sürümde sadece 24 odaklı test eklendi (önceki sürümler 90+). Kritik yollar ve edge case'ler üzerine odaklanıldı, exhaustive coverage değil.

### Mimari
- 3 yeni blueprint: `sessions`, `snapshot_diff`, `quick_capture`
- 1 yeni model: `models/session.py` (WritingSession)
- 2 yeni service: `session_service`, `snapshot_diff_service`
- Toplam blueprint sayısı: 37 → 40

### Test
- 24 yeni odaklı test (769 → 793)
- tests/test_v46_focused.py — sessions (5), snapshot_diff (5), quick_capture routes (7), session routes (4), snapshot_diff routes (3)
- Kritik yollar: start/end session, pause/resume, cannot-start-two-active, diff same date, capture all 4 types, empty body rejection

---

## v4.5.0 — Gamification & Reference (2026-07-15)

### Yeni Modüller
- **Achievements** (`/achievements/`): 18 rozet, 5 kategori (streak/words/chapters/cast/consistency). Streak rozetleri: 3/7/30/100 gün. Word milestone'ları: 1K/10K/50K/100K/250K. Chapter milestone'ları: 1/5/10/25. Cast & World: first character, 10 characters, 20 world entries. Consistency: full week, weekend warrior. Her achievement: check fonksiyonu + progress bar + progress label. Unlock'lar DB'de persisted (UnlockedAchievement). check_and_unlock() otomatik kontrol eder.
- **Goals Calendar** (`/goals/`): Aylık görsel takvim — her gün heatmap renkli (0-4 seviye, daily goal'a göre). Month stats: total words, writing days, goal-met days, best day, avg/writing day. **Year overview**: 12-month bar grid, year words, writing days, year goal %. Current progress: today/week/month/year against goals. Prev/next month navigation. 60s cache.
- **Story Bible Auto-Generator** (`/story-bible/`): Mevcut içerikten otomatik story bible derleme. 6 bölüm: Plot Summary (chapter synopses), Characters (tüm profil alanları), Character Relationships (from→to→type), World Entries (by type), Timeline (story_date sorted), Glossary. 4 format: HTML (styled, printable CSS), TXT, MD, JSON. Preview page + download. Stats grid: chapters/characters/world/timeline/glossary/total words.
- **Spell Check & Custom Dictionary** (`/spellcheck/`): Yerel spell check — bağımsızlık (no Hunspell/aspell dependency). ~500 bundled common word + writer'ın custom dictionary + character names + world entry names + glossary terms hepsi "known good". _tokenize (markdown/HTML strip, 2+ char filter), _levenshtein (max_dist early exit), _suggest (distance ≤ 2). Per-chapter: flagged words with count, context, suggestions. Custom dictionary CRUD: add word, add batch, delete by id/text. Click suggestion to add to dictionary.

### İyileştirmeler
- `models/achievement.py` ve `models/spellcheck.py` — model sınıfları models/ altında (service'te değil), dairesel import önlemek için
- `services/spellcheck_service.py` BUNDLED_WORDS — hero/villain/castle/sword/magic gibi yaygın fantastik kelimeler eklendi
- Sidebar'a 4 yeni link: Achievements, Goals Calendar, Story Bible, Spell Check

### Mimari
- 4 yeni blueprint: `achievements`, `goals_calendar`, `story_bible`, `spellcheck`
- 2 yeni model: `models/achievement.py` (UnlockedAchievement), `models/spellcheck.py` (CustomWord)
- 4 yeni service: `achievement_service`, `goals_calendar_service`, `story_bible_service`, `spellcheck_service`
- Toplam blueprint sayısı: 33 → 37

### Test
- 93 yeni test eklendi (676 → 769, hepsi yeşil)
- tests/test_achievement_service.py (13 test — definitions, context building, check/unlock, idempotency, progress bounds)
- tests/test_goals_calendar_service.py (11 test — month calendar, year overview, heat levels, progress)
- tests/test_story_bible_service.py (16 test — gather data, render HTML/TXT/MD/JSON, validation, escaping)
- tests/test_spellcheck_service.py (26 test — tokenize, levenshtein, known words, check chapter, suggestions, custom dict CRUD)
- tests/test_routes/test_v45_routes.py (27 test — tüm endpoint'ler + sidebar görünürlüğü)

---

## v4.4.0 — Cards, Journal & Compile (2026-07-15)

### Yeni Modüller
- **Scene Card Index** (`/scenes/`): Bölüm içeriğini otomatik sahne kartlarına böl (* * *, ---, 3+ newline). Corkboard görünümü: 7 mood (tense/calm/humorous/dark/hopeful/romantic/mysterious), 3 status, 8 kart rengi. POV character, location, time of day, tags. **Drag-drop reorder** (global sort_order). Move to chapter. Aggregate stats (cards per chapter, per mood, per status).
- **Daily Writing Journal** (`/journal/`): Tarihli yazım günlüğü. 5 mood (great/good/ok/struggling/blocked), 1-5 energy, word goal/actual (auto-pulled from settings + activity log). Wins, struggles, intentions, gratitude, notes. **Journal streak** (consecutive days). 30-day aggregate stats: avg mood score, avg energy, goals met count, mood distribution. One entry per day (unique date constraint).
- **Manuscript Compile Wizard** (`/compile/`): Publication-ready manuscript derleme. **Front matter**: title page, copyright, dedication, epigraph (with attribution), TOC, acknowledgments. **Chapter formatting**: 4 number formats (none/chapter/number/chapter_number), scene break marker, status filter. **Back matter**: author's note, about author, other books. Config persisted. Preview structure before download. Output: HTML (with print CSS), DOCX (page breaks, centered headings), TXT, MD.
- **Theme & CSS Editor** (`/theme/`): 7 preset tema (dark, light, sepia, forest, ocean, sunset, midnight-OLED). Per-variable color overrides (13 CSS variables). Font family override. Base font size override. **Custom CSS** (freeform, 10K char limit). Live preview pane. **CSS otomatik tüm sayfalara inject edilir** (`<style id="custom-theme-css">`).

### İyileştirmeler
- `services/scene_service.py` — `_split_into_scenes` 4 farklı scene break pattern destekler
- `services/theme_service.py` — `get_config` artık hem dict hem string JSON handle eder (Setting.get zaten parse ediyor)
- `services/compile_service.py` — aynı dict/string fix uygulandı
- `app.py` context processor — `custom_theme_css` her sayfaya inject edilir
- `templates/base.html` — `<style id="custom-theme-css">` bloğu eklendi
- Sidebar'a 4 yeni link: Scene Cards, Writing Journal, Compile Wizard, Theme Editor

### Mimari
- 4 yeni blueprint: `scenes`, `journal`, `compile`, `theme`
- 2 yeni model: `models/scene.py` (SceneCard), `models/journal.py` (JournalEntry)
- 4 yeni service: `scene_service`, `journal_service`, `compile_service`, `theme_service`
- Toplam blueprint sayısı: 29 → 33

### Test
- 107 yeni test eklendi (569 → 676, hepsi yeşil)
- tests/test_scene_service.py (21 test — split patterns, extract, CRUD, reorder, move, stats)
- tests/test_journal_service.py (18 test — CRUD, mood validation, streak, goal met, stats)
- tests/test_compile_service.py (19 test — config, compile with front/back matter, render HTML/TXT/MD, chapter number formats, status filter)
- tests/test_theme_service.py (15 test — config, save/reset, CSS generation, preset validation, color overrides)
- tests/test_routes/test_v44_routes.py (34 test — tüm endpoint'ler + sidebar görünürlüğü + theme injection)

---

## v4.3.0 — Reader, Voice & Plot Audit (2026-07-15)

### Yeni Modüller
- **Reading Mode** (`/reading/`): Tüm bölümleri tek sürekli akışta oku. Font ailesi (serif/Lora/sans/WenKai/mono), font boyu (14-28px), satır yüksekliği (1.2-2.2), max genişlik, ve 4 tema (auto/paper/sepia/dark/night) — hepsi localStorage'da kalıcı. Sticky progress bar, bölüm jump dropdown, IntersectionObserver ile otomatik bölüm takibi. Klavye kısayolları: ← → (bölüm nav), F (fullscreen), H (controls toggle). Okuma konumu otomatik kaydedilir.
- **Character Voice Profiles** (`/voice/`): Her karakter için konuşma profili. 3 verbosity (terse/moderate/verbose), 4 formality (informal/neutral/formal/archaic), 3 sentence length. Favorite words, avoided words, catchphrases, speech quirks, favorite/avoided topics, example dialogue. **Dialogue scanner** karakterin bulunduğu tüm bölümleri tarayıp: avoided word kullanımlarını yakalar, catchphrase hit sayısını sayar, gerçek ortalama cümle uzunluğunu declared style ile karşılaştırır. **consistency_summary()** — karakterin sesini doğal dilde özetler (AI prompt context için ideal).
- **Timeline Conflict Detection** (`/timeline-check/`): story_date'leri otomatik parse eder (ISO, "Month Day, Year", year-month, year-only, ve metin içinden yıl çıkarma). 5 çakışma türü tespit eder: out-of-order (kronolojik ≠ outline sırası), duplicate_date (aynı tarihte 2+ kritik event), large_gaps (>30 gün boşluk), character_double_booked (aynı karakter aynı gün farklı track'lerde), unparseable_date. Track bazlı filtreleme. Tüm event'ler kronolojik tabloda gösterilir.
- **Research & References** (`/references/`): Araştırma kütüphanesi — kitap, makale, web sitesi, video, röportaj, podcast, doküman. 8 kaynak tipi. Her kayıt: title, author, URL, publication date, publisher, ISBN/DOI, description, **quotes** (alıntılar with page numbers), tags, read status (unread/reading/read), priority (low/medium/high), 1-5 rating, notes. Filtreleme: tip/status/priority/tag/search. Aggregate stats: toplam, okunmuş, ortalama rating.

### İyileştirmeler
- `models/__init__.py` — voice ve reference modülleri eklendi
- Sidebar'a 4 yeni link: Reading Mode, Voice Profiles, Timeline Audit, Research & Refs
- Reading Mode tüm bölümleri tek API çağrısında yükler (lazy loading sonraki sürüm için)

### Mimari
- 4 yeni blueprint: `reading`, `voice`, `timeline_check`, `references`
- 2 yeni model: `models/voice.py` (CharacterVoice), `models/reference.py` (Reference)
- 3 yeni service: `voice_service`, `timeline_check_service`, `reference_service`
- Toplam blueprint sayısı: 25 → 29

### Test
- 82 yeni test eklendi (487 → 569, hepsi yeşil)
- tests/test_voice_service.py (17 test — CRUD, scan dialogue, catchphrase counting, length match, summary)
- tests/test_timeline_check_service.py (20 test — date parsing 10 format, conflict detection 5 tür, gap analysis, track filter)
- tests/test_reference_service.py (21 test — CRUD, filters, stats, priority sort, quotes/tags)
- tests/test_routes/test_v43_routes.py (24 test — tüm endpoint'ler + sidebar görünürlüğü)

---

## v4.2.0 — Consistency & Career (2026-07-15)

### Yeni Modüller
- **Glossary & Style Sheet** (`/glossary/`): Yazarın tutarlı terimler sözlüğü. 6 kategori (character/place/magic/item/style/other). Her entry: canonical term + acceptable alternates + forbidden variants + case-sensitivity. **Manuscript scanner** tüm bölümleri tarar, forbidden bulgularını ve Levenshtein distance ≤ 2 yakın-yazım hatalarını context ile birlikte listeler. Term presence tracking (hangi terim kaç bölümde geçiyor).
- **Bulk Find & Replace** (`/find-replace/`): Tüm bölümlerde regex destekli bul-değiştir. Plain text veya regex modu, case-sensitive, whole-word seçenekleri. Status veya chapter ID bazlı scope. **Her zaman preview önce** — her bölüm için ilk 10 match context ile gösterilir. Apply her bölüm için yeni version snapshot oluşturur (find_replace source etiketi ile).
- **Submission Tracker** (`/submissions/`): Dergi/ajan/yayınevi/yarışma takibi. 7 status (drafting/submitted/in_review/accepted/rejected/withdrawn/published), 6 market type. Otomatik days-to-respond hesaplama. Aggregate stats: toplam, kabul oranı, ortalama/median yanıt süresi. Markets listesi (her market için submission/accepted/rejected/pending sayıları). Chapter link opsiyonel.
- **Writing Analytics** (`/analytics/`): Dashboard'un ötesinde derin analiz. Per-chapter: word count, sentence/paragraph count, avg sentence length, **dialogue ratio** (tırnak içi metin oranı), **lexical diversity** (type-token ratio), reading time. Manuscript summary: en kısa/en uzun bölüm, total unique words, ortalama bölüm uzunluğu. **Top 30 words** (stopwords hariç) progress bar ile. **Character screen time**: her karakter manuscript'in yüzde kaçında görünüyor. İki Chart.js bar chart (word count distribution, dialogue ratio per chapter).

### İyileştirmeler
- `services/chapter_service.py:list_chapters` local `read_session` shadow bug düzeltildi (modül-level import artık kullanılıyor)
- `tests/conftest.py` artık her test öncesi `cache.clear()` çağırıyor — analytics testleri arası cache leak önlendi
- Sidebar'a 4 yeni link: Glossary & Style, Find & Replace, Submission Tracker, Writing Analytics

### Mimari
- 4 yeni blueprint: `glossary`, `find_replace`, `submissions`, `analytics`
- 2 yeni model dosyası: `models/glossary.py`, `models/submission.py`
- 4 yeni service: `glossary_service`, `find_replace_service`, `submission_service`, `analytics_service`
- Toplam blueprint sayısı: 21 → 25

### Test
- 101 yeni test eklendi (386 → 487, hepsi yeşil)
- tests/test_glossary_service.py (16 test — CRUD, scan, Levenshtein, near-miss detection)
- tests/test_find_replace_service.py (18 test — preview/apply, regex, scope, versioning)
- tests/test_submission_service.py (18 test — CRUD, stats, markets, days-to-respond)
- tests/test_analytics_service.py (16 test — per-chapter, manuscript, top words, screen time)
- tests/test_routes/test_v42_routes.py (33 test — tüm endpoint'ler + sidebar görünürlüğü)

---

## v4.1.0 — Inspiration & Structure (2026-07-15)

### Yeni Modüller
- **Inspiration Hub** (`/inspiration/`): 7 kategoride 70+ hand-curated yazım promptu (opening/conflict/character/setting/twist/dialogue/whatif). Tarih-bazlı deterministik günlük prompt. 5 parçalı (protagonist/setting/goal/obstacle/twist) senaryo üreticisi. Kaydet, pin'le, "used" işaretle, prompt'tan chapter'a dönüştür.
- **Plot Structure Templates** (`/plot-templates/`): 6 klasik kurgu yapısı — Hero's Journey (12 beat), Save the Cat (15 beat), Three-Act (7 beat), Seven-Point (7 beat), Freytag's Pyramid (5 beat), Kishōtenketsu (4 beat). "Apply" ile her beat için plan oluşturur, `plot:<key>` track'inde.
- **Notes & Ideas Inbox** (`/notes/`): 6 kategoride (idea/question/reminder/reference/scene_idea/todo) hızlı not yakalama. Pin/done, etiketler, arama, çapraz-referans linkleri (chapter/character/world_entry/plan). Notu chapter/snippet/plan'a promote et.
- **Keyboard Shortcuts Center**: `?` tuşu ile açılan cheatsheet modalı. Yeni kısayollar: `t` (tema), `b` (sidebar), `g` chord navigasyonu (g+d/c/k/p/w/s/n/i/t/e/x). Footer'da `?` butonu.

### İyileştirmeler
- `chapters/new` artık `?prompt=` query parametresi kabul ediyor — prompt'tan yeni bölüme otomatik geçiş
- `link_url` Jinja global'i eklendi (note cross-reference linkleri için)
- Footer versiyon etiketi v4.0 → v4.1

### Mimari
- `models/inspiration.py` ve `models/note.py` ayrı dosyalara taşındı (dairesel import önlemek için)
- 3 yeni blueprint: `inspiration`, `plot_templates`, `notes`
- Toplam blueprint sayısı: 18 → 21

### Test
- 98 yeni test eklendi (288 → 386, hepsi yeşil)
- tests/test_inspiration_service.py (19 test)
- tests/test_plot_template_service.py (14 test)
- tests/test_note_service.py (25 test)
- tests/test_routes/test_v41_routes.py (40 test — tüm yeni endpoint'ler + sidebar görünürlüğü)

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
| Python dosyası | 140 |
| HTML template | 91 |
| JS dosyası | 15 |
| CSS dosyası | 4 |
| Vendor asset | 12+ |
| Test sayısı | 872 |
| URL endpoint | 240+ |
| Blueprint | 51 |
| AI özelliği | 9 |
| Export format | 30+ kombinasyon |
| Milestone | 12 |
| Character mood | 8 |
| Toplam dosya | 325+ |

## Çalıştırma
```bash
# Windows: start.bat (browser otomatik açılır)
# Linux/Mac: python app.py
# Test: PYTHONPATH=. python -m pytest tests/ -v
```
