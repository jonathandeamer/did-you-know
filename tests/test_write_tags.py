# tests/test_write_tags.py
"""Tests for scripts/write_tags.py."""
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import dyk

# These imports will fail until write_tags.py exists — that is expected.
import write_tags
from write_tags import apply_tags, load_vocabulary, main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vocab_csv(tmp_path, extra_tags=None):
    rows = [
        ("history",    "domain", "History"),
        ("science",    "domain", "Science"),
        ("music",      "domain", "Music"),
        ("surprising", "tone",   "Surprising"),
        ("straight",   "tone",   "Straight"),
        ("quirky",     "tone",   "Quirky"),
    ]
    if extra_tags:
        rows.extend(extra_tags)
    p = tmp_path / "tags.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["tag_id", "dimension", "description"])
        writer.writerows(rows)
    return p


def _make_store(tags_value="SENTINEL", include_tags_key=True):
    """Return an in-memory store with one hook.

    tags_value="SENTINEL" → use None (untagged).
    include_tags_key=False → legacy hook with no 'tags' key.
    """
    hook = {
        "text": "some fact",
        "urls": ["https://en.wikipedia.org/wiki/Foo"],
        "returned": False,
    }
    if include_tags_key:
        hook["tags"] = None if tags_value == "SENTINEL" else tags_value
    return {
        "collections": [
            {"date": "2026-01-01", "fetched_at": "2026-01-01T00:00:00Z", "hooks": [hook]}
        ],
        "seen_urls": [],
    }


_VALID_ENTRY = {
    "url": "https://en.wikipedia.org/wiki/Foo",
    "domain": ["science"],
    "tone": "surprising",
    "low_confidence": False,
}


# ---------------------------------------------------------------------------
# load_vocabulary
# ---------------------------------------------------------------------------

def test_load_vocabulary_groups_by_dimension(tmp_path):
    vocab_path = _make_vocab_csv(tmp_path)
    vocab = load_vocabulary(vocab_path)
    assert "domain" in vocab
    assert "tone" in vocab
    assert "science" in vocab["domain"]
    assert "surprising" in vocab["tone"]


# ---------------------------------------------------------------------------
# apply_tags
# ---------------------------------------------------------------------------

def test_merges_tags_into_matching_hook(tmp_path):
    vocab = load_vocabulary(_make_vocab_csv(tmp_path))
    store = _make_store()
    apply_tags(store, [_VALID_ENTRY], vocab)
    hook = store["collections"][0]["hooks"][0]
    assert hook["tags"] == {"domain": ["science"], "tone": "surprising", "low_confidence": False}


def test_ignores_hooks_without_tags_key(tmp_path):
    vocab = load_vocabulary(_make_vocab_csv(tmp_path))
    store = _make_store(include_tags_key=False)
    original = dict(store["collections"][0]["hooks"][0])
    apply_tags(store, [_VALID_ENTRY], vocab)
    assert store["collections"][0]["hooks"][0] == original


def test_does_not_modify_text_urls_or_returned(tmp_path):
    vocab = load_vocabulary(_make_vocab_csv(tmp_path))
    store = _make_store()
    hook_before = store["collections"][0]["hooks"][0]
    text_before = hook_before["text"]
    urls_before = list(hook_before["urls"])
    returned_before = hook_before["returned"]
    apply_tags(store, [_VALID_ENTRY], vocab)
    hook = store["collections"][0]["hooks"][0]
    assert hook["text"] == text_before
    assert hook["urls"] == urls_before
    assert hook["returned"] == returned_before


def test_rejects_unknown_domain(tmp_path):
    vocab = load_vocabulary(_make_vocab_csv(tmp_path))
    store = _make_store()
    bad_entry = {**_VALID_ENTRY, "domain": ["nonexistent_domain"]}
    with pytest.raises(ValueError, match="domain"):
        apply_tags(store, [bad_entry], vocab)


def test_rejects_unknown_tone(tmp_path):
    vocab = load_vocabulary(_make_vocab_csv(tmp_path))
    store = _make_store()
    bad_entry = {**_VALID_ENTRY, "tone": "nonexistent_tone"}
    with pytest.raises(ValueError, match="tone"):
        apply_tags(store, [bad_entry], vocab)


def test_store_unchanged_after_validation_error(tmp_path):
    """apply_tags validates all entries before merging any."""
    vocab = load_vocabulary(_make_vocab_csv(tmp_path))
    store = _make_store()
    bad_entry = {**_VALID_ENTRY, "domain": ["nonexistent_domain"]}
    try:
        apply_tags(store, [bad_entry], vocab)
    except ValueError:
        pass
    assert store["collections"][0]["hooks"][0]["tags"] is None


def test_no_match_for_url_is_silently_skipped(tmp_path):
    vocab = load_vocabulary(_make_vocab_csv(tmp_path))
    store = _make_store()
    unknown_entry = {**_VALID_ENTRY, "url": "https://en.wikipedia.org/wiki/DoesNotExist"}
    apply_tags(store, [unknown_entry], vocab)
    assert store["collections"][0]["hooks"][0]["tags"] is None  # unchanged


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def test_main_rejects_malformed_json(tmp_path, monkeypatch):
    monkeypatch.setattr("dyk.DATA_PATH", tmp_path / "store.json")
    result = main(["--json", "{bad json}", "--vocabulary", str(_make_vocab_csv(tmp_path))])
    assert result == 1


def test_main_rejects_unknown_domain_exits_1_and_leaves_store_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr("dyk.DATA_PATH", tmp_path / "store.json")
    store = _make_store()
    (tmp_path / "store.json").write_text(json.dumps(store), encoding="utf-8")
    bad_entry = {**_VALID_ENTRY, "domain": ["nonexistent"]}
    result = main([
        "--json", json.dumps([bad_entry]),
        "--vocabulary", str(_make_vocab_csv(tmp_path)),
    ])
    assert result == 1
    saved = json.loads((tmp_path / "store.json").read_text())
    assert saved["collections"][0]["hooks"][0]["tags"] is None


def test_main_merges_and_saves_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr("dyk.DATA_PATH", tmp_path / "store.json")
    store = _make_store()
    (tmp_path / "store.json").write_text(json.dumps(store), encoding="utf-8")
    result = main([
        "--json", json.dumps([_VALID_ENTRY]),
        "--vocabulary", str(_make_vocab_csv(tmp_path)),
    ])
    assert result == 0
    saved = json.loads((tmp_path / "store.json").read_text())
    assert saved["collections"][0]["hooks"][0]["tags"]["domain"] == ["science"]
