#!/usr/bin/env python3
"""Shared utilities for DYK scripts: parsing, caching, API, and timestamps."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import html
import json
import re
from pathlib import Path
import sys
import time
from typing import TypeVar
import urllib.parse
import urllib.request

_T = TypeVar("_T")

VERSION = "0.1.1"

# MediaWiki API endpoint for the DYK template wikitext.
API_URL = (
    "https://en.wikipedia.org/w/api.php"
    "?action=query&format=json&prop=revisions&titles=Template:Did_you_know"
    "&rvprop=content&rvslots=main"
)

# Wikitext parsing helpers.
RE_HOOK_LINE = re.compile(r"^\*\s*\.{3}\s*that\s+(.*)$", re.IGNORECASE)
RE_LINK = re.compile(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]")
RE_BOLD_SECTION = re.compile(r"'''(.*?)'''", re.DOTALL)

# On-disk cache location and retention.
DATA_PATH = Path.home() / ".openclaw" / "dyk-facts.json"
MAX_COLLECTIONS = 10

# Refresh schedule: how often to hit the API.
REFRESH_INTERVAL = 12 * 60 * 60  # DYK sets rotate every 12–24 h
CHECK_COOLDOWN = 5 * 60  # min seconds between API calls regardless of fetch status

def title_to_url(title: str) -> str:
    """Convert a Wikipedia article title into a percent-encoded URL.

    Note: titles taken verbatim from mid-sentence wikilinks may start with a
    lowercase letter (e.g. 'net-filter coffee' instead of 'Net-filter coffee').
    The correct fix is to resolve display titles via the MediaWiki API, but that
    requires extra API calls. Tracked in:
    https://github.com/jonathandeamer/did-you-know/issues/1
    """
    return (
        "https://en.wikipedia.org/wiki/"
        + urllib.parse.quote(title.replace(" ", "_"), safe="/:")  # / for subpages, : for namespaces
    )


def retry_with_backoff(func: Callable[[], _T], retries: int = 3, backoff: float = 2.0) -> _T:
    """Retry a function with exponential backoff between attempts."""
    last_exc = None
    for attempt in range(retries):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                delay = backoff * (2 ** attempt)
                print(
                    f"Attempt {attempt + 1} failed ({exc}), retrying in {delay}s...",
                    file=sys.stderr,
                )
                time.sleep(delay)
    raise RuntimeError(f"Failed after {retries} attempts: {last_exc}")


def now_utc() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def to_iso_z(ts: datetime) -> str:
    """Serialize a datetime as ISO 8601 with a trailing Z."""
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(ts: str) -> datetime | None:
    """Parse ISO timestamps, accepting a trailing Z."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_text(text: str) -> str:
    """Strip wiki markup and normalize whitespace for display."""
    possessive_token = "__DYK_POSSESSIVE__"
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = text.replace("&nbsp;", " ")  # before whitespace-collapse; html.unescape gives \xa0 which \s+ misses
    text = text.replace("{{'s}}", possessive_token)
    while "{{" in text:
        cleaned = re.sub(r"\{\{[^{}]*\}\}", "", text)
        if cleaned == text:
            break
        text = cleaned
    text = re.sub(r"\[\[([^|\]]+)\|\s*\]\]", r"[[\1]]", text)
    text = re.sub(r"'{2,}", "", text)
    text = text.replace(possessive_token, "'s")

    def replace_link(match: re.Match) -> str:
        title = match.group(1).strip()
        label = match.group(2).strip() if match.group(2) else title
        return label

    text = RE_LINK.sub(replace_link, text)
    text = re.sub(r"\s*\([^)]*pictured[^)]*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    text = html.unescape(text)
    text = text.replace("\xa0", " ")  # normalise non-breaking spaces from &#160; etc.
    text = re.sub(r" +", " ", text).strip()  # collapse any runs created by the above
    return text


def extract_hooks_section(wikitext: str) -> str | None:
    """Return the hooks section contents or None if markers are missing."""
    start = wikitext.find("<!--Hooks-->")
    end = wikitext.find("<!--HooksEnd-->")
    if start == -1 or end == -1 or end <= start:
        return None
    return wikitext[start + len("<!--Hooks-->") : end]


def extract_hook_titles(line: str) -> list[str]:
    """Prefer bold-linked titles; otherwise fall back to the first link."""
    titles = []
    for segment in RE_BOLD_SECTION.findall(line):
        for match in RE_LINK.finditer(segment):
            titles.append(match.group(1).strip())
    if titles:
        return titles
    match = RE_LINK.search(line)
    if not match:
        return []
    return [match.group(1).strip()]


def fetch_wikitext(retries: int = 3, backoff: float = 2.0) -> str:
    """Fetch the DYK template wikitext with simple retry/backoff."""
    def _fetch():
        req = urllib.request.Request(
            API_URL,
            headers={
                "User-Agent": f"did-you-know/{VERSION} (https://en.wikipedia.org/wiki/User:Jonathan_Deamer)"
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            revisions = page.get("revisions", [])
            if revisions:
                return revisions[0]["slots"]["main"]["*"]
        raise RuntimeError("No wikitext found in API response")

    try:
        return retry_with_backoff(_fetch, retries=retries, backoff=backoff)
    except Exception as exc:
        raise RuntimeError("Failed to fetch Did You Know hooks") from exc


def collect_hooks(exclude_urls: set[str] | None = None) -> list[dict]:
    """Fetch, parse, and normalize hook candidates from the DYK template."""
    wikitext = fetch_wikitext()
    section = extract_hooks_section(wikitext)
    if not section:
        return []
    hooks: list[dict] = []
    # Unquote for comparison so encoded and plain forms (e.g. C%2B%2B vs C++) match.
    seen_urls: set[str] = set(urllib.parse.unquote(url) for url in (exclude_urls or set()))
    for raw in section.splitlines():
        raw = raw.strip()
        match = RE_HOOK_LINE.match(raw)
        if not match:
            continue
        hook_line = match.group(1)
        titles = extract_hook_titles(hook_line)
        if not titles:
            continue
        normalized = normalize_text(hook_line)
        if not normalized:
            continue
        urls = [title_to_url(title) for title in titles]
        if any(urllib.parse.unquote(url) in seen_urls for url in urls):
            continue
        seen_urls.update(urllib.parse.unquote(url) for url in urls)
        hooks.append({"text": normalized, "urls": urls, "returned": False})
    return hooks


def stored_urls(store: dict) -> set[str]:
    """Collect all URLs seen across stored and trimmed collections."""
    urls: set[str] = set(
        urllib.parse.unquote(url) for url in (store.get("seen_urls") or [])
    )
    for coll in (store.get("collections") or []):
        for hook in (coll.get("hooks") or []):
            urls.update(urllib.parse.unquote(url) for url in (hook.get("urls") or []))
    return urls


def refresh_due(store: dict, now: datetime) -> bool:
    """Return True if we should fetch a fresh set of hooks."""
    last_checked_at = store.get("last_checked_at")
    if last_checked_at:
        parsed = parse_iso(last_checked_at)
        if parsed is not None and (now - parsed).total_seconds() < CHECK_COOLDOWN:
            return False  # cooldown active — don't hammer the API

    collections = store.get("collections", [])
    if not collections:
        return True
    last = collections[-1]
    fetched_at = last.get("fetched_at")
    if not fetched_at:
        return True
    parsed = parse_iso(fetched_at)
    if parsed is None:
        return True
    return (now - parsed).total_seconds() >= REFRESH_INTERVAL


def load_store() -> dict:
    """Load the on-disk cache, returning an empty structure if missing/invalid."""
    try:
        text = DATA_PATH.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict) or not isinstance(data.get("collections"), list):
            return {"collections": []}
        if not isinstance(data.get("seen_urls", []), list):
            data["seen_urls"] = []
        return data
    except (json.JSONDecodeError, OSError):
        return {"collections": []}


def save_store(store: dict) -> None:
    """Persist the cache to disk atomically via write-to-temp + rename."""
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = DATA_PATH.with_suffix(".tmp")
    try:
        tmp_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.rename(DATA_PATH)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def trim_store(store: dict) -> None:
    """Keep only the most recent MAX_COLLECTIONS collections."""
    collections = store.setdefault("collections", [])
    while len(collections) > MAX_COLLECTIONS:
        collections.pop(0)
