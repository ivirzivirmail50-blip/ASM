"""Internationalization (i18n) — multi-language UI support.

Supports: English (default), Turkish, Spanish, French, German.
Language is stored in settings as 'ui_language'.

Usage in templates:
  {{ t('dashboard.title') }}
  {{ t('chapters.new') }}

Translation files are simple Python dicts in TRANSLATIONS.
Missing keys fall back to English, then to the key itself.
"""
from __future__ import annotations

import logging
from typing import Any

from core.db import read_session
from models.settings import Setting

log = logging.getLogger("asm.i18n")

SUPPORTED_LANGUAGES = {
    "en": {"label": "English", "icon": "🇬🇧"},
    "tr": {"label": "Türkçe", "icon": "🇹🇷"},
    "es": {"label": "Español", "icon": "🇪🇸"},
    "fr": {"label": "Français", "icon": "🇫🇷"},
    "de": {"label": "Deutsch", "icon": "🇩🇪"},
}

# Translation strings — each key maps to {lang: translation}
TRANSLATIONS: dict[str, dict[str, str]] = {
    # Navigation
    "nav.dashboard": {"en": "Dashboard", "tr": "Panel", "es": "Panel", "fr": "Tableau de bord", "de": "Übersicht"},
    "nav.chapters": {"en": "Chapters", "tr": "Bölümler", "es": "Capítulos", "fr": "Chapitres", "de": "Kapitel"},
    "nav.characters": {"en": "Characters", "tr": "Karakterler", "es": "Personajes", "fr": "Personnages", "de": "Charaktere"},
    "nav.search": {"en": "Search", "tr": "Arama", "es": "Buscar", "fr": "Rechercher", "de": "Suche"},
    "nav.settings": {"en": "Settings", "tr": "Ayarlar", "es": "Ajustes", "fr": "Paramètres", "de": "Einstellungen"},
    "nav.world": {"en": "World Library", "tr": "Dünya Kütüphanesi", "es": "Biblioteca del Mundo", "fr": "Bibliothèque du Monde", "de": "Weltbibliothek"},
    "nav.plans": {"en": "Kanban Board", "tr": "Kanban Tablosu", "es": "Tablero Kanban", "fr": "Tableau Kanban", "de": "Kanban-Board"},
    "nav.timeline": {"en": "Timeline", "tr": "Zaman Çizelgesi", "es": "Línea de Tiempo", "fr": "Chronologie", "de": "Zeitleiste"},
    "nav.export": {"en": "Export", "tr": "Dışa Aktar", "es": "Exportar", "fr": "Exporter", "de": "Exportieren"},
    "nav.reading": {"en": "Reading Mode", "tr": "Okuma Modu", "es": "Modo Lectura", "fr": "Mode Lecture", "de": "Lesemodus"},
    "nav.workspace": {"en": "Workspace", "tr": "Çalışma Alanı", "es": "Espacio de Trabajo", "fr": "Espace de Travail", "de": "Arbeitsbereich"},
    "nav.story": {"en": "Story", "tr": "Hikaye", "es": "Historia", "fr": "Histoire", "de": "Story"},
    "nav.planning": {"en": "Planning", "tr": "Planlama", "es": "Planificación", "fr": "Planification", "de": "Planung"},
    "nav.world_section": {"en": "World", "tr": "Dünya", "es": "Mundo", "fr": "Monde", "de": "Welt"},
    "nav.system": {"en": "System", "tr": "Sistem", "es": "Sistema", "fr": "Système", "de": "System"},
    "nav.books": {"en": "Books / Series", "tr": "Kitaplar / Seri", "es": "Libros / Series", "fr": "Livres / Séries", "de": "Bücher / Serien"},
    "nav.chapter_deps": {"en": "Chapter Deps", "tr": "Bölüm Bağımlılıkları", "es": "Dependencias", "fr": "Dépendances", "de": "Kapitel-Abhängigkeiten"},
    "nav.scenes": {"en": "Scene Cards", "tr": "Sahne Kartları", "es": "Tarjetas de Escena", "fr": "Cartes de Scène", "de": "Szenenkarten"},
    "nav.journal": {"en": "Writing Journal", "tr": "Yazım Günlüğü", "es": "Diario", "fr": "Journal", "de": "Tagebuch"},
    "nav.goals": {"en": "Goals Calendar", "tr": "Hedef Takvimi", "es": "Calendario", "fr": "Calendrier", "de": "Zielkalender"},
    "nav.character_groups": {"en": "Character Groups", "tr": "Karakter Grupları", "es": "Grupos", "fr": "Groupes", "de": "Charakter-Gruppen"},
    "nav.relationship_graph": {"en": "Relationship Graph", "tr": "İlişki Grafiği", "es": "Grafo de Relaciones", "fr": "Graphe de Relations", "de": "Beziehungsgraph"},
    "nav.compare_characters": {"en": "Compare Characters", "tr": "Karakter Karşılaştır", "es": "Comparar", "fr": "Comparer", "de": "Vergleichen"},
    "nav.voice": {"en": "Voice Profiles", "tr": "Ses Profilleri", "es": "Perfiles de Voz", "fr": "Profils de Voix", "de": "Stimmprofile"},
    "nav.character_arcs": {"en": "Character Arcs", "tr": "Karakter Yayları", "es": "Arcos de Personaje", "fr": "Arcs de Personnage", "de": "Charakter-Bögen"},
    "nav.rel_timeline": {"en": "Relationship Timeline", "tr": "İlişki Zaman Çizelgesi", "es": "Línea de Relaciones", "fr": "Chronologie des Relations", "de": "Beziehungs-Zeitleiste"},
    "nav.mood": {"en": "Mood Tracker", "tr": "Duygu Takibi", "es": "Estados de Ánimo", "fr": "Suivi d'Humeur", "de": "Stimmungs-Tracker"},
    "nav.corkboard": {"en": "Corkboard", "tr": "Pano", "es": "Tablero", "fr": "Liège", "de": "Korkwand"},
    "nav.outline": {"en": "Outline", "tr": "Taslak", "es": "Esquema", "fr": "Plan", "de": "Gliederung"},
    "nav.timeline_audit": {"en": "Timeline Audit", "tr": "Zaman Denetimi", "es": "Auditoría", "fr": "Audit", "de": "Zeitleiste-Audit"},
    "nav.plot_structures": {"en": "Plot Structures", "tr": "Kurgu Yapıları", "es": "Estructuras", "fr": "Structures", "de": "Plot-Strukturen"},
    "nav.location_tree": {"en": "Location Tree", "tr": "Lokasyon Ağacı", "es": "Árbol de Lugares", "fr": "Arbre de Lieux", "de": "Orts-Baum"},
    "nav.world_map": {"en": "World Map", "tr": "Dünya Haritası", "es": "Mapa del Mundo", "fr": "Carte du Monde", "de": "Weltkarte"},
    "nav.references": {"en": "Research & Refs", "tr": "Araştırma & Kaynaklar", "es": "Investigación", "fr": "Recherche", "de": "Recherche"},
    "nav.import_center": {"en": "Import Center", "tr": "İçe Aktar", "es": "Centro de Importación", "fr": "Centre d'Import", "de": "Import-Center"},
    "nav.manuscript_diff": {"en": "Manuscript Diff", "tr": "Yazım Farkları", "es": "Diff del Manuscrito", "fr": "Diff du Manuscrit", "de": "Manuskript-Diff"},
    "nav.find_replace": {"en": "Find & Replace", "tr": "Bul & Değiştir", "es": "Buscar y Reemplazar", "fr": "Chercher et Remplacer", "de": "Suchen & Ersetzen"},
    "nav.snippets": {"en": "Snippets & Templates", "tr": "Parçalar & Şablonlar", "es": "Fragmentos", "fr": "Fragments", "de": "Schnipsel"},
    "nav.prompt_calendar": {"en": "Prompt Calendar", "tr": "Prompt Takvimi", "es": "Calendario de Prompts", "fr": "Calendrier de Prompts", "de": "Prompt-Kalender"},
    "nav.notes": {"en": "Notes & Ideas", "tr": "Notlar & Fikirler", "es": "Notas e Ideas", "fr": "Notes et Idées", "de": "Notizen & Ideen"},
    "nav.glossary": {"en": "Glossary & Style", "tr": "Sözlük & Stil", "es": "Glosario y Estilo", "fr": "Glossaire et Style", "de": "Glossar & Stil"},
    "nav.spellcheck": {"en": "Spell Check", "tr": "Yazım Kontrolü", "es": "Corrector", "fr": "Vérification", "de": "Rechtschreibung"},
    "nav.pacing": {"en": "Pacing Analysis", "tr": "Tempo Analizi", "es": "Análisis de Ritmo", "fr": "Analyse du Rythme", "de": "Tempo-Analyse"},
    "nav.analytics": {"en": "Writing Analytics", "tr": "Yazım Analitiği", "es": "Analítica", "fr": "Analytique", "de": "Schreib-Analyse"},
    "nav.forecast": {"en": "Manuscript Forecast", "tr": "Tahmin", "es": "Pronóstico", "fr": "Prévision", "de": "Prognose"},
    "nav.habits": {"en": "Writing Habits", "tr": "Yazım Alışkanlıkları", "es": "Hábitos", "fr": "Habitudes", "de": "Schreibgewohnheiten"},
    "nav.compile": {"en": "Compile Wizard", "tr": "Derleme Sihirbazı", "es": "Asistente", "fr": "Assistant", "de": "Compile-Assistent"},
    "nav.scrivener": {"en": "Scrivener Export", "tr": "Scrivener Dışa Aktar", "es": "Exportar Scrivener", "fr": "Export Scrivener", "de": "Scrivener-Export"},
    "nav.submissions": {"en": "Submission Tracker", "tr": "Gönderi Takibi", "es": "Seguimiento", "fr": "Suivi", "de": "Einreichungen"},
    "nav.ai_chat": {"en": "AI Chat", "tr": "AI Sohbet", "es": "Chat IA", "fr": "Chat IA", "de": "KI-Chat"},
    "nav.ai_history": {"en": "AI History", "tr": "AI Geçmişi", "es": "Historial IA", "fr": "Historique IA", "de": "KI-Verlauf"},
    "nav.ai_settings": {"en": "AI Settings", "tr": "AI Ayarları", "es": "Ajustes IA", "fr": "Paramètres IA", "de": "KI-Einstellungen"},
    "nav.inspiration": {"en": "Inspiration Hub", "tr": "İlham Merkezi", "es": "Centro de Inspiración", "fr": "Centre d'Inspiration", "de": "Inspirationszentrum"},
    "nav.achievements": {"en": "Achievements", "tr": "Başarımlar", "es": "Logros", "fr": "Succès", "de": "Erfolge"},
    "nav.milestones": {"en": "Milestones", "tr": "Kilometre Taşları", "es": "Hitos", "fr": "Jalons", "de": "Meilensteine"},
    "nav.sessions": {"en": "Session Timer", "tr": "Oturum Zamanlayıcı", "es": "Temporizador", "fr": "Minuteur", "de": "Sitzungstimer"},
    "nav.music": {"en": "Music Player", "tr": "Müzik Çalar", "es": "Reproductor", "fr": "Lecteur de Musique", "de": "Musikplayer"},
    "nav.spellcheck": {"en": "Spell Check", "tr": "Yazım Kontrolü", "es": "Corrector", "fr": "Vérification", "de": "Rechtschreibung"},
    "nav.glossary": {"en": "Glossary & Style", "tr": "Sözlük & Stil", "es": "Glosario y Estilo", "fr": "Glossaire et Style", "de": "Glossar & Stil"},
    "nav.lint": {"en": "Story Lint", "tr": "Hikaye Kontrolü", "es": "Revisión", "fr": "Vérification", "de": "Story-Lint"},
    "nav.analytics": {"en": "Writing Analytics", "tr": "Yazım Analitiği", "es": "Analítica", "fr": "Analytique", "de": "Schreib-Analyse"},
    "nav.forecast": {"en": "Manuscript Forecast", "tr": "Tahmin", "es": "Pronóstico", "fr": "Prévision", "de": "Prognose"},
    "nav.habits": {"en": "Writing Habits", "tr": "Yazım Alışkanlıkları", "es": "Hábitos", "fr": "Habitudes", "de": "Schreibgewohnheiten"},

    # Common actions
    "action.new_chapter": {"en": "+ New Chapter", "tr": "+ Yeni Bölüm", "es": "+ Nuevo Capítulo", "fr": "+ Nouveau Chapitre", "de": "+ Neues Kapitel"},
    "action.new_character": {"en": "+ New Character", "tr": "+ Yeni Karakter", "es": "+ Nuevo Personaje", "fr": "+ Nouveau Personnage", "de": "+ Neuer Charakter"},
    "action.save": {"en": "Save", "tr": "Kaydet", "es": "Guardar", "fr": "Enregistrer", "de": "Speichern"},
    "action.cancel": {"en": "Cancel", "tr": "İptal", "es": "Cancelar", "fr": "Annuler", "de": "Abbrechen"},
    "action.delete": {"en": "Delete", "tr": "Sil", "es": "Eliminar", "fr": "Supprimer", "de": "Löschen"},
    "action.edit": {"en": "Edit", "tr": "Düzenle", "es": "Editar", "fr": "Modifier", "de": "Bearbeiten"},
    "action.close": {"en": "Close", "tr": "Kapat", "es": "Cerrar", "fr": "Fermer", "de": "Schließen"},
    "action.search": {"en": "Search…", "tr": "Ara…", "es": "Buscar…", "fr": "Rechercher…", "de": "Suchen…"},

    # Dashboard
    "dashboard.title": {"en": "Story Cockpit", "tr": "Hikaye Kokpiti", "es": "Cabina de la Historia", "fr": "Cockpit de l'Histoire", "de": "Story-Cockpit"},
    "dashboard.total_chapters": {"en": "Total Chapters", "tr": "Toplam Bölüm", "es": "Capítulos Totales", "fr": "Chapitres Totaux", "de": "Kapitel Gesamt"},
    "dashboard.total_words": {"en": "Total Words", "tr": "Toplam Kelime", "es": "Palabras Totales", "fr": "Mots Totaux", "de": "Wörter Gesamt"},
    "dashboard.streak": {"en": "Writing Streak", "tr": "Yazım Serisi", "es": "Racha de Escritura", "fr": "Série d'Écriture", "de": "Schreib-Strich"},

    # World map
    "map.title": {"en": "Interactive World Map", "tr": "Etkileşimli Dünya Haritası", "es": "Mapa del Mundo Interactivo", "fr": "Carte du Monde Interactive", "de": "Interaktive Weltkarte"},
    "map.upload": {"en": "Upload Map Image", "tr": "Harita Resmi Yükle", "es": "Subir Imagen del Mapa", "fr": "Télécharger Image de Carte", "de": "Kartenbild Hochladen"},
    "map.add_pin": {"en": "+ Add Pin", "tr": "+ Pin Ekle", "es": "+ Añadir Marcador", "fr": "+ Ajouter Épingle", "de": "+ Pin Hinzufügen"},
    "map.enter_submap": {"en": "Enter Sub-Map", "tr": "Alt Haritaya Gir", "es": "Entrar Sub-Mapa", "fr": "Entrer Sous-Carte", "de": "Unterkarte Öffnen"},

    # Settings
    "settings.language": {"en": "Interface Language", "tr": "Arayüz Dili", "es": "Idioma de Interfaz", "fr": "Langue de l'Interface", "de": "Oberflächensprache"},
}


def get_current_language() -> str:
    """Get the current UI language from settings."""
    with read_session() as s:
        lang = Setting.get(s, "ui_language", "en")
        if isinstance(lang, str):
            return lang if lang in SUPPORTED_LANGUAGES else "en"
        return "en"


def set_language(lang: str) -> None:
    """Set the UI language."""
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"
    from core.db import write_transaction
    with write_transaction() as s:
        existing = s.query(Setting).filter_by(key="ui_language").first()
        if existing:
            existing.value = lang
        else:
            s.add(Setting(key="ui_language", value=lang))


def translate(key: str, lang: str | None = None) -> str:
    """Translate a key to the given language (or current language)."""
    if not lang:
        lang = get_current_language()
    if key in TRANSLATIONS:
        translations = TRANSLATIONS[key]
        if lang in translations:
            return translations[lang]
        # Fallback to English
        if "en" in translations:
            return translations["en"]
    # Key not found — return the key itself
    return key


def get_translation_dict(lang: str | None = None) -> dict[str, str]:
    """Return all translations for the given language as a flat dict."""
    if not lang:
        lang = get_current_language()
    result: dict[str, str] = {}
    for key, translations in TRANSLATIONS.items():
        if lang in translations:
            result[key] = translations[lang]
        elif "en" in translations:
            result[key] = translations["en"]
        else:
            result[key] = key
    return result
