#!/usr/bin/env python3
"""Unit tests for scripts/prefs.py.

Run with: python3 -m pytest tests/ -v
Requires: pip install pytest
"""
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import prefs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vocab_csv(tmp_path):
    rows = [
        ("history",    "domain", "History"),
        ("science",    "domain", "Science"),
        ("surprising", "tone",   "Surprising"),
        ("straight",   "tone",   "Straight"),
    ]
    p = tmp_path / "tags.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["tag_id", "dimension", "description"])
        writer.writerows(rows)
    return p


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def test_init_creates_file(tmp_path, monkeypatch):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["init"])

    assert result == 0
    data = json.loads(prefs_path.read_text())
    assert data == {"domain": {"history": 0, "science": 0}, "tone": {"straight": 0, "surprising": 0}}
    raw = prefs_path.read_text()
    parsed = json.loads(raw)
    assert list(parsed.keys()) == sorted(parsed.keys())
    for dim_tags in parsed.values():
        assert list(dim_tags.keys()) == sorted(dim_tags.keys())


def test_init_refuses_if_file_exists(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    prefs_path.write_text("{}")
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["init"])

    assert result == 1
    assert "already exists" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def _write_prefs(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_list_prints_prefs(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    _write_prefs(prefs_path, {"domain": {"history": 1, "science": -1}, "tone": {"straight": 0}})
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["list"])

    out = capsys.readouterr().out
    assert result == 0
    assert "history" in out
    assert "like" in out
    assert "science" in out
    assert "dislike" in out
    assert "neutral" in out


def test_list_warns_on_out_of_range_value(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    _write_prefs(prefs_path, {"domain": {"history": 5}, "tone": {"straight": 0}})
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["list"])

    assert result == 0
    captured = capsys.readouterr()
    assert "history" in captured.out
    assert "5" in captured.out
    assert "domain.history" in captured.err


def test_list_missing_file_suggests_init(tmp_path, monkeypatch, capsys):
    prefs_path = tmp_path / "dyk-prefs.json"
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)

    result = prefs.main(["list"])

    assert result == 1
    assert "init" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

def test_get_returns_word(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    _write_prefs(prefs_path, {"domain": {"history": 1}, "tone": {"straight": 0}})
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["get", "domain", "history"])

    assert result == 0
    assert "like" in capsys.readouterr().out


def test_get_unknown_dimension(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    _write_prefs(prefs_path, {"domain": {"history": 0}, "tone": {"straight": 0}})
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["get", "badDim", "history"])

    assert result == 1
    assert "Unknown dimension" in capsys.readouterr().err


def test_get_unknown_tag(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    _write_prefs(prefs_path, {"domain": {"history": 0}, "tone": {"straight": 0}})
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["get", "domain", "badTag"])

    assert result == 1
    assert "Unknown tag" in capsys.readouterr().err


def test_get_warns_on_out_of_range_value(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    _write_prefs(prefs_path, {"domain": {"history": 5}, "tone": {"straight": 0}})
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["get", "domain", "history"])

    assert result == 0
    captured = capsys.readouterr()
    assert "5" in captured.out
    assert "domain.history" in captured.err


def test_get_missing_file_suggests_init(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["get", "domain", "history"])

    assert result == 1
    assert "init" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------

def test_set_updates_value(tmp_path, monkeypatch):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    _write_prefs(prefs_path, {"domain": {"history": 0, "science": 0}, "tone": {"straight": 0, "surprising": 0}})
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["set", "domain", "history", "like"])

    assert result == 0
    data = json.loads(prefs_path.read_text())
    assert data["domain"]["history"] == 1
    assert data["domain"]["science"] == 0  # untouched


def test_set_dislike(tmp_path, monkeypatch):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    _write_prefs(prefs_path, {"domain": {"history": 0}, "tone": {"straight": 0}})
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["set", "domain", "history", "dislike"])

    assert result == 0
    data = json.loads(prefs_path.read_text())
    assert data["domain"]["history"] == -1


def test_set_invalid_value(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    _write_prefs(prefs_path, {"domain": {"history": 0}, "tone": {"straight": 0}})
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["set", "domain", "history", "love"])

    assert result == 1
    assert "like" in capsys.readouterr().err


def test_set_unknown_dimension(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    _write_prefs(prefs_path, {"domain": {"history": 0}, "tone": {"straight": 0}})
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["set", "badDim", "history", "like"])

    assert result == 1
    assert "Unknown dimension" in capsys.readouterr().err


def test_set_unknown_tag(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    _write_prefs(prefs_path, {"domain": {"history": 0}, "tone": {"straight": 0}})
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["set", "domain", "badTag", "like"])

    assert result == 1
    assert "Unknown tag" in capsys.readouterr().err


def test_set_missing_file_suggests_init(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["set", "domain", "history", "like"])

    assert result == 1
    assert "init" in capsys.readouterr().err
