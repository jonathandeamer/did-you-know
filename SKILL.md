---
name: did-you-know
description: Fetches English Wikipedia's "Did you know?" facts, caches them locally, and serves them one at a time. No API key required. Does not edit Wikipedia.
homepage: https://en.wikipedia.org/wiki/User:Jonathan_Deamer
metadata: {"openclaw":{"emoji":"❓","requires":{"bins":["python3"]}}}
---

# Did You Know

Wikipedia's [Did You Know?](https://en.wikipedia.org/wiki/Wikipedia:Did_you_know) section highlights well-sourced facts from recently created or expanded articles. It's curated and refreshed at least daily by volunteers. Schedule it to run regularly using cron for a steady supply of conversation starters!


## Serving a fact

When invoked, the default behaviour is to share the next fact from the queue:

```bash
python3 {baseDir}/scripts/dyk.py
```

Prints one fact. Return it to the user verbatim:

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


## Managing preferences

Facts are scored at serve time. Each `like` or `dislike` preference adds +1 (`like`) or −1 (`dislike`) to the score (domain tags are summed; tone is a single tag). On top of that, small automatic bonuses apply to all facts: recency, brevity, and multiple source URLs are rewarded, while consecutive facts from the same domain are lightly penalised.

### Setup

```bash
python3 {baseDir}/scripts/prefs.py init
```

Creates `~/.openclaw/dyk-prefs.json` with every tag set to `neutral`. Fails if the file already exists.

### Commands

```bash
# View all current preferences
python3 {baseDir}/scripts/prefs.py list

# Get a single preference
python3 {baseDir}/scripts/prefs.py get domain science

# Set a preference
python3 {baseDir}/scripts/prefs.py set domain science like
python3 {baseDir}/scripts/prefs.py set tone dark dislike
```

The `set` command's value argument accepts: `like`, `neutral`, `dislike`.

`list`, `get`, and `set` all require the prefs file to exist — if they report "no prefs file found", run `init` first and then retry.

### Tags

**domain:** `animals` · `economics_business` · `film` · `history` · `journalism` · `language_linguistics` · `literature` · `medicine_health` · `military_history` · `music` · `mythology_folklore` · `nature` · `performing_arts` · `places` · `religion` · `science` · `sports` · `technology` · `television` · `visual_art`

**tone:** `dark` · `dramatic` · `inspiring` · `poignant` · `provocative` · `quirky` · `straight` · `surprising` · `whimsical`


## Setting up automated refresh

To keep the fact queue topped up automatically, set a cron job to run every 12 hours:

```bash
openclaw cron add \
  --name "DYK refresh" \
  --every 12h \
  --session isolated \
  --channel none \
  --message "Refresh the DYK cache and tag new hooks"
```

The cron agent will follow the refresh workflow below each time it runs.

To check the job is running: `openclaw cron list`

To trigger it immediately: `openclaw cron run <id>`


## Refresh workflow

When asked to refresh the DYK cache and tag new hooks:

1. Run: `python3 {baseDir}/scripts/fetch_hooks.py`

   This fetches the latest hooks and stores them in `~/.openclaw/dyk-facts.json` with `"tags": null` for new entries.

   If it exits non-zero, stop and report the error. Do not continue.

2. Read `~/.openclaw/dyk-facts.json` and find all hooks where `"tags"` is `null`.

   If there are none, stop — nothing to tag.

3. For each untagged hook, assign tags using:
   - Tagging guide: `{baseDir}/tagging/tagging-guide.md`
   - Vocabulary: `{baseDir}/tagging/tags.csv`

   Output requirements:
   - Use only tag values defined in `tags.csv`
   - Write valid JSON only — no comments or explanations
   - Collect results into a single JSON array
   - Write the array to a temporary file such as `/tmp/dyk-tags.json`

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
