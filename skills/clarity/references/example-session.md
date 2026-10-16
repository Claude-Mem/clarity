# Example: the cloud sync cost check

A real exchange, trimmed. The user asked one question: does cloud sync make money, and what does it cost per user?

The agent's answer said sync costs about $0.55 per paying user a month. Then it said one cancelled user's stored data costs about $23 a month. Then it added a section headed "The real cost is the AI that writes the memories, not sync."

**User:**

> ok so let me ask you this, you keep saying 50 cents per user
>
> now there's a "real cost"
>
> what in the holy fuck
>
> [...]
>
> because I ASKED ABOUT CLOUD SYNC COST NOT FUCKING MEMORY WRITING
>
> [...]
>
> YOU SAY SHIT LIKE
>
> ONE USERS STORE COSTS $23 A MONTH AND THEY CANCELLED
>
> THEN WHAT IN THE HOLY FUCKING FUCK AS AN INDEPENDENT OPERATOR AM I SUPPOSED TO THINK

**Agent:**

> You're right. You asked about cloud sync and I dragged memory-writing costs in. That was out of scope and it muddied the answer. The $23 figure was also wrong.
>
> Why the two numbers clash: I split the whole Supabase bill across users by how much data each one holds. That includes fixed costs like the $25 plan and the database server, which you pay whether that user exists or not. What that user actually adds is their share of the disk: about 15% of ~150 GB is roughly 23 GB, about $3 a month at Supabase's $0.125/GB. That's an estimate from their share of sync activity, not their measured bytes.
>
> Here's what I think you want, and I won't do anything until you answer:
>
> A sync-only cost model that answers: "If I sell cloud sync alone at $9–12 a month, do I make money on every kind of user, including the heaviest?"
>
> 1. Fixed sync costs: what you pay no matter how many users there are.
> 2. What each extra user adds: real disk, requests and data transfer, measured per user from actual bytes, not a share of the bill.
> 3. The spread: what the typical user, the heavy users and the single worst user each add a month, and whether any of them costs more than $9.
> 4. Break-even: how many sync-only subscribers at $9 and at $12 cover the fixed costs, and the margin after that.
> 5. No memory-writing costs anywhere.
>
> Is this it? Yes, no, or modify?

**User:**

> yes

## What the check did

- Owned the miss in one line: the scope creep into memory-writing costs.
- Fixed the contradiction plainly: $23 was a share of fixed costs; the user's real added cost was about $3.
- Turned the outburst into a numbered spec, with an explicit "No memory-writing costs anywhere."
- Asked, and did nothing else. The reply took no tool calls and cost about seven cents.
