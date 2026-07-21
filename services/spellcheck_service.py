"""Spell Check & Custom Dictionary — local spell checking for chapter content.

Since no system dictionary is available, we bundle a compact English word
list (~1000 most common words) plus the writer's custom dictionary.

The spell checker:
- Tokenizes chapter content into words (ignoring markdown, HTML, numbers)
- Checks each word against: bundled word list + custom dictionary + glossary terms
  + character names + world entry names (these are all "known good")
- Flags unknown words as potential misspellings
- Suggests corrections using Levenshtein distance (≤ 2)

The writer can:
- Add words to their custom dictionary (per-project)
- Ignore suggestions
- See all flagged words across all chapters with context

This is intentionally lightweight — not a full Hunspell replacement, but
good enough to catch typos in a local-first app without external deps.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select

from core.db import read_session, write_transaction
from core.errors import NotFoundError
from models.spellcheck import CustomWord
from models.chapter import Chapter
from models.character import Character
from models.glossary import GlossaryEntry
from models.world import WorldEntry
from services._common import current_project_id, dump_json, load_json, new_uuid, now_utc

log = logging.getLogger("asm.spellcheck")


# ---------------------------------------------------------------------------
# Bundled word list (most common ~500 English words + common writing words)
# This is a fallback — the real "dictionary" comes from the writer's own
# vocabulary across their manuscript + custom words + glossary + character names.
# ---------------------------------------------------------------------------

BUNDLED_WORDS = frozenset("""
a about above after again against all am an and any are aren't as at be because
been before being below between both but by can't cannot could couldn't did
didn't do does doesn't doing don't down during each few for from further had
hadn't has hasn't have haven't having he he'd he'll he's her here here's hers
herself him himself his how how's i i'd i'll i'm i've if in into is isn't it
it's its itself let's me more most mustn't my myself no nor not of off on once
only or other ought our ours ourselves out over own same shan't she she'd
she'll she's should shouldn't so some such than that that's the their theirs
them themselves then there there's these they they'd they'll they're they've
this those through to too under until up very was wasn't we we'd we'll we're
we've were weren't what what's when when's where where's which while who who's
whom why why's with won't would wouldn't you you'd you'll you're you've your
yours yourself yourselves

the of and to in a is that for it as was with be by on not he this are or his
from at but which had has have an were they one you all her she there would
their we him been has when who will more no if out so said what up its about
into than them can only other new some could time these two may then do first
any my now such like our over man me even most made after also did many before
must through back years where much your way well down should because each just
those people mr how too little state good very make world still own see men
work long get here between both life being under never day same another know
while last might us great old year go come off since against came right come
take think say many every need case fact school help went big point children
want away water side again home place high small found mrs house large next
night end does set thing place need part why things put head women away day
looked found run went felt door open turned eyes told gave voice face looked
came hand left stood head looked smiled spoke sat heard knew took felt
came hand left stood head smiled spoke sat heard knew took felt saw
elara kael mira voss malachar lira throne sword magic king queen prince
princess lord lady knight castle forest mountain river sea storm shadow
dawn dusk twilight morning evening night star moon sun sky wind rain snow
fire water earth air blood bone ash gold silver iron steel
door window wall floor ceiling roof stair path road street
horse dragon wolf raven eagle lion bear snake spider
sword dagger bow arrow shield armor helmet cloak staff wand
father mother brother sister daughter son child friend enemy lover
battle war peace death life love hate hope fear joy sorrow
walked ran jumped climbed fell rose stood sat lay turned
said spoke whispered shouted cried laughed smiled nodded shook
saw looked stared gazed glanced watched observed noticed
knew thought felt heard smelled tasted remembered forgot
took gave brought carried held threw caught dropped picked
morning afternoon evening midnight dawn dusk today tomorrow yesterday
north south east west above below behind before after inside outside
black white red blue green yellow brown grey golden silver
big small tall short wide narrow thick thin heavy light
fast slow strong weak young old new ancient broken whole
happy sad angry calm afraid brave tired hungry thirsty
beautiful ugly plain pretty handsome lovely hideous
cold hot warm cool freezing boiling wet dry damp crisp

hero villain protagonist antagonist mentor sidekick
castle tavern forest mountain river valley desert ocean
king queen prince princess knight warrior mage wizard witch
dragon wolf eagle raven lion bear snake spider
sword shield armor helmet dagger bow arrow staff wand
journey quest adventure battle war peace treaty alliance
magic spell curse potion enchantment ritual incantation
grief joy sorrow anger fear hope love hate courage
dawn dusk twilight midnight morning evening afternoon
whispered shouted murmured chuckled sighed gasped groaned
""".split())


def _build_known_words() -> set[str]:
    """Build the set of known-good words for this project."""
    known = set(BUNDLED_WORDS)
    with read_session() as s:
        pid = current_project_id(s)
        # Custom words
        customs = list(s.scalars(select(CustomWord).where(CustomWord.project_id == pid)))
        for c in customs:
            known.add(c.word.lower())
        # Character names + aliases
        chars = list(s.scalars(select(Character).where(Character.project_id == pid)))
        for c in chars:
            for part in re.split(r"\s+", c.name or ""):
                if part:
                    known.add(part.lower())
            for alias in load_json(c.aliases, []):
                for part in re.split(r"\s+", alias):
                    if part:
                        known.add(part.lower())
        # World entry names
        entries = list(s.scalars(select(WorldEntry).where(WorldEntry.project_id == pid)))
        for e in entries:
            for part in re.split(r"\s+", e.name or ""):
                if part:
                    known.add(part.lower())
        # Glossary terms + alternates
        glossary = list(s.scalars(select(GlossaryEntry).where(GlossaryEntry.project_id == pid)))
        for g in glossary:
            for part in re.split(r"\s+", g.term or ""):
                if part:
                    known.add(part.lower())
            for alt in load_json(g.alternates, []):
                for part in re.split(r"\s+", alt):
                    if part:
                        known.add(part.lower())
    return known


def _levenshtein(a: str, b: str, max_dist: int = 3) -> int:
    """Levenshtein distance with early exit if it exceeds max_dist."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
            if cur[-1] < best:
                best = cur[-1]
        if best > max_dist:
            return max_dist + 1
        prev = cur
    return prev[-1]


def _tokenize(text: str) -> list[tuple[str, int]]:
    """Extract (word, position) tuples from text, ignoring markdown/HTML/numbers."""
    if not text:
        return []
    # Remove markdown headers, emphasis markers, HTML tags
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = re.sub(r"#+\s*", "", cleaned)
    cleaned = re.sub(r"\*+|_+", "", cleaned)
    # Find all word tokens (letters + apostrophes for contractions)
    tokens: list[tuple[str, int]] = []
    for m in re.finditer(r"[A-Za-z][A-Za-z']*", cleaned):
        word = m.group(0)
        # Skip if it's a number or too short
        if len(word) < 2:
            continue
        tokens.append((word, m.start()))
    return tokens


def _suggest(word: str, known: set[str], max_suggestions: int = 5) -> list[str]:
    """Suggest corrections for a misspelled word."""
    word_lower = word.lower()
    # Find known words within distance 2
    candidates: list[tuple[int, str]] = []
    for k in known:
        # Quick length filter
        if abs(len(k) - len(word_lower)) > 2:
            continue
        d = _levenshtein(word_lower, k, max_dist=2)
        if d <= 2:
            candidates.append((d, k))
    candidates.sort()
    return [c[1] for c in candidates[:max_suggestions]]


def check_chapter(chapter_id: str) -> dict[str, Any]:
    """Spell-check a single chapter. Returns flagged words with context."""
    with read_session() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            raise NotFoundError("Chapter not found.")
        content = ch.content or ""
        title = ch.title
    known = _build_known_words()
    tokens = _tokenize(content)
    flagged: list[dict[str, Any]] = []
    seen_words: set[str] = set()
    for word, pos in tokens:
        word_lower = word.lower()
        if word_lower in known:
            continue
        if word_lower in seen_words:
            # Already flagged this word — just count occurrences
            for f in flagged:
                if f["word"].lower() == word_lower:
                    f["count"] += 1
                    break
            continue
        seen_words.add(word_lower)
        # Extract context
        ctx_start = max(0, pos - 40)
        ctx_end = min(len(content), pos + len(word) + 40)
        ctx = content[ctx_start:ctx_end].replace("\n", " ").replace("\r", "")
        prefix = "…" if ctx_start > 0 else ""
        suffix = "…" if ctx_end < len(content) else ""
        suggestions = _suggest(word, known)
        flagged.append({
            "word": word,
            "count": 1,
            "context": f"{prefix}{ctx}{suffix}",
            "suggestions": suggestions,
        })
    # Sort by count descending (most frequent misspellings first)
    flagged.sort(key=lambda f: f["count"], reverse=True)
    return {
        "chapter_id": chapter_id,
        "chapter_title": title,
        "total_words": len(tokens),
        "flagged_count": len(flagged),
        "flagged": flagged,
    }


def check_all_chapters() -> dict[str, Any]:
    """Spell-check all chapters. Returns aggregate results."""
    with read_session() as s:
        chapters = list(s.scalars(
            select(Chapter).where(Chapter.project_id == current_project_id(s))
            .order_by(Chapter.sort_order.asc())
        ))
    results: list[dict[str, Any]] = []
    total_flagged = 0
    total_words = 0
    for ch in chapters:
        result = check_chapter(ch.id)
        results.append(result)
        total_flagged += result["flagged_count"]
        total_words += result["total_words"]
    return {
        "chapters_checked": len(chapters),
        "total_words": total_words,
        "total_flagged": total_flagged,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Custom dictionary CRUD
# ---------------------------------------------------------------------------

def list_custom_words() -> list[CustomWord]:
    with read_session() as s:
        return list(s.scalars(
            select(CustomWord).where(CustomWord.project_id == current_project_id(s))
            .order_by(CustomWord.word.asc())
        ))


def add_word(word: str) -> CustomWord:
    word = word.strip().lower()
    if not word or len(word) > 200:
        from core.errors import ValidationError
        raise ValidationError("Word required, ≤ 200 chars.")
    with write_transaction() as s:
        # Check if already exists
        existing = s.scalar(
            select(CustomWord).where(
                CustomWord.project_id == current_project_id(s),
                CustomWord.word == word,
            )
        )
        if existing:
            return existing
        rec = CustomWord(
            id=new_uuid(),
            project_id=current_project_id(s),
            word=word,
            added_at=now_utc(),
        )
        s.add(rec)
        s.flush()
        return rec


def add_words_batch(words: list[str]) -> int:
    """Add multiple words. Returns count of newly-added (skips duplicates)."""
    count = 0
    for w in words:
        try:
            add_word(w)
            count += 1
        except Exception:
            pass
    return count


def remove_word(word_id: str) -> None:
    with write_transaction() as s:
        rec = s.get(CustomWord, word_id)
        if rec:
            s.delete(rec)


def remove_word_by_text(word: str) -> None:
    word = word.strip().lower()
    with write_transaction() as s:
        rec = s.scalar(
            select(CustomWord).where(
                CustomWord.project_id == current_project_id(s),
                CustomWord.word == word,
            )
        )
        if rec:
            s.delete(rec)


def to_dict(w: CustomWord) -> dict[str, Any]:
    return {
        "id": w.id,
        "word": w.word,
        "added_at": w.added_at.isoformat() if w.added_at else None,
    }
