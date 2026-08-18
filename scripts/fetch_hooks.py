#!/usr/bin/env python3
"""Fetch Wikipedia DYK hooks and write them untagged (tags=null) to the cache."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from helpers import (
    load_store,
    refresh_collections,
    save_store,
)


def fetch_and_stage(store: dict) -> None:
    """Fetch new hooks and append them untagged to the store."""
    refresh_collections(store, mark_untagged=True, failure_label="fetch")


def main() -> int:
    """Entrypoint: refresh cache with untagged hooks if due."""
    store = load_store()
    try:
        fetch_and_stage(store)
    except Exception as exc:
        print(f"DYK fetch error: {exc}", file=sys.stderr)
        try:
            save_store(store)
        except Exception:
            pass
        return 1
    save_store(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
