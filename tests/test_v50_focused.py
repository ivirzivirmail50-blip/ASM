"""Focused tests for v5.0: word frequency, character mood, music player.

Critical paths only.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Word Frequency Analyzer
# ---------------------------------------------------------------------------

class TestWordFreq:
    def test_index_renders(self, client):
        r = client.get("/word-freq/")
        assert r.status_code == 200
        assert b"Word Frequency" in r.data

    def test_api_manuscript(self, client):
        r = client.get("/word-freq/api/manuscript")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "total_words" in d
        assert "top_words" in d
        assert "overused" in d

    def test_analysis_with_content(self, client):
        client.post("/chapters/new", data={
            "title": "Freq Test",
            "content": "the cat sat on the mat the cat was happy the cat smiled",
            "status": "draft",
        })
        r = client.get("/word-freq/api/manuscript")
        d = r.get_json()
        assert d["total_words"] > 0
        # "cat" should be in top words (appears 3 times, not a stopword)
        top_words = [w["word"] for w in d["top_words"]]
        assert "cat" in top_words

    def test_api_chapter(self, client):
        r = client.post("/chapters/new", data={
            "title": "Ch Freq", "content": "hello world hello", "status": "draft",
        })
        ch_id = r.get_json()["id"]
        r = client.get(f"/word-freq/api/chapter/{ch_id}")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["total_words"] == 3

    def test_api_chapter_not_found(self, client):
        r = client.get("/word-freq/api/chapter/nonexistent")
        assert r.status_code == 404

    def test_repeated_phrases_detected(self, client):
        client.post("/chapters/new", data={
            "title": "Phrase Test",
            "content": "she smiled and walked away she smiled and walked away she smiled and walked away",
            "status": "draft",
        })
        r = client.get("/word-freq/api/manuscript")
        d = r.get_json()
        # "she smiled" should be a repeated 2-word phrase
        phrases = [p["phrase"] for p in d["repeated_phrases_2"]]
        assert "she smiled" in phrases


# ---------------------------------------------------------------------------
# Character Mood Tracker
# ---------------------------------------------------------------------------

class TestCharMood:
    def test_index_renders(self, client):
        r = client.get("/char-mood/")
        assert r.status_code == 200
        assert b"Mood Tracker" in r.data

    def test_set_mood(self, client):
        from services.character_service import create_character
        c = create_character(name="Mood Hero", role="protagonist")
        r = client.post("/chapters/new", data={
            "title": "Mood Ch", "content": "Content.", "status": "draft",
        })
        ch_id = r.get_json()["id"]
        r = client.post("/char-mood/api/set", json={
            "character_id": c.id, "chapter_id": ch_id,
            "mood": "joyful", "intensity": "high",
            "note": "Great day",
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_set_mood_invalid(self, client):
        from services.character_service import create_character
        c = create_character(name="Invalid Mood", role="protagonist")
        r = client.post("/chapters/new", data={
            "title": "Inv Ch", "content": "x", "status": "draft",
        })
        ch_id = r.get_json()["id"]
        r = client.post("/char-mood/api/set", json={
            "character_id": c.id, "chapter_id": ch_id,
            "mood": "bogus",
        })
        assert r.status_code == 400

    def test_set_mood_updates_existing(self, client):
        from services.character_service import create_character
        from services.char_mood_service import set_mood, list_moods
        c = create_character(name="Update Mood", role="protagonist")
        r = client.post("/chapters/new", data={
            "title": "Upd Ch", "content": "x", "status": "draft",
        })
        ch_id = r.get_json()["id"]
        set_mood(character_id=c.id, chapter_id=ch_id, mood="happy" if "happy" in __import__("services.char_mood_service", fromlist=["MOODS"]).MOODS else "joyful")
        set_mood(character_id=c.id, chapter_id=ch_id, mood="sad")
        moods = list_moods(character_id=c.id)
        assert len(moods) == 1  # updated, not duplicated
        assert moods[0].mood == "sad"

    def test_timeline(self, client):
        r = client.get("/char-mood/api/timeline")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "mood_timeline" in d

    def test_delete_mood(self, client):
        from services.character_service import create_character
        from services.char_mood_service import set_mood, list_moods
        c = create_character(name="Del Mood", role="protagonist")
        r = client.post("/chapters/new", data={
            "title": "Del Ch", "content": "x", "status": "draft",
        })
        ch_id = r.get_json()["id"]
        m = set_mood(character_id=c.id, chapter_id=ch_id, mood="angry")
        r = client.post(f"/char-mood/api/{m.id}/delete")
        assert r.get_json()["ok"]


# ---------------------------------------------------------------------------
# Music Player
# ---------------------------------------------------------------------------

class TestMusic:
    def test_index_renders(self, client):
        r = client.get("/music/")
        assert r.status_code == 200
        assert b"Music Player" in r.data

    def test_api_tracks(self, client):
        r = client.get("/music/api/tracks")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert isinstance(d["tracks"], list)

    def test_upload_audio(self, client):
        import io
        data = {
            "file": (io.BytesIO(b"fake audio content"), "test.mp3"),
        }
        r = client.post("/music/api/upload", data=data, content_type="multipart/form-data")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["track"]["filename"] == "test.mp3"

    def test_upload_invalid_extension(self, client):
        import io
        data = {
            "file": (io.BytesIO(b"not audio"), "test.txt"),
        }
        r = client.post("/music/api/upload", data=data, content_type="multipart/form-data")
        assert r.status_code == 400

    def test_upload_no_file(self, client):
        r = client.post("/music/api/upload", data={})
        assert r.status_code == 400

    def test_delete_track(self, client):
        import io
        # Upload first
        data = {"file": (io.BytesIO(b"audio"), "delete_test.mp3")}
        client.post("/music/api/upload", data=data, content_type="multipart/form-data")
        r = client.post("/music/api/delete_test.mp3/delete")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

class TestV50Sidebar:
    def test_sidebar_has_word_freq(self, client):
        r = client.get("/")
        assert b"Word Frequency" in r.data

    def test_sidebar_has_mood_tracker(self, client):
        r = client.get("/")
        assert b"Mood Tracker" in r.data

    def test_sidebar_has_music(self, client):
        r = client.get("/")
        assert b"Music Player" in r.data
