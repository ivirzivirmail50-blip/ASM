"""Story Lint Engine — AI-free automated consistency checks.

Scans chapters for:
- Repeated words (same word 5+ times in a paragraph)
- Character name typos (fuzzy match against known names)
- Sentence length outliers (very long or very short sentences)
- Passive voice overuse (basic heuristic)
- Adverb overuse (words ending in -ly)
- Dialogue tag variety (too many "said" vs. other tags)
- Character attribute mentions (eye color, hair color consistency)
"""
from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select

from core.db import read_session
from models.chapter import Chapter
from models.character import Character
from models.world import WorldEntry
from services._common import load_json, current_project_id

log = logging.getLogger("asm.lint")

# Common words to ignore in repetition checks
_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "of",
    "is", "was", "are", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "must", "can", "shall", "it", "its", "he", "she",
    "his", "her", "they", "them", "their", "there", "here", "this",
    "that", "these", "those", "with", "from", "by", "as", "for", "not",
    "no", "so", "if", "then", "than", "too", "very", "just", "also",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "up", "down", "out", "off", "over", "under", "again",
    "further", "once", "i", "you", "we", "me", "my", "your", "our",
})


def lint_all() -> dict[str, Any]:
    """Run all lint checks across all chapters.

    Returns {findings: [...], summary: {total, by_severity, by_type}}.
    """
    findings: list[dict] = []

    with read_session() as s:
        pid = current_project_id(s)
        chapters = list(s.scalars(
            select(Chapter).where(Chapter.project_id == pid)
            .order_by(Chapter.sort_order.asc())
        ).all())
        characters = list(s.scalars(
            select(Character).where(Character.project_id == pid)
        ).all())

    # Build character name lookup
    char_names: dict[str, dict] = {}
    for c in characters:
        char_names[c.name.lower()] = {
            "id": c.id, "name": c.name,
            "aliases": load_json(c.aliases, []),
            "physical": c.physical or "",
        }
        for alias in load_json(c.aliases, []):
            char_names[alias.lower()] = char_names[c.name.lower()]

    for ch in chapters:
        content = ch.content or ""
        if not content.strip():
            continue

        # 1. Repeated words
        findings.extend(_check_repeated_words(ch, content))

        # 2. Character name fuzzy match (typos)
        findings.extend(_check_name_typos(ch, content, char_names))

        # 3. Sentence length outliers
        findings.extend(_check_sentence_length(ch, content))

        # 4. Adverb overuse
        findings.extend(_check_adverb_overuse(ch, content))

        # 5. Passive voice (basic)
        findings.extend(_check_passive_voice(ch, content))

        # 6. Dialogue tag variety
        findings.extend(_check_dialogue_tags(ch, content))

    # 7. Cross-chapter: character attribute consistency
    findings.extend(_check_attribute_consistency(chapters, char_names))

    # Summary
    by_severity = Counter(f["severity"] for f in findings)
    by_type = Counter(f["type"] for f in findings)

    return {
        "findings": findings,
        "summary": {
            "total": len(findings),
            "errors": by_severity.get("error", 0),
            "warnings": by_severity.get("warning", 0),
            "info": by_severity.get("info", 0),
            "by_type": dict(by_type),
        },
    }


def _check_repeated_words(chapter, content: str) -> list[dict]:
    """Check for words repeated 5+ times in a single paragraph."""
    findings = []
    paragraphs = content.split("\n\n")
    for i, para in enumerate(paragraphs):
        words = re.findall(r'\b[a-z]{3,}\b', para.lower())
        word_counts = Counter(w for w in words if w not in _STOP_WORDS)
        for word, count in word_counts.most_common(3):
            if count >= 5:
                findings.append({
                    "severity": "warning",
                    "type": "repeated_word",
                    "chapter_id": chapter.id,
                    "chapter_title": chapter.title,
                    "location": f"Paragraph {i+1}",
                    "message": f"'{word}' used {count} times in one paragraph. Consider varying your vocabulary.",
                    "suggestion": f"Replace some instances with synonyms.",
                })
    return findings


def _check_name_typos(chapter, content: str, char_names: dict) -> list[dict]:
    """Check for potential character name typos using fuzzy matching."""
    findings = []
    if not char_names:
        return findings

    # Find all capitalized words that might be names
    words = re.findall(r'\b([A-Z][a-z]{2,})\b', content)
    known_names = set(char_names.keys())

    for word in set(words):
        word_lower = word.lower()
        if word_lower in known_names:
            continue
        # Check if it's close to a known name (Levenshtein distance ≤ 2)
        for known in known_names:
            if _levenshtein(word_lower, known) <= 2 and len(word_lower) >= 4:
                findings.append({
                    "severity": "info",
                    "type": "name_typo",
                    "chapter_id": chapter.id,
                    "chapter_title": chapter.title,
                    "location": f"'{word}'",
                    "message": f"'{word}' might be a typo of '{char_names[known]['name']}'.",
                    "suggestion": f"Did you mean '{char_names[known]['name']}'?",
                })
                break
    return findings


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j+1]+1, curr[j]+1, prev[j]+(ca != cb)))
        prev = curr
    return prev[-1]


def _check_sentence_length(chapter, content: str) -> list[dict]:
    """Check for very long or very short sentences."""
    findings = []
    sentences = re.split(r'[.!?]+', content)
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if not sent:
            continue
        words = sent.split()
        wc = len(words)
        if wc > 50:
            findings.append({
                "severity": "info",
                "type": "long_sentence",
                "chapter_id": chapter.id,
                "chapter_title": chapter.title,
                "location": f"Sentence {i+1} ({wc} words)",
                "message": f"Very long sentence ({wc} words). Consider breaking it up.",
                "suggestion": "Split into shorter sentences for readability.",
            })
    return findings


def _check_adverb_overuse(chapter, content: str) -> list[dict]:
    """Check for overuse of -ly adverbs."""
    findings = []
    words = re.findall(r'\b\w+ly\b', content.lower())
    # Filter out common non-adverb -ly words
    non_adverbs = {"only", "family", "reply", "apply", "supply", "uly", "july",
                   "assembly", "fly", "belly", "jelly", "holy", "ugly"}
    adverbs = [w for w in words if w not in non_adverbs]
    total_words = len(content.split())
    if total_words > 100:
        ratio = len(adverbs) / total_words * 100
        if ratio > 3.0:  # more than 3% adverbs
            findings.append({
                "severity": "info",
                "type": "adverb_overuse",
                "chapter_id": chapter.id,
                "chapter_title": chapter.title,
                "location": f"{len(adverbs)} adverbs in {total_words} words ({ratio:.1f}%)",
                "message": f"High adverb density ({ratio:.1f}%). Consider using stronger verbs.",
                "suggestion": "Replace 'ran quickly' with 'sprinted', 'said softly' with 'whispered', etc.",
            })
    return findings


def _check_passive_voice(chapter, content: str) -> list[dict]:
    """Basic passive voice detection (was/were/been + past participle)."""
    findings = []
    # Simple heuristic: look for "was/were/been/is/are + [word]ed"
    passive_patterns = [
        r'\b(?:was|were|been|is|are|being)\s+\w+ed\b',
    ]
    matches = []
    for pattern in passive_patterns:
        matches.extend(re.findall(pattern, content, re.IGNORECASE))
    total_sentences = len(re.split(r'[.!?]+', content))
    if total_sentences > 10 and len(matches) > total_sentences * 0.25:
        findings.append({
            "severity": "info",
            "type": "passive_voice",
            "chapter_id": chapter.id,
            "chapter_title": chapter.title,
            "location": f"{len(matches)} passive constructions",
            "message": f"High passive voice usage ({len(matches)} instances). Active voice is more engaging.",
            "suggestion": "Change 'The door was opened by Elara' to 'Elara opened the door'.",
        })
    return findings


def _check_dialogue_tags(chapter, content: str) -> list[dict]:
    """Check dialogue tag variety — too many 'said' is monotonous."""
    findings = []
    # Find dialogue tags: "word," said/whispered/etc.
    tags = re.findall(r'[,"]\s*(\w+)\s*(?:\.|,|$)', content)
    tag_counts = Counter(t.lower() for t in tags if t.lower() in {
        "said", "whispered", "shouted", "asked", "replied", "muttered",
        "growled", "snapped", "murmured", "declared", "stated", "added",
    })
    total_tags = sum(tag_counts.values())
    if total_tags > 10:
        said_count = tag_counts.get("said", 0)
        if said_count / total_tags > 0.7:
            findings.append({
                "severity": "info",
                "type": "dialogue_tags",
                "chapter_id": chapter.id,
                "chapter_title": chapter.title,
                "location": f"{said_count}/{total_tags} tags are 'said'",
                "message": f"'Said' accounts for {said_count}/{total_tags} dialogue tags. Consider more variety.",
                "suggestion": "Try: whispered, muttered, snapped, growled, murmured, or use action beats.",
            })
    return findings


def _check_attribute_consistency(chapters: list, char_names: dict) -> list[dict]:
    """Check if character attributes (eye color, hair color) are mentioned consistently."""
    findings = []
    # Extract physical attributes from character profiles
    attr_patterns = {
        "eye": r"(blue|green|brown|hazel|gray|grey|amber|violet|black|gold)\s+eye",
        "hair": r"(black|brown|blonde|red|white|gray|grey|silver|auburn)\s+hair",
    }

    for char_name_lower, char_data in char_names.items():
        if char_name_lower != char_data["name"].lower():
            continue  # skip aliases
        physical = char_data.get("physical", "").lower()

        # Find stated attributes in the character profile
        stated_attrs: dict[str, str] = {}
        for attr, pattern in attr_patterns.items():
            match = re.search(pattern, physical)
            if match:
                stated_attrs[attr] = match.group(1)

        if not stated_attrs:
            continue

        # Check chapters for conflicting mentions
        for ch in chapters:
            content = (ch.content or "").lower()
            for attr, stated_value in stated_attrs.items():
                pattern = attr_patterns[attr]
                # Find all mentions of this attribute in the chapter
                mentions = re.findall(pattern, content)
                for mention in mentions:
                    if mention != stated_value:
                        findings.append({
                            "severity": "warning",
                            "type": "attribute_conflict",
                            "chapter_id": ch.id,
                            "chapter_title": ch.title,
                            "location": f"{attr} color",
                            "message": f"{char_data['name']}'s {attr} is '{stated_value}' in profile but '{mention}' appears in this chapter.",
                            "suggestion": f"Check if this is intentional or an error.",
                        })
    return findings


def style_coach(chapter_id: str) -> dict:
    """Combined lint + style analysis for a single chapter.

    Returns per-chapter style report with actionable suggestions.
    """
    from core.db import read_session
    from models.chapter import Chapter
    with read_session() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            return {"ok": False, "error": "Chapter not found."}
        content = ch.content or ""
        if not content.strip():
            return {"ok": False, "error": "Chapter is empty."}

    findings = []
    # Run existing lint checks
    chapter_findings = _check_repeated_words(ch, content)
    chapter_findings += _check_sentence_length(ch, content)
    chapter_findings += _check_adverb_overuse(ch, content)
    chapter_findings += _check_passive_voice(ch, content)
    chapter_findings += _check_dialogue_tags(ch, content)

    # Additional style metrics
    words = content.split()
    word_count = len(words)

    # Dialogue ratio
    import re
    dialogue_matches = re.findall(r'"[^"]*"', content)
    dialogue_words = sum(len(m.split()) for m in dialogue_matches)
    dialogue_pct = round(dialogue_words / max(word_count, 1) * 100, 1)

    # Average sentence length
    sentences = [s.strip() for s in re.split(r'[.!?]+', content) if s.strip()]
    avg_sent_len = round(sum(len(s.split()) for s in sentences) / max(len(sentences), 1), 1)

    # Show-don't-tell indicators (feeling words)
    telling_words = ["felt", "feeling", "feelings", "felt that", "was angry", "was sad",
                     "was happy", "was afraid", "was scared", "was excited",
                     "was nervous", "was confused", "was surprised"]
    telling_count = sum(content.lower().count(w) for w in telling_words)

    # Sensory words (showing indicators)
    sensory_words = ["saw", "heard", "smelled", "tasted", "touched", "felt the",
                     "warmth", "cold", "brightness", "darkness", "echo", "scent",
                     "flavor", "texture", "rough", "smooth", "bitter", "sweet"]
    sensory_count = sum(content.lower().count(w) for w in sensory_words)

    # Report
    style_report = {
        "ok": True,
        "chapter_title": ch.title,
        "word_count": word_count,
        "dialogue_pct": dialogue_pct,
        "narration_pct": round(100 - dialogue_pct, 1),
        "avg_sentence_length": avg_sent_len,
        "sentence_count": len(sentences),
        "telling_indicators": telling_count,
        "sensory_indicators": sensory_count,
        "show_dont_tell_ratio": round(sensory_count / max(telling_count, 1), 1),
        "findings": chapter_findings,
        "suggestions": [],
    }

    # Generate suggestions
    if dialogue_pct < 15:
        style_report["suggestions"].append({
            "type": "dialogue",
            "severity": "info",
            "message": f"Dialogue is only {dialogue_pct}% of the chapter. Consider adding more character interaction."
        })
    if dialogue_pct > 70:
        style_report["suggestions"].append({
            "type": "dialogue",
            "severity": "info",
            "message": f"Dialogue is {dialogue_pct}% — very dialogue-heavy. Add more narration and description."
        })
    if avg_sent_len > 25:
        style_report["suggestions"].append({
            "type": "pacing",
            "severity": "info",
            "message": f"Average sentence length is {avg_sent_len} words. Try shorter sentences for action scenes."
        })
    if telling_count > sensory_count and telling_count > 3:
        style_report["suggestions"].append({
            "type": "show_dont_tell",
            "severity": "warning",
            "message": f"Found {telling_count} 'telling' indicators vs {sensory_count} sensory words. Try 'show, don't tell'."
        })

    return style_report
