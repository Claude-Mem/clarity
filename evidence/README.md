# Evidence

What happened after I cursed at coding agents for a year, and what the clarity check changed. Every number here comes from [spirals.py](spirals.py), run on my own history on 2026-10-16.

## Sources

- **A year of prompts.** claude-mem's `user_prompts` table, 2025-10-22 to 2026-10-16. After dropping duplicates (sync copies, re-sends), machine-written prompts (hook output, task notifications, briefs one agent wrote for another) and bot traffic, that leaves 19,568 prompts I typed into coding agents across 4,901 sessions.
- **Seven weeks of transcripts.** Claude Code's local transcripts, 2026-08-25 to 2026-10-16: 179 interactive sessions and 797 prompts, with exact token usage for every reply, subagents included. Priced at OpenRouter's public list prices using the claude-mem agent-cost-report rules. These are list-price equivalents, not what I paid. I'm on a subscription.

claude-mem also stores what its own note-taker spends (`discovery_tokens`). That is the cost of writing memories, not the cost of the coding session, so none of it is counted here.

## Definitions

- **Cursing prompt:** profanity, an insult aimed at the agent, or a mostly-caps message, minus happy cursing ("fuck yeah, it works"). I hand-checked a random sample of 80 flagged prompts: 76 were real cursing or frustration (95%). This counts cursing, not quiet frustration.
- **Spiral:** cursing prompts in one session where each one lands within 3 prompts and 60 minutes of the last. Every curse in a spiral after the first is a **follow-up curse**.
- **The rule:** "If they are frustrated or cursing, stop, write out exactly what you think they want done, ask 'Is this it? Yes, no, or modify?', and take no other action until they answer." First written 2026-09-07 in the house rules for my agent seats, rewritten 2026-09-09, then moved into my global `CLAUDE.md`. Everything earlier counts as before the rule.
- **Clarity check:** a reply to a cursing prompt that asks "Is this it?" and makes no tool calls. **Act first:** a reply that makes tool calls and doesn't ask.

## A year of cursing

| | |
|---|---|
| Prompts I typed | 19,568 |
| Cursing prompts | 2,181 (11.1%) |
| Sessions with at least one | 988 of 4,901 |
| Spirals where the cursing came back | 477 |
| Follow-up curses | 1,046 |
| Longest spiral | 15 cursing prompts |
| First curse to last curse, summed over those spirals | 54 hours |
| Worst day | 2025-11-21: 93 cursing prompts across 19 sessions |

| Month | Prompts | Cursing | Share |
|---|---|---|---|
| 2025-10 (from the 22nd) | 736 | 124 | 16.8% |
| 2025-11 | 3,261 | 521 | 16.0% |
| 2025-12 | 2,632 | 350 | 13.3% |
| 2026-01 | 1,563 | 246 | 15.7% |
| 2026-02 | 1,326 | 82 | 6.2% |
| 2026-03 | 774 | 54 | 7.0% |
| 2026-04 | 2,563 | 241 | 9.4% |
| 2026-05 | 2,325 | 224 | 9.6% |
| 2026-06 | 711 | 87 | 12.2% |
| 2026-07 | 600 | 44 | 7.3% |
| 2026-08 | 919 | 70 | 7.6% |
| 2026-09 | 1,123 | 58 | 5.2% |
| 2026-10 (to the 16th) | 1,035 | 80 | 7.7% |

By hour of day (Pacific time), cursing peaks in the 1 a.m. hour (60 of 351 prompts, 17%) and bottoms out in the 9 a.m. hour (10 of 277, 4%). From midnight to 6 a.m. it runs 13%; afternoons, 10%.

## What the rule didn't change

How often I curse, and how often it spirals. In Claude Code sessions, comparing the 60 days right before the rule with the 39 days since:

| | 60 days before | Since the rule |
|---|---|---|
| Prompts with cursing | 7.0% | 8.1% |
| Spirals where I cursed again | 19 of 51 (37%) | 18 of 54 (33%) |
| Curses per repeat spiral (median) | 2 | 2 |

The big drop, from about 16% of prompts last winter to 6 to 8% now, happened months before the rule.

## What the rule did change

**What the agent does next.** Before the rule, the agent did recorded work after 47% of my curses (330 of 699, counted in sessions where claude-mem linked work to the prompt that caused it). In the seven weeks of transcripts, it stopped and asked after 51 of 82 cursing prompts (62%) and acted first after 26 (32%).

**The price of each round.**

| Reply to a cursing prompt | Replies | Mean cost | Mean tokens | Mean minutes | Costliest single reply |
|---|---|---|---|---|---|
| Act first | 26 | $2.36 | 5.4M | 8.7 | $18.79: 55.5M tokens, 180 tool calls, 38 min |
| Clarity check | 47 | $0.61 | 0.42M | 1.0 | $6.54: 0.5M tokens, no tool calls, 42 s |
| Difference, 95% bootstrap interval | | $1.75 ($0.29 to $3.58) | 5.0M (1.3M to 10.2M) | 7.8 (1.6 to 16.7) | |

Medians: $0.35 and $0.18; 0.78M and 0.28M tokens; 59 and 21 seconds. The longest act-first reply ran 101 minutes. Four more replies asked "Is this it?" after doing tool work; four only talked.

**The price of a miss.** The check didn't stop me cursing at the next prompt. That happened after 30% of act-first replies (6 of 20 that had a next prompt) and 32% of clarity checks (15 of 47). What changed is what the miss had already burned:

| When the next prompt was another curse | Misses | Spent per miss |
|---|---|---|
| Act first | 6 | $1.85, 4.0M tokens, 5.6 minutes |
| Clarity check | 15 | $0.29, 0.52M tokens, 43 seconds |

## The year before the rule, estimated

There were 975 follow-up curses in Claude Code sessions before the rule. The agent had done real work after 47% of curses, so roughly 460 times it worked on something I then cursed at again. Priced at the measured gap between an act-first reply and a clarity check, that comes to:

- about $805 at list price ($133 to $1,648)
- about 2.3 billion tokens (0.6B to 4.7B), mostly cached context read again and again
- about 60 hours of agent time (12 to 128) spent on the wrong thing

This is an estimate. There are no token logs for most of that year, today's models and prices stand in for last year's, and the ranges come only from the bootstrap interval above.

## The hook

The plugin's hook was written after this data, so none of the numbers above involve it. Run on the same year of prompts, it fires on 2,109 of the 2,181 prompts flagged as cursing (96.7%) and on 6 of 2,000 randomly sampled other prompts (0.3%). Most of those 6 are angry prompts the classifier filed as happy ("you're reading old logs. holy fuck"). In all, it would have spoken up on about 11% of my prompts.

## Limits

- This is observational. Nothing was randomized, and the rule arrived alongside other changes in models, projects, and mood. The reply-level comparison holds the period, the models, and me constant, but the agent chose when to follow the rule, and the cases where it acted first may have been different cases.
- The transcript sample is small: 82 cursing prompts with token data.
- The classifier is a set of regular expressions with 95% precision on a hand check.
- Dollars are list-price equivalents.

## Measure your own

Needs claude-mem (for the prompt history and the agent-cost-report price rules) and Python 3.9+.

```bash
python3 evidence/spirals.py all --rule-date 2026-09-07
python3 evidence/spirals.py sample --sample-size 80   # read these and count the real ones
python3 evidence/spirals.py hook
```

Set `--rule-date` to the day you started using the rule, and `--timezone` to yours (default `America/Los_Angeles`). Results go to `spirals-out/summary.json`. Your prompt text is written to `spirals-out/private/`; keep it out of git.
