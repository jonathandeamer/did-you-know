#!/usr/bin/env python3
"""Backwards-compatibility tests for the dyk.py shim.

These tests pin the external-facing contract (stdout format, exit codes, cache
schema) so that breaking changes are caught explicitly.  Unit tests for the
implementation modules live in test_helpers.py and test_serve_hook.py.

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
import serve_hook
import dyk  # shim — keeps dyk.main() working in backwards-compat tests


class TestBackwardsCompatibility:
    """Pin the external-facing contract so breaking changes are caught explicitly."""

    # --- Cache file location ---

    def test_cache_path(self):
        """DATA_PATH must stay at ~/.openclaw/dyk-facts.json.

        Moving this silently abandons existing user caches.
        """
        assert helpers.DATA_PATH == Path.home() / ".openclaw" / "dyk-facts.json"

    # --- stdout contract ---

    def test_success_output_format(self, monkeypatch, tmp_path, capsys):
        """Success output must be: prefix + fact + '?' + blank line + URL."""
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(
            serve_hook,
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
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 12, 1, 0, tzinfo=timezone.utc))

        result = dyk.main()
        captured = capsys.readouterr()

        assert result == 0
        assert captured.out == "No more facts to share today; check back tomorrow!\n"

    def test_error_output_format(self, monkeypatch, tmp_path, capsys):
        """Error output must be the exact error message on its own line."""
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(serve_hook, "collect_hooks", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("network down")))

        result = dyk.main()
        captured = capsys.readouterr()

        assert result == 1
        assert captured.out == "Something went wrong with the fact-fetching; please try again later.\n"

    # --- Exit codes ---

    def test_exit_code_success(self, monkeypatch, tmp_path):
        """main() must return 0 on success."""
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(
            serve_hook,
            "collect_hooks",
            lambda **_kwargs: [{"text": "fact", "urls": [], "returned": False}],
        )
        assert dyk.main() == 0

    def test_exit_code_error(self, monkeypatch, tmp_path):
        """main() must return 1 on unrecoverable error."""
        data_path = tmp_path / "dyk.json"
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(serve_hook, "collect_hooks", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
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
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 20, 0, 0, tzinfo=timezone.utc))

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
        monkeypatch.setattr(helpers, "DATA_PATH", data_path)
        monkeypatch.setattr(serve_hook, "now_utc", lambda: datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc))
        monkeypatch.setattr(
            serve_hook,
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
