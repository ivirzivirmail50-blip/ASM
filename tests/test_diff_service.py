"""Tests for diff_service: line-level and word-level diff."""
import pytest

from services import diff_service


class TestLineDiff:
    def test_identical_text(self):
        diff = diff_service.line_diff("hello\nworld", "hello\nworld")
        assert all(d["op"] == "eq" for d in diff)
        assert len(diff) == 2

    def test_addition(self):
        diff = diff_service.line_diff("line1", "line1\nline2")
        ops = [d["op"] for d in diff]
        assert "add" in ops

    def test_deletion(self):
        diff = diff_service.line_diff("line1\nline2", "line1")
        ops = [d["op"] for d in diff]
        assert "del" in ops

    def test_replacement(self):
        diff = diff_service.line_diff("old line", "new line")
        ops = [d["op"] for d in diff]
        assert "del" in ops
        assert "add" in ops

    def test_empty_strings(self):
        diff = diff_service.line_diff("", "")
        assert diff == []

    def test_none_inputs(self):
        diff = diff_service.line_diff(None, None)
        assert diff == []

    def test_word_diff_in_replace(self):
        """Changed lines should include word_diff segments."""
        diff = diff_service.line_diff("the quick brown fox", "the quick red fox")
        dels = [d for d in diff if d["op"] == "del"]
        adds = [d for d in diff if d["op"] == "add"]
        # At least one should have word_diff
        assert any(d.get("word_diff") for d in dels + adds)


class TestWordDiff:
    def test_word_diff_equal(self):
        result = diff_service.word_diff("hello world", "hello world")
        assert len(result) == 1
        assert result[0]["op"] == "eq"

    def test_word_diff_replace(self):
        result = diff_service.word_diff("hello world", "hello earth")
        ops = [r["op"] for r in result]
        assert "del" in ops
        assert "add" in ops


class TestRenderHtmlDiff:
    def test_renders_html(self):
        html = diff_service.render_html_diff("old", "new")
        assert "<div class=\"diff-view\">" in html
        assert "</div>" in html

    def test_renders_ins_del_for_changes(self):
        html = diff_service.render_html_diff("the brown fox", "the red fox")
        assert "<ins" in html or "<del" in html

    def test_no_changes_no_ins_del(self):
        html = diff_service.render_html_diff("same text", "same text")
        assert "<ins" not in html
        assert "<del" not in html


class TestStats:
    def test_stats_additions(self):
        s = diff_service.stats("line1", "line1\nline2\nline3")
        assert s["added_lines"] == 2
        assert s["deleted_lines"] == 0

    def test_stats_deletions(self):
        s = diff_service.stats("line1\nline2\nline3", "line1")
        assert s["added_lines"] == 0
        assert s["deleted_lines"] == 2

    def test_stats_equal(self):
        s = diff_service.stats("same", "same")
        assert s["added_lines"] == 0
        assert s["deleted_lines"] == 0


class TestHunks:
    def test_hunks_grouping(self):
        hunks = diff_service.hunks("line1\nline2\nline3\nline4",
                                    "line1\nCHANGED\nline3\nCHANGED2")
        assert len(hunks) >= 1
        # Each hunk should have lines
        for h in hunks:
            assert "lines" in h
            assert len(h["lines"]) > 0

    def test_hunks_no_changes(self):
        hunks = diff_service.hunks("same", "same")
        assert len(hunks) == 0

    def test_hunks_single_change(self):
        hunks = diff_service.hunks("a\nb\nc", "a\nB\nc")
        assert len(hunks) == 1
