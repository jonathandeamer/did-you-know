---
name: did-you-know
description: Fetches English Wikipedia’s "Did you know?" facts no more than once per day, caches them locally, and serves them one at a time. No API key required. Does not edit Wikipedia.
user-invocable: true
homepage: https://en.wikipedia.org/wiki/User:Jonathan_Deamer
metadata: {"openclaw":{"emoji":"❓","requires":{"bins":["python3"]}}}
---

# Did You Know

Wikipedia's [Did You Know?](https://en.wikipedia.org/wiki/Wikipedia:Did_you_know) section is a community-curated showcase of fully cited, consistently intriguing facts. It's refreshed daily by volunteers who care deeply about ensuring everyone can freely access and contribute to the sum of human knowledge.


## Run

```bash
python3 {baseDir}/scripts/dyk.py
```

Prints one fact:

```
Did you know that the shortest war in history lasted 38 minutes?

https://en.wikipedia.org/wiki/Anglo-Zanzibar_War
```

If no new hooks remain:

```
Something went wrong with the fact-fetching; please try again later.
```

---

## What It Does

- Fetches Wikipedia’s `Template:Did you know` (once per calendar day)
- Only refetches if 24 hours have elapsed since the last successful fetch that added at least one new hook
- Extracts hooks between `<!--Hooks-->` and `<!--HooksEnd-->`
- Strips wiki markup and `(pictured)` annotations
- Caches hooks locally
- Serves the next unserved hook
- Marks it as delivered
- Globally de-dupes against all cached hook URLs (not just the latest fetch)
- Keeps up to 3 days of history

Cache file:

```
~/.openclaw/dyk-facts.json
```

No refetching until 24 hours have elapsed since the last successful fetch that added at least one new hook. If a fetch returns only hooks already in the cache, no new collection is stored and the timer is not reset.

---

## Output Rules

- Always starts with: `Did you know that `
- Plain text only
- No leading ellipses
- Double spaces normalized
- Includes canonical Wikipedia link(s)

Output format:
1. The fact line.
2. A blank line.
3. One or more Wikipedia URLs, one per line.

---

## Failure Behavior

- Network failure → reuse cached hooks
- Empty feed or only cached hooks → reuse cached hooks
- If no cached hooks remain and a fetch fails, print: `Something went wrong with the fact-fetching; please try again later.`
- Corrupt cache → recreate

---

## Notes

- Public, unauthenticated MediaWiki API
- No credentials stored
- No messaging side effects
- Deterministic selection
- One fact per run
- Cannot edit Wikipedia
