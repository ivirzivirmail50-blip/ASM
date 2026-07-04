"""Diff service: line-level + word-level diff with inline highlighting."""
from __future__ import annotations

import difflib
import re
from typing import Any


def line_diff(a: str, b: str) -> list[dict]:
    """Return a list of {op, text, words} where op is 'eq'|'add'|'del'.

    For changed lines, also includes a 'word_diff' field with word-level
    inline highlighting.
    """
    a_lines = (a or "").splitlines(keepends=False)
    b_lines = (b or "").splitlines(keepends=False)
    matcher = difflib.SequenceMatcher(None, a_lines, b_lines)
    out: list[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in a_lines[i1:i2]:
                out.append({"op": "eq", "text": line})
        elif tag == "delete":
            for line in a_lines[i1:i2]:
                out.append({"op": "del", "text": line})
        elif tag == "insert":
            for line in b_lines[j1:j2]:
                out.append({"op": "add", "text": line})
        elif tag == "replace":
            # Pair up del/add lines and compute word-level diff
            del_lines = a_lines[i1:i2]
            add_lines = b_lines[j1:j2]
            max_len = max(len(del_lines), len(add_lines))
            for k in range(max_len):
                if k < len(del_lines):
                    out.append({
                        "op": "del",
                        "text": del_lines[k],
                        "word_diff": _word_diff_segments(del_lines[k], add_lines[k] if k < len(add_lines) else ""),
                    })
                if k < len(add_lines):
                    out.append({
                        "op": "add",
                        "text": add_lines[k],
                        "word_diff": _word_diff_segments(del_lines[k] if k < len(del_lines) else "", add_lines[k]),
                    })
    return out


def _word_diff_segments(a: str, b: str) -> list[dict]:
    """Return word-level segments for inline highlighting.

    Each segment: {op: 'eq'|'add'|'del', text: str}
    """
    a_words = a.split()
    b_words = b.split()
    matcher = difflib.SequenceMatcher(None, a_words, b_words)
    segments: list[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            segments.append({"op": "eq", "text": " ".join(a_words[i1:i2])})
        elif tag == "delete":
            segments.append({"op": "del", "text": " ".join(a_words[i1:i2])})
        elif tag == "insert":
            segments.append({"op": "add", "text": " ".join(b_words[j1:j2])})
        elif tag == "replace":
            segments.append({"op": "del", "text": " ".join(a_words[i1:i2])})
            segments.append({"op": "add", "text": " ".join(b_words[j1:j2])})
    return segments


def word_diff(a: str, b: str) -> list[dict]:
    """Word-level diff with inline highlight markers (whole text)."""
    a_words = (a or "").split()
    b_words = (b or "").split()
    matcher = difflib.SequenceMatcher(None, a_words, b_words)
    out: list[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            out.append({"op": "eq", "text": " ".join(a_words[i1:i2])})
        elif tag == "delete":
            out.append({"op": "del", "text": " ".join(a_words[i1:i2])})
        elif tag == "insert":
            out.append({"op": "add", "text": " ".join(b_words[j1:j2])})
        elif tag == "replace":
            out.append({"op": "del", "text": " ".join(a_words[i1:i2])})
            out.append({"op": "add", "text": " ".join(b_words[j1:j2])})
    return out


def render_html_diff(a: str, b: str) -> str:
    """Render a side-by-side HTML diff with word-level highlighting."""
    diff = line_diff(a, b)
    parts = ['<div class="diff-view">']
    for d in diff:
        cls = {"eq": "diff-eq", "add": "diff-add", "del": "diff-del"}[d["op"]]
        sign = {"eq": " ", "add": "+", "del": "-"}[d["op"]]
        # If we have word_diff segments, render them inline
        if d.get("word_diff"):
            seg_html = []
            for seg in d["word_diff"]:
                text = (seg["text"] or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if seg["op"] == "add":
                    seg_html.append(f'<ins style="background: var(--success-soft); color: var(--success); text-decoration: none">{text}</ins>')
                elif seg["op"] == "del":
                    seg_html.append(f'<del style="background: var(--danger-soft); color: var(--danger); text-decoration: none">{text}</del>')
                else:
                    seg_html.append(text)
            parts.append(f'<div class="{cls}"><span class="diff-sign">{sign}</span><span class="diff-text">{" ".join(seg_html)}</span></div>')
        else:
            text = (d["text"] or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f'<div class="{cls}"><span class="diff-sign">{sign}</span><span class="diff-text">{text}</span></div>')
    parts.append("</div>")
    return "\n".join(parts)


def stats(a: str, b: str) -> dict[str, int]:
    diff = line_diff(a, b)
    added = sum(1 for d in diff if d["op"] == "add")
    deleted = sum(1 for d in diff if d["op"] == "del")
    return {"added_lines": added, "deleted_lines": deleted}


def hunks(a: str, b: str) -> list[dict]:
    """Group diff into hunks (contiguous changed regions with context).

    Each hunk: {start_a, start_b, lines: [{op, text}]}
    Useful for 'navigate between hunks' feature.
    """
    diff = line_diff(a, b)
    hunks_list: list[dict] = []
    current_hunk: list[dict] = []
    context_lines = 2  # lines of unchanged context around changes
    eq_buffer: list[dict] = []

    for d in diff:
        if d["op"] == "eq":
            if current_hunk:
                eq_buffer.append(d)
                if len(eq_buffer) > context_lines:
                    # Flush hunk
                    hunks_list.append({"lines": current_hunk})
                    current_hunk = []
                    eq_buffer = []
            else:
                # Skip leading equal lines
                pass
        else:
            # Flush eq_buffer into current hunk as context
            if eq_buffer:
                current_hunk.extend(eq_buffer)
                eq_buffer = []
            current_hunk.append(d)

    if current_hunk:
        hunks_list.append({"lines": current_hunk})
    return hunks_list
