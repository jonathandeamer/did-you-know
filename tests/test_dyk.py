#!/usr/bin/env python3
"""Unit tests for scripts/dyk.py.

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

import dyk as dyk


def make_store(date="2026-02-23", hooks=None, fetched_at="2026-02-23T00:00:00Z"):
    """Build a single-collection store dict for test fixtures."""
    return {
        "collections": [
            {
                "date": date,
                "fetched_at": fetched_at,
                "hooks": hooks if hooks is not None else [],
            }
        ]
    }


class TestNormalizeText:
    def test_basic_markup_cleanup(self):
        text = "The [[Albert Einstein|Einstein]] {{cite}} was ''brilliant''{{'s}}"
        assert dyk.normalize_text(text) == "The Einstein was brilliant's"

    def test_removes_pictured_parenthetical(self):
        text = "a bird (pictured here) in flight"
        assert dyk.normalize_text(text) == "a bird in flight"

    def test_collapses_whitespace(self):
        assert dyk.normalize_text("  hello   world  ") == "hello world"

    def test_decodes_html_entities(self):
        assert dyk.normalize_text("5&amp;10") == "5&10"
        assert dyk.normalize_text("A&ndash;B") == "A\u2013B"
        assert dyk.normalize_text("A&mdash;B") == "A\u2014B"

    def test_normalises_numeric_nbsp_entity(self):
        assert dyk.normalize_text("5&#160;10") == "5 10"

    def test_normalises_hex_nbsp_entity(self):
        assert dyk.normalize_text("5&#xA0;10") == "5 10"

    def test_collapses_consecutive_nbsp_entities(self):
        assert dyk.normalize_text("5&#160;&#160;10") == "5 10"

    def test_strips_leading_trailing_nbsp_entity(self):
        assert dyk.normalize_text("&#160;hello&#160;") == "hello"

    def test_wikilink_with_template_label_falls_back_to_title(self):
        # {{nowrap|...}} stripped from label leaves [[Title|]] which RE_LINK can't
        # match (empty capture group), so brackets leak into output. The fix must
        # resolve [[Title|]] → title text instead of leaving raw wikilink syntax.
        text = "the [[Lockheed U-2|{{nowrap|U-2}}]] spy aircraft"
        assert dyk.normalize_text(text) == "the Lockheed U-2 spy aircraft"

    def test_strips_inline_html_comment(self):
        # Raw <!-- ... --> comment tags survive normalize_text unchanged today.
        # They must be stripped before the text is displayed.
        text = "before Philippe <!-- deliberately not linked --> took photos"
        assert dyk.normalize_text(text) == "before Philippe took photos"

    def test_four_quote_run_no_stray_apostrophe(self):
        # ''''word''' is italic+bold run-together; stray ' must not survive.
        # Currently broken: normalize_text produces "'tissue" not "tissue".
        text = "''''[[Tissue (cloth)|tissue]]'''"
        assert dyk.normalize_text(text) == "tissue"

    def test_bold_wikilink_with_template_label(self):
        # Bold markers around [[Title|{{template}}]] must resolve to title text.
        text = "'''[[IG-11|{{nowrap|IG-11}}]]'''"
        assert dyk.normalize_text(text) == "IG-11"

    def test_html_entity_in_wikilink_label(self):
        # Numeric HTML entities inside a wikilink label must be decoded.
        text = "[[Konopi&#353;te|Konopi&#353;t&#283;]]"
        assert dyk.normalize_text(text) == "Konopiště"

    def test_strips_multiline_html_comment(self):
        # HTML comments that span newlines must also be stripped.
        text = "before <!-- editorial\nnote --> after"
        assert dyk.normalize_text(text) == "before after"

    def test_italic_pictured_parenthetical(self):
        # ''(pictured)'' must be stripped the same as plain (pictured).
        text = "a bird ''(pictured)'' in flight"
        assert dyk.normalize_text(text) == "a bird in flight"


class TestExtractHooksSection:
    def test_extracts_between_markers(self):
        source = "a<!--Hooks-->line1\nline2<!--HooksEnd-->z"
        assert dyk.extract_hooks_section(source) == "line1\nline2"

    def test_missing_markers_returns_none(self):
        assert dyk.extract_hooks_section("<!--Hooks-->missing end") is None
        assert dyk.extract_hooks_section("missing start<!--HooksEnd-->") is None

    def test_end_before_start_returns_none(self):
        assert dyk.extract_hooks_section("<!--HooksEnd--><!--Hooks-->") is None


class TestExtractHookTitles:
    def test_prefers_bold_link_titles(self):
        line = "'''[[First Article]]''' then [[Fallback]]"
        assert dyk.extract_hook_titles(line) == ["First Article"]

    def test_collects_multiple_bold_links(self):
        line = "'''[[One]]''' and '''[[Two|Two Label]]'''"
        assert dyk.extract_hook_titles(line) == ["One", "Two"]

    def test_falls_back_to_first_link(self):
        line = "See [[Albert Einstein]] and [[Isaac Newton]]"
        assert dyk.extract_hook_titles(line) == ["Albert Einstein"]

    def test_no_links_returns_empty(self):
        assert dyk.extract_hook_titles("plain text") == []


class TestTitleToUrl:
    def test_builds_expected_wikipedia_url(self):
        assert (
            dyk.title_to_url("Albert Einstein")
            == "https://en.wikipedia.org/wiki/Albert_Einstein"
        )

    def test_encodes_special_characters(self):
        url = dyk.title_to_url("C++ (programming language)")
        assert url == "https://en.wikipedia.org/wiki/C%2B%2B_%28programming_language%29"


class TestFormatHook:
    def test_returns_text_only_when_no_urls(self):
        assert dyk.format_hook({"text": "hello", "urls": []}) == "Did you know that hello?"

    def test_appends_first_url_when_available(self):
        hook = {"text": "hello", "urls": ["https://en.wikipedia.org/wiki/Hello", "https://example.com"]}
        assert dyk.format_hook(hook) == (
            "Did you know that hello?\n\n"
            "https://en.wikipedia.org/wiki/Hello\n"
            "https://example.com"
        )

    def test_decodes_encoded_url_for_display(self):
        hook = {"text": "C++ is interesting", "urls": ["https://en.wikipedia.org/wiki/C%2B%2B_%28programming_language%29"]}
        assert dyk.format_hook(hook) == (
            "Did you know that C++ is interesting?\n\n"
            "https://en.wikipedia.org/wiki/C++_(programming_language)"
        )


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

        monkeypatch.setattr(dyk.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())
        assert dyk.fetch_wikitext(retries=1, backoff=0) == "HOOKS"

    def test_retries_then_raises(self, monkeypatch):
        attempts = {"count": 0}

        def fail(*_args, **_kwargs):
            attempts["count"] += 1
            raise RuntimeError("boom")

        monkeypatch.setattr(dyk.urllib.request, "urlopen", fail)
        monkeypatch.setattr(dyk.time, "sleep", lambda _secs: None)

        with pytest.raises(RuntimeError, match="Failed to fetch Did You Know hooks"):
            dyk.fetch_wikitext(retries=3, backoff=0)
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

        monkeypatch.setattr(dyk, "fetch_wikitext", lambda: wikitext)
        hooks = dyk.collect_hooks()

        assert len(hooks) == 2
        assert hooks[0]["text"] == "Alpha did a thing?"
        assert hooks[0]["urls"] == ["https://en.wikipedia.org/wiki/Alpha"]
        assert hooks[0]["returned"] is False
        assert hooks[1]["text"] == "B worked with Gamma?"
        assert hooks[1]["urls"][0] == "https://en.wikipedia.org/wiki/Beta"

    def test_returns_empty_when_section_missing(self, monkeypatch):
        monkeypatch.setattr(dyk, "fetch_wikitext", lambda: "no markers")
        assert dyk.collect_hooks() == []

    def test_dedupes_urls_across_hooks(self, monkeypatch):
        wikitext = """
<!--Hooks-->
* ... that [[Alpha]] did a thing?
* ... that [[Alpha]] did another thing?
* ... that [[Beta]] exists?
<!--HooksEnd-->
"""
        monkeypatch.setattr(dyk, "fetch_wikitext", lambda: wikitext)
        hooks = dyk.collect_hooks()
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
        monkeypatch.setattr(dyk, "fetch_wikitext", lambda: wikitext)
        hooks = dyk.collect_hooks(exclude_urls={"https://en.wikipedia.org/wiki/Alpha"})
        assert len(hooks) == 1
        assert hooks[0]["urls"][0] == "https://en.wikipedia.org/wiki/Beta"

    def test_excludes_hook_matching_encoded_exclude_url(self, monkeypatch):
        wikitext = """\
<!--Hooks-->
* ... that '''[[C++ (programming language)|C++]]''' is interesting?
<!--HooksEnd-->"""
        monkeypatch.setattr(dyk, "fetch_wikitext", lambda: wikitext)
        encoded_url = "https://en.wikipedia.org/wiki/C%2B%2B_%28programming_language%29"
        hooks = dyk.collect_hooks(exclude_urls={encoded_url})
        assert hooks == []

    def test_excludes_hook_matching_legacy_unencoded_exclude_url(self, monkeypatch):
        wikitext = """\
<!--Hooks-->
* ... that '''[[C++ (programming language)|C++]]''' is interesting?
<!--HooksEnd-->"""
        monkeypatch.setattr(dyk, "fetch_wikitext", lambda: wikitext)
        # Old-format URL as stored by the buggy pre-fix code
        legacy_url = "https://en.wikipedia.org/wiki/C++_(programming_language)"
        hooks = dyk.collect_hooks(exclude_urls={legacy_url})
        assert hooks == []


class TestStoredUrls:
    def test_collects_urls_from_store(self):
        store = {
            "collections": [
                {"date": "2026-02-23", "hooks": [{"urls": ["https://en.wikipedia.org/wiki/One"]}]},
                {"date": "2026-02-24", "hooks": [{"urls": ["https://en.wikipedia.org/wiki/Two"]}]},
            ]
        }
        assert dyk.stored_urls(store) == {
            "https://en.wikipedia.org/wiki/One",
            "https://en.wikipedia.org/wiki/Two",
        }

    def test_includes_urls_from_seen_urls_key(self):
        store = {
            "seen_urls": ["https://en.wikipedia.org/wiki/Trimmed_Article"],
            "collections": [],
        }
        assert "https://en.wikipedia.org/wiki/Trimmed_Article" in dyk.stored_urls(store)

    def test_null_hooks_in_collection_returns_empty(self):
        # A collection whose "hooks" key is null must not crash stored_urls.
        # This can arise from manual edits or future schema changes.
        store = {
            "collections": [{"date": "2026-02-24", "hooks": None}],
        }
        assert dyk.stored_urls(store) == set()

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
        urls = dyk.stored_urls(store)
        assert "https://en.wikipedia.org/wiki/Fine" in urls
        # bad hook contributed nothing — no crash
        assert len(urls) == 1


class TestStoreHelpers:
    def test_load_store_missing_returns_default(self, monkeypatch, tmp_path):
        monkeypatch.setattr(dyk, "DATA_PATH", tmp_path / "dyk.json")
        assert dyk.load_store() == {"collections": []}

    def test_load_store_bad_json_returns_default(self, monkeypatch, tmp_path):
        data_path = tmp_path / "dyk.json"
        data_path.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        assert dyk.load_store() == {"collections": []}

    def test_load_store_oserror_returns_default(self, monkeypatch, tmp_path):
        data_path = tmp_path / "dyk.json"
        data_path.write_text("{}", encoding="utf-8")
        data_path.chmod(0o000)
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        assert dyk.load_store() == {"collections": []}
        data_path.chmod(0o644)  # cleanup so tmp_path removal works

    def test_load_store_non_dict_json_returns_default(self, monkeypatch, tmp_path):
        data_path = tmp_path / "dyk.json"
        data_path.write_text("[1, 2, 3]", encoding="utf-8")
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        assert dyk.load_store() == {"collections": []}

    def test_load_store_dict_without_collections_returns_default(self, monkeypatch, tmp_path):
        data_path = tmp_path / "dyk.json"
        data_path.write_text('{"other_key": 1}', encoding="utf-8")
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        assert dyk.load_store() == {"collections": []}

    def test_load_store_null_collections_returns_default(self, monkeypatch, tmp_path):
        # {"collections": null} passes the "key exists" check but must be
        # treated as invalid — null is not a usable collection list.
        data_path = tmp_path / "dyk.json"
        data_path.write_text('{"collections": null}', encoding="utf-8")
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        assert dyk.load_store() == {"collections": []}

    def test_load_store_null_seen_urls_is_stripped(self, monkeypatch, tmp_path):
        # {"collections": [], "seen_urls": null} — collections are valid but
        # seen_urls is corrupted; strip it to [] rather than discarding the cache.
        data_path = tmp_path / "dyk.json"
        data_path.write_text('{"collections": [], "seen_urls": null}', encoding="utf-8")
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        result = dyk.load_store()
        assert result["collections"] == []
        assert result.get("seen_urls") == []

    def test_trim_store_keeps_max_days(self):
        store = {
            "collections": [
                {"date": f"2026-02-{i:02d}", "hooks": []}
                for i in range(15, 30)  # 15 collections to exceed MAX_COLLECTIONS=10
            ]
        }
        dyk.trim_store(store)
        # Should keep only the last 10
        assert len(store["collections"]) == 10
        assert store["collections"][0]["date"] == "2026-02-20"
        assert store["collections"][-1]["date"] == "2026-02-29"


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
        assert dyk.refresh_due(store, now) is False

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
        assert dyk.refresh_due(store, now) is True

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
        assert dyk.refresh_due(store, now) is False

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
        assert dyk.refresh_due(store, now) is True

    def test_due_when_no_collections(self):
        now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
        assert dyk.refresh_due({"collections": []}, now) is True


class TestEnsureToday:
    def test_noop_when_recent_fetch(self, monkeypatch):
        store = make_store(date="2026-02-24", fetched_at="2026-02-24T10:00:00Z")
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 20, 0, 0, tzinfo=timezone.utc))

        called = {"collect": 0}
        monkeypatch.setattr(dyk, "collect_hooks", lambda: called.__setitem__("collect", 1))
        dyk.ensure_fresh(store)
        assert called["collect"] == 0

    def test_appends_new_day_and_saves(self, monkeypatch):
        store = make_store()
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(
            dyk,
            "collect_hooks",
            lambda **_kwargs: [{"text": "t", "urls": [], "returned": False}],
        )

        dyk.ensure_fresh(store)
        assert store["collections"][-1]["date"] == "2026-02-24"
        assert store["collections"][-1]["fetched_at"] == "2026-02-24T12:00:00Z"
        assert store["collections"][-1]["hooks"][0]["text"] == "t"

    def test_fetch_failure_uses_existing_cache(self, monkeypatch):
        store = make_store()
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))

        def explode(**_kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(dyk, "collect_hooks", explode)

        dyk.ensure_fresh(store)
        assert len(store["collections"]) == 1

    def test_fetch_failure_without_cache_raises(self, monkeypatch):
        store = {"collections": []}
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))

        def explode(**_kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(dyk, "collect_hooks", explode)
        with pytest.raises(RuntimeError, match="network down"):
            dyk.ensure_fresh(store)

    def test_does_not_append_empty_collection(self, monkeypatch):
        store = make_store()
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(dyk, "collect_hooks", lambda **_kwargs: [])

        dyk.ensure_fresh(store)
        assert len(store["collections"]) == 1

    def test_sets_last_checked_at_on_success(self, monkeypatch):
        """ensure_fresh sets last_checked_at when new hooks are fetched."""
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(dyk, "now_utc", lambda: now)
        store = make_store()
        monkeypatch.setattr(
            dyk,
            "collect_hooks",
            lambda **_kwargs: [{"text": "new fact", "urls": [], "returned": False}],
        )

        dyk.ensure_fresh(store)
        assert store.get("last_checked_at") == "2026-02-24T12:00:00Z"
        assert store["collections"][-1]["date"] == "2026-02-24"

    def test_sets_last_checked_at_on_all_duplicates(self, monkeypatch):
        """ensure_fresh sets last_checked_at even when all hooks are duplicates."""
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(dyk, "now_utc", lambda: now)
        store = make_store()
        # collect_hooks returns empty (all duplicates)
        monkeypatch.setattr(dyk, "collect_hooks", lambda **_kwargs: [])

        dyk.ensure_fresh(store)
        assert store.get("last_checked_at") == "2026-02-24T12:00:00Z"
        # No new collection appended because all were duplicates
        assert len(store["collections"]) == 1

    def test_sets_last_checked_at_on_fetch_failure(self, monkeypatch):
        """ensure_fresh sets last_checked_at even on fetch failure with existing cache."""
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(dyk, "now_utc", lambda: now)
        store = make_store()

        def explode(**_kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(dyk, "collect_hooks", explode)
        dyk.ensure_fresh(store)
        # Even though fetch failed, last_checked_at should be set (fallback to cache)
        assert store.get("last_checked_at") == "2026-02-24T12:00:00Z"
        assert len(store["collections"]) == 1

    def test_persists_hook_urls_to_seen_urls(self, monkeypatch):
        """ensure_fresh must add new hook URLs to seen_urls so trim_store
        cannot cause them to be re-fetched on a later refresh."""
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(dyk, "now_utc", lambda: now)
        store = make_store()
        monkeypatch.setattr(
            dyk,
            "collect_hooks",
            lambda **_kwargs: [
                {"text": "fact", "urls": ["https://en.wikipedia.org/wiki/Article_A"], "returned": False}
            ],
        )

        dyk.ensure_fresh(store)

        assert "https://en.wikipedia.org/wiki/Article_A" in store.get("seen_urls", [])

    def test_seen_urls_survives_trim_store(self, monkeypatch):
        """URLs from a trimmed collection must still appear in stored_urls,
        preventing Wikipedia from re-serving a hook the user has already seen."""
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(dyk, "now_utc", lambda: now)

        # Fill store to MAX_COLLECTIONS with one hook each; all hooks served.
        # No seen_urls key — simulates a legacy cache written before that field
        # was introduced; ensure_fresh must backfill it before trimming.
        store = {
            "collections": [
                {
                    "date": f"2026-02-{i:02d}",
                    "fetched_at": f"2026-02-{i:02d}T12:00:00Z",
                    "hooks": [
                        {
                            "text": f"fact {i}",
                            "urls": [f"https://en.wikipedia.org/wiki/Article_{i}"],
                            "returned": True,
                        }
                    ],
                }
                for i in range(1, dyk.MAX_COLLECTIONS + 1)
            ],
        }

        # 11th fetch brings one genuinely new hook; this will trigger a trim.
        monkeypatch.setattr(
            dyk,
            "collect_hooks",
            lambda **_kwargs: [
                {
                    "text": "new fact",
                    "urls": ["https://en.wikipedia.org/wiki/Article_New"],
                    "returned": False,
                }
            ],
        )

        dyk.ensure_fresh(store)

        # trim_store removed collection 1 (Article_1), but seen_urls must
        # still include it so it can never be re-fetched.
        assert len(store["collections"]) == dyk.MAX_COLLECTIONS
        urls = dyk.stored_urls(store)
        assert "https://en.wikipedia.org/wiki/Article_1" in urls


class TestNextHook:
    def test_marks_first_unreturned(self, monkeypatch):
        store = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "hooks": [
                        {"text": "old", "urls": [], "returned": True},
                        {"text": "fresh", "urls": ["https://en.wikipedia.org/wiki/Fresh"], "returned": False},
                    ],
                }
            ]
        }

        result = dyk.next_hook(store)
        assert result == "Did you know that fresh?\n\nhttps://en.wikipedia.org/wiki/Fresh"
        assert store["collections"][0]["hooks"][1]["returned"] is True

    def test_returns_no_more_message(self):
        store = {"collections": [{"date": "2026-02-24", "hooks": [{"returned": True}]}]}
        result = dyk.next_hook(store)
        assert "No more facts to share today" in result

    def test_falls_back_to_older_collection_when_newest_exhausted(self):
        store = {
            "collections": [
                {"date": "2026-02-23", "hooks": [{"text": "old fact", "urls": [], "returned": False}]},
                {"date": "2026-02-24", "hooks": [{"text": "new fact", "urls": [], "returned": True}]},
            ]
        }
        result = dyk.next_hook(store)
        assert result == "Did you know that old fact?"


class TestSaveStore:
    def test_writes_json_utf8(self, monkeypatch, tmp_path):
        data_path = tmp_path / "nested" / "dyk.json"
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)

        store = {"collections": [{"date": "2026-02-24", "hooks": [{"text": "caf\u00e9", "urls": [], "returned": False}]}]}
        dyk.save_store(store)

        loaded = json.loads(data_path.read_text(encoding="utf-8"))
        assert loaded == store

    def test_save_is_atomic(self, monkeypatch, tmp_path):
        """save_store should write atomically so a crash can't corrupt the cache."""
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)

        # Seed a valid cache on disk
        original = {"collections": [{"date": "2026-01-01", "hooks": []}]}
        data_path.write_text(json.dumps(original), encoding="utf-8")

        # Patch rename to explode, simulating a crash after temp write
        def boom(self_path, target):
            raise OSError("simulated crash")

        monkeypatch.setattr(Path, "rename", boom)

        with pytest.raises(OSError):
            dyk.save_store({"collections": []})

        # Original file must still be intact
        assert json.loads(data_path.read_text(encoding="utf-8")) == original


class TestMain:
    def test_saves_store_after_fetch_failure_with_no_cache(self, monkeypatch, tmp_path, capsys):
        """last_checked_at must be persisted even when ensure_fresh raises (no cache).

        Without this, each invocation hammers the API with no cooldown when
        the network is down and there is no existing cache on disk.
        """
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(dyk, "now_utc", lambda: now)
        monkeypatch.setattr(dyk, "collect_hooks", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("network down")))

        result = dyk.main()

        assert result == 1
        # The store must have been saved so the cooldown is applied next run
        assert data_path.exists(), "store was never saved to disk"
        saved = json.loads(data_path.read_text(encoding="utf-8"))
        assert saved.get("last_checked_at") == "2026-02-24T12:00:00Z"

    def test_fallback_when_refresh_fails(self, monkeypatch, tmp_path, capsys):
        # Provide cached data so ensure_fresh can fall back to it
        monkeypatch.setattr(dyk, "DATA_PATH", tmp_path / "dyk.json")
        monkeypatch.setattr(
            dyk,
            "load_store",
            lambda: {
                "collections": [
                    {
                        "date": "2026-02-27",
                        "hooks": [
                            {"text": "cached fact", "urls": [], "returned": False}
                        ],
                    }
                ]
            },
        )

        def explode(_store):
            raise RuntimeError("network down")

        monkeypatch.setattr(dyk, "ensure_fresh", explode)
        result = dyk.main()
        captured = capsys.readouterr()
        assert result == 1
        assert "Something went wrong with the fact-fetching" in captured.out


class TestBackwardsCompatibility:
    """Pin the external-facing contract so breaking changes are caught explicitly."""

    # --- Cache file location ---

    def test_cache_path(self):
        """DATA_PATH must stay at ~/.openclaw/dyk-facts.json.

        Moving this silently abandons existing user caches.
        """
        assert dyk.DATA_PATH == Path.home() / ".openclaw" / "dyk-facts.json"

    # --- stdout contract ---

    def test_success_output_format(self, monkeypatch, tmp_path, capsys):
        """Success output must be: prefix + fact + '?' + blank line + URL."""
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(
            dyk,
            "collect_hooks",
            lambda **_kwargs: [{"text": "the shortest war lasted 38 minutes", "urls": ["https://en.wikipedia.org/wiki/Anglo-Zanzibar_War"], "returned": False}],
        )

        result = dyk.main()
        captured = capsys.readouterr()

        assert result == 0
        assert captured.out == (
            "Did you know that the shortest war lasted 38 minutes?\n"
            "\n"
            "https://en.wikipedia.org/wiki/Anglo-Zanzibar_War\n"
        )

    def test_exhausted_output_format(self, monkeypatch, tmp_path, capsys):
        """Exhausted output must be the exact no-facts message on its own line."""
        data_path = tmp_path / "dyk.json"
        store = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "fetched_at": "2026-02-24T12:00:00Z",
                    "hooks": [{"text": "fact", "urls": [], "returned": True}],
                }
            ],
            "last_checked_at": "2026-02-24T12:00:00Z",
        }
        data_path.write_text(json.dumps(store), encoding="utf-8")
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 12, 1, 0, tzinfo=timezone.utc))

        result = dyk.main()
        captured = capsys.readouterr()

        assert result == 0
        assert captured.out == "No more facts to share today; check back tomorrow!\n"

    def test_error_output_format(self, monkeypatch, tmp_path, capsys):
        """Error output must be the exact error message on its own line."""
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(dyk, "collect_hooks", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("network down")))

        result = dyk.main()
        captured = capsys.readouterr()

        assert result == 1
        assert captured.out == "Something went wrong with the fact-fetching; please try again later.\n"

    # --- Exit codes ---

    def test_exit_code_success(self, monkeypatch, tmp_path):
        """main() must return 0 on success."""
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(
            dyk,
            "collect_hooks",
            lambda **_kwargs: [{"text": "fact", "urls": [], "returned": False}],
        )
        assert dyk.main() == 0

    def test_exit_code_error(self, monkeypatch, tmp_path):
        """main() must return 1 on unrecoverable error."""
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(dyk, "collect_hooks", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
        assert dyk.main() == 1

    # --- Cache schema forwards-read ---

    def test_old_cache_without_last_checked_at_still_serves(self, monkeypatch, tmp_path, capsys):
        """A cache written before last_checked_at was introduced must still serve hooks."""
        data_path = tmp_path / "dyk.json"
        old_cache = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "fetched_at": "2026-02-24T12:00:00Z",
                    "hooks": [{"text": "old format fact", "urls": [], "returned": False}],
                }
            ]
            # No last_checked_at field — as written by older versions
        }
        data_path.write_text(json.dumps(old_cache), encoding="utf-8")
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 20, 0, 0, tzinfo=timezone.utc))

        result = dyk.main()
        captured = capsys.readouterr()

        assert result == 0
        assert captured.out.startswith("Did you know that old format fact?")

    def test_old_cache_without_seen_urls_backfills_on_first_refresh(
        self, monkeypatch, tmp_path, capsys
    ):
        """After upgrading from a version that never wrote seen_urls, the first
        refresh must backfill seen_urls from existing collections so that
        trim_store can never later re-expose those URLs.

        Contract: old cache → refresh → seen_urls contains all pre-existing URLs.
        """
        data_path = tmp_path / "dyk.json"
        # Old-format cache: no seen_urls, no last_checked_at, stale fetched_at
        old_cache = {
            "collections": [
                {
                    "date": "2026-02-23",
                    "fetched_at": "2026-02-23T00:00:00Z",
                    "hooks": [
                        {
                            "text": "old fact",
                            "urls": ["https://en.wikipedia.org/wiki/Old_Article"],
                            "returned": False,
                        }
                    ],
                }
            ]
            # No seen_urls, no last_checked_at — as written by older versions
        }
        data_path.write_text(json.dumps(old_cache), encoding="utf-8")
        monkeypatch.setattr(dyk, "DATA_PATH", data_path)
        monkeypatch.setattr(dyk, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(
            dyk,
            "collect_hooks",
            lambda **_kwargs: [
                {
                    "text": "new fact",
                    "urls": ["https://en.wikipedia.org/wiki/New_Article"],
                    "returned": False,
                }
            ],
        )

        result = dyk.main()

        assert result == 0
        saved = json.loads(data_path.read_text(encoding="utf-8"))
        # Pre-existing URL must be in seen_urls after the backfill
        assert "https://en.wikipedia.org/wiki/Old_Article" in saved.get("seen_urls", [])
        # Newly fetched URL must also be in seen_urls
        assert "https://en.wikipedia.org/wiki/New_Article" in saved.get("seen_urls", [])
