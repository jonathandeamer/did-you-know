#!/usr/bin/env python3
"""Tests for the autouse network guard in conftest.py.

The suite is entirely offline: every test that exercises a network path
monkeypatches urlopen itself. The guard turns a *missed* patch into a loud
failure instead of a silent live HTTP request.
"""
import sys
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import helpers
from conftest import NetworkBlocked


# A port nothing listens on, so an unguarded call fails fast and locally
# rather than reaching out to the internet.
DEAD_URL = "http://127.0.0.1:1/"


def test_urlopen_is_blocked_by_default():
    with pytest.raises(NetworkBlocked, match="network access is blocked"):
        urllib.request.urlopen(DEAD_URL)


def test_guard_names_the_offending_url():
    with pytest.raises(NetworkBlocked, match="127.0.0.1"):
        urllib.request.urlopen(DEAD_URL)


def test_guard_is_not_an_exception_subclass():
    """So application code that catches Exception cannot swallow it."""
    assert issubclass(NetworkBlocked, BaseException)
    assert not issubclass(NetworkBlocked, Exception)


def test_guard_escapes_the_retry_loop_without_sleeping(monkeypatch):
    """retry_with_backoff must not retry a blocked call.

    Retrying costs real wall-clock sleeps and buries the guard message under
    the application's own error, so the guard has to be unretryable.
    """
    slept = []
    monkeypatch.setattr(helpers.time, "sleep", lambda s: slept.append(s))
    with pytest.raises(NetworkBlocked):
        helpers.retry_with_backoff(lambda: urllib.request.urlopen(DEAD_URL))
    assert slept == []


def test_guard_survives_the_fetch_wikitext_error_wrapping():
    """fetch_wikitext() catches Exception; the guard must pass straight through."""
    with pytest.raises(NetworkBlocked, match="network access is blocked"):
        helpers.fetch_wikitext(retries=1)


def test_explicit_monkeypatch_still_overrides_the_guard(monkeypatch):
    """Tests that deliberately stub urlopen keep working."""
    sentinel = object()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: sentinel)
    assert urllib.request.urlopen(DEAD_URL) is sentinel
