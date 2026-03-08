#!/usr/bin/env python3
"""Unit tests for scripts/serve_hook.py.

Run with: python3 -m pytest tests/ -v
Requires: pip install pytest
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import helpers
import serve_hook


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


class TestFormatHook:
    def test_returns_text_only_when_no_urls(self):
        assert serve_hook.format_hook({"text": "hello", "urls": []}) == "Did you know that hello?"

    def test_appends_first_url_when_available(self):
        hook = {"text": "hello", "urls": ["https://en.wikipedia.org/wiki/Hello", "https://example.com"]}
        assert serve_hook.format_hook(hook) == (
            "Did you know that hello?\n\n"
            "https://en.wikipedia.org/wiki/Hello\n"
            "https://example.com"
        )

    def test_decodes_encoded_url_for_display(self):
        hook = {"text": "C++ is interesting", "urls": ["https://en.wikipedia.org/wiki/C%2B%2B_%28programming_language%29"]}
        assert serve_hook.format_hook(hook) == (
            "Did you know that C++ is interesting?\n\n"
            "https://en.wikipedia.org/wiki/C++_(programming_language)"
        )


class TestEnsureFresh:
    def test_noop_when_recent_fetch(self, monkeypatch):
        store = make_store(date="2026-02-24", fetched_at="2026-02-24T10:00:00Z")
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 20, 0, 0, tzinfo=timezone.utc))

        called = {"collect": 0}
        monkeypatch.setattr(serve_hook, "collect_hooks", lambda: called.__setitem__("collect", 1))
        serve_hook.ensure_fresh(store)
        assert called["collect"] == 0

    def test_appends_new_day_and_saves(self, monkeypatch):
        store = make_store()
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(
            serve_hook,
            "collect_hooks",
            lambda **_kwargs: [{"text": "t", "urls": [], "returned": False}],
        )

        serve_hook.ensure_fresh(store)
        assert store["collections"][-1]["date"] == "2026-02-24"
        assert store["collections"][-1]["fetched_at"] == "2026-02-24T12:00:00Z"
        assert store["collections"][-1]["hooks"][0]["text"] == "t"

    def test_fetch_failure_uses_existing_cache(self, monkeypatch):
        store = make_store()
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))

        def explode(**_kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(serve_hook, "collect_hooks", explode)

        serve_hook.ensure_fresh(store)
        assert len(store["collections"]) == 1

    def test_fetch_failure_without_cache_raises(self, monkeypatch):
        store = {"collections": []}
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))

        def explode(**_kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(serve_hook, "collect_hooks", explode)
        with pytest.raises(RuntimeError, match="network down"):
            serve_hook.ensure_fresh(store)

    def test_does_not_append_empty_collection(self, monkeypatch):
        store = make_store()
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(serve_hook, "collect_hooks", lambda **_kwargs: [])

        serve_hook.ensure_fresh(store)
        assert len(store["collections"]) == 1

    def test_sets_last_checked_at_on_success(self, monkeypatch):
        """ensure_fresh sets last_checked_at when new hooks are fetched."""
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: now)
        store = make_store()
        monkeypatch.setattr(
            serve_hook,
            "collect_hooks",
            lambda **_kwargs: [{"text": "new fact", "urls": [], "returned": False}],
        )

        serve_hook.ensure_fresh(store)
        assert store.get("last_checked_at") == "2026-02-24T12:00:00Z"
        assert store["collections"][-1]["date"] == "2026-02-24"

    def test_sets_last_checked_at_on_all_duplicates(self, monkeypatch):
        """ensure_fresh sets last_checked_at even when all hooks are duplicates."""
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: now)
        store = make_store()
        # collect_hooks returns empty (all duplicates)
        monkeypatch.setattr(serve_hook, "collect_hooks", lambda **_kwargs: [])

        serve_hook.ensure_fresh(store)
        assert store.get("last_checked_at") == "2026-02-24T12:00:00Z"
        # No new collection appended because all were duplicates
        assert len(store["collections"]) == 1

    def test_sets_last_checked_at_on_fetch_failure(self, monkeypatch):
        """ensure_fresh sets last_checked_at even on fetch failure with existing cache."""
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: now)
        store = make_store()

        def explode(**_kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(serve_hook, "collect_hooks", explode)
        serve_hook.ensure_fresh(store)
        # Even though fetch failed, last_checked_at should be set (fallback to cache)
        assert store.get("last_checked_at") == "2026-02-24T12:00:00Z"
        assert len(store["collections"]) == 1

    def test_persists_hook_urls_to_seen_urls(self, monkeypatch):
        """ensure_fresh must add new hook URLs to seen_urls so trim_store
        cannot cause them to be re-fetched on a later refresh."""
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: now)
        store = make_store()
        monkeypatch.setattr(
            serve_hook,
            "collect_hooks",
            lambda **_kwargs: [
                {"text": "fact", "urls": ["https://en.wikipedia.org/wiki/Article_A"], "returned": False}
            ],
        )

        serve_hook.ensure_fresh(store)

        assert "https://en.wikipedia.org/wiki/Article_A" in store.get("seen_urls", [])

    def test_seen_urls_survives_trim_store(self, monkeypatch):
        """URLs from an expired collection must still appear in stored_urls,
        preventing Wikipedia from re-serving a hook the user has already seen."""
        now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: now)

        # One expired collection (9 days ago — will be trimmed) and one recent.
        # No seen_urls key — simulates a legacy cache; ensure_fresh must backfill.
        store = {
            "collections": [
                {
                    "date": "2026-03-01",
                    "fetched_at": "2026-03-01T12:00:00Z",  # 9 days ago — > MAX_HOOK_AGE_DAYS (8), expired
                    "hooks": [
                        {
                            "text": "old fact",
                            "urls": ["https://en.wikipedia.org/wiki/Article_Old"],
                            "returned": True,
                        }
                    ],
                },
                {
                    "date": "2026-03-09",
                    "fetched_at": "2026-03-09T12:00:00Z",  # 1 day ago — < MAX_HOOK_AGE_DAYS (8), kept
                    "hooks": [
                        {
                            "text": "recent fact",
                            "urls": ["https://en.wikipedia.org/wiki/Article_Recent"],
                            "returned": True,
                        }
                    ],
                },
            ],
        }

        # New fetch brings a genuinely new hook, triggering a trim.
        monkeypatch.setattr(
            serve_hook,
            "collect_hooks",
            lambda **_kwargs: [
                {
                    "text": "new fact",
                    "urls": ["https://en.wikipedia.org/wiki/Article_New"],
                    "returned": False,
                }
            ],
        )

        serve_hook.ensure_fresh(store)

        # Expired collection was trimmed; recent collection was kept.
        assert all(c["fetched_at"] != "2026-03-01T12:00:00Z" for c in store["collections"])
        assert any(c["fetched_at"] == "2026-03-09T12:00:00Z" for c in store["collections"])
        # Expired collection's URL must still be in seen_urls.
        urls = helpers.stored_urls(store)
        assert "https://en.wikipedia.org/wiki/Article_Old" in urls


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

        result = serve_hook.next_hook(store)
        assert result == "Did you know that fresh?\n\nhttps://en.wikipedia.org/wiki/Fresh"
        assert store["collections"][0]["hooks"][1]["returned"] is True

    def test_returns_no_more_message(self):
        store = {"collections": [{"date": "2026-02-24", "hooks": [{"returned": True}]}]}
        result = serve_hook.next_hook(store)
        assert "No more facts to share today" in result

    def test_falls_back_to_older_collection_when_newest_exhausted(self):
        store = {
            "collections": [
                {"date": "2026-02-23", "hooks": [{"text": "old fact", "urls": [], "returned": False}]},
                {"date": "2026-02-24", "hooks": [{"text": "new fact", "urls": [], "returned": True}]},
            ]
        }
        result = serve_hook.next_hook(store)
        assert result == "Did you know that old fact?"

    def test_empty_collections_returns_no_more_message(self):
        result = serve_hook.next_hook({"collections": []})
        assert "No more facts to share today" in result

    def test_serves_highest_scored_hook_first(self):
        prefs = {"domain": {"science": 1}, "tone": {}}
        store = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "hooks": [
                        {"text": "history fact", "urls": [], "returned": False,
                         "tags": {"domain": ["history"], "tone": "straight", "low_confidence": False}},
                        {"text": "science fact", "urls": [], "returned": False,
                         "tags": {"domain": ["science"], "tone": "straight", "low_confidence": False}},
                    ],
                }
            ]
        }
        result = serve_hook.next_hook(store, prefs)
        assert "science fact" in result

    def test_tiebreak_most_recent_collection_first(self):
        store = {
            "collections": [
                {"date": "2026-02-23", "fetched_at": "2026-02-23T12:00:00Z",
                 "hooks": [{"text": "older fact", "urls": [], "returned": False, "tags": None}]},
                {"date": "2026-02-24", "fetched_at": "2026-02-24T12:00:00Z",
                 "hooks": [{"text": "newer fact", "urls": [], "returned": False, "tags": None}]},
            ]
        }
        result = serve_hook.next_hook(store, {})
        assert "newer fact" in result

    def test_tiebreak_within_same_collection_is_random(self):
        store = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "hooks": [
                        {"text": "hook A", "urls": [], "returned": False, "tags": None},
                        {"text": "hook B", "urls": [], "returned": False, "tags": None},
                    ],
                }
            ]
        }
        seen = set()
        for _ in range(50):
            for h in store["collections"][0]["hooks"]:
                h["returned"] = False
            result = serve_hook.next_hook(store, {})
            seen.add("A" if "hook A" in result else "B")
        assert seen == {"A", "B"}

    def test_tiebreak_shortest_text_before_random(self):
        """When score and collection tie, the hook with fewer characters is served."""
        store = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "hooks": [
                        {"text": "a longer hook text here", "urls": [], "returned": False, "tags": None},
                        {"text": "short hook", "urls": [], "returned": False, "tags": None},
                    ],
                }
            ]
        }
        result = serve_hook.next_hook(store, {})
        assert "short hook" in result

    def test_negative_scored_hooks_still_served(self):
        prefs = {"domain": {"history": -1}, "tone": {}}
        store = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "hooks": [
                        {"text": "history fact", "urls": [], "returned": False,
                         "tags": {"domain": ["history"], "tone": "straight", "low_confidence": False}},
                    ],
                }
            ]
        }
        result = serve_hook.next_hook(store, prefs)
        assert "history fact" in result

    def test_score_beats_recency_across_collections(self):
        prefs = {"domain": {"science": 1}, "tone": {}}
        store = {
            "collections": [
                {
                    "date": "2026-02-23",
                    "hooks": [
                        {"text": "science fact", "urls": [], "returned": False,
                         "tags": {"domain": ["science"], "tone": "straight", "low_confidence": False}},
                    ],
                },
                {
                    "date": "2026-02-24",
                    "hooks": [
                        {"text": "history fact", "urls": [], "returned": False,
                         "tags": {"domain": ["history"], "tone": "straight", "low_confidence": False}},
                    ],
                },
            ]
        }
        result = serve_hook.next_hook(store, prefs)
        assert "science fact" in result

    def test_freshness_bonus_passed_to_newest_collection(self, monkeypatch):
        """next_hook passes freshness_bonus=0.1 for hooks in the most recent collection only."""
        calls = []
        original = helpers.score_hook

        def recording(hook, prefs, freshness_bonus=0.0, prev_domains=None):
            calls.append(freshness_bonus)
            return original(hook, prefs, freshness_bonus, prev_domains)

        monkeypatch.setattr(serve_hook, "score_hook", recording)
        store = {
            "collections": [
                {"date": "2026-02-23", "hooks": [{"text": "old", "urls": [], "returned": False, "tags": None}]},
                {"date": "2026-02-24", "hooks": [{"text": "new", "urls": [], "returned": False, "tags": None}]},
            ]
        }
        serve_hook.next_hook(store, {})
        assert 0.1 in calls
        assert 0.0 in calls

    def test_returned_at_written_when_hook_served(self, monkeypatch):
        """next_hook writes returned_at timestamp to the served hook."""
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: now)
        store = {
            "collections": [
                {"date": "2026-02-24", "hooks": [{"text": "fact", "urls": [], "returned": False, "tags": None}]}
            ]
        }
        serve_hook.next_hook(store, {})
        assert store["collections"][0]["hooks"][0]["returned_at"] == "2026-02-24T12:00:00Z"

    def test_domain_penalty_applied_to_previously_served_domain(self, monkeypatch):
        """Hooks sharing the last served domain incur a flat −0.2 diversity penalty per tag."""
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: now)
        prefs = {"domain": {"science": 1, "history": 1}, "tone": {}}
        store = {
            "collections": [
                {
                    "date": "2026-02-24",
                    "hooks": [
                        # Previously served science hook (returned_at used by last_served_domains)
                        {"text": "old science", "urls": [], "returned": True,
                         "returned_at": "2026-02-24T11:00:00Z",
                         "tags": {"domain": ["science"], "tone": "straight", "low_confidence": False}},
                        # Science hook: pref 1 − 0.2 (diversity penalty) = 0.8
                        {"text": "new science", "urls": [], "returned": False,
                         "tags": {"domain": ["science"], "tone": "straight", "low_confidence": False}},
                        # History hook: pref 1 + 0 (no penalty) = 1.0
                        {"text": "new history", "urls": [], "returned": False,
                         "tags": {"domain": ["history"], "tone": "straight", "low_confidence": False}},
                    ],
                }
            ]
        }
        result = serve_hook.next_hook(store, prefs)
        assert "new history" in result


class TestMain:
    def test_saves_store_after_fetch_failure_with_no_cache(self, monkeypatch, tmp_path, capsys):
        """last_checked_at must be persisted even when ensure_fresh raises (no cache).

        Without this, each invocation hammers the API with no cooldown when
        the network is down and there is no existing cache on disk.
        """
        import json
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        now = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: now)
        monkeypatch.setattr(serve_hook, "collect_hooks", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("network down")))

        result = serve_hook.main()

        assert result == 1
        # The store must have been saved so the cooldown is applied next run
        assert data_path.exists(), "store was never saved to disk"
        saved = json.loads(data_path.read_text(encoding="utf-8"))
        assert saved.get("last_checked_at") == "2026-02-24T12:00:00Z"

    def test_fallback_when_refresh_fails(self, monkeypatch, tmp_path, capsys):
        # Provide cached data so ensure_fresh can fall back to it
        monkeypatch.setattr(helpers, "DATA_PATH", tmp_path / "dyk.json")
        monkeypatch.setattr(
            serve_hook,
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

        monkeypatch.setattr(serve_hook, "ensure_fresh", explode)
        result = serve_hook.main()
        captured = capsys.readouterr()
        assert result == 1
        assert "Something went wrong with the fact-fetching" in captured.out
