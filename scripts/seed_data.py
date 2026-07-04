"""Seed data: creates a realistic demo project with chapters, characters, plans, world entries."""
from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from core.db import init_db, write_transaction, read_session
from models.chapter import Chapter, ChapterVersion
from models.character import (Character, CharacterArc, CharacterGroup,
                              CharacterGroupMember, CharacterRelationship)
from models.plan import Plan, PlanSubtask
from models.world import WorldEntry, WorldEntryVersion
from models.activity import ActivityLog
from services._common import dump_json, log_activity, now_utc

log = logging.getLogger("asm.seed")

CHARACTERS = [
    {"name": "Elara Vance", "role": "protagonist", "age": "27", "gender": "Female",
     "aliases": ["The Veiled One", "El"], "color": "#6366f1",
     "physical": "Tall and lean, with raven-black hair cut short. Her left eye is a deep violet — the mark of those touched by the Veil. A pale scar traces from her right temple to her chin.",
     "psychology": "Methodical and quiet, Elara conceals a fierce curiosity behind a calm exterior. She fears loss of control most of all — having watched her mother succumb to the same gift that defines her.",
     "background": "Raised in the northern village of Hollowmere by her mother, a healer. After her mother's death, Elara trained at the Academy of Veiled Arts in Aethelgard.",
     "philosophy": "Believes knowledge must be earned, never stolen. Her moral code forbids her from reading minds without consent — even enemies'.",
     "philosophy_quotes": ["\"Some doors should stay closed, even when we hold the key.\""],
     "story_role": "Central protagonist whose awakening triggers the events of the trilogy.",
     "voice": "Speaks in measured sentences. Uses archaic formal address when stressed."},
    {"name": "Lord Malachar", "role": "antagonist", "age": "Centuries old", "gender": "Male",
     "aliases": ["The Throneless King", "Mal"], "color": "#ef4444",
     "physical": "Tall, gaunt, with silver-white hair that never moves in wind. His eyes are entirely black — void-stained. Wears ceremonial armor that predates the current era.",
     "psychology": "Patient beyond mortal ken. Has waited three centuries for the convergence. Empathetic in conversation, which makes him more terrifying.",
     "background": "Once a guardian of the Veil, Malachar sought to merge the worlds after his daughter's death. Now leads the Hollow Court from the ruins of Old Aethelgard.",
     "philosophy": "Believes suffering is the only honest currency. Sees himself as merciful.",
     "philosophy_quotes": ["\"I do not punish. I simply reveal what was always true.\""],
     "story_role": "Antagonist; offers Elara the very choice she fears.",
     "voice": "Slow, deliberate, never raises his voice. Uses 'we' when referring to himself."},
    {"name": "Kael Thorne", "role": "supporting", "age": "30", "gender": "Male",
     "aliases": ["K"], "color": "#22c55e",
     "physical": "Stocky, brown-haired, with calloused hands from years of smithing. Wears a simple iron ring on his left thumb.",
     "psychology": "Loyal to a fault. Pragmatic. Hides grief under work.",
     "background": "Village smith from Hollowmere. Childhood friend of Elara. Lost his brother in the Hollowmere raid.",
     "philosophy": "Duty before desire. But what is duty when the law is wrong?",
     "story_role": "Elara's anchor to her past and a moral mirror.",
     "voice": "Plain speech, country accent. Laughs easily but briefly."},
    {"name": "Mira Solenne", "role": "supporting", "age": "40", "gender": "Female",
     "aliases": ["The Librarian"], "color": "#ec4899",
     "physical": "Silver-haired, with ink-stained fingers. Wears the gray robes of an Academy archivist.",
     "psychology": "Knowledge-hungry but kind. Suppresses a mischievous streak.",
     "background": "Senior archivist at the Academy. Mentored Elara. Secretly a member of the resistance.",
     "philosophy": "\"All knowledge is dangerous. That is precisely why we must keep it.\"",
     "story_role": "Mentor figure; reveals the truth of Malachar's origin.",
     "voice": "Quotes obscure texts. Always mid-sentence in some book."},
    {"name": "Brennan Ash", "role": "supporting", "age": "33", "gender": "Non-binary",
     "aliases": ["Ash"], "color": "#f59e0b",
     "physical": "Lean, weather-beaten. Carries a longbow and a single arrow with a black feather.",
     "psychology": "Slow to trust, slower to forgive. Honorable in combat.",
     "background": "Former Royal Ranger. Discharged after refusing an order. Now sells his skills.",
     "philosophy": "A vow kept is worth more than a life saved.",
     "story_role": "Reluctant ally; provides tactical intelligence.",
     "voice": "Terse. Uses soldier slang."},
    {"name": "Tessa", "role": "minor", "age": "12", "gender": "Female",
     "aliases": [], "color": "#a78bfa",
     "physical": "Small for her age. Freckled. Always barefoot.",
     "psychology": "Fearless in the way only children can be.",
     "background": "Orphan of the Hollowmere raid.",
     "story_role": "Represents the cost of Malachar's mercy.",
     "voice": "Asks questions adults won't."},
    {"name": "Captain Voss", "role": "minor", "age": "50", "gender": "Male",
     "aliases": [], "color": "#3b82f6",
     "physical": "Broad, gray-bearded. Wears the crimson cloak of the City Watch.",
     "psychology": "By-the-book. Corrupt in small, survivable ways.",
     "background": "Watch captain in Aethelgard's lower quarter.",
     "story_role": "Obstacle character; represents institutional rot.",
     "voice": "Barks orders. Uses 'lad' regardless of age."},
    {"name": "The Hollow Queen", "role": "minor", "age": "Unknown", "gender": "Female",
     "aliases": ["The Veil's Bride"], "color": "#0ea5e9",
     "physical": "Appears only as a silhouette in mirrors. When manifested, wears a gown of woven mist.",
     "psychology": "Alien. Curious. Hungry.",
     "background": "The Veil itself, given form.",
     "story_role": "Third-act reveal.",
     "voice": "Whispers. Repeats the last word of every sentence."},
]

RELATIONSHIPS = [
    (0, 1, "rival_of", "Fated opposites.", True),
    (0, 2, "friend_of", "Childhood friends from Hollowmere.", True),
    (0, 3, "mentors", "Mira mentored Elara at the Academy.", False),
    (0, 4, "friend_of", "Forged in the raid on Hollowmere.", True),
    (0, 5, "loves", "Elara sees Tessa as the daughter she never had.", True),
    (1, 3, "enemy_of", "Old enemies — Mira knows Malachar's true name.", True),
    (2, 4, "friend_of", "Smith and ranger, an unlikely duo.", True),
    (6, 1, "serves", "Voss takes orders from the Hollow Court.", False),
    (1, 7, "married_to", "Malachar bound himself to the Veil centuries ago.", True),
]

GROUPS = [
    {"name": "The Academy", "color": "#6366f1", "description": "Veiled Arts scholars in Aethelgard.", "members": [0, 3]},
    {"name": "Hollowmere Survivors", "color": "#22c55e", "description": "Refugees from the raid.", "members": [0, 2, 5]},
    {"name": "The Hollow Court", "color": "#ef4444", "description": "Malachar's inner circle.", "members": [1, 6, 7]},
]

PLANS = [
    {"title": "Hollowmere Raid", "description": "Opening inciting incident: Malachar's forces attack Elara's village.", "status": "final", "track": "Main Plot", "event_type": "plot_point", "story_date": "Day 1"},
    {"title": "Elara's Awakening", "description": "Elara discovers her gift after the raid.", "status": "final", "track": "Main Plot", "event_type": "character_moment", "story_date": "Day 3"},
    {"title": "Journey to Aethelgard", "description": "Elara, Kael, and Ash travel to the Academy.", "status": "writing", "track": "Main Plot", "event_type": "plot_point", "story_date": "Day 5-12"},
    {"title": "Mira's Confession", "description": "Mira reveals Malachar's true origin.", "status": "planned", "track": "Main Plot", "event_type": "character_moment", "story_date": "Day 14"},
    {"title": "Voss's Betrayal", "description": "Captain Voss sells them out to the Hollow Court.", "status": "planned", "track": "Subplot: Resistance", "event_type": "climax", "story_date": "Day 15"},
    {"title": "The Veil Convergence", "description": "Final confrontation between Elara and Malachar.", "status": "idea", "track": "Main Plot", "event_type": "climax", "story_date": "Day 30"},
]

WORLD_ENTRIES = [
    {"type": "location", "name": "Hollowmere", "category": "Village",
     "description": "Elara's birthplace, destroyed in the opening raid.",
     "content": "A small northern village of perhaps two hundred souls, Hollowmere sits at the edge of the Whisperwood. Its people were known for two things: their stubborn independence and the purple-eyed children born there once a generation. After the raid, only ashes remain.",
     "metadata": {"region": "Northern Reaches", "population": "200 (former)", "climate": "Cold temperate", "atmosphere": "Haunted"}},
    {"type": "location", "name": "Aethelgard", "category": "Capital City",
     "description": "The kingdom's capital and seat of the Academy.",
     "content": "Aethelgard spans seven hills, each crowned with a tower of pale stone. The Academy of Veiled Arts dominates the central hill, its library holding ten thousand years of records. Below, the lower quarter seethes with resentment, hunger, and Watch corruption.",
     "metadata": {"region": "Central Aethel", "population": "~250,000", "climate": "Mediterranean", "atmosphere": "Courtly, decayed"}},
    {"type": "location", "name": "Old Aethelgard", "category": "Ruins",
     "description": "The original capital, swallowed by the Veil three centuries ago.",
     "content": "Where the Hollow Court holds court. Few who enter return. Those who do are not what they were.",
     "metadata": {"region": "Beneath the Veil", "climate": "Perpetual twilight", "atmosphere": "Dread"}},
    {"type": "faction", "name": "The Academy of Veiled Arts", "category": "Institution",
     "description": "Scholars and practitioners of veil-magic.",
     "content": "Founded in the year 412 of the Third Era to regulate the use of veil-magic. The Academy trains those born with the violet eye. Publicly apolitical; secretly the kingdom's most powerful faction.",
     "metadata": {"allegiance": "The Crown", "members_count": "127", "leader": "Archmaster Quill", "territory": "Central Aethelgard"}},
    {"type": "faction", "name": "The Hollow Court", "category": "Cult",
     "description": "Malachar's inner circle, devoted to merging the worlds.",
     "content": "Seven sworn members, each having surrendered something irreplaceable. They meet in the throne room of Old Aethelgard, where time itself is said to bend.",
     "metadata": {"allegiance": "The Veil", "members_count": "7", "leader": "Lord Malachar", "territory": "Old Aethelgard"}},
    {"type": "lore", "name": "The Veil", "category": "Cosmology",
     "description": "The boundary between the waking world and the Hollow.",
     "content": "The Veil is not a wall but a membrane. It thins at certain times and places. Those born with violet eyes can perceive — and, with training, pierce — it. Malachar was its guardian for two centuries before his daughter's death broke him.",
     "metadata": {"origin_era": "Pre-Foundation", "source": "Academy archives", "significance": "Cosmic", "related_locations": "Old Aethelgard"}},
    {"type": "lore", "name": "The Convergence", "category": "Prophecy",
     "description": "Foretold event when the Veil will fall entirely.",
     "content": "Once per era, the Veil thins enough to be torn. The last convergence ended the Second Era. The next is predicted within Elara's lifetime — and may be triggered by a sufficiently powerful veil-worker.",
     "metadata": {"origin_era": "End of Second Era", "source": "The Hollow Codex", "significance": "Apocalyptic"}},
    {"type": "magic_system", "name": "Veil-Magic", "category": "Discipline",
     "description": "The ability to perceive and pierce the Veil.",
     "content": "Innate to those born with violet eyes. With training, a veil-worker can: see through illusions, speak with the recently dead, and (forbidden) read minds. The ultimate taboo is to summon something through the Veil.",
     "metadata": {"source": "Innate", "rules": "Requires concentration; weakened by iron", "limitations": "Cannot create, only perceive", "known_users": "Elara, Mira, Malachar (former)"}},
    {"type": "glossary", "name": "Veil-Worker", "category": "Term",
     "description": "A person born with the ability to perceive the Veil.",
     "content": "Marked by violet eyes. Once revered, now regulated by the Academy.",
     "metadata": {"term": "Veil-Worker", "pronunciation": "/veɪlˈwɜːrkər/", "definition": "One who can pierce the Veil", "related_terms": "The Veil, Veil-Magic"}},
    {"type": "glossary", "name": "The Hollow", "category": "Term",
     "description": "The space beyond the Veil.",
     "content": "Not a place of death, but of waiting. Some say the Hollow is where forgotten things go. Others say it is hungry.",
     "metadata": {"term": "The Hollow", "pronunciation": "/ˈhɒloʊ/", "definition": "The realm beyond the Veil"}},
]


def _sample_paragraphs(seed_text: str, n: int = 5) -> str:
    """Generate n sample paragraphs from a base text."""
    paragraphs = []
    base = seed_text.split(". ")
    for i in range(n):
        start = (i * 7) % len(base)
        chunk = ". ".join(base[start:start + 6])
        if chunk and not chunk.endswith("."):
            chunk += "."
        paragraphs.append(chunk)
    return "\n\n".join(paragraphs)


def _word_count(text: str) -> int:
    import re
    if not text: return 0
    cleaned = re.sub(r"\s+", " ", text.strip())
    return len(cleaned.split()) if cleaned else 0


def seed(force: bool = False) -> None:
    """Seed the database with sample data. Skips if already seeded (unless force=True)."""
    init_db(seed_defaults=True)
    with read_session() as s:
        existing = s.query(Chapter).count()
    if existing and not force:
        log.info("Seed: already has %d chapters. Use force=True to re-seed.", existing)
        return

    log.info("Seeding sample data…")
    now = now_utc()

    # Characters
    char_ids: list[str] = []
    with write_transaction() as s:
        for c in CHARACTERS:
            cid = uuid.uuid4().hex
            char_ids.append(cid)
            ch = Character(
                id=cid, project_id="default",
                name=c["name"], role=c["role"], age=c.get("age"),
                gender=c.get("gender"),
                aliases=dump_json(c.get("aliases", [])),
                avatar_color=c["color"],
                physical=c.get("physical"),
                psychology=c.get("psychology"),
                background=c.get("background"),
                philosophy=c.get("philosophy"),
                philosophy_quotes=dump_json(c.get("philosophy_quotes", [])),
                story_role=c.get("story_role"),
                voice=c.get("voice"),
                created_at=now, updated_at=now,
            )
            s.add(ch)
        s.flush()

    # Groups
    group_ids: list[str] = []
    with write_transaction() as s:
        for g in GROUPS:
            gid = uuid.uuid4().hex
            group_ids.append(gid)
            s.add(CharacterGroup(
                id=gid, project_id="default", name=g["name"],
                description=g["description"], color=g["color"],
            ))
            s.flush()
            for member_idx in g["members"]:
                s.add(CharacterGroupMember(
                    id=uuid.uuid4().hex,
                    character_id=char_ids[member_idx],
                    group_id=gid,
                ))

    # Relationships
    with write_transaction() as s:
        for from_idx, to_idx, rel_type, desc, bi in RELATIONSHIPS:
            s.add(CharacterRelationship(
                id=uuid.uuid4().hex,
                from_character_id=char_ids[from_idx],
                to_character_id=char_ids[to_idx],
                relationship_type=rel_type, description=desc,
                is_bidirectional=bi, created_at=now,
            ))

    # Arcs for Elara
    with write_transaction() as s:
        arc = CharacterArc(
            id=uuid.uuid4().hex,
            character_id=char_ids[0],
            arc_name="From Victim to Guardian",
            description="Elara's journey from grieving survivor to self-appointed guardian of the Veil.",
            stages=dump_json([
                {"name": "Innocence", "description": "Life in Hollowmere before the raid.",
                 "status": "completed", "chapter_ids": []},
                {"name": "Loss", "description": "The raid and her mother's death.",
                 "status": "completed", "chapter_ids": []},
                {"name": "Awakening", "description": "Discovery of her powers and the wider world.",
                 "status": "in_progress", "chapter_ids": []},
                {"name": "Choice", "description": "The confrontation with Malachar.",
                 "status": "planned", "chapter_ids": []},
                {"name": "Guardian", "description": "Accepting the role Malachar once held.",
                 "status": "planned", "chapter_ids": []},
            ]),
            created_at=now,
        )
        s.add(arc)

    # Chapters
    chapter_titles = [
        ("Ashes of Hollowmere", "draft", "Elara returns to find her village in flames.", 2200),
        ("The Veiled Eye", "draft", "Elara's gift manifests for the first time.", 1800),
        ("The Road South", "revised", "Elara, Kael, and Ash begin their journey.", 2600),
        ("Aethelgard", "draft", "The party arrives at the capital.", 2900),
        ("The Academy's Welcome", "draft", "Mira welcomes Elara to the Academy.", 2400),
    ]
    chapter_ids: list[str] = []
    for idx, (title, status, synopsis, target_wc) in enumerate(chapter_titles, start=1):
        text = _sample_paragraphs(
            f"The wind carried ash from Hollowmere across the moorland. "
            f"Elara's boots crunched on frost-burnt grass as she walked the road her mother had once walked. "
            f"She did not weep. The tears had come at dawn, when the smoke still rose. "
            f"Now there was only the cold, and the long road south, and a violet eye she had hidden all her life. "
            f"Kael walked beside her, his hammer slung across his back. "
            f"Ash scouted ahead, a shadow among the pines. "
            f"They did not speak of what they had seen. There were no words for it. "
            f"In the distance, the spires of Aethelgard caught the late sun. "
            f"Mira was waiting. There were answers there — or at least, the shape of answers.",
            n=8 + idx,
        )
        cid = uuid.uuid4().hex
        chapter_ids.append(cid)
        with write_transaction() as s:
            wc = _word_count(text)
            s.add(Chapter(
                id=cid, project_id="default", title=title, content=text,
                synopsis=synopsis, status=status,
                word_count=wc, target_word_count=target_wc,
                sort_order=idx,
                character_ids=dump_json([char_ids[0], char_ids[2], char_ids[4]][:2 + (idx % 3)]),
                tags=dump_json(["opening", "journey"][:1 + (idx % 2)]),
                created_at=now - timedelta(days=30 - idx * 5),
                updated_at=now - timedelta(days=30 - idx * 5, hours=-12),
            ))
            s.add(ChapterVersion(
                id=uuid.uuid4().hex, chapter_id=cid, version_number=1,
                content=text, word_count=wc, source="manual",
                uploaded_at=now - timedelta(days=30 - idx * 5),
                notes="Initial version",
            ))

    # Plans
    for idx, p in enumerate(PLANS):
        with write_transaction() as s:
            plan_id = uuid.uuid4().hex
            s.add(Plan(
                id=plan_id, project_id="default",
                title=p["title"], description=p["description"],
                status=p["status"], column=p["status"],
                sort_order=idx + 1,
                track=p.get("track"), event_type=p.get("event_type"),
                story_date=p.get("story_date"),
                characters_involved=dump_json([char_ids[0]]),
                created_at=now - timedelta(days=20 - idx),
                updated_at=now - timedelta(days=20 - idx),
            ))
            # Subtasks
            for sidx, st_title in enumerate(["Outline beats", "Draft scenes", "Revise"]):
                s.add(PlanSubtask(
                    id=uuid.uuid4().hex, plan_id=plan_id,
                    title=st_title,
                    is_completed=(idx < 2 and sidx == 0),
                    sort_order=sidx + 1,
                    created_at=now,
                ))

    # World entries
    for idx, w in enumerate(WORLD_ENTRIES):
        with write_transaction() as s:
            eid = uuid.uuid4().hex
            s.add(WorldEntry(
                id=eid, project_id="default",
                type=w["type"], name=w["name"],
                category=w.get("category"), description=w.get("description"),
                content=w.get("content"),
                metadata_=dump_json(w.get("metadata", {})),
                sort_order=idx + 1,
                created_at=now - timedelta(days=15 - idx),
                updated_at=now - timedelta(days=15 - idx),
            ))
            s.add(WorldEntryVersion(
                id=uuid.uuid4().hex, entry_id=eid, version_number=1,
                snapshot=dump_json(w), source="manual",
                created_at=now - timedelta(days=15 - idx),
                notes="Initial version",
            ))
            # Pin some locations on the map
            if w["type"] == "location":
                we = s.get(WorldEntry, eid)
                we.map_pin_x = 20 + (idx * 25) % 60
                we.map_pin_y = 30 + (idx * 17) % 40
                we.map_pin_label = w["name"]

    # Activity log for past 60 days (for streaks + heatmap)
    log.info("Generating 60-day activity log…")
    with write_transaction() as s:
        for days_ago in range(60, 0, -1):
            # Write something most days (skip ~20%)
            if random.random() < 0.2:
                continue
            ts = now - timedelta(days=days_ago, hours=random.randint(0, 23))
            delta = random.randint(100, 1200)
            ch_idx = random.randint(0, len(chapter_ids) - 1)
            s.add(ActivityLog(
                project_id="default",
                entity_type="chapter",
                entity_id=chapter_ids[ch_idx],
                entity_title=chapter_titles[ch_idx][0],
                action=random.choice(["updated", "status_changed", "updated"]),
                word_count_delta=delta,
                timestamp=ts,
            ))
    log.info("Seed complete.")


if __name__ == "__main__":
    from core.logging import configure_logging
    configure_logging()
    seed(force="--force" in __import__("sys").argv)
