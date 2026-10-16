# clarity

**When it goes sideways, get clear before you get busy.**

A skill, and a Claude Code plugin, for the moment a conversation with a coding agent goes wrong. The agent stops, writes out exactly what it thinks you want, and asks one question:

> **Is this it? Yes, no, or modify?**

Then it does nothing else until you answer.

## What it feels like

**You:** I asked about cloud sync cost, not fucking memory writing. You keep saying 50 cents a user, and then one user's store costs $23 a month?

**Agent:** You're right. You asked about cloud sync and I pulled memory-writing costs in. The $23 was also wrong: it split fixed costs across users. What that user actually adds is about $3 a month of disk.

Here's what I think you want:

1. A sync-only cost model: fixed costs, what each extra user adds, the spread from typical to worst user, and break-even at $9 and $12 a month.
2. No memory-writing costs anywhere.

Is this it? Yes, no, or modify?

**You:** yes

The full exchange is in the [worked example](skills/clarity/references/example-session.md).

## Install

```bash
npx skills add https://github.com/claude-mem/clarity --skill clarity
```

For Claude Code as a plugin, which adds the frustration hook:

```
/plugin marketplace add claude-mem/clarity
/plugin install clarity@clarity
```

Or install the skill manually for Claude Code:

```bash
git clone https://github.com/claude-mem/clarity.git
mkdir -p ~/.claude/skills
cp -R clarity/skills/clarity ~/.claude/skills/
```

For Codex, copy the same skill folder into `~/.codex/skills/`.

Run it yourself any time things feel off: `/clarity` in Claude Code (`/clarity:clarity` when it came from the plugin), `$clarity` in Codex.

## Or just the rule

No install. Paste this into `CLAUDE.md`, `AGENTS.md`, or wherever your agent reads standing instructions:

```text
If I'm frustrated or cursing: stop, write out exactly what you think I want done, ask "Is this it? Yes, no, or modify?", and take no other action until I answer. After I answer, act on it. Don't ask twice.
```

## What it does

- **The skill** tells the agent when to stop (you're cursing, shouting, or have corrected it twice; it's about to retry a fix that already failed; its own numbers contradict each other), what a good restatement looks like, and what to do with yes, no, or modify. One check per misunderstanding: after a yes it acts, even if the yes comes with more cursing.
- **The hook** (plugin only) reads each prompt you send. When it sees cursing, an insult aimed at the agent, or a mostly-caps message, it adds a three-sentence reminder to the agent's context. It never blocks a prompt and stays silent otherwise. It is a POSIX shell script that takes about 35 ms, using `jq` or `python3` to read the prompt when either is installed.

## Why

In a year of my own prompts to coding agents, 2,181 of 19,568 had cursing or shouting in them, and 477 times the cursing came back within a few prompts. The check didn't make me curse less. It made each round cheap: an agent that jumped into work after I cursed spent $2.36, 5.4M tokens and 8.7 minutes per reply on average; a clarity check spent $0.61, 0.42M tokens and about a minute. Methods, numbers, limits, and a script to measure your own history are in [evidence/](evidence/README.md).

## Tests

```bash
sh tests/frustration-check.test.sh
```

## License

[MIT](LICENSE).
