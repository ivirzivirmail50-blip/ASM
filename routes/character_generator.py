"""Character Generator — AI-powered random character creation."""
from __future__ import annotations
import random
from flask import Blueprint, render_template, jsonify, request
from services import character_service, ai_service

bp = Blueprint("character_generator", __name__, url_prefix="/character-generator")


NAMES_FANTASY = ["Elara", "Kael", "Mira", "Voss", "Lyra", "Darian", "Seraphine", "Thorne", "Elowen", "Ragnar", "Isolde", "Caspian"]
NAMES_MODERN = ["Alex", "Sam", "Jordan", "Casey", "Riley", "Morgan", "Taylor", "Quinn"]
ROLES = ["protagonist", "antagonist", "supporting", "minor"]
ROLES_FANTASY = ["warrior", "mage", "rogue", "healer", "scholar", "noble", "merchant", "assassin"]
TRAITS_POS = ["brave", "loyal", "clever", "compassionate", "determined", "honorable", "witty", "patient"]
TRAITS_NEG = ["stubborn", "arrogant", "impulsive", "vengeful", " secretive", "cynical", "reckless", "possessive"]
MOTIVATIONS = ["revenge", "redemption", "discovery", "love", "power", "freedom", "justice", "survival", "family", "duty"]
FEARS = ["death", "betrayal", "losing loved ones", "failure", "the unknown", "being forgotten", "heights", "darkness"]
QUIRKS = ["collects odd objects", "hums when nervous", "always late", "never lies", "talks to animals", "obsessive about cleanliness", "can't swim", " remembers every face"]


@bp.route("/")
def index():
    return render_template("character_generator/index.html", active_nav="character_generator")


@bp.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(silent=True) or request.form
    use_ai = data.get("use_ai", False)
    setting = data.get("setting", "fantasy")

    if use_ai:
        try:
            prompt = f"Create a detailed character for a {setting} story. Include name, role, age, physical description, personality, background, motivation, fear, and a quirk. Be creative."
            result = ai_service.complete(prompt, max_tokens=400)
            return jsonify({"ok": True, "character": {"ai_generated": True, "description": result}})
        except Exception:
            pass  # Fall back to random

    # Random generation
    names = NAMES_FANTASY if setting == "fantasy" else NAMES_MODERN
    name = random.choice(names) + " " + random.choice(["Blackwood", "Stormrider", "Nightshade", "Ironheart", "Moonwhisper", "Thornfield", "Ashbourne", "Ravenscar"])
    role = random.choice(ROLES)
    age = random.randint(16, 65)
    traits_pos = random.sample(TRAITS_POS, 2)
    traits_neg = random.sample(TRAITS_NEG, 1)
    motivation = random.choice(MOTIVATIONS)
    fear = random.choice(FEARS)
    quirk = random.choice(QUIRKS)
    if setting == "fantasy":
        fantasy_role = random.choice(ROLES_FANTASY)

    character = {
        "name": name,
        "role": role,
        "age": str(age),
        "physical": f"{'Tall' if random.random() > 0.5 else 'Short'} and {'lean' if random.random() > 0.5 else 'stout'}, with {random.choice(['dark', 'fair', 'tanned'])} skin and {random.choice(['blue', 'green', 'brown', 'grey'])} eyes.",
        "personality": f"{', '.join(traits_pos)} but {traits_neg[0]}.",
        "background": f"A {fantasy_role if setting == 'fantasy' else 'former ' + random.choice(['soldier', 'teacher', 'thief', 'doctor'])} who lost everything and now seeks {motivation}.",
        "motivation": motivation,
        "fear": fear,
        "quirk": quirk,
        "ai_generated": False,
    }
    return jsonify({"ok": True, "character": character})


@bp.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(silent=True) or request.form
    try:
        ch = character_service.create_character(
            name=data.get("name", "Generated"),
            role=data.get("role", "supporting"),
            age=data.get("age", ""),
            physical=data.get("physical", ""),
            psychology=data.get("personality", ""),
            background=data.get("background", ""),
        )
        return jsonify({"ok": True, "id": ch.id})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
