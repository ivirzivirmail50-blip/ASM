"""Inspiration Hub — writing prompts, scenario generator, daily prompt.

A purely-local inspiration engine (no AI required). Provides:
- Categorized writing prompts (opening lines, conflict, character moments, etc.)
- Random scenario generator (character + setting + conflict + twist + goal)
- Daily prompt (deterministic by date, so every writer sees the same one)
- Saved inspirations (bookmarked prompts/scenarios)
- Convert any prompt to a chapter or snippet

All prompt data is bundled in-code so it works fully offline.
"""
from __future__ import annotations

import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import Any

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.inspiration import SavedInspiration
from services._common import current_project_id, dump_json, load_json, log_activity, new_uuid, now_utc

log = logging.getLogger("asm.inspiration")


# ---------------------------------------------------------------------------
# Prompt library — purely offline, hand-curated
# ---------------------------------------------------------------------------

PROMPT_CATEGORIES = {
    "opening": {
        "label": "Opening Lines",
        "icon": "🚪",
        "description": "First lines to launch a scene or chapter.",
        "prompts": [
            "The letter had been sitting on the kitchen table for three days, and Mara still hadn't opened it.",
            "By the time the second sun rose over the city, the dyes in the river had already turned to blood.",
            "Everyone agreed the old lighthouse keeper was mad — until the day his predictions started coming true.",
            "She found the key in her grandmother's sewing box, tied to a label that read: 'Do not use unless I am dead.'",
            "The cartographer drew the new border in red ink, and four hundred people ceased to exist.",
            "The first thing Kael noticed about the stranger was that his shadow fell the wrong way.",
            "It was the kind of quiet that comes after a war — the kind that makes you check the windows twice.",
            "When the bell tolled the seventh time, everyone in the village stopped what they were doing and walked toward the square.",
            "The merchant ship arrived with no crew, no cargo, and a single passenger who refused to speak.",
            "Mara had killed three men before breakfast, and none of them had been the one she was hunting.",
            "The oracle had predicted this day for forty years. Now that it was here, she couldn't remember why it mattered.",
            "The contract was written in the kind of ink that only appears after someone dies.",
        ],
    },
    "conflict": {
        "label": "Conflict Sparks",
        "icon": "⚔",
        "description": "Drop one of these into a slow scene and watch it ignite.",
        "prompts": [
            "A character discovers that the ally they trust most has been reporting their every move to the enemy.",
            "The map they've been following for three chapters is suddenly revealed to be a forgery.",
            "A promise made in chapter one must now be broken — and the person it was made to has not forgotten.",
            "Two characters want the same thing, but only one can have it, and the other is willing to die for it.",
            "A secret society offers help — at a price that will cost the protagonist their identity.",
            "The thing the protagonist has been searching for was hidden in their own home all along — by someone who knew they would look.",
            "A character returns from the dead with information that contradicts everything the heroes believed.",
            "The protagonist must choose between saving one person they love and saving a hundred strangers — and time has just run out.",
            "An ancient law is invoked that strips the protagonist of all their hard-won power in a single decree.",
            "The enemy proposes a truce that, if refused, will mean the deaths of everyone the protagonist has sworn to protect.",
        ],
    },
    "character": {
        "label": "Character Moments",
        "icon": "👤",
        "description": "Scenes that reveal who a character really is.",
        "prompts": [
            "Your protagonist is alone, in the dark, with no one watching. What do they do that no one else knows they do?",
            "Write the moment your character realizes their mentor has been lying to them for years — and decides whether to confront it.",
            "A stranger mistakes your character for someone else. Your character plays along. Why?",
            "Your character receives a gift from someone they hate — and it's the perfect gift. Write the moment they decide what to do with it.",
            "Show your character doing something small and kind for a stranger, then immediately doing something cruel to someone they love.",
            "Your character has five minutes to pack a bag and leave forever. What do they take, and what do they leave behind?",
            "Write the conversation your character has been avoiding for the entire book — finally happening, with no escape.",
            "Your character breaks a personal rule they swore they would never break. What was the rule, and what pushed them past it?",
            "Show your character in a memory from childhood that explains one of their adult fears.",
            "Your character meets someone who is exactly who they used to be — and dislikes them intensely.",
        ],
    },
    "setting": {
        "label": "Setting & Atmosphere",
        "icon": "🗺",
        "description": "Place-driven prompts to ground your world.",
        "prompts": [
            "Describe a marketplace at dawn, before the first merchant arrives — what sounds, smells, and shadows remain from the night?",
            "A library where the books rearrange themselves based on who is reading them. Your protagonist is looking for one specific page.",
            "Describe a city that has been built on the back of a sleeping creature — and the creature is beginning to wake.",
            "A tavern that exists only between midnight and the first cock's crow, and the people who choose to be there.",
            "Write a setting that has been abandoned for fifty years, but where everything is still perfectly preserved — and explain why.",
            "Describe a garden where every flower is the grave of someone the gardener once loved.",
            "A fortress carved into the side of a cliff, accessible only by a single rope bridge that is cut every night.",
            "A city beneath the ice, where the residents have never seen the sun — and one of them is about to.",
            "Describe a clock tower that counts down to something no one alive remembers.",
            "A road that appears only to those who are lost — and takes them somewhere they did not intend to go.",
        ],
    },
    "twist": {
        "label": "Twists & Revelations",
        "icon": "🌀",
        "description": "Mid-story revelations that change everything.",
        "prompts": [
            "The protagonist has been the villain of someone else's story all along — and that someone has just arrived.",
            "The prophecy was misread for a thousand years. The 'savior' is the one who must be stopped.",
            "The mentor didn't die — they switched sides. And they've been working against the hero ever since.",
            "The artifact the heroes have been protecting is the source of the evil they're fighting.",
            "The protagonist's memories of the inciting event have been fabricated. The truth is far worse.",
            "The enemy is not trying to destroy the world — they're trying to save it, and the protagonist is in their way.",
            "The love interest was a plant from the very beginning — but they fell in love for real, and now must choose.",
            "The map they've been following is a portrait of the protagonist's own face, drawn centuries before their birth.",
            "The protagonist's dead sibling is alive — and has been running the enemy's operations from the start.",
            "The gods the characters have been praying to have been dead for centuries. Something else has been answering.",
        ],
    },
    "dialogue": {
        "label": "Dialogue Openers",
        "icon": "💬",
        "description": "First lines of conversation to drop into any scene.",
        "prompts": [
            "\"You weren't supposed to find out this way.\"",
            "\"I lied. About all of it. Now sit down, because the truth is going to take longer.\"",
            "\"The price has gone up. I need an answer by sundown.\"",
            "\"Don't say his name. Not in this house. Not after what he did.\"",
            "\"I can teach you how to do it. But you have to promise me one thing first.\"",
            "\"They're going to come for you. Probably tonight. I came to give you a head start — that's all.\"",
            "\"You look exactly like your mother did, the night she made the same mistake you're about to make.\"",
            "\"I'm not asking you to forgive me. I'm asking you to understand why I had to do it.\"",
            "\"Three people know what really happened that night. Two of them are dead. I'm the third.\"",
            "\"I made a deal, and the deal is the only reason any of us are still alive. Don't make me regret it.\"",
        ],
    },
    "whatif": {
        "label": "'What If?' Premises",
        "icon": "❓",
        "description": "Story-level premises to seed a new project.",
        "prompts": [
            "What if every lie a person tells becomes real, but only after they die?",
            "What if memories could be inherited — and you've just inherited one that doesn't belong to anyone in your family?",
            "What if the moon is an egg, and tonight is the night it hatches?",
            "What if every seven years, every person forgets one specific year of their life — and you've just discovered which one you forgot?",
            "What if the gods are real, but they're locked in a prison of their own design — and the lock is breaking?",
            "What if the dead don't move on because there's nowhere for them to go, and the world is filling up?",
            "What if your shadow is the real you, and you're just the shadow it casts?",
            "What if every book ever written is a true story from another world, and someone just wrote yours?",
            "What if the war ended a hundred years ago, but no one told the soldiers on either side?",
            "What if the protagonist is the only person in the world who can lie — and everyone else is bound by their word?",
        ],
    },
}


# ---------------------------------------------------------------------------
# Scenario generator parts
# ---------------------------------------------------------------------------

SCENARIO_PARTS = {
    "protagonist": [
        "a disgraced cartographer", "an immortal who has forgotten their original name",
        "a thief with a code", "a healer who can't save anyone they love",
        "a soldier who refused to fight", "an oracle who has stopped believing in fate",
        "a scholar of forbidden languages", "a musician whose songs can wake the dead",
        "a former assassin trying to be good", "a noble who has lost everything",
        "a witch who can only curse", "a blacksmith's apprentice with royal blood",
        "a sailor who has seen the edge of the map", "a child who can speak to inanimate objects",
        "a prisoner who has forgotten their crime", "a priest who has lost their faith",
    ],
    "setting": [
        "in a city that floats above the clouds", "in a kingdom where the sun hasn't set in a hundred years",
        "in a port town where the tide brings in more than fish", "in a desert where the sand is made of ground bone",
        "in a forest that moves when no one is looking", "in a fortress carved into the heart of a glacier",
        "in a city beneath the sea, lit by bioluminescent kelp", "in a library that exists in seven dimensions",
        "in a marketplace that appears only on the new moon", "in a castle where every room is a different season",
        "in a village at the foot of a sleeping dragon", "in a tower with no doors, only windows",
        "in a country that has just lost its king", "in a town where everyone shares the same dream",
    ],
    "goal": [
        "to find the person who killed their mentor", "to deliver a letter that must never be read",
        "to recover a child stolen in the night", "to break a curse that has plagued their family for seven generations",
        "to bury their brother in sacred ground", "to steal back something that was taken from them",
        "to reach the capital before the army does", "to translate a book that has driven everyone else mad",
        "to fulfill a promise made to a dying friend", "to find a doctor who can cure the impossible",
        "to attend a coronation that will change the world", "to bury a secret so deep no one will ever find it",
    ],
    "obstacle": [
        "but their only ally is the person they least trust", "but the magic they need is forbidden, and the punishment is death",
        "but they have only three days before the moon turns", "but the path leads through a country that has put a price on their head",
        "but their own memories are being erased, one day at a time", "but the truth they uncover will force them to betray someone they love",
        "but they're being hunted by something that can smell lies", "but the person who sent them doesn't want them to succeed",
        "but every step forward takes them further from who they used to be", "but the gods have noticed them, and the gods are not kind",
        "but they're running out of the drug that keeps them sane", "but the only map leads through a place no one has ever returned from",
    ],
    "twist": [
        "and the person they're looking for has been with them all along.",
        "and the truth they're carrying is more dangerous than the one they're seeking.",
        "and the mentor they trusted has been steering them wrong from the start.",
        "and the prophecy they've been running from is the one they must fulfill.",
        "and the enemy they're fighting is the only one who can save them.",
        "and the price of success will cost them everything they've gained.",
        "and the past they've been hiding from has finally caught up.",
        "and the answer they've been seeking was inside them all along.",
        "and the choice they must make has no right answer.",
        "and the world they're trying to save may not deserve it.",
    ],
}


# ---------------------------------------------------------------------------
# Daily prompt — deterministic by date
# ---------------------------------------------------------------------------

def daily_prompt(for_date: datetime | None = None) -> dict[str, Any]:
    """Return today's prompt (deterministic — same for everyone on the same date).

    Uses a hash of the date string to pick from a flattened list of all prompts.
    """
    d = for_date or datetime.now(timezone.utc)
    date_str = d.strftime("%Y-%m-%d")
    # Hash the date to a stable integer
    h = int(hashlib.sha256(date_str.encode("utf-8")).hexdigest(), 16)
    # Flatten all prompts
    all_prompts: list[tuple[str, str]] = []
    for cat, data in PROMPT_CATEGORIES.items():
        for p in data["prompts"]:
            all_prompts.append((cat, p))
    idx = h % len(all_prompts)
    cat, text = all_prompts[idx]
    return {
        "date": date_str,
        "category": cat,
        "category_label": PROMPT_CATEGORIES[cat]["label"],
        "icon": PROMPT_CATEGORIES[cat]["icon"],
        "text": text,
    }


# ---------------------------------------------------------------------------
# Random prompt / scenario
# ---------------------------------------------------------------------------

def random_prompt(category: str | None = None) -> dict[str, Any]:
    """Return one random prompt, optionally from a specific category."""
    if category and category in PROMPT_CATEGORIES:
        cat = category
    else:
        cat = random.choice(list(PROMPT_CATEGORIES.keys()))
    data = PROMPT_CATEGORIES[cat]
    return {
        "category": cat,
        "category_label": data["label"],
        "icon": data["icon"],
        "description": data["description"],
        "text": random.choice(data["prompts"]),
    }


def random_scenario() -> dict[str, Any]:
    """Generate a random five-part story premise."""
    parts = {
        "protagonist": random.choice(SCENARIO_PARTS["protagonist"]),
        "setting": random.choice(SCENARIO_PARTS["setting"]),
        "goal": random.choice(SCENARIO_PARTS["goal"]),
        "obstacle": random.choice(SCENARIO_PARTS["obstacle"]),
        "twist": random.choice(SCENARIO_PARTS["twist"]),
    }
    # Capitalize first letter of protagonist for the prose line
    p = parts["protagonist"]
    prose = (
        f"{p[0].upper()}{p[1:]} {parts['setting']} {parts['goal']} {parts['obstacle']} {parts['twist']}"
    )
    return {
        "parts": parts,
        "prose": prose,
    }


def random_whatif() -> dict[str, Any]:
    """Return one random 'What If?' premise."""
    return random_prompt(category="whatif")


# ---------------------------------------------------------------------------
# Saved inspirations CRUD
# ---------------------------------------------------------------------------

def list_saved(*, kind: str | None = None, pinned_only: bool = False) -> list[SavedInspiration]:
    with read_session() as s:
        q = s.query(SavedInspiration).filter_by(project_id=current_project_id(s))
        if kind:
            q = q.filter_by(kind=kind)
        if pinned_only:
            q = q.filter_by(pinned=1)
        # Pinned first, then most recent
        return list(q.order_by(SavedInspiration.pinned.desc(),
                               SavedInspiration.created_at.desc()).all())


def save_inspiration(
    *, kind: str, category: str, body: str,
    title: str = "",
    meta: dict | None = None,
) -> SavedInspiration:
    if kind not in ("prompt", "scenario", "whatif"):
        raise ValidationError("kind must be prompt/scenario/whatif")
    if not body or len(body) > 5000:
        raise ValidationError("Body required, ≤ 5000 chars.")
    sid = new_uuid()
    with write_transaction() as s:
        rec = SavedInspiration(
            id=sid,
            project_id=current_project_id(s),
            kind=kind,
            category=category or "general",
            title=(title or "")[:300],
            body=body,
            meta=dump_json(meta or {}),
            pinned=0,
            used=0,
            created_at=now_utc(),
        )
        s.add(rec)
        log_activity(
            s, entity_type="inspiration", entity_id=sid,
            entity_title=title or body[:80], action="created",
        )
        s.flush()
        return rec


def toggle_pin(inspiration_id: str) -> SavedInspiration:
    with write_transaction() as s:
        rec = s.get(SavedInspiration, inspiration_id)
        if not rec:
            raise NotFoundError("Inspiration not found.")
        rec.pinned = 0 if rec.pinned else 1
        s.flush()
        return rec


def mark_used(inspiration_id: str) -> SavedInspiration:
    with write_transaction() as s:
        rec = s.get(SavedInspiration, inspiration_id)
        if not rec:
            raise NotFoundError("Inspiration not found.")
        rec.used = 1
        s.flush()
        return rec


def delete_inspiration(inspiration_id: str) -> None:
    with write_transaction() as s:
        rec = s.get(SavedInspiration, inspiration_id)
        if rec:
            s.delete(rec)


def to_dict(rec: SavedInspiration) -> dict[str, Any]:
    return {
        "id": rec.id,
        "kind": rec.kind,
        "category": rec.category,
        "title": rec.title,
        "body": rec.body,
        "meta": load_json(rec.meta, {}),
        "pinned": bool(rec.pinned),
        "used": bool(rec.used),
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


# ---------------------------------------------------------------------------
# Public API for templates
# ---------------------------------------------------------------------------

def categories() -> list[dict[str, Any]]:
    return [
        {"key": k, "label": v["label"], "icon": v["icon"],
         "description": v["description"], "count": len(v["prompts"])}
        for k, v in PROMPT_CATEGORIES.items()
    ]


def prompts_for(category: str) -> list[str]:
    if category not in PROMPT_CATEGORIES:
        return []
    return list(PROMPT_CATEGORIES[category]["prompts"])
