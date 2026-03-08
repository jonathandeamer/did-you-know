#!/usr/bin/env python3
"""CLI for reading and writing dyk-prefs.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from write_tags import load_vocabulary
from helpers import PREFS_PATH

TAGS_CSV = Path(__file__).parent.parent / "tagging" / "tags.csv"

VALUE_MAP = {"like": 1, "neutral": 0, "dislike": -1}
VALUE_MAP_INV = {v: k for k, v in VALUE_MAP.items()}


def _load_vocab() -> dict[str, set[str]]:
    return load_vocabulary(TAGS_CSV)


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.rename(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def cmd_init(args: argparse.Namespace) -> int:
    if PREFS_PATH.exists():
        print(f"dyk-prefs.json already exists at {PREFS_PATH}", file=sys.stderr)
        return 1
    vocab = _load_vocab()
    data = {dim: {tag: 0 for tag in sorted(tags)} for dim, tags in sorted(vocab.items())}
    _atomic_write(PREFS_PATH, data)
    print(f"Created {PREFS_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage DYK preferences.")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init", help="Create prefs file (fails if already exists)")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 1
    if args.command == "init":
        return cmd_init(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
