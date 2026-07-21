"""Plot structure templates — apply classic story beats to your outline.

Provides well-known structures (Hero's Journey, Save the Cat, Three-Act,
Seven-Point, Freytag's Pyramid) and lets the writer apply one to their
plans, auto-creating a set of beat-stub plans under a new track.

Each template is a list of beats with: position, name, description,
suggested_status, suggested_event_type.

When applied, a track is created (named after the template) and one plan
is created per beat, ordered by position, with a description explaining
what that beat should accomplish.
"""
from __future__ import annotations

import logging
from typing import Any

from services._common import log_activity

log = logging.getLogger("asm.plot_templates")


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, dict[str, Any]] = {
    "heros_journey": {
        "name": "Hero's Journey (Campbell)",
        "icon": "🛡",
        "summary": "Joseph Campbell's 12-stage monomyth — the classic structure for fantasy, sci-fi, and adventure.",
        "beats": [
            ("Ordinary World", "Show the hero in their normal life before the adventure. Establish what's at stake and what they stand to lose.", "idea", "character_moment"),
            ("Call to Adventure", "An event disrupts the ordinary world — a message, a stranger, a disaster — inviting the hero into the unknown.", "idea", "plot_point"),
            ("Refusal of the Call", "The hero hesitates. Fear, duty, or doubt holds them back. Show the cost of refusing.", "idea", "character_moment"),
            ("Meeting the Mentor", "A guide appears — offering wisdom, tools, or a push. The mentor's role is to overcome the refusal.", "planned", "character_moment"),
            ("Crossing the Threshold", "The hero commits. There's no going back. They enter the special world.", "planned", "plot_point"),
            ("Tests, Allies, Enemies", "The hero learns the rules of the new world, makes friends, makes enemies, and is tested.", "planned", "plot_point"),
            ("Approach to the Inmost Cave", "Preparation for the big challenge. The hero and allies plan their approach to the central ordeal.", "writing", "plot_point"),
            ("The Ordeal", "The hero confronts their greatest fear. A death and rebirth — literal or symbolic.", "writing", "climax"),
            ("Reward (Seizing the Sword)", "The hero survives and claims a reward — a treasure, knowledge, reconciliation, or weapon.", "writing", "plot_point"),
            ("The Road Back", "The hero begins the return, but faces consequences. The enemy regroups. New dangers emerge.", "draft_done", "plot_point"),
            ("Resurrection", "The final test. The hero must apply everything they've learned in a climactic confrontation.", "revised", "climax"),
            ("Return with the Elixir", "The hero returns home transformed, bearing gifts that heal or renew the ordinary world.", "final", "resolution"),
        ],
    },
    "save_the_cat": {
        "name": "Save the Cat (Snyder)",
        "icon": "🐱",
        "summary": "Blake Snyder's 15-beat structure from screenwriting — adapted for novels, very tight pacing.",
        "beats": [
            ("Opening Image", "A single visual that sets tone and stakes. The 'before' snapshot of the protagonist.", "idea", "character_moment"),
            ("Theme Stated", "Someone (often not the hero) says the theme out loud — usually without the hero understanding it yet.", "idea", "plot_point"),
            ("Set-Up", "Introduce the hero's flaws, the world, and what needs fixing. Establish the status quo.", "idea", "character_moment"),
            ("Catalyst", "The inciting incident. The knock at the door. Life will never be the same.", "idea", "plot_point"),
            ("Debate", "The hero hesitates. Should they go? Show the doubt that makes them human.", "planned", "character_moment"),
            ("Break into Two", "The hero makes a choice. They step into Act II — the new world.", "planned", "plot_point"),
            ("B Story", "A subplot begins — often a love interest or friendship that carries the theme.", "planned", "character_moment"),
            ("Fun and Games", "The 'promise of the premise.' Explore the new world. The trailer moments live here.", "writing", "plot_point"),
            ("Midpoint", "A false victory or false defeat. The stakes rise. The clock starts ticking.", "writing", "plot_point"),
            ("Bad Guys Close In", "External pressures mount. Internal flaws worsen. Things fall apart.", "writing", "plot_point"),
            ("All Is Lost", "The lowest point. The whiff of death. The hero loses what they thought they wanted.", "draft_done", "climax"),
            ("Dark Night of the Soul", "The hero reacts to the loss. They wallow, doubt, and finally understand the theme.", "draft_done", "character_moment"),
            ("Break into Three", "The hero finds the answer. Synthesis of A and B stories. They know what to do.", "revised", "plot_point"),
            ("Finale", "The final test. The hero proves they've changed by defeating the antagonist in a new way.", "revised", "climax"),
            ("Final Image", "The 'after' snapshot — a visual mirror of the opening, proving the hero's transformation.", "final", "resolution"),
        ],
    },
    "three_act": {
        "name": "Three-Act Structure",
        "icon": "🎭",
        "summary": "The simplest classical structure: setup, confrontation, resolution. Good for literary fiction and short stories.",
        "beats": [
            ("Act I — Setup", "Establish the world, the protagonist, and the status quo. End with the inciting incident.", "idea", "plot_point"),
            ("Plot Point 1", "The protagonist commits to the journey. The first act turns into the second.", "planned", "plot_point"),
            ("Act II — Rising Action", "The protagonist pursues the goal, faces obstacles, and grows. Subplots develop.", "writing", "plot_point"),
            ("Midpoint", "A reversal or revelation shifts the direction. Stakes escalate.", "writing", "plot_point"),
            ("Plot Point 2", "A major setback or discovery. The protagonist's plan fails; they must change strategy.", "draft_done", "plot_point"),
            ("Act III — Resolution", "The protagonist confronts the antagonist. The central question is answered.", "revised", "climax"),
            ("Denouement", "Loose ends tied off. The new normal is shown. The protagonist has changed.", "final", "resolution"),
        ],
    },
    "seven_point": {
        "name": "Seven-Point Story Structure (Wells)",
        "icon": "7️⃣",
        "summary": "Dan Wells' compact 7-beat structure. Great for tight novels and short stories.",
        "beats": [
            ("Hook", "The opposite of the resolution. Show who the protagonist is before the story changes them.", "idea", "character_moment"),
            ("Plot Turn 1", "The inciting incident. The world shifts; the journey begins.", "planned", "plot_point"),
            ("Pinch Point 1", "Pressure applied. The antagonist's presence is felt. Things go wrong.", "writing", "plot_point"),
            ("Midpoint", "The protagonist shifts from reaction to action. They commit to fighting back.", "writing", "plot_point"),
            ("Pinch Point 2", "More pressure. A bigger threat. The protagonist loses an ally or resource.", "draft_done", "plot_point"),
            ("Plot Turn 2", "The final piece falls into place. The protagonist gets what they need to win.", "revised", "plot_point"),
            ("Resolution", "The opposite of the hook. The protagonist has transformed. The conflict is resolved.", "final", "resolution"),
        ],
    },
    "freytag": {
        "name": "Freytag's Pyramid",
        "icon": "🔺",
        "summary": "Gustav Freytag's 5-stage dramatic structure — the classic shape of tragedy and drama.",
        "beats": [
            ("Exposition", "Set the scene. Introduce characters, setting, and the initial situation.", "idea", "plot_point"),
            ("Rising Action", "A series of events build tension and develop the conflict. Complications arise.", "writing", "plot_point"),
            ("Climax", "The turning point of highest tension. The protagonist's fortune reverses.", "writing", "climax"),
            ("Falling Action", "The consequences of the climax unfold. The conflict unravels toward resolution.", "revised", "plot_point"),
            ("Resolution", "The story ends — tragically or happily. The new normal is established.", "final", "resolution"),
        ],
    },
    "kishotenketsu": {
        "name": "Kishōtenketsu (4-Act, no conflict)",
        "icon": "🌸",
        "summary": "A conflict-free structure common in East Asian storytelling. Drives interest through twist, not battle.",
        "beats": [
            ("Ki (Introduction)", "Introduce characters and setting. Establish what is normal.", "idea", "character_moment"),
            ("Shō (Development)", "Build on the introduction. Add depth, daily life, and texture — but no conflict yet.", "planned", "plot_point"),
            ("Ten (Twist)", "An unexpected event or development. Something that doesn't fit the established pattern.", "writing", "plot_point"),
            ("Ketsu (Conclusion)", "Reconcile the twist with the introduction. The reader understands in a new way.", "final", "resolution"),
        ],
    },
    "fichtean_curve": {
        "name": "Fichtean Curve",
        "icon": "📈",
        "summary": "Rising action with alternating crises and resolutions. Each crisis raises the stakes.",
        "beats": [
            ("Opening", "Start in media res — in the middle of action or conflict.", "idea", "plot_point"),
            ("Crisis 1", "First crisis — the protagonist faces a challenge and partially resolves it.", "planned", "plot_point"),
            ("Rising Action 1", "Aftermath of crisis 1. New information or complication.", "planned", "character_moment"),
            ("Crisis 2", "Second crisis — bigger stakes, harder challenge.", "writing", "plot_point"),
            ("Rising Action 2", "Aftermath of crisis 2. Tension builds.", "writing", "character_moment"),
            ("Crisis 3", "Third crisis — the biggest challenge yet. Stakes are at their highest.", "draft_done", "climax"),
            ("Climax", "The final, decisive confrontation. All threads converge.", "revised", "climax"),
            ("Falling Action", "The dust settles. Consequences of the climax unfold.", "revised", "plot_point"),
            ("Resolution", "The new normal. How has the protagonist changed?", "final", "resolution"),
        ],
    },
    "heroines_journey": {
        "name": "Heroine's Journey (Murphy)",
        "icon": "🗡️",
        "summary": "A feminine-focused structure emphasizing relationships, integration, and healing.",
        "beats": [
            ("Separation from the Feminine", "The protagonist separates from a feminine figure or value system.", "idea", "character_moment"),
            ("Identification with the Masculine", "The protagonist adopts masculine values — action, competition, individualism.", "planned", "character_moment"),
            ("Road of Trials", "The protagonist faces challenges using their new masculine approach.", "writing", "plot_point"),
            ("Illusory Triumph", "A false victory — the protagonist seems to win but feels empty.", "writing", "climax"),
            ("Awakening", "The protagonist realizes something is missing. The masculine approach has limits.", "draft_done", "character_moment"),
            ("Descent to the Goddess", "The protagonist reconnects with the feminine — through pain, vulnerability, or love.", "revised", "plot_point"),
            ("Integration", "The protagonist integrates both masculine and feminine. Wholeness achieved.", "revised", "character_moment"),
            ("Return", "The protagonist returns to their community, transformed and whole.", "final", "resolution"),
        ],
    },
    "tragedy": {
        "name": "Tragic Arc (Aristotle)",
        "icon": "🎭",
        "summary": "The classical tragic structure: hubris, hamartia, peripeteia, anagnorisis, catharsis.",
        "beats": [
            ("Prologue", "Establish the tragic hero — noble, capable, but with a fatal flaw (hamartia).", "idea", "character_moment"),
            ("Parodos", "The hero enters, confident and powerful. Pride (hubris) is on display.", "planned", "plot_point"),
            ("Rising Action", "The hero faces challenges and succeeds, but each success deepens the flaw.", "writing", "plot_point"),
            ("Peripeteia (Reversal)", "The turning point — fortune reverses. The hero's flaw causes a catastrophic mistake.", "draft_done", "climax"),
            ("Anagnorisis (Recognition)", "The hero recognizes their error — too late to undo it.", "revised", "character_moment"),
            ("Suffering", "The hero suffers the consequences. Loss of everything they valued.", "revised", "plot_point"),
            ("Catharsis", "The audience experiences pity and fear, leading to emotional release.", "final", "resolution"),
        ],
    },
    "voyage_return": {
        "name": "Voyage and Return",
        "icon": "🚢",
        "summary": "The protagonist travels to a strange world, faces challenges, and returns transformed.",
        "beats": [
            ("Departure", "The protagonist leaves their familiar world — by choice or by force.", "idea", "plot_point"),
            ("Arrival in Strange World", "The protagonist enters an unfamiliar place with different rules.", "planned", "plot_point"),
            ("Initial Wonder", "The protagonist explores the new world. Fascination and discovery.", "planned", "character_moment"),
            ("Danger Emerges", "The new world reveals its dangers. The protagonist is threatened.", "writing", "plot_point"),
            ("Adaptation", "The protagonist learns to navigate the strange world. Growth and change.", "writing", "character_moment"),
            ("Climax", "The protagonist faces the ultimate threat in the strange world.", "draft_done", "climax"),
            ("Escape/Return", "The protagonist escapes the strange world and returns home.", "revised", "plot_point"),
            ("Transformation", "The protagonist is forever changed by the journey. Home feels different.", "final", "resolution"),
        ],
    },
    "comedic_structure": {
        "name": "Comedic Structure (Frye)",
        "icon": "😄",
        "summary": "The classic comedy arc: disorder, confusion, recognition, and joyful resolution.",
        "beats": [
            ("Establishment of Order", "Show the normal social order. Who's in charge? What are the rules?", "idea", "character_moment"),
            ("Disruption", "Something disrupts the order — a trickster, a lie, a misunderstanding.", "planned", "plot_point"),
            ("Escalating Confusion", "The disruption spreads. More characters get involved. Lies compound.", "writing", "plot_point"),
            ("Comic Climax", "Maximum confusion — everything is chaos. All characters are in the wrong place.", "draft_done", "climax"),
            ("Recognition Scene", "The truth comes out. Mistakes are revealed. Identities are unmasked.", "revised", "plot_point"),
            ("Restoration of Order", "A new, better order is established. The right couples pair off.", "revised", "resolution"),
            ("Celebration", "A feast, wedding, or festival marks the happy ending.", "final", "resolution"),
        ],
    },
}


def list_templates() -> list[dict[str, Any]]:
    return [
        {
            "key": k,
            "name": v["name"],
            "icon": v["icon"],
            "summary": v["summary"],
            "beat_count": len(v["beats"]),
        }
        for k, v in TEMPLATES.items()
    ]


def get_template(key: str) -> dict[str, Any] | None:
    return TEMPLATES.get(key)


def apply_template(key: str) -> dict[str, Any]:
    """Apply a plot structure template: create a track of beats as plans.

    Returns a summary dict with the created plan ids.
    """
    if key not in TEMPLATES:
        from core.errors import ValidationError
        raise ValidationError(f"Unknown template: {key}")
    tmpl = TEMPLATES[key]
    # Import here to avoid circular import
    from services.plan_service import create_plan
    track_name = f"plot:{key}"
    created_ids: list[str] = []
    for i, (name, desc, status, event_type) in enumerate(tmpl["beats"], start=1):
        full_title = f"[{i:02d}] {name}"
        full_desc = (
            f"**Beat {i} of {len(tmpl['beats'])} — {tmpl['name']}**\n\n"
            f"{desc}\n\n"
            f"_Suggested status:_ {status}  ·  _Suggested event type:_ {event_type}"
        )
        p = create_plan(
            title=full_title,
            description=full_desc,
            status="idea",  # always start as idea; the description recommends a status
            track=track_name,
            event_type=event_type,
            tags=["plot_template", key],
        )
        created_ids.append(p.id)
    log.info("Applied plot template %s — created %d plans on track %s",
             key, len(created_ids), track_name)
    return {
        "template": key,
        "template_name": tmpl["name"],
        "track": track_name,
        "beats_created": len(created_ids),
        "plan_ids": created_ids,
    }
