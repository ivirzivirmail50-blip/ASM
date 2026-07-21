"""AI service — optional, opt-in hybrid AI (Ollama or OpenAI-compatible).

Disabled unless ai.enabled = true in settings. Returns AiDisabledError
otherwise. Routes return 404 when disabled so AI is invisible by default.

Every AI action is logged to activity_log with entity_type='ai_action'.
Prompt text is NEVER stored — only action type + entity id + timestamp.

Rate limit: 30 requests per session per minute (configurable).
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

import requests

from core.db import read_session, write_transaction
from core.cache import cache
from core.errors import AiDisabledError, AiProviderError
from models.settings import Setting
from services._common import log_activity, new_uuid

log = logging.getLogger("asm.ai")


_THINK_BLOCK_RE = __import__("re").compile(r'<think(?:ing)?>.*?</think(?:ing)?>', __import__("re").DOTALL | __import__("re").IGNORECASE)
_THINK_UNCLOSED_RE = __import__("re").compile(r'<think(?:ing)?>.*$', __import__("re").DOTALL | __import__("re").IGNORECASE)
_THINK_TAG_RE = __import__("re").compile(r'</?think(?:ing)?>', __import__("re").IGNORECASE)


def _clean_thinking(text: str) -> str:
    """Remove <think>...</think> blocks from reasoning models.

    Handles: <think>, <thinking>, unclosed blocks, dangling close tags.
    NEVER falls back to raw text — returns empty string if nothing remains.
    """
    if not text:
        return ""
    # Remove complete <think>...</think> (and <thinking>...</thinking>) blocks
    text = _THINK_BLOCK_RE.sub('', text)
    # Remove any unclosed thinking block at the end (model still thinking / no close tag)
    text = _THINK_UNCLOSED_RE.sub('', text)
    # Remove any leftover dangling open/close tags (e.g. stray </think> from streaming)
    text = _THINK_TAG_RE.sub('', text)
    return text.strip()

# Rate limit: 30 requests per 60 seconds (sliding window)
_RATE_LIMIT = 30
_RATE_WINDOW = 60  # seconds
_request_times: deque = deque()
_rate_lock = __import__("threading").Lock()


def _check_rate_limit() -> None:
    """Raise AiProviderError if rate limit exceeded."""
    with _rate_lock:
        now = time.time()
        while _request_times and _request_times[0] < now - _RATE_WINDOW:
            _request_times.popleft()
        if len(_request_times) >= _RATE_LIMIT:
            from core.errors import AsmError
            raise AsmError(
                f"Rate limit exceeded ({_RATE_LIMIT} requests/{_RATE_WINDOW}s). Please wait.",
                code="rate_limited", status_code=429,
            )
        _request_times.append(now)


def is_enabled(session=None) -> bool:
    """Check if AI is enabled in settings."""
    if session is None:
        with read_session() as s:
            return bool(Setting.get(s, "ai.enabled", False))
    return bool(Setting.get(session, "ai.enabled", False))


def _get_config(session) -> dict[str, Any]:
    return {
        "enabled": bool(Setting.get(session, "ai.enabled", False)),
        "provider": Setting.get(session, "ai.provider", "ollama") or "ollama",
        "api_base": Setting.get(session, "ai.api_base",
                                "http://localhost:11434") or "http://localhost:11434",
        "api_key": Setting.get(session, "ai.api_key", "") or "",
        "model": Setting.get(session, "ai.model", "") or "",
        "timeout": int(Setting.get(session, "ai.timeout_seconds", 60) or 60),
    }


def generate(prompt: str, *, max_tokens: int = 600,
             temperature: float = 0.7) -> str:
    """Generate text via the configured provider.

    Raises AiDisabledError if disabled, AiProviderError on HTTP failure.
    Enforces a rate limit of 30 requests per 60 seconds.
    """
    with read_session() as s:
        cfg = _get_config(s)
    if not cfg["enabled"]:
        raise AiDisabledError()
    if not cfg["model"]:
        raise AiProviderError("No AI model configured.")
    _check_rate_limit()
    if cfg["provider"] == "ollama":
        raw = _call_ollama(cfg, prompt, max_tokens, temperature)
    else:
        raw = _call_openai_compat(cfg, prompt, max_tokens, temperature)
    cleaned = _clean_thinking(raw)
    if not cleaned:
        # Model returned only thinking/reasoning, no actual answer
        # Return the raw text with thinking tags stripped as best-effort
        # but also log a warning
        log.warning("AI response was empty after cleaning thinking tags. Raw length: %d", len(raw or ""))
        # Try a more aggressive clean: just remove the tags themselves
        cleaned = _THINK_TAG_RE.sub('', raw or "").strip()
        if not cleaned:
            raise AiProviderError("The AI model returned only reasoning/thinking text with no final answer. Try a non-reasoning model or increase max_tokens.")
    return cleaned


def generate_streaming(prompt: str, *, max_tokens: int = 600,
                       temperature: float = 0.7):
    """Generator that yields text chunks for streaming display.

    Supports Ollama's native streaming API. For OpenAI-compatible providers,
    uses SSE streaming. Yields (chunk_text, is_final) tuples.
    """
    with read_session() as s:
        cfg = _get_config(s)
    if not cfg["enabled"]:
        raise AiDisabledError()
    if not cfg["model"]:
        raise AiProviderError("No AI model configured.")
    _check_rate_limit()
    if cfg["provider"] == "ollama":
        yield from _stream_ollama(cfg, prompt, max_tokens, temperature)
    else:
        yield from _stream_openai_compat(cfg, prompt, max_tokens, temperature)


def _stream_ollama(cfg, prompt: str, max_tokens: int, temperature: float):
    url = cfg["api_base"].rstrip("/") + "/api/generate"
    try:
        resp = requests.post(
            url,
            json={
                "model": cfg["model"],
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
            timeout=cfg["timeout"],
            stream=True,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                import json
                chunk = json.loads(line)
                text = chunk.get("response", "")
                if text:
                    yield (_clean_thinking(text), False)
                if chunk.get("done"):
                    yield ("", True)
                    return
            except (json.JSONDecodeError, ValueError):
                continue
        yield ("", True)
    except requests.RequestException as exc:
        raise AiProviderError(f"Ollama streaming failed: {exc}") from exc


def _stream_openai_compat(cfg, prompt: str, max_tokens: int,
                          temperature: float):
    url = cfg["api_base"].rstrip("/") + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    try:
        resp = requests.post(
            url,
            headers=headers,
            json={
                "model": cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            },
            timeout=cfg["timeout"],
            stream=True,
        )
        resp.raise_for_status()
        import json
        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8", errors="replace")
            if line_str.startswith("data: "):
                line_str = line_str[6:]
            if line_str.strip() == "[DONE]":
                yield ("", True)
                return
            try:
                chunk = json.loads(line_str)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                text = delta.get("content", "")
                if text:
                    yield (_clean_thinking(text), False)
            except (json.JSONDecodeError, ValueError, IndexError):
                continue
        yield ("", True)
    except requests.RequestException as exc:
        raise AiProviderError(f"OpenAI streaming failed: {exc}") from exc


def _call_ollama(cfg, prompt: str, max_tokens: int, temperature: float) -> str:
    url = cfg["api_base"].rstrip("/") + "/api/generate"
    try:
        resp = requests.post(
            url,
            json={
                "model": cfg["model"],
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
            timeout=cfg["timeout"],
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except requests.RequestException as exc:
        raise AiProviderError(f"Ollama request failed: {exc}") from exc


def _call_openai_compat(cfg, prompt: str, max_tokens: int,
                        temperature: float) -> str:
    url = cfg["api_base"].rstrip("/") + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    try:
        resp = requests.post(
            url,
            headers=headers,
            json={
                "model": cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            },
            timeout=cfg["timeout"],
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.RequestException as exc:
        raise AiProviderError(f"OpenAI-compat request failed: {exc}") from exc
    except (KeyError, IndexError) as exc:
        raise AiProviderError(f"Malformed provider response: {exc}") from exc


# --- High-level capabilities (each logs to activity_log as ai_action) ---

def _log_ai_action(action: str, entity_id: str | None = None,
                   entity_title: str | None = None,
                   details: dict | None = None) -> None:
    """Log AI usage to activity_log. Prompt body is NEVER stored."""
    try:
        with write_transaction() as s:
            log_activity(
                s,
                entity_type="ai_action",
                entity_id=entity_id or new_uuid(),
                entity_title=entity_title or action,
                action=action,
                details=details or {},
            )
    except Exception as exc:
        log.warning("Failed to log AI action: %s", exc)


def continue_writing(chapter_tail: str | None, *, max_tokens: int = 400,
                     entity_id: str | None = None) -> str:
    """Suggest the next paragraph(s) given the end of a chapter."""
    prompt = (
        "Continue the following story text in the same style and tone. "
        "Return only the continuation, no preamble.\n\n"
        f"...{(chapter_tail or "")[-1000:]}"
    )
    result = generate(prompt, max_tokens=max_tokens, temperature=0.8)
    _log_ai_action("continue_writing", entity_id=entity_id,
                   details={"max_tokens": max_tokens})
    return result


def continue_with_context(chapter_tail: str, *,
                          character_profiles: list[dict] | None = None,
                          world_entries: list[dict] | None = None,
                          recent_summaries: list[str] | None = None,
                          tone: str = "",
                          max_tokens: int = 500,
                          entity_id: str | None = None) -> str:
    """Context-aware continuation: sends character/world context + recent chapter summaries.

    This produces much better results than continue_writing() because the AI
    knows the characters, world, and recent plot events.
    """
    parts = ["You are a skilled fiction writer. Continue the story in the same style and tone."]
    parts.append("Return ONLY the continuation text, no preamble or commentary.\n")

    # Add character context
    if character_profiles:
        parts.append("CHARACTERS IN THIS SCENE:")
        for c in character_profiles[:8]:
            parts.append(f"- {c.get('name', '?')}: {(c.get('physical') or '')[:80]}")
            if c.get('voice'):
                parts.append(f"  Voice: {c['voice'][:80]}")
            if c.get('psychology'):
                parts.append(f"  Personality: {c['psychology'][:80]}")
        parts.append("")

    # Add world context
    if world_entries:
        parts.append("WORLD/SETTING:")
        for w in world_entries[:5]:
            parts.append(f"- {w.get('name', '?')} ({w.get('type', '?')}): {(w.get('description') or '')[:80]}")
        parts.append("")

    # Add recent plot context
    if recent_summaries:
        parts.append("RECENT EVENTS:")
        for i, s in enumerate(recent_summaries[-3:], 1):
            parts.append(f"  Chapter {i}: {s[:150]}")
        parts.append("")

    if tone:
        parts.append(f"DESIRED TONE: {tone}")
        parts.append("")

    # Add the actual text to continue
    parts.append("TEXT TO CONTINUE:")
    parts.append(chapter_tail[-1500:])

    prompt = "\n".join(parts)
    result = generate(prompt, max_tokens=max_tokens, temperature=0.8)
    _log_ai_action("continue_with_context", entity_id=entity_id,
                   details={"max_tokens": max_tokens,
                            "has_chars": bool(character_profiles),
                            "has_world": bool(world_entries),
                            "has_summaries": bool(recent_summaries)})
    return result


def summarize(text: str, *, max_tokens: int = 200,
              entity_id: str | None = None) -> str:
    prompt = (
        "Summarize the following text in 1-3 sentences. "
        "Return only the summary.\n\n" + text[:4000]
    )
    result = generate(prompt, max_tokens=max_tokens, temperature=0.5)
    _log_ai_action("summarize", entity_id=entity_id)
    return result


def rewrite(text: str, tone: str, *, max_tokens: int = 600,
            entity_id: str | None = None) -> str:
    prompt = (
        f"Rewrite the following text in a {tone} tone. "
        "Return only the rewritten text.\n\n" + text[:4000]
    )
    result = generate(prompt, max_tokens=max_tokens, temperature=0.7)
    _log_ai_action("rewrite", entity_id=entity_id, details={"tone": tone})
    return result


def suggest_tags(text: str, *, max_tokens: int = 60,
                 entity_id: str | None = None) -> list[str]:
    prompt = (
        "Suggest 3-5 short tags (single words or short phrases, comma-separated) "
        "for the following text. Return only the tags.\n\n" + text[:2000]
    )
    out = generate(prompt, max_tokens=max_tokens, temperature=0.4)
    tags = [t.strip() for t in out.split(",") if t.strip()][:10]
    _log_ai_action("suggest_tags", entity_id=entity_id,
                   details={"count": len(tags)})
    return tags


def suggest_synopsis(text: str, *, max_tokens: int = 120,
                     entity_id: str | None = None) -> str:
    prompt = (
        "Write a 1-2 sentence synopsis for the following chapter. "
        "Return only the synopsis.\n\n" + text[:4000]
    )
    result = generate(prompt, max_tokens=max_tokens, temperature=0.5)
    _log_ai_action("suggest_synopsis", entity_id=entity_id)
    return result


def generate_name(culture: str = "fantasy", kind: str = "character",
                  *, max_tokens: int = 30) -> list[str]:
    """Generate names with caching — same culture+kind returns cached result for 5 min."""
    cache_key = f"ai:name_gen:{culture}:{kind}"
    cached_names = cache.get(cache_key)
    if cached_names is not None:
        return cached_names
    prompt = (
        f"Suggest 5 {culture}-style names for a {kind}. "
        "Return only the names, one per line."
    )
    out = generate(prompt, max_tokens=max_tokens, temperature=0.9)
    # Clean each line and filter empty
    names = [n.strip() for n in out.splitlines() if n.strip() and not n.strip().startswith('<')][:5]
    _log_ai_action("generate_name", details={"culture": culture, "kind": kind})
    if names:
        cache.set(cache_key, names, ttl_seconds=300)  # 5 min cache
    return names


def generate_dialogue(character_name: str, character_voice: str,
                      character_psychology: str,
                      other_character: str = "",
                      scene_context: str = "",
                      emotion: str = "neutral",
                      *, max_tokens: int = 300,
                      entity_id: str | None = None) -> str:
    """Generate dialogue in a character's voice.

    Args:
        character_name: The speaking character's name.
        character_voice: How they speak (dialect, vocabulary, verbal tics).
        character_psychology: Personality, fears, motivations.
        other_character: Who they're talking to (optional).
        scene_context: What's happening in the scene.
        emotion: angry, sad, happy, fearful, sarcastic, neutral.

    Returns: Generated dialogue text (no quotation marks, just the spoken words).
    """
    parts = [
        f"You are writing dialogue for {character_name}, a character in a novel.",
        f"\nCHARACTER VOICE: {character_voice or 'No specific voice notes.'}",
        f"\nCHARACTER PERSONALITY: {character_psychology or 'No personality notes.'}",
    ]
    if other_character:
        parts.append(f"\nSPEAKING TO: {other_character}")
    if scene_context:
        parts.append(f"\nSCENE CONTEXT: {scene_context}")
    parts.append(f"\nEMOTION: {emotion}")
    parts.append(
        f"\nWrite 3-5 lines of dialogue for {character_name}. "
        "Return ONLY the spoken words (no narration, no action tags, no quotation marks). "
        "Each line on its own line."
    )
    prompt = "\n".join(parts)
    result = generate(prompt, max_tokens=max_tokens, temperature=0.8)
    _log_ai_action("generate_dialogue", entity_id=entity_id,
                   details={"character": character_name, "emotion": emotion})
    return result


def consistency_check(chapter_texts: list[dict],
                      character_profiles: list[dict],
                      world_entries: list[dict]) -> list[dict]:
    """Scan chapters for contradictions against character/world DB.

    chapter_texts: [{"title": ..., "content": ...}, ...]
    character_profiles: [{"name": ..., "physical": ..., "psychology": ...}, ...]
    world_entries: [{"name": ..., "type": ..., "description": ...}, ...]

    Returns a list of findings, each: {severity, category, chapter, message}.
    The user reviews these before any change is made — AI never edits.
    """
    # Build a compact context summary (under 4000 chars to fit most models)
    char_summary = "\n".join(
        f"- {c.get('name', '?')}: {(c.get('physical') or '')[:100]} | "
        f"{(c.get('psychology') or '')[:100]}"
        for c in character_profiles[:20]
    )
    world_summary = "\n".join(
        f"- {w.get('name', '?')} ({w.get('type', '?')}): {(w.get('description') or '')[:80]}"
        for w in world_entries[:20]
    )
    chapter_summary = "\n\n".join(
        f"CHAPTER: {ch.get('title', '?')}\n{(ch.get('content') or '')[:1500]}"
        for ch in chapter_texts[:5]
    )
    prompt = (
        "You are a story consistency checker. Read the chapters below and the "
        "character/world reference. Find any contradictions, e.g.:\n"
        "- A character's eye color differs across chapters\n"
        "- A character dies in chapter 1 but reappears in chapter 3\n"
        "- A location's description contradicts earlier text\n"
        "- Timeline inconsistencies (events out of order)\n\n"
        "CHARACTERS:\n" + char_summary + "\n\n"
        "WORLD:\n" + world_summary + "\n\n"
        "CHAPTERS:\n" + chapter_summary + "\n\n"
        "Return findings as a JSON array, one per line, each object with keys: "
        "severity (error/warning), category (character/world/timeline), "
        "chapter (title), message (1-2 sentences). "
        "Return ONLY the JSON array, no preamble."
    )
    out = generate(prompt, max_tokens=800, temperature=0.3)
    # Parse the JSON response
    import json
    import re as _re
    # Try to extract a JSON array from the response
    match = _re.search(r'\[.*\]', out or "", _re.DOTALL)
    if match:
        try:
            findings = json.loads(match.group(0))
            if isinstance(findings, list):
                _log_ai_action("consistency_check",
                               details={"findings": len(findings)})
                return findings
        except json.JSONDecodeError:
            pass
    # Fallback: return the raw text as a single info finding
    _log_ai_action("consistency_check", details={"findings": 0, "fallback": True})
    return [{
        "severity": "info",
        "category": "ai_response",
        "chapter": "",
        "message": out[:500] if out else "No findings returned.",
    }]
