#!/usr/bin/env python3
"""Shared pytest configuration.

Blocks real network access for the whole suite. Every test that exercises a
network path stubs urlopen itself; without this guard a stub aimed at the
wrong module (a patch target that drifted after code moved) silently falls
through to live HTTP, and the test passes against real Wikipedia data
instead of failing. Runtime is the only tell.
"""
import urllib.request

import pytest


class NetworkBlocked(BaseException):
    """Raised when a test attempts real network I/O.

    Deliberately derives from BaseException, not Exception, so that
    application error handling cannot swallow it — helpers.retry_with_backoff
    would otherwise retry it through several seconds of real sleeps, and
    fetch_wikitext would rewrap it as its own generic failure, hiding the
    fact that a test escaped to the network. pytest's own control-flow
    exceptions use the same trick.
    """


def _blocked_urlopen(url, *_args, **_kwargs):
    target = getattr(url, "full_url", url)
    raise NetworkBlocked(
        f"network access is blocked in tests: attempted to open {target!r}. "
        "A test reached the real network. This usually means a monkeypatch "
        "target no longer matches where the name is resolved — patch the "
        "module that actually looks the name up, not the one that used to."
    )


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Fail loudly on any unstubbed network call.

    Applied before each test, so a test's own monkeypatch of urlopen still
    takes precedence — deliberate stubs keep working.
    """
    monkeypatch.setattr(urllib.request, "urlopen", _blocked_urlopen)
