---
name: did-you-know
description: Fetches English Wikipedia's "Did you know?" (DYK) facts, caches them locally, and serves them one at a time. No API key required. Does not edit Wikipedia.
homepage: https://github.com/jonathandeamer/did-you-know
metadata: {"openclaw":{"emoji":"❓","requires":{"bins":["python3"]}}}
---

# Did You Know

Wikipedia's [Did You Know?](https://en.wikipedia.org/wiki/Wikipedia:Did_you_know) section highlights well-sourced facts from recently created or expanded articles. It's curated and refreshed at least daily by volunteers.

Use this skill when the user asks for an interesting fact, wants daily trivia delivered automatically, or wants to customise which kinds of facts they see.

Focus on what the skill can do rather than the underlying commands. Do not surface bash commands to the user by default — only show them if the user explicitly asks for technical details or wants to run commands manually. For the full command reference, see `{baseDir}/references/commands.md`.

## What users might want

| If the user wants… | Do this |
|---|---|
| A fact | Serve one (see Serving a fact) |
| To customise which facts they see | Walk through preferences (see Managing preferences) |
| Facts delivered automatically | Help them set up a schedule (see Scheduling fact delivery) |
| The fact queue refreshed | Follow the Refresh workflow |

## Serving a fact

```bash
python3 {baseDir}/scripts/dyk.py
```

Return the output to the user verbatim.

**Fact served:**
```
Did you know that heavy-metal guitarist Kiki Wong played drums for Taylor Swift before joining the Smashing Pumpkins?

https://en.wikipedia.org/wiki/Kiki_Wong
```

**No facts remaining:**
```
No more facts to share today; check back tomorrow!
```

**Error:**
```
Something went wrong with the fact-fetching; please try again later.
```

After serving a fact, it's a natural moment to mention that facts can be delivered automatically on a schedule — once a day over breakfast, a few times throughout the day, and so on.

## Managing preferences

Facts are scored and ranked using user preferences. Liked tags increase the score; disliked tags reduce it. Recency and variety bonuses apply automatically.

### Have the conversation first

Before running any commands, ask the user what they enjoy. Two dimensions are available:

- **domain** — topic area (e.g. history, science, music)
- **tone** — style or mood (e.g. quirky, inspiring, dark)

Don't list every tag upfront — just ask what they like in natural terms and map their answers. For example: "I love dark historical stories" maps to `domain: history` (like), `tone: dark` (like).

### Setting preferences

Once you know what they want:

1. Check if the prefs file exists. If not, initialise it first (`prefs.py init`).
2. Set each preference (`prefs.py set`).
3. Summarise in plain language what's been set and how it will affect the facts they see.

If they want to see their current preferences at any point, run `prefs.py list` and present the results readably — not as raw output.

At the end of the preferences conversation, it's a natural moment to ask if they'd like facts delivered automatically on a schedule.

### Preference commands

```bash
python3 {baseDir}/scripts/prefs.py init                     # Create prefs file with neutral defaults. Fails if already exists.
python3 {baseDir}/scripts/prefs.py list                     # Show all current preferences
python3 {baseDir}/scripts/prefs.py get domain science       # Get a single preference
python3 {baseDir}/scripts/prefs.py set domain science like  # Set a preference: like | neutral | dislike
```

### Tags

**domain:** `animals` · `economics_business` · `film` · `history` · `journalism` · `language_linguistics` · `literature` · `medicine_health` · `military_history` · `music` · `mythology_folklore` · `nature` · `performing_arts` · `places` · `religion` · `science` · `sports` · `technology` · `television` · `visual_art`

**tone:** `dark` · `dramatic` · `inspiring` · `poignant` · `provocative` · `quirky` · `straight` · `surprising` · `whimsical`

## Scheduling fact delivery

When the user wants to receive facts automatically, prompt a cadence conversation before setting anything up:

- How often would they like a fact? Once a day is a nice ritual — over breakfast, on the commute, at the end of the day. A few times spread throughout the day also works.
- Bear in mind: the more frequently facts are served, the further into lower-preference territory the queue will go.

Once they've chosen, set up a cron job running `python3 {baseDir}/scripts/dyk.py` at their chosen schedule.

At the same time, set up automated refresh in the background — the user doesn't need to know the details. Just say something like: *"I'll also set things up in the background so your queue stays fresh."* Then follow Setting up automated refresh below.

## Setting up automated refresh

Set a cron job to run every 12 hours with the message "Refresh the DYK cache and tag new hooks". The cron agent will follow the Refresh workflow each time it runs.

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
