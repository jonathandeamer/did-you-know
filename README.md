# "Did You Know?" OpenClaw skill

A daily dose of interesting facts, pulled straight from Wikipedia — one at a time, no repeats.

An [OpenClaw](https://openclaw.ai) skill. Skills extend what your agent can do — install this one to give it a daily supply of Wikipedia facts. Find more skills at [ClawHub](https://clawhub.ai).

[![GitHub Release](https://img.shields.io/github/v/release/jonathandeamer/did-you-know)](https://github.com/jonathandeamer/did-you-know/releases)
[![License: MIT](https://img.shields.io/github/license/jonathandeamer/did-you-know)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org)

---

## What it does

Ask for a fact, get a fact:

```
Did you know that heavy-metal guitarist Kiki Wong played drums for Taylor Swift
before joining the Smashing Pumpkins?

https://en.wikipedia.org/wiki/Kiki_Wong
```

Each fact comes from Wikipedia's [Did You Know?](https://en.wikipedia.org/wiki/Wikipedia:Did_you_know) section — a curated collection of surprising, well-sourced tidbits from recently written or expanded articles, refreshed daily by Wikipedia volunteers. Think of it as a conversation starter that arrives already fact-checked.

The skill keeps track of what it's already shown you, so you'll never get the same fact twice. When the current batch runs dry, check back the next day for a fresh set.

No account or API key required, and never edits Wikipedia.

---

## Install

**The easy way — via ClawHub:**

```
clawhub install did-you-know
```

**Manually:**

```bash
mkdir -p ~/.openclaw/workspace/skills/did-you-know && \
curl -L https://github.com/jonathandeamer/did-you-know/archive/refs/tags/v0.2.0.tar.gz | \
tar -xz --strip-components=1 -C ~/.openclaw/workspace/skills/did-you-know
```

---

## How to use it

Facts work immediately — no setup required. Preferences and scheduling are optional extras that make the experience better over time.

### Get a fact

Ask your agent:

> *"Give me a did you know fact"*

Or use the slash command:

```
/did_you_know
```

One fact per ask, with a link to the full Wikipedia article if you want to go deeper.

### Tune which facts you see

Tell the agent what you enjoy and it will set preferences accordingly:

> *"I want more history and dark stories, less science"*
> *"Quirky and surprising facts please, nothing too serious"*

Preferences influence the order facts are served: liked topics and tones rise to the top, disliked ones are pushed to the back. Two dimensions are available:

**domain** (20 tags): `animals` · `economics_business` · `film` · `history` · `journalism` · `language_linguistics` · `literature` · `medicine_health` · `military_history` · `music` · `mythology_folklore` · `nature` · `performing_arts` · `places` · `religion` · `science` · `sports` · `technology` · `television` · `visual_art`

**tone** (9 tags): `dark` · `dramatic` · `inspiring` · `poignant` · `provocative` · `quirky` · `straight` · `surprising` · `whimsical`

Beyond your explicit preferences, scoring also factors in recency, variety, and brevity automatically — newer facts, different topics from what you just saw, and shorter hooks all get a small boost.

Setting preferences also enables automatic refresh, which tags new facts as they arrive so scoring stays current.

### Schedule fact delivery

Ask the agent to send you a fact automatically at a time that suits you:

> *"Send me a fact every morning at 8am"*
> *"Give me three facts a day — morning, lunch, and evening"*

Scheduled delivery works independently of preferences. If you have preferences set up, the two work together: facts are delivered on your schedule, ranked by what you like.

---

## Setup tiers at a glance

*From least to most setup:*

| What you want | What's needed |
|---|---|
| Facts on demand | Nothing — just ask |
| Facts delivered automatically | A delivery schedule |
| Facts tuned to your interests | Preferences + automatic refresh |

Preferences and refresh go together: preferences control which facts rank highest; refresh fetches and tags new facts from Wikipedia so your preferences keep applying as the queue turns over. Without refresh, preferences only affect the facts already in the cache. Both are configured together when you set up preferences.

Scheduled delivery is independent — it sends you a fact at a chosen time, with or without preferences.

---

Most interaction is through natural language. The full command reference is in [`references/commands.md`](references/commands.md) if you want to run things directly.
