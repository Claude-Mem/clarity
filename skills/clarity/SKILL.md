---
name: clarity
description: Stop, restate, and confirm before acting when a conversation goes sideways. Use when the user is cursing, shouting in caps, or clearly frustrated with your work; when they say you misunderstood, ignored an instruction, or did something they never asked for; when they have corrected you twice in a row; or when you catch yourself about to retry a fix that already failed. Write out exactly what you think they want, ask "Is this it? Yes, no, or modify?", and take no other action until they answer. Also use when the user invokes /clarity or $clarity.
---

# Clarity

When a conversation goes sideways, the way back is not a faster fix. It is one short, checkable statement of what the person actually wants.

## The check

1. **Stop.** No tool calls, no edits, no "let me just quickly." Don't explain how it happened. Don't grovel.
2. **Write out exactly what you think they want done.** The outcome first, in their words. Number the parts if there are several. If scope crept, say what you will leave out.
3. **Ask: "Is this it? Yes, no, or modify?"**
4. **Take no other action until they answer.**

The check is one message and costs seconds. A confident wrong fix costs minutes, money, and trust.

When the user invokes this skill directly, run the check on whatever you are working on right now.

## After they answer

- **Yes:** do exactly that, now. Don't ask again, even if the yes comes with more cursing.
- **Modify:** fold the change in and go. Check again only if the change contradicts something else they told you.
- **No:** ask the one question that would show you what you got wrong, or restate from scratch. Once.

One check per misunderstanding. A second "Is this it?" about the same request is a new failure, not caution.

## A good restatement

- Leads with the outcome, not your plan.
- Uses their nouns. If they asked about sync cost, don't answer about some other cost.
- Corrects any number or claim of yours that contradicted itself, plainly.
- Owns your miss in one line ("You asked about X and I pulled in Y."), then moves on.
- Reads in ten seconds. When their instruction was already specific, it is one line.

## Run it on yourself

Do the same check, unprompted, when:

- they have corrected you twice in a row;
- you are about to retry something that already failed;
- you notice you answered a different question than the one they asked;
- your own numbers or claims contradict each other.

## Skip it

- Happy cursing. "Fuck yeah, it works" needs no check.
- A message that answers a check you already asked. Act on the answer.

## Why it works

An agent that just got yelled at wants to make up for it by doing something, fast. That is how one misunderstanding becomes five. The restatement turns a frustrated message into a spec the person can check at a glance, and it gives the human a beat too: was the prompt clear, does the agent have the context they assume it has, is this the model or is it them?

[references/example-session.md](references/example-session.md) has a real exchange.
