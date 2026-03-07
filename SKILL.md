---
name: did-you-know
description: Fetches English Wikipedia's "Did you know?" facts, caches them locally, and serves them one at a time. No API key required. Does not edit Wikipedia.
homepage: https://en.wikipedia.org/wiki/User:Jonathan_Deamer
metadata: {"openclaw":{"emoji":"❓","requires":{"bins":["python3"]}}}
---

# Did You Know

Wikipedia's [Did You Know?](https://en.wikipedia.org/wiki/Wikipedia:Did_you_know) section highlights well-sourced facts from recently created or expanded articles. It's curated and refreshed at least daily by volunteers. A never-ending supply of conversation starters!


## Serving a fact

To share the next fact from the queue:

```bash
python3 {baseDir}/scripts/dyk.py
```

Prints one fact:

```
Did you know that heavy-metal guitarist Kiki Wong played drums for Taylor Swift before joining the Smashing Pumpkins?

https://en.wikipedia.org/wiki/Kiki_Wong
```

If no new facts remain:

```
No more facts to share today; check back tomorrow!
```

If something goes wrong:

```
Something went wrong with the fact-fetching; please try again later.
```


## Setting up automated refresh

To keep the fact queue topped up automatically, set a cron job to run every 12 hours:

```bash
openclaw cron add \
  --name "DYK refresh" \
  --every 12h \
  --session isolated \
  --message "Refresh the DYK cache and tag new hooks"
```

The cron agent will follow the refresh workflow below each time it runs.

To check the job is running: `openclaw cron list`

To trigger it immediately: `openclaw cron run <id>`


## Refresh workflow

When asked to refresh the DYK cache and tag new hooks:

1. Run: `python3 {baseDir}/scripts/fetch_hooks.py`

   If it exits non-zero, stop and report the error. Do not continue.

2. Read `~/.openclaw/dyk-facts.json` and find all hooks where `"tags"` is `null`.

   If there are none, stop — nothing to tag.

3. For each untagged hook, classify it using:
   - Tagging guide: `{baseDir}/references/tagging-guide.md`
   - Vocabulary: `{baseDir}/references/tags.csv`

   Produce a JSON array and write it to a temporary file:

   ```bash
   # Example array written to /tmp/dyk-tags.json
   [
     {"url": "https://en.wikipedia.org/wiki/Kiki_Wong",
      "domain": ["music"], "tone": "surprising", "low_confidence": false}
   ]
   ```

4. Run: `python3 {baseDir}/scripts/write_tags.py --json-file /tmp/dyk-tags.json`

   If it exits non-zero, report the error.

5. Do not message the user unless there is an error.
