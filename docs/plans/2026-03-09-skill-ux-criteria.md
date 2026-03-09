# Skill UX criteria

Quality criteria for the agent-facing SKILL.md. All of these were identified as issues and fixed in March 2026. Re-verify against these if SKILL.md is significantly edited, or use as a prompt for `/skill-creator` eval sessions.

## Criteria

1. **No commands shown to users.** The skill should run all commands silently. Users should never see `python3 ...` or shell syntax unless they explicitly ask for technical details.

2. **Follow-up after serving a fact.** After delivering a fact, the agent should actively offer both preferences *and* scheduled delivery — not just one, and not passively. Something like: *"Would you like to tune which topics you see, or get a fact delivered automatically each day?"*

3. **Setup question answered fully.** When asked "do I need to set anything up?", the agent should say facts work immediately, then offer both preferences and scheduling as optional extras — not just one of them.

4. **Preferences and refresh connected.** When starting the preferences conversation, the agent should mention upfront that it will also set up automatic refresh alongside — this is what makes preferences apply to new facts as they arrive. The user doesn't need to understand the mechanics, but should know the full setup is happening.

5. **Refresh set up automatically, not as a separate offer.** Once preferences are confirmed, refresh should be set up and confirmed as done — not offered as a follow-up question the user has to say yes to.

6. **Refresh/delivery distinction clear.** If a user asks about scheduling or setup, the agent should understand that scheduled delivery (facts at a set time) and scheduled refresh (tagging new facts for preferences) are separate things. Refresh is only needed if preferences are active.
