# "Did You Know?" OpenClaw skill

A daily dose of interesting facts, pulled straight from Wikipedia — one at a time, no repeats.

An [OpenClaw](https://openclaw.ai) skill. Skills extend what your agent can do — install this one to give it a daily supply of Wikipedia facts. Find more skills at [ClawHub](https://clawhub.ai).

[![GitHub Release](https://img.shields.io/github/v/release/jonathandeamer/did-you-know)](https://github.com/jonathandeamer/did-you-know/releases)
[![License: MIT](https://img.shields.io/github/license/jonathandeamer/did-you-know)](LICENSE)
[![Python 3](https://img.shields.io/badge/python-3-blue)](https://www.python.org)

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
curl -L https://github.com/jonathandeamer/did-you-know/archive/refs/tags/v0.1.1.tar.gz | \
tar -xz --strip-components=1 -C ~/.openclaw/workspace/skills/did-you-know
```

---

## How to use it

Once installed, just ask your agent:

> *"Give me a did you know fact"*

Or use the slash command:

```
/did_you_know
```

That's it. One fact per ask, with a link to the full Wikipedia article if you want to go deeper.
