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


def test_init_refuses_if_file_exists(tmp_path, monkeypatch, capsys):
    vocab = _make_vocab_csv(tmp_path)
    prefs_path = tmp_path / "dyk-prefs.json"
    prefs_path.write_text("{}")
    monkeypatch.setattr(prefs, "PREFS_PATH", prefs_path)
    monkeypatch.setattr(prefs, "TAGS_CSV", vocab)

    result = prefs.main(["init"])

    assert result == 1
    assert "already exists" in capsys.readouterr().err
