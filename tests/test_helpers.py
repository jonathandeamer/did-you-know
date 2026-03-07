#!/usr/bin/env python3
"""Unit tests for scripts/helpers.py.

Run with: python3 -m pytest tests/ -v
Requires: pip install pytest
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import helpers


class TestNormalizeText:
    def test_basic_markup_cleanup(self):
        text = "The [[Albert Einstein|Einstein]] {{cite}} was ''brilliant''{{'s}}"
        assert helpers.normalize_text(text) == "The Einstein was brilliant's"

    def test_removes_pictured_parenthetical(self):
        text = "a bird (pictured here) in flight"
        assert helpers.normalize_text(text) == "a bird in flight"

    def test_collapses_whitespace(self):
        assert helpers.normalize_text("  hello   world  ") == "hello world"

    def test_decodes_html_entities(self):
        assert helpers.normalize_text("5&amp;10") == "5&10"
        assert helpers.normalize_text("A&ndash;B") == "A\u2013B"
        assert helpers.normalize_text("A&mdash;B") == "A\u2014B"

    def test_normalises_numeric_nbsp_entity(self):
        assert helpers.normalize_text("5&#160;10") == "5 10"

    def test_normalises_hex_nbsp_entity(self):
        assert helpers.normalize_text("5&#xA0;10") == "5 10"

    def test_collapses_consecutive_nbsp_entities(self):
        assert helpers.normalize_text("5&#160;&#160;10") == "5 10"

    def test_strips_leading_trailing_nbsp_entity(self):
        assert helpers.normalize_text("&#160;hello&#160;") == "hello"

    def test_wikilink_with_template_label_falls_back_to_title(self):
        # {{nowrap|...}} stripped from label leaves [[Title|]] which RE_LINK can't
        # match (empty capture group), so brackets leak into output. The fix must
        # resolve [[Title|]] → title text instead of leaving raw wikilink syntax.
        text = "the [[Lockheed U-2|{{nowrap|U-2}}]] spy aircraft"
        assert helpers.normalize_text(text) == "the Lockheed U-2 spy aircraft"

    def test_strips_inline_html_comment(self):
        # Raw <!-- ... --> comment tags survive normalize_text unchanged today.
        # They must be stripped before the text is displayed.
        text = "before Philippe <!-- deliberately not linked --> took photos"
        assert helpers.normalize_text(text) == "before Philippe took photos"

    def test_four_quote_run_no_stray_apostrophe(self):
        # ''''word''' is italic+bold run-together; stray ' must not survive.
        # Currently broken: normalize_text produces "'tissue" not "tissue".
        text = "''''[[Tissue (cloth)|tissue]]'''"
        assert helpers.normalize_text(text) == "tissue"

    def test_bold_wikilink_with_template_label(self):
        # Bold markers around [[Title|{{template}}]] must resolve to title text.
        text = "'''[[IG-11|{{nowrap|IG-11}}]]'''"
        assert helpers.normalize_text(text) == "IG-11"

    def test_html_entity_in_wikilink_label(self):
        # Numeric HTML entities inside a wikilink label must be decoded.
        text = "[[Konopi&#353;te|Konopi&#353;t&#283;]]"
        assert helpers.normalize_text(text) == "Konopiště"

    def test_strips_multiline_html_comment(self):
        # HTML comments that span newlines must also be stripped.
        text = "before <!-- editorial\nnote --> after"
        assert helpers.normalize_text(text) == "before after"

    def test_italic_pictured_parenthetical(self):
        # ''(pictured)'' must be stripped the same as plain (pictured).
        text = "a bird ''(pictured)'' in flight"
        assert helpers.normalize_text(text) == "a bird in flight"


class TestExtractHooksSection:
    def test_extracts_between_markers(self):
        source = "a<!--Hooks-->line1\nline2<!--HooksEnd-->z"
        assert helpers.extract_hooks_section(source) == "line1\nline2"

    def test_missing_markers_returns_none(self):
        assert helpers.extract_hooks_section("<!--Hooks-->missing end") is None
        assert helpers.extract_hooks_section("missing start<!--HooksEnd-->") is None

    def test_end_before_start_returns_none(self):
        assert helpers.extract_hooks_section("<!--HooksEnd--><!--Hooks-->") is None


class TestExtractHookTitles:
    def test_prefers_bold_link_titles(self):
        line = "'''[[First Article]]''' then [[Fallback]]"
        assert helpers.extract_hook_titles(line) == ["First Article"]

    def test_collects_multiple_bold_links(self):
        line = "'''[[One]]''' and '''[[Two|Two Label]]'''"
        assert helpers.extract_hook_titles(line) == ["One", "Two"]

    def test_falls_back_to_first_link(self):
        line = "See [[Albert Einstein]] and [[Isaac Newton]]"
        assert helpers.extract_hook_titles(line) == ["Albert Einstein"]

    def test_no_links_returns_empty(self):
        assert helpers.extract_hook_titles("plain text") == []


class TestTitleToUrl:
    def test_builds_expected_wikipedia_url(self):
        assert (
            helpers.title_to_url("Albert Einstein")
            == "https://en.wikipedia.org/wiki/Albert_Einstein"
        )

    def test_encodes_special_characters(self):
        url = helpers.title_to_url("C++ (programming language)")
        assert url == "https://en.wikipedia.org/wiki/C%2B%2B_%28programming_language%29"


class TestParseIso:
    def test_parses_z_suffix(self):
        result = helpers.parse_iso("2026-02-24T12:00:00Z")
        assert result == datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)

    def test_parses_offset_suffix(self):
        result = helpers.parse_iso("2026-02-24T12:00:00+00:00")
        assert result == datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)

    def test_returns_none_for_invalid_string(self):
        assert helpers.parse_iso("not-a-date") is None

    def test_returns_none_for_empty_string(self):
        assert helpers.parse_iso("") is None


class TestRetryWithBackoff:
    def test_returns_immediately_on_first_success(self):
        calls = {"n": 0}

        def succeed():
            calls["n"] += 1
            return "ok"

        result = helpers.retry_with_backoff(succeed, retries=3, backoff=0)
        assert result == "ok"
        assert calls["n"] == 1

    def test_succeeds_on_second_attempt(self, monkeypatch):
        monkeypatch.setattr(helpers.time, "sleep", lambda _: None)
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("not yet")
            return "done"

        result = helpers.retry_with_backoff(flaky, retries=3, backoff=0)
        assert result == "done"
        assert calls["n"] == 2

    def test_raises_after_all_retries_exhausted(self, monkeypatch):
        monkeypatch.setattr(helpers.time, "sleep", lambda _: None)

        def always_fail():
            raise ValueError("always")

        with pytest.raises(RuntimeError, match="Failed after 3 attempts"):
            helpers.retry_with_backoff(always_fail, retries=3, backoff=0)


class TestFetchWikitext:
    def test_returns_revision_content(self, monkeypatch):
        payload = {
            "query": {
                "pages": {
                    "1": {"revisions": [{"slots": {"main": {"*": "HOOKS"}}}]}
                }
            }
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        monkeypatch.setattr(helpers.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())
        assert helpers.fetch_wikitext(retries=1, backoff=0) == "HOOKS"

    def test_retries_then_raises(self, monkeypatch):
        attempts = {"count": 0}

        def fail(*_args, **_kwargs):
            attempts["count"] += 1
            raise RuntimeError("boom")

        monkeypatch.setattr(helpers.urllib.request, "urlopen", fail)
        monkeypatch.setattr(helpers.time, "sleep", lambda _secs: None)

        with pytest.raises(RuntimeError, match="Failed to fetch Did You Know hooks"):
            helpers.fetch_wikitext(retries=3, backoff=0)
        assert attempts["count"] == 3


class TestCollectHooks:
    def test_parses_hooks_from_wikitext(self, monkeypatch):
        wikitext = """
<!--Hooks-->
* ... that '''[[Alpha]]''' did a thing?
* ... that [[Beta|B]] worked with [[Gamma]]?
Not a hook
<!--HooksEnd-->
"""

        monkeypatch.setattr(helpers, "fetch_wikitext", lambda: wikitext)
        hooks = helpers.collect_hooks()

        assert len(hooks) == 2
        assert hooks[0]["text"] == "Alpha did a thing?"
        assert hooks[0]["urls"] == ["https://en.wikipedia.org/wiki/Alpha"]
        assert hooks[0]["returned"] is False
        assert hooks[1]["text"] == "B worked with Gamma?"
        assert hooks[1]["urls"][0] == "https://en.wikipedia.org/wiki/Beta"

    def test_returns_empty_when_section_missing(self, monkeypatch):
        monkeypatch.setattr(helpers, "fetch_wikitext", lambda: "no markers")
        assert helpers.collect_hooks() == []

    def test_dedupes_urls_across_hooks(self, monkeypatch):
        wikitext = """
<!--Hooks-->
* ... that [[Alpha]] did a thing?
* ... that [[Alpha]] did another thing?
* ... that [[Beta]] exists?
<!--HooksEnd-->
"""
        monkeypatch.setattr(helpers, "fetch_wikitext", lambda: wikitext)
        hooks = helpers.collect_hooks()
        assert len(hooks) == 2
        assert hooks[0]["urls"][0] == "https://en.wikipedia.org/wiki/Alpha"
        assert hooks[1]["urls"][0] == "https://en.wikipedia.org/wiki/Beta"

    def test_excludes_urls_from_previous_collections(self, monkeypatch):
        wikitext = """
<!--Hooks-->
* ... that [[Alpha]] did a thing?
* ... that [[Beta]] exists?
<!--HooksEnd-->
"""
        monkeypatch.setattr(helpers, "fetch_wikitext", lambda: wikitext)
        hooks = helpers.collect_hooks(exclude_urls={"https://en.wikipedia.org/wiki/Alpha"})
        assert len(hooks) == 1
        assert hooks[0]["urls"][0] == "https://en.wikipedia.org/wiki/Beta"

    def test_excludes_hook_matching_encoded_exclude_url(self, monkeypatch):
        wikitext = """\
<!--Hooks-->
* ... that '''[[C++ (programming language)|C++]]''' is interesting?
<!--HooksEnd-->"""
        monkeypatch.setattr(helpers, "fetch_wikitext", lambda: wikitext)
        encoded_url = "https://en.wikipedia.org/wiki/C%2B%2B_%28programming_language%29"
        hooks = helpers.collect_hooks(exclude_urls={encoded_url})
        assert hooks == []

    def test_excludes_hook_matching_legacy_unencoded_exclude_url(self, monkeypatch):
        wikitext = """\
<!--Hooks-->
* ... that '''[[C++ (programming language)|C++]]''' is interesting?
<!--HooksEnd-->"""
        monkeypatch.setattr(helpers, "fetch_wikitext", lambda: wikitext)
        # Old-format URL as stored by the buggy pre-fix code
        legacy_url = "https://en.wikipedia.org/wiki/C++_(programming_language)"
        hooks = helpers.collect_hooks(exclude_urls={legacy_url})
        assert hooks == []


class TestStoredUrls:
    def test_collects_urls_from_store(self):
        store = {
            "collections": [
                {"date": "2026-02-23", "hooks": [{"urls": ["https://en.wikipedia.org/wiki/One"]}]},
                {"date": "2026-02-24", "hooks": [{"urls": ["https://en.wikipedia.org/wiki/Two"]}]},
            ]
        }
        assert helpers.stored_urls(store) == {
            "https://en.wikipedia.org/wiki/One",
            "https://en.wikipedia.org/wiki/Two",
        }

    def test_includes_urls_from_seen_urls_key(self):
        store = {
            "seen_urls": ["https://en.wikipedia.org/wiki/Trimmed_Article"],
            "collections": [],
        }
        assert "https://en.wikipedia.org/wiki/Trimmed_Article" in helpers.stored_urls(store)

    def test_null_hooks_in_collection_returns_empty(self):
        # A collection whose "hooks" key is null must not crash stored_urls.
        # This can arise from manual edits or future schema changes.
        store = {
            "collections": [{"date": "2026-02-24", "hooks": None}],
        }
        assert helpers.stored_urls(store) == set()

    def test_null_urls_in_hook_skips_hook(self):
        # A hook whose "urls" key is null must not crash stored_urls.
        store = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "hooks": [
                        {"text": "fine hook", "urls": ["https://en.wikipedia.org/wiki/Fine"], "returned": False},
                        {"text": "bad hook",  "urls": None, "returned": False},
                    ],
                }
            ]
        }
        urls = helpers.stored_urls(store)
        assert "https://en.wikipedia.org/wiki/Fine" in urls
        # bad hook contributed nothing — no crash
        assert len(urls) == 1


class TestStoreHelpers:
    def test_load_store_missing_returns_default(self, monkeypatch, tmp_path):
        monkeypatch.setattr(helpers, "DATA_PATH", tmp_path / "dyk.json")
        assert helpers.load_store() == {"collections": []}

    def test_load_store_bad_json_returns_default(self, monkeypatch, tmp_path):
        data_path = tmp_path / "dyk.json"
        data_path.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        assert helpers.load_store() == {"collections": []}

    def test_load_store_oserror_returns_default(self, monkeypatch, tmp_path):
        data_path = tmp_path / "dyk.json"
        data_path.write_text("{}", encoding="utf-8")
        data_path.chmod(0o000)
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        assert helpers.load_store() == {"collections": []}
        data_path.chmod(0o644)  # cleanup so tmp_path removal works

    def test_load_store_non_dict_json_returns_default(self, monkeypatch, tmp_path):
        data_path = tmp_path / "dyk.json"
        data_path.write_text("[1, 2, 3]", encoding="utf-8")
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        assert helpers.load_store() == {"collections": []}

    def test_load_store_dict_without_collections_returns_default(self, monkeypatch, tmp_path):
        data_path = tmp_path / "dyk.json"
        data_path.write_text('{"other_key": 1}', encoding="utf-8")
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        assert helpers.load_store() == {"collections": []}

    def test_load_store_null_collections_returns_default(self, monkeypatch, tmp_path):
        # {"collections": null} passes the "key exists" check but must be
        # treated as invalid — null is not a usable collection list.
        data_path = tmp_path / "dyk.json"
        data_path.write_text('{"collections": null}', encoding="utf-8")
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        assert helpers.load_store() == {"collections": []}

    def test_load_store_null_seen_urls_is_stripped(self, monkeypatch, tmp_path):
        # {"collections": [], "seen_urls": null} — collections are valid but
        # seen_urls is corrupted; strip it to [] rather than discarding the cache.
        data_path = tmp_path / "dyk.json"
        data_path.write_text('{"collections": [], "seen_urls": null}', encoding="utf-8")
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        result = helpers.load_store()
        assert result["collections"] == []
        assert result.get("seen_urls") == []

    def test_trim_store_keeps_max_days(self):
        store = {
            "collections": [
                {"date": f"2026-02-{i:02d}", "hooks": []}
                for i in range(15, 30)  # 15 collections to exceed MAX_COLLECTIONS=10
            ]
        }
        helpers.trim_store(store)
        # Should keep only the last 10
        assert len(store["collections"]) == 10
        assert store["collections"][0]["date"] == "2026-02-20"
        assert store["collections"][-1]["date"] == "2026-02-29"


class TestSaveStore:
    def test_writes_json_utf8(self, monkeypatch, tmp_path):
        data_path = tmp_path / "nested" / "dyk.json"
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)

        store = {"collections": [{"date": "2026-02-24", "hooks": [{"text": "caf\u00e9", "urls": [], "returned": False}]}]}
        helpers.save_store(store)

        loaded = json.loads(data_path.read_text(encoding="utf-8"))
        assert loaded == store

    def test_save_is_atomic(self, monkeypatch, tmp_path):
        """save_store should write atomically so a crash can't corrupt the cache."""
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)

        # Seed a valid cache on disk
        original = {"collections": [{"date": "2026-01-01", "hooks": []}]}
        data_path.write_text(json.dumps(original), encoding="utf-8")

        # Patch rename to explode, simulating a crash after temp write
        def boom(self_path, target):
            raise OSError("simulated crash")

        monkeypatch.setattr(Path, "rename", boom)

        with pytest.raises(OSError):
            helpers.save_store({"collections": []})

        # Original file must still be intact
        assert json.loads(data_path.read_text(encoding="utf-8")) == original


class TestRefreshDue:
    def test_not_due_when_checked_recently(self):
        """5-minute cooldown on last_checked_at prevents hammering API."""
        now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)

        store = {
            "collections": [
                {
                    "date": "2026-02-28",
                    "fetched_at": "2026-02-27T00:00:00Z",  # 13h ago, should refresh
                    "hooks": [],
                }
            ],
            "last_checked_at": "2026-02-28T11:57:00Z",  # 3 min ago
        }
        # Cooldown wins: even though fetched_at is stale, we checked 3 min ago
        assert helpers.refresh_due(store, now) is False

    def test_due_after_cooldown_with_stale_fetch(self):
        """After 5-min cooldown, stale fetch triggers refresh."""
        now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)

        store = {
            "collections": [
                {
                    "date": "2026-02-28",
                    "fetched_at": "2026-02-27T00:00:00Z",  # 13h ago
                    "hooks": [],
                }
            ],
            "last_checked_at": "2026-02-28T11:50:00Z",  # 10 min ago
        }
        # After cooldown, stale fetch triggers refresh
        assert helpers.refresh_due(store, now) is True

    def test_not_due_when_fetched_recently(self):
        """12-hour REFRESH_INTERVAL still controls fetch freshness."""
        now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)

        store = {
            "collections": [
                {
                    "date": "2026-02-28",
                    "fetched_at": "2026-02-28T11:00:00Z",  # 1h ago
                    "hooks": [],
                }
            ],
            "last_checked_at": "2026-02-28T11:50:00Z",  # 10 min ago (cooldown passed)
        }
        # But fetched_at is recent (1h), so don't refresh
        assert helpers.refresh_due(store, now) is False

    def test_backward_compat_no_last_checked_at(self):
        """Missing last_checked_at behaves as never checked."""
        now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)

        store = {
            "collections": [
                {
                    "date": "2026-02-28",
                    "fetched_at": "2026-02-27T00:00:00Z",  # 13h ago
                    "hooks": [],
                }
            ]
            # No last_checked_at field
        }
        # Missing last_checked_at means we should refresh
        assert helpers.refresh_due(store, now) is True

    def test_due_when_no_collections(self):
        now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
        assert helpers.refresh_due({"collections": []}, now) is True
