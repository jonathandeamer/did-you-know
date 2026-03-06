---
name: did-you-know
description: Fetches English Wikipedia’s "Did you know?" facts, caches them locally, and serves them one at a time. No API key required. Does not edit Wikipedia.
homepage: https://en.wikipedia.org/wiki/User:Jonathan_Deamer
metadata: {"openclaw":{"emoji":"❓","requires":{"bins":["python3"]}}}
---

# Did You Know

Wikipedia's [Did You Know?](https://en.wikipedia.org/wiki/Wikipedia:Did_you_know) section highlights well-sourced facts from recently created or expanded articles. It's curated and refreshed at least daily by volunteers. A never-ending supply of conversation starters!


## Run

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
