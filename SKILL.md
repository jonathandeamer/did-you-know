---
name: did-you-know
description: Fetches English Wikipedia's "Did you know?" (DYK) facts, caches them locally, and serves them one at a time. No API key required. Does not edit Wikipedia.
homepage: https://github.com/jonathandeamer/did-you-know
metadata: {"openclaw":{"emoji":"❓","requires":{"bins":["python3"]}}}
---

# Did You Know

Wikipedia's [Did You Know?](https://en.wikipedia.org/wiki/Wikipedia:Did_you_know) section highlights well-sourced facts from recently created or expanded articles. It's curated and refreshed at least daily by volunteers.

Use this skill when the user asks for an interesting fact, wants daily trivia delivered automatically, or wants to customise which kinds of facts they see.

This skill can help with:
- Sharing a "Did you know?" fact on demand
- Scheduling daily fact delivery
- Customising which facts surface using tag preferences
- Keeping the fact queue topped up by refreshing it automatically

When guiding the user, focus on what the skill can do rather than the underlying commands. Do not surface bash commands by default. Only show commands if the user explicitly asks for technical details or wants to run them manually.

## Commands

| Task | Command |
|------|---------|
| Share a fact | `python3 {baseDir}/scripts/dyk.py` |
| Initialise preferences | `python3 {baseDir}/scripts/prefs.py init` |
| List preferences | `python3 {baseDir}/scripts/prefs.py list` |
| Get a preference | `python3 {baseDir}/scripts/prefs.py get domain science` |
| Set a preference | `python3 {baseDir}/scripts/prefs.py set domain science like` |

For fetching and refreshing facts (usually scheduled automatically), see **Refresh workflow** below.

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

Facts are scored using user preferences. Liked tags increase the score and disliked tags reduce it. Recency and variety bonuses are applied automatically.

If the user wants to customise preferences, walk them through `init` (if necessary) → `list` → `set` one step at a time, giving them details of the tag options available. Remember, when guiding the user, focus on what the skill can do rather than the underlying commands. Do not surface bash commands by default. Only show commands if the user explicitly asks for technical details or wants to run them manually.

### Commands

```bash
# Initialise preferences - creates ~/.openclaw/dyk-prefs.json with every tag set to neutral. Fails if the file already exists.
python3 {baseDir}/scripts/prefs.py init

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

## Scheduling fact delivery (once)

To receive a daily fact automatically, set a cron job to run `python3 {baseDir}/scripts/dyk.py`

## Setting up automated refresh (once)

To keep the fact queue topped up automatically, set a cron job to run every 12 hours with the message "Refresh the DYK cache and tag new hooks".

The cron agent will follow the refresh workflow below each time it runs.

## Refresh workflow

When asked to refresh the DYK facts cache and tag new hooks:

1. Run: `python3 {baseDir}/scripts/fetch_hooks.py`

   This fetches the latest hooks and stores them in `~/.openclaw/dyk-facts.json` with `"tags": null` for new entries.

   If it exits non-zero, stop and report the error. Do not continue.

2. Read `~/.openclaw/dyk-facts.json` and find all hooks where `"tags"` is `null`.

   If there are none, stop — nothing to tag.

3. Assign tags for all untagged hooks at once — do not loop across multiple turns or tool calls. For each hook, assign tags using:
   - Tagging guide: `{baseDir}/references/tagging-guide.md`
   - Vocabulary: `{baseDir}/references/tags.csv`

   Output requirements:
   - Use only tag values defined in `tags.csv`
   - If tagging confidence is low, set "low_confidence": true.
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
