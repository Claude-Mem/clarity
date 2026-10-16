"""Frustration spirals: how often you cursed at coding agents, what the agent did next, and what it cost.

Two sources, never mixed:
  1. claude-mem `user_prompts` (everything claude-mem has seen): every prompt you sent, for counts,
     spirals and time.
  2. Claude Code transcripts (~/.claude/projects, whatever Claude Code has not cleaned up yet): exact
     per-reply token usage, for tokens and dollars. Dollars use OpenRouter public list prices through
     the claude-mem agent-cost-report skill's own rate rules, so they are ESTIMATED list-price
     equivalents, not invoices.

The claude-mem `observations.discovery_tokens` column is the note-taker's own spend, not the coding
session's, so it is deliberately not used here.

Needs Python 3.9+ (standard library only) and the claude-mem plugin installed.

Usage:
  python3 evidence/spirals.py all --rule-date 2026-09-07       # everything below, in order
  python3 evidence/spirals.py prompts                          # claude-mem prompts -> counts by month
  python3 evidence/spirals.py sample --sample-size 80          # random flagged prompts, for a precision check
  python3 evidence/spirals.py transcripts                      # transcripts -> what each reply cost
  python3 evidence/spirals.py summary --rule-date 2026-09-07   # both -> <out>/summary.json
  python3 evidence/spirals.py hook                             # how often the plugin's hook would have fired

--rule-date is the day you started asking agents to stop and check when you curse.
Your prompt text is written to <out>/private/. It is yours; never commit it.
"""
import argparse
import datetime as dt
import glob
import json
import os
import random
import re
import sqlite3
import statistics
import sys

OUTPUT_DIR = "spirals-out"
SCRATCH_DIR = os.path.join(OUTPUT_DIR, "private")
RESULTS_DIR = OUTPUT_DIR
CLAUDE_MEM_DB_PATH = os.path.expanduser("~/.claude-mem/claude-mem.db")
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Everything before this day is "before the rule". Set with --rule-date.
RULE_FIRST_VERSION_DATE = dt.datetime(2026, 9, 7, tzinfo=dt.timezone.utc)

# A spiral keeps going while the next curse lands within this many of my prompts and minutes.
SPIRAL_MAX_PROMPT_GAP = 3
SPIRAL_MAX_MINUTES_GAP = 60

# Agents I type at directly. Bot seats, meeting bots and probes are other machinery.
INTERACTIVE_PLATFORM_SOURCES = {"claude", "codex", "gemini-cli", "hermes-cli", "kimi", "pi-agent", "grok-bot"}

# ---------------------------------------------------------------------------------------------
# Prompt classification
# ---------------------------------------------------------------------------------------------

MACHINE_PROMPT_MARKERS = (
    "<command-name>", "<command-message>", "<command-args>", "<local-command-stdout>",
    "<local-command-stderr>", "<local-command-caveat>", "<task-notification>", "<system-reminder>",
    "<bash-input>", "<bash-stdout>", "<bash-stderr>", "<user-prompt-submit-hook>", "<teammate-message>",
    "<scheduled-task", "<<autonomous-loop", "Caveat: The messages below were generated",
    "This session is being continued from a previous conversation", "[Request interrupted by user",
    "[SAND_HIDDEN_PROMPT]", "[Group chat:", "A message just arrived from another of your user's agents",
    "[The user handed the box back", "For EACH numbered user prompt below",
)
# Long "You are ..." prompts are briefs one agent wrote for another, not something I typed.
AGENT_BRIEF_PREFIX = "You are "
AGENT_BRIEF_MIN_LENGTH = 600
# In a long prompt my own words sit at the start and end; the middle is pasted logs or transcripts.
LONG_PROMPT_LENGTH = 2000
LONG_PROMPT_EDGE_LENGTH = 600

STRONG_PROFANITY_PATTERN = re.compile(
    r"\bf+u+c+k+\w*|\bf(?:c|u)kin[g']?\b|\bfking\b|\bfkn\b|\bmotherf\w*"
    r"|\bshit\w*|\b\w+shit\b|\bwtf\b|\bffs\b|\bstfu\b|\bjfc\b|\bfml\b|\bgtfo\b|\bomfg\b"
    r"|\bgod\s?damn\w*|\b(?:dumb|jack)?ass(?:hole|holes|hat|wipe)?\b"
    r"|\bcunt\w*|\btwat\w*|\bdickhead\w*|\bbitch\w*|\bbastard\w*|\bpiss(?:ed|ing|es)?\b",
    re.IGNORECASE,
)
DIRECTED_INSULT_PATTERN = re.compile(
    r"\b(?:you|u|ur|you'?re|youre)\s+(?:are\s+|r\s+)?(?:so\s+|such\s+an?\s+|an?\s+|completely\s+|fucking\s+)*"
    r"(?:idiot\w*|stupid\w*|moron\w*|dumb|retard\w*|useless|incompetent|brain-?dead)\b",
    re.IGNORECASE,
)
POSITIVE_PATTERN = re.compile(
    r"\bf+u+c+k+(?:ing)?\s+(?:yeah|yes|yea|ya|yess+)\b|\bhell\s+yeah\b|\bholy\s+(?:shit|fuck)\b"
    r"|\bf+u+c+k+ing\s+(?:love|awesome|amazing|beautiful|sexy|incredible|great|nice|cool|sick|dope"
    r"|genius|brilliant|perfect|killer|legit|good|epic|rad)\b"
    r"|\blove\s+(?:it|this|that|you|u)\b|\bbadass\b|\bawesome\b|\bamazing\b|\bperfect\b|\blfg\b"
    r"|\bnailed\s+it\b|\bsexy\b|\bbeautiful\b|\b(?:great|nice|good)\s+(?:job|work)\b|\bkick(?:s|ing)?\s+ass\b",
    re.IGNORECASE,
)
NEGATIVE_PATTERN = re.compile(
    r"\bwhy\b|\bwhat\s+the\b|\byou\s+(?:keep|always|never|didn'?t|did\s+not|are\s+not|aren'?t|broke"
    r"|ignored|forgot|lied|missed|skipped|changed|deleted|removed|still|just)\b|\bu\s+(?:keep|didn'?t|broke)\b"
    r"|\bi\s+(?:said|told|asked|already|just\s+said)\b|\bnot\s+what\s+i\b|\bstop\b|\bwrong\b|\bagain\b"
    r"|\bseriously\b|\bno\s+no\b|\blisten\b|\bhow\s+many\s+times\b|\bare\s+you\s+(?:kidding|serious)\b"
    r"|\?!|!!|\buseless\b|\bdoesn'?t\s+work\b|\bbroken?\b|\bstill\s+(?:not|doesn'?t|broken|failing)\b"
    r"|\bgaslight\w*|\bmiserable\b|\bwaste\w*\b|\bridiculous\b|\bcan'?t\s+believe\b|\bnot\s+working\b"
    r"|\bstupid\b|\bidiot\b|\bwtf\b",
    re.IGNORECASE,
)
CODE_OR_PATH_PATTERN = re.compile(r"```.*?```|`[^`]*`|https?://\S+|\S*[/\\_]\S*", re.DOTALL)
WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z']+")
SHOUT_ALLOWLIST = {
    "API", "APIS", "URL", "URLS", "JSON", "MCP", "PR", "PRS", "CI", "UI", "UX", "CLI", "SDK", "HTTP", "HTTPS",
    "AWS", "GPU", "LLM", "LLMS", "SQL", "AI", "OK", "ID", "IDS", "DB", "CSS", "HTML", "JS", "TS", "MD", "YAML",
    "README", "CLAUDE", "AGENTS", "TODO", "GET", "POST", "PUT", "PATCH", "DELETE", "ERROR", "WARN", "INFO",
    "DEBUG", "NULL", "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "IS", "AS", "ON", "BY", "JOIN",
    "ORDER", "GROUP", "LIMIT", "INSERT", "UPDATE", "INTO", "VALUES", "TRUE", "FALSE", "NPM", "PNPM", "MIT",
    "GPT", "XML", "PDF", "PNG", "SVG", "SSE", "WS", "SSH", "DNS", "SSL", "TLS", "CORS", "JWT", "OAUTH", "USD",
    "ASAP", "FYI", "IIRC", "IMO", "TLDR", "ETA", "QA", "MVP", "ROI", "ARR", "MRR", "SAAS", "PST", "PDT", "PT",
    "UTC", "EST", "CEO", "CTO", "OS", "VM", "VPS", "CPU", "RAM", "SSD", "MB", "GB", "KB", "TB", "IO", "PID",
    "ENV", "PATH", "HOME", "USER", "GH", "CMEM", "MEM", "SQLITE", "FTS", "RAG", "OCR", "TTS", "STT", "IOS",
    "MACOS", "PWA", "SEO", "CTA", "OG", "LP", "AB", "VS", "NO", "YES", "II", "III", "IV", "TBD", "WIP", "EOD",
}


def measure_shouting(prompt_text):
    """(share of words in ALL CAPS, longest ALL CAPS run, ALL CAPS word count) outside code, paths, acronyms."""
    words = WORD_PATTERN.findall(CODE_OR_PATH_PATTERN.sub(" ", prompt_text))
    if not words:
        return 0.0, 0, 0
    is_shouted_word = [len(word) >= 2 and word.isupper() and word.strip("'") not in SHOUT_ALLOWLIST for word in words]
    longest_shouted_run = current_run = 0
    for shouted in is_shouted_word:
        current_run = current_run + 1 if shouted else 0
        longest_shouted_run = max(longest_shouted_run, current_run)
    shouted_word_count = sum(is_shouted_word)
    return shouted_word_count / len(words), longest_shouted_run, shouted_word_count


def own_words(prompt_text):
    """The part of a prompt I most likely typed myself: code blocks out, long pastes trimmed to the edges."""
    without_code_blocks = re.sub(r"```.*?```", " ", prompt_text, flags=re.DOTALL)
    if len(without_code_blocks) <= LONG_PROMPT_LENGTH:
        return without_code_blocks
    return without_code_blocks[:LONG_PROMPT_EDGE_LENGTH] + "\n" + without_code_blocks[-LONG_PROMPT_EDGE_LENGTH:]


def classify_prompt(prompt_text):
    """Profanity, insults aimed at the agent and shouting, minus prompts that are only happy cursing.

    Shouting alone counts when nearly the whole prompt is caps, or a caps run comes with a complaint;
    caps used for emphasis inside a calm instruction does not."""
    text = own_words(prompt_text)
    profanity_hits = STRONG_PROFANITY_PATTERN.findall(text)
    is_directed_insult = bool(DIRECTED_INSULT_PATTERN.search(text))
    is_positive = bool(POSITIVE_PATTERN.search(text))
    is_negative = bool(NEGATIVE_PATTERN.search(text))
    shouted_share, longest_shouted_run, shouted_word_count = measure_shouting(text)
    is_shouting = (shouted_word_count >= 3 and shouted_share >= 0.6) or (longest_shouted_run >= 4 and is_negative)
    has_cursing_signal = bool(profanity_hits) or is_directed_insult or is_shouting
    is_happy_cursing_only = is_positive and not is_negative
    return dict(
        is_curse=has_cursing_signal and not is_happy_cursing_only,
        is_happy_cursing=has_cursing_signal and is_happy_cursing_only,
        profanity_count=len(profanity_hits),
        is_directed_insult=is_directed_insult,
        is_shouting=is_shouting,
    )


def is_machine_prompt(prompt_text):
    stripped = prompt_text.lstrip()
    if not stripped or any(marker in prompt_text[:400] for marker in MACHINE_PROMPT_MARKERS):
        return True
    return stripped.startswith(AGENT_BRIEF_PREFIX) and len(stripped) >= AGENT_BRIEF_MIN_LENGTH


# ---------------------------------------------------------------------------------------------
# Source 1: a year of prompts from claude-mem
# ---------------------------------------------------------------------------------------------

def load_year_of_prompts():
    """Distinct human prompts from interactive agents, oldest first, with classification."""
    connection = sqlite3.connect(f"file:{CLAUDE_MEM_DB_PATH}?mode=ro", uri=True)
    rows = connection.execute(
        """
        select p.content_session_id, p.prompt_number, p.prompt_text, p.created_at_epoch,
               coalesce(s.platform_source, '(none)'), coalesce(s.project, '')
        from user_prompts p
        left join sdk_sessions s on s.content_session_id = p.content_session_id
        order by p.created_at_epoch asc, p.id asc
        """
    ).fetchall()
    connection.close()

    # Sync copies and parallel sends of one prompt land as near-identical rows; keep the first.
    duplicate_window_ms = 120_000
    seen_session_prompt_keys, last_seen_epoch_by_text = set(), {}
    prompts, dropped = [], dict(duplicate=0, machine=0, non_interactive_platform=0)
    for session_id, prompt_number, prompt_text, created_at_epoch_ms, platform_source, project in rows:
        session_prompt_key = (session_id, prompt_number)
        normalized_text = " ".join(prompt_text.split())
        previous_epoch_for_text = last_seen_epoch_by_text.get(normalized_text)
        is_repeat_of_recent_text = (len(normalized_text) >= 20 and previous_epoch_for_text is not None
                                    and created_at_epoch_ms - previous_epoch_for_text <= duplicate_window_ms)
        if session_prompt_key in seen_session_prompt_keys or is_repeat_of_recent_text or (
                previous_epoch_for_text == created_at_epoch_ms):
            dropped["duplicate"] += 1
            continue
        seen_session_prompt_keys.add(session_prompt_key)
        last_seen_epoch_by_text[normalized_text] = created_at_epoch_ms
        if platform_source not in INTERACTIVE_PLATFORM_SOURCES:
            dropped["non_interactive_platform"] += 1
            continue
        if is_machine_prompt(prompt_text):
            dropped["machine"] += 1
            continue
        prompts.append(dict(
            session_id=session_id, prompt_number=prompt_number, epoch_ms=created_at_epoch_ms,
            platform_source=platform_source, project=project, text=prompt_text, **classify_prompt(prompt_text),
        ))
    return prompts, dropped


def group_by_session(prompts):
    sessions = {}
    for prompt in prompts:
        sessions.setdefault(prompt["session_id"], []).append(prompt)
    for session_prompts in sessions.values():
        session_prompts.sort(key=lambda p: (p["epoch_ms"], p["prompt_number"]))
    return sessions


def prompt_epoch_ms(prompt):
    """Prompts from claude-mem carry epoch_ms; transcript rows carry an ISO timestamp."""
    return prompt["epoch_ms"] if "epoch_ms" in prompt else parse_timestamp(prompt["ts"]).timestamp() * 1000


def find_spirals(session_prompts):
    """Runs of curse prompts where each next curse lands within SPIRAL_MAX_PROMPT_GAP prompts and
    SPIRAL_MAX_MINUTES_GAP minutes of the previous one. Returns [(first_index, last_index)]."""
    curse_indexes = [i for i, p in enumerate(session_prompts) if p["is_curse"]]
    spirals = []
    for index in curse_indexes:
        if spirals:
            previous_curse = session_prompts[spirals[-1][1]]
            minutes_since_previous_curse = (prompt_epoch_ms(session_prompts[index]) - prompt_epoch_ms(previous_curse)) / 60000
            if index - spirals[-1][1] <= SPIRAL_MAX_PROMPT_GAP and minutes_since_previous_curse <= SPIRAL_MAX_MINUTES_GAP:
                spirals[-1][1] = index
                continue
        spirals.append([index, index])
    return [tuple(spiral) for spiral in spirals]


def command_prompts():
    prompts, dropped = load_year_of_prompts()
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    with open(os.path.join(SCRATCH_DIR, "prompts.jsonl"), "w") as output_file:
        for prompt in prompts:
            output_file.write(json.dumps(prompt) + "\n")
    curse_prompts = [p for p in prompts if p["is_curse"]]
    print(f"human prompts kept: {len(prompts)}  dropped: {dropped}")
    print(f"curse prompts: {len(curse_prompts)}  happy-cursing prompts excluded: {sum(p['is_happy_cursing'] for p in prompts)}")
    print(f"  with profanity: {sum(p['profanity_count'] > 0 for p in curse_prompts)}"
          f"  shouting: {sum(p['is_shouting'] for p in curse_prompts)}"
          f"  directed insult: {sum(p['is_directed_insult'] for p in curse_prompts)}")
    by_month = {}
    for prompt in prompts:
        month = dt.datetime.fromtimestamp(prompt["epoch_ms"] / 1000, dt.timezone.utc).strftime("%Y-%m")
        counts = by_month.setdefault(month, [0, 0])
        counts[0] += 1
        counts[1] += prompt["is_curse"]
    for month, (prompt_count, curse_count) in sorted(by_month.items()):
        print(f"  {month}  prompts {prompt_count:5d}  curses {curse_count:4d}  ({100 * curse_count / prompt_count:4.1f}%)")


def command_sample(sample_size=60, seed=7):
    """Print a seeded random sample of flagged prompts (truncated) for a hand precision check."""
    with open(os.path.join(SCRATCH_DIR, "prompts.jsonl")) as input_file:
        prompts = [json.loads(line) for line in input_file]
    flagged = [p for p in prompts if p["is_curse"]]
    random.Random(seed).shuffle(flagged)
    for number, prompt in enumerate(flagged[:sample_size], 1):
        flat_text = " ".join(prompt["text"].split())
        signals = "".join(["P" if prompt["profanity_count"] else "-", "S" if prompt["is_shouting"] else "-",
                           "I" if prompt["is_directed_insult"] else "-"])
        print(f"{number:3d} [{signals}] {flat_text[:220]}")


# ---------------------------------------------------------------------------------------------
# Source 2: Claude Code transcripts, for tokens and dollars
# ---------------------------------------------------------------------------------------------

AGENT_COST_REPORT_SCRIPTS_GLOB = os.path.expanduser(
    "~/.claude/plugins/cache/thedotmack/claude-mem/*/skills/agent-cost-report/scripts")
INTERACTIVE_ENTRYPOINTS = {"cli", "claude-desktop"}
CLARITY_QUESTION_PATTERN = re.compile(r"is this it\?|yes, no,? or modify", re.IGNORECASE)
COMMAND_ARGS_PATTERN = re.compile(r"<command-args>(.*?)</command-args>", re.DOTALL)


def load_price_table():
    """OpenRouter public list prices through the agent-cost-report skill's own rate rules."""
    scripts_dir = sorted(glob.glob(AGENT_COST_REPORT_SCRIPTS_GLOB))[-1]
    sys.path.insert(0, scripts_dir)
    from acr import prices as agent_cost_report_prices
    saved_prices_path = os.path.join(RESULTS_DIR, "prices.json")
    if os.path.exists(saved_prices_path):
        price_document = agent_cost_report_prices.load(saved_prices_path)
    else:
        price_document = agent_cost_report_prices.fetch(OPENROUTER_MODELS_URL)
        agent_cost_report_prices.write(price_document, RESULTS_DIR)
    return lambda model: agent_cost_report_prices.rate(model, price_document["models"]), price_document


def parse_timestamp(iso_text):
    return dt.datetime.fromisoformat(iso_text.replace("Z", "+00:00"))


def human_prompt_text(event):
    """The text I typed, or None when the user line is a tool result, a hook, or other machinery."""
    if event.get("isMeta") or event.get("isCompactSummary") or event.get("isSidechain"):
        return None
    content = (event.get("message") or {}).get("content")
    if isinstance(content, list):
        if any(isinstance(block, dict) and block.get("type") == "tool_result" for block in content):
            return None
        content = "\n".join(block.get("text", "") for block in content
                            if isinstance(block, dict) and block.get("type") == "text")
    if not isinstance(content, str) or not content.strip():
        return None
    command_args = COMMAND_ARGS_PATTERN.search(content)
    if command_args:
        return command_args.group(1).strip() or None
    return None if is_machine_prompt(content) else content


def read_transcript_file(path, model_calls_by_key, collect_prompts):
    """Stream one transcript. Model calls are deduped on (message.id, requestId) across lines,
    keeping the largest usage seen; tool names and text are gathered from every content line."""
    entrypoint, prompts = None, []
    with open(path, errors="ignore") as transcript_file:
        for line in transcript_file:
            if '"type":"assistant"' not in line and '"type":"user"' not in line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            entrypoint = entrypoint or event.get("entrypoint")
            if event.get("type") == "user" and collect_prompts and event.get("timestamp"):
                prompt_text = human_prompt_text(event)
                if prompt_text:
                    prompts.append(dict(ts=parse_timestamp(event["timestamp"]), text=prompt_text))
                continue
            message = event.get("message") or {}
            usage = message.get("usage")
            if event.get("type") != "assistant" or not usage or not event.get("timestamp"):
                continue
            call_key = (message.get("id"), event.get("requestId"))
            cache_creation = usage.get("cache_creation") or {}
            cache_write_total = usage.get("cache_creation_input_tokens", 0) or 0
            cache_write_1h = cache_creation.get("ephemeral_1h_input_tokens", 0) or 0
            token_counts = dict(
                input=usage.get("input_tokens", 0) or 0, output=usage.get("output_tokens", 0) or 0,
                cache_read=usage.get("cache_read_input_tokens", 0) or 0,
                cache_write_1h=cache_write_1h, cache_write_5m=max(cache_write_total - cache_write_1h, 0))
            call = model_calls_by_key.setdefault(call_key, dict(
                ts=parse_timestamp(event["timestamp"]), session_id=event.get("sessionId"),
                model=message.get("model"), is_subagent=bool(event.get("isSidechain")),
                tool_names=[], text="", **{name: 0 for name in token_counts}))
            for name, count in token_counts.items():
                call[name] = max(call[name], count)
            for block in message.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    call["tool_names"].append(block.get("name"))
                elif block.get("type") == "text":
                    call["text"] += block.get("text", "")
    return entrypoint, prompts


def command_transcripts():
    """One row per human prompt in interactive sessions: what the agent spent until my next prompt."""
    rate_for_model, price_document = load_price_table()
    projects_root = os.path.expanduser("~/.claude/projects")
    main_transcript_paths = glob.glob(os.path.join(projects_root, "*", "*.jsonl"))
    subagent_transcript_paths = glob.glob(os.path.join(projects_root, "*", "*", "subagents", "*.jsonl"))

    model_calls_by_key, prompts_by_session, project_by_session = {}, {}, {}
    for path in main_transcript_paths:
        session_id = os.path.basename(path)[:-len(".jsonl")]
        entrypoint, prompts = read_transcript_file(path, model_calls_by_key, collect_prompts=True)
        if entrypoint in INTERACTIVE_ENTRYPOINTS and prompts:
            prompts_by_session[session_id] = sorted(prompts, key=lambda p: p["ts"])
            project_by_session[session_id] = os.path.basename(os.path.dirname(path))
    for path in subagent_transcript_paths:
        read_transcript_file(path, model_calls_by_key, collect_prompts=False)

    unpriced_models = {}
    calls_by_session = {}
    for call in model_calls_by_key.values():
        if call["session_id"] not in prompts_by_session:
            continue
        rate = rate_for_model(call["model"])
        if rate is None:
            unpriced_models[call["model"]] = unpriced_models.get(call["model"], 0) + 1
            call["cost_usd"] = 0.0
        else:
            call["cost_usd"] = (call["input"] * rate["input_usd_per_mtok"] + call["output"] * rate["output_usd_per_mtok"]
                                + call["cache_read"] * rate["cache_read"] + call["cache_write_5m"] * rate["cache_write"]
                                + call["cache_write_1h"] * rate["cache_write_1h"]) / 1e6
        calls_by_session.setdefault(call["session_id"], []).append(call)

    rows = []
    for session_id, prompts in prompts_by_session.items():
        calls = sorted(calls_by_session.get(session_id, []), key=lambda c: c["ts"])
        call_index = 0
        for prompt_index, prompt in enumerate(prompts):
            window_end = prompts[prompt_index + 1]["ts"] if prompt_index + 1 < len(prompts) else None
            while call_index < len(calls) and calls[call_index]["ts"] < prompt["ts"]:
                call_index += 1
            window_calls = []
            while call_index < len(calls) and (window_end is None or calls[call_index]["ts"] < window_end):
                window_calls.append(calls[call_index])
                call_index += 1
            main_thread_calls = [c for c in window_calls if not c["is_subagent"]]
            reply_text = "\n".join(c["text"] for c in main_thread_calls if c["text"])
            rows.append(dict(
                session_id=session_id, project=project_by_session[session_id], prompt_index=prompt_index,
                ts=prompt["ts"].isoformat(), next_prompt_ts=window_end.isoformat() if window_end else None,
                text=prompt["text"], **classify_prompt(prompt["text"]),
                model_calls=len(window_calls),
                tool_calls=sum(len(c["tool_names"]) for c in main_thread_calls),
                subagent_calls=sum(c["is_subagent"] for c in window_calls),
                asked_clarity_question=bool(CLARITY_QUESTION_PATTERN.search(reply_text)),
                reply_seconds=(window_calls[-1]["ts"] - prompt["ts"]).total_seconds() if window_calls else 0.0,
                reply_text_head=reply_text[:300],
                cost_usd=sum(c["cost_usd"] for c in window_calls),
                **{name: sum(c[name] for c in window_calls)
                   for name in ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h")},
            ))
    rows.sort(key=lambda r: r["ts"])
    with open(os.path.join(SCRATCH_DIR, "transcript_prompts.jsonl"), "w") as output_file:
        for row in rows:
            output_file.write(json.dumps(row) + "\n")
    curse_rows = [r for r in rows if r["is_curse"]]
    print(f"interactive sessions: {len(prompts_by_session)}  human prompts: {len(rows)}  curse prompts: {len(curse_rows)}")
    print(f"span: {rows[0]['ts'][:10]} .. {rows[-1]['ts'][:10]}  priced with OpenRouter list fetched {price_document.get('fetched')}")
    print(f"total cost in interactive sessions: ${sum(r['cost_usd'] for r in rows):,.2f}  unpriced calls: {unpriced_models}")


# ---------------------------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------------------------

# Sessions to leave out, such as the one running this analysis if it quotes angry messages.
# Set with --exclude-session.
EXCLUDED_SESSION_IDS = set()
YES_ANSWER_PATTERN = re.compile(
    r"^\W*(?:yes|yep|yeah|yea|y|correct|exactly|do it|go|ok(?:ay)?,? do it|perfect|sounds good|that'?s it|this is it)\b",
    re.IGNORECASE)
NEXT_PROMPTS_WINDOW = 3


def epoch_ms_to_datetime(epoch_ms):
    return dt.datetime.fromtimestamp(epoch_ms / 1000, dt.timezone.utc)


def bootstrap_difference_in_means(first_values, second_values, resamples=10_000, seed=2026):
    """mean(first) - mean(second) with a 95% percentile bootstrap interval."""
    random_generator = random.Random(seed)
    differences = sorted(
        statistics.mean(random_generator.choices(first_values, k=len(first_values)))
        - statistics.mean(random_generator.choices(second_values, k=len(second_values)))
        for _ in range(resamples))
    return dict(point=round(statistics.mean(first_values) - statistics.mean(second_values), 2),
                low=round(differences[int(0.025 * resamples)], 2), high=round(differences[int(0.975 * resamples)], 2))


def describe(values):
    if not values:
        return dict(n=0)
    ordered = sorted(values)
    return dict(n=len(values), total=round(sum(values), 2), mean=round(statistics.mean(values), 2),
                median=round(statistics.median(values), 2), p90=round(ordered[int(0.9 * (len(ordered) - 1))], 2),
                max=round(ordered[-1], 2))


def summarize_spirals(sessions, keep_session=lambda session_prompts: True, keep_spiral=lambda first_prompt: True):
    """Spiral counts and sizes for the sessions and spirals that pass the filters."""
    curse_count = spiral_count = repeat_spiral_count = followup_curse_count = 0
    curses_per_repeat_spiral, minutes_per_repeat_spiral, prompts_per_repeat_spiral = [], [], []
    for session_prompts in sessions.values():
        if not keep_session(session_prompts):
            continue
        for first_index, last_index in find_spirals(session_prompts):
            if not keep_spiral(session_prompts[first_index]):
                continue
            spiral_curses = sum(p["is_curse"] for p in session_prompts[first_index:last_index + 1])
            curse_count += spiral_curses
            spiral_count += 1
            if spiral_curses >= 2:
                repeat_spiral_count += 1
                followup_curse_count += spiral_curses - 1
                curses_per_repeat_spiral.append(spiral_curses)
                prompts_per_repeat_spiral.append(last_index - first_index + 1)
                minutes_per_repeat_spiral.append(
                    (session_prompts[last_index]["epoch_ms"] - session_prompts[first_index]["epoch_ms"]) / 60000)
    return dict(
        curse_prompts=curse_count, spirals=spiral_count, spirals_with_repeat_cursing=repeat_spiral_count,
        share_of_curses_that_repeat=round(repeat_spiral_count / spiral_count, 3) if spiral_count else None,
        followup_curses=followup_curse_count,
        curses_per_repeat_spiral=describe(curses_per_repeat_spiral),
        prompts_per_repeat_spiral=describe(prompts_per_repeat_spiral),
        minutes_per_repeat_spiral=describe(minutes_per_repeat_spiral),
    )


def load_observation_counts_by_prompt():
    """{(content_session_id, prompt_number): observations recorded for the work done on that prompt}."""
    connection = sqlite3.connect(f"file:{CLAUDE_MEM_DB_PATH}?mode=ro", uri=True)
    rows = connection.execute(
        """
        select coalesce(o.content_session_id, s.content_session_id), o.prompt_number, count(*)
        from observations o left join sdk_sessions s on s.memory_session_id = o.memory_session_id
        where o.prompt_number is not null and coalesce(o.content_session_id, s.content_session_id) is not null
        group by 1, 2
        """
    ).fetchall()
    connection.close()
    return {(session_id, prompt_number): count for session_id, prompt_number, count in rows}


def summarize_agent_action_after_curses(sessions, observation_counts, period_filter):
    """In sessions where claude-mem linked observations to prompts, did the agent do recorded work in
    response to each curse, and did I curse again within the next prompts?"""
    linked_sessions = {session_id for session_id, _ in observation_counts}
    acted, held = [], []
    for session_id, session_prompts in sessions.items():
        if session_id not in linked_sessions:
            continue
        for index, prompt in enumerate(session_prompts):
            if not prompt["is_curse"] or not period_filter(prompt):
                continue
            next_prompts = session_prompts[index + 1:index + 1 + NEXT_PROMPTS_WINDOW]
            if not next_prompts:
                continue
            cursed_again = any(p["is_curse"] for p in next_prompts)
            observation_count = observation_counts.get((session_id, prompt["prompt_number"]), 0)
            (acted if observation_count > 0 else held).append(cursed_again)
    total = len(acted) + len(held)
    return dict(
        curse_prompts_with_followups=total,
        agent_did_recorded_work=len(acted),
        share_agent_did_recorded_work=round(len(acted) / total, 3) if total else None,
        cursed_again_after_work=round(sum(acted) / len(acted), 3) if acted else None,
        cursed_again_after_no_work=round(sum(held) / len(held), 3) if held else None,
    )


def response_type(row):
    if row["model_calls"] == 0:
        return "no_reply"
    if row["asked_clarity_question"]:
        return "clarity_check" if row["tool_calls"] == 0 else "clarity_check_after_tools"
    return "acted_first" if row["tool_calls"] > 0 else "talked_only"


def load_transcript_sessions():
    with open(os.path.join(SCRATCH_DIR, "transcript_prompts.jsonl")) as input_file:
        rows = [json.loads(line) for line in input_file]
    sessions = {}
    for row in rows:
        if row["session_id"] in EXCLUDED_SESSION_IDS:
            continue
        row["tokens"] = row["input"] + row["output"] + row["cache_read"] + row["cache_write_5m"] + row["cache_write_1h"]
        sessions.setdefault(row["session_id"], []).append(row)
    for session_id, session_rows in sessions.items():
        session_rows.sort(key=lambda r: r["prompt_index"])
        # A prompt that got no reply and was sent again word for word is one event, not two.
        sessions[session_id] = [row for index, row in enumerate(session_rows)
                                if not (row["model_calls"] == 0 and index + 1 < len(session_rows)
                                        and session_rows[index + 1]["text"].strip() == row["text"].strip())]
    return sessions


def summarize_transcripts(transcript_sessions):
    by_type = {}
    for session_rows in transcript_sessions.values():
        for index, row in enumerate(session_rows):
            if not row["is_curse"]:
                continue
            next_row = session_rows[index + 1] if index + 1 < len(session_rows) else None
            bucket = by_type.setdefault(response_type(row), dict(
                cost=[], tokens=[], output_tokens=[], seconds=[], tool_calls=[], next_yes=0, next_curse=0,
                with_next=0, rejected_cost=0.0, rejected_tokens=0, rejected_seconds=0.0, session_ended=0))
            bucket["cost"].append(row["cost_usd"])
            bucket["tokens"].append(row["tokens"])
            bucket["output_tokens"].append(row["output"])
            bucket["seconds"].append(row["reply_seconds"])
            bucket["tool_calls"].append(row["tool_calls"])
            if next_row is None:
                bucket["session_ended"] += 1
                continue
            bucket["with_next"] += 1
            if YES_ANSWER_PATTERN.search(next_row["text"]):
                bucket["next_yes"] += 1
            if next_row["is_curse"]:
                bucket["next_curse"] += 1
                bucket["rejected_cost"] += row["cost_usd"]
                bucket["rejected_tokens"] += row["tokens"]
                bucket["rejected_seconds"] += row["reply_seconds"]
    response_summary = {}
    for name, bucket in by_type.items():
        response_summary[name] = dict(
            curse_prompts=len(bucket["cost"]), cost_usd=describe(bucket["cost"]), tokens=describe(bucket["tokens"]),
            output_tokens=describe(bucket["output_tokens"]), reply_minutes=describe([s / 60 for s in bucket["seconds"]]),
            tool_calls=describe(bucket["tool_calls"]), with_next_prompt=bucket["with_next"],
            next_prompt_is_yes=bucket["next_yes"], next_prompt_is_curse=bucket["next_curse"],
            session_ended_after=bucket["session_ended"],
            spend_on_replies_cursed_at_usd=round(bucket["rejected_cost"], 2),
            tokens_on_replies_cursed_at=bucket["rejected_tokens"],
            minutes_on_replies_cursed_at=round(bucket["rejected_seconds"] / 60, 1),
        )
    acted_first_rows, clarity_rows = [], []
    for session_rows in transcript_sessions.values():
        for row in session_rows:
            if row["is_curse"] and response_type(row) == "acted_first":
                acted_first_rows.append(row)
            elif row["is_curse"] and response_type(row) == "clarity_check":
                clarity_rows.append(row)
    difference_in_means = {
        metric: bootstrap_difference_in_means([extract(r) for r in acted_first_rows], [extract(r) for r in clarity_rows])
        for metric, extract in (("cost_usd", lambda r: r["cost_usd"]), ("tokens", lambda r: r["tokens"]),
                                ("reply_minutes", lambda r: r["reply_seconds"] / 60))
    }

    spirals = []
    for session_rows in transcript_sessions.values():
        for first_index, last_index in find_spirals(session_rows):
            spiral_rows = session_rows[first_index:last_index + 1]
            curse_rows = [r for r in spiral_rows if r["is_curse"]]
            started = parse_timestamp(spiral_rows[0]["ts"])
            last_reply_end = parse_timestamp(spiral_rows[-1]["ts"]) + dt.timedelta(seconds=spiral_rows[-1]["reply_seconds"])
            spirals.append(dict(
                curses=len(curse_rows), cost_usd=sum(r["cost_usd"] for r in spiral_rows),
                tokens=sum(r["tokens"] for r in spiral_rows),
                minutes=(last_reply_end - started).total_seconds() / 60,
                any_acted_first=any(response_type(r) == "acted_first" for r in curse_rows),
                all_clarity=all(response_type(r).startswith("clarity_check") for r in curse_rows),
            ))
    repeat_spirals = [s for s in spirals if s["curses"] >= 2]

    def spiral_group(group):
        return dict(spirals=len(group), curses=describe([s["curses"] for s in group]),
                    cost_usd=describe([s["cost_usd"] for s in group]), tokens=describe([s["tokens"] for s in group]),
                    minutes=describe([s["minutes"] for s in group]))

    all_rows = [r for session_rows in transcript_sessions.values() for r in session_rows]
    return dict(
        window=[min(r["ts"] for r in all_rows)[:10], max(r["ts"] for r in all_rows)[:10]],
        interactive_sessions=len(transcript_sessions), human_prompts=len(all_rows),
        curse_prompts=sum(r["is_curse"] for r in all_rows),
        total_cost_usd=round(sum(r["cost_usd"] for r in all_rows), 2),
        total_tokens=sum(r["tokens"] for r in all_rows),
        clarity_questions_asked_without_cursing=sum(
            1 for r in all_rows if r["asked_clarity_question"] and not r["is_curse"]),
        by_response_type=response_summary,
        acted_first_minus_clarity_check_mean_with_95ci=difference_in_means,
        repeat_spirals_with_any_act_first=spiral_group([s for s in repeat_spirals if s["any_acted_first"]]),
        repeat_spirals_all_clarity=spiral_group([s for s in repeat_spirals if s["all_clarity"]]),
        all_spirals=spiral_group(spirals),
    )


def estimate_year_before_rule(year, transcripts):
    """ESTIMATE, not a measurement: the year before the rule has prompts but no token logs.

    Every follow-up curse means the reply before it missed. Before the rule the agent did real work
    on a share of curses; each of those work-first misses is priced at the measured mean gap between
    an act-first reply and a clarity check (last ~7 weeks, today's models, OpenRouter list prices)."""
    followup_curses = year["spirals_claude_before_rule"]["followup_curses"]
    share_acted = year["agent_action_claude_before_rule"]["share_agent_did_recorded_work"]
    work_first_misses = followup_curses * share_acted
    gap = transcripts["acted_first_minus_clarity_check_mean_with_95ci"]
    scale = lambda interval: {bound: round(work_first_misses * value) for bound, value in interval.items()}
    return dict(
        label="ESTIMATE",
        followup_curses_in_claude_sessions_before_rule=followup_curses,
        share_of_curses_followed_by_agent_work_before_rule=share_acted,
        work_first_misses=round(work_first_misses),
        avoidable_usd_at_list_price=scale(gap["cost_usd"]),
        avoidable_tokens=scale(gap["tokens"]),
        avoidable_agent_hours={bound: round(work_first_misses * value / 60, 1) for bound, value in gap["reply_minutes"].items()},
    )


def command_summary():
    with open(os.path.join(SCRATCH_DIR, "prompts.jsonl")) as input_file:
        prompts = [p for p in map(json.loads, input_file) if p["session_id"] not in EXCLUDED_SESSION_IDS]
    sessions = group_by_session(prompts)
    rule_start_ms = RULE_FIRST_VERSION_DATE.timestamp() * 1000
    is_before_rule = lambda prompt: prompt["epoch_ms"] < rule_start_ms
    is_after_rule = lambda prompt: prompt["epoch_ms"] >= rule_start_ms
    is_platform = lambda *platforms: (lambda session_prompts: session_prompts[0]["platform_source"] in platforms)

    curses_by_day = {}
    for prompt in prompts:
        if prompt["is_curse"]:
            day = epoch_ms_to_datetime(prompt["epoch_ms"]).astimezone(dt.timezone(dt.timedelta(hours=-8))).date().isoformat()
            curses_by_day[day] = curses_by_day.get(day, 0) + 1
    by_month = {}
    for prompt in prompts:
        month = epoch_ms_to_datetime(prompt["epoch_ms"]).strftime("%Y-%m")
        counts = by_month.setdefault(month, dict(human_prompts=0, curse_prompts=0))
        counts["human_prompts"] += 1
        counts["curse_prompts"] += prompt["is_curse"]
    rule_days_after = (max(p["epoch_ms"] for p in prompts) - rule_start_ms) / 86_400_000
    rule_days_before = (rule_start_ms - min(p["epoch_ms"] for p in prompts)) / 86_400_000

    observation_counts = load_observation_counts_by_prompt()
    claude_sessions = {sid: sp for sid, sp in sessions.items() if sp[0]["platform_source"] == "claude"}
    year = dict(
        window=[epoch_ms_to_datetime(prompts[0]["epoch_ms"]).date().isoformat(),
                epoch_ms_to_datetime(prompts[-1]["epoch_ms"]).date().isoformat()],
        human_prompts=len(prompts), curse_prompts=sum(p["is_curse"] for p in prompts),
        happy_cursing_prompts_excluded=sum(p["is_happy_cursing"] for p in prompts),
        sessions_with_a_curse=sum(any(p["is_curse"] for p in sp) for sp in sessions.values()),
        sessions=len(sessions), by_month=by_month,
        worst_days=sorted(curses_by_day.items(), key=lambda kv: -kv[1])[:8],
        days_before_rule=round(rule_days_before), days_after_rule=round(rule_days_after),
        spirals_all=summarize_spirals(sessions),
        spirals_claude_before_rule=summarize_spirals(sessions, is_platform("claude"), is_before_rule),
        spirals_claude_after_rule=summarize_spirals(sessions, is_platform("claude"), is_after_rule),
        spirals_codex_before_rule=summarize_spirals(sessions, is_platform("codex"), is_before_rule),
        spirals_codex_after_rule=summarize_spirals(sessions, is_platform("codex"), is_after_rule),
        agent_action_claude_before_rule=summarize_agent_action_after_curses(claude_sessions, observation_counts, is_before_rule),
        agent_action_claude_after_rule=summarize_agent_action_after_curses(claude_sessions, observation_counts, is_after_rule),
    )
    # The year-long "before" mixes in last winter's much angrier months; the fair comparison is the
    # stretch right before the rule.
    is_in_60_days_before_rule = lambda prompt: rule_start_ms - 60 * 86_400_000 <= prompt["epoch_ms"] < rule_start_ms
    year["spirals_claude_60_days_before_rule"] = summarize_spirals(sessions, is_platform("claude"), is_in_60_days_before_rule)
    for label, period_filter in (("before", is_before_rule), ("60_days_before", is_in_60_days_before_rule),
                                 ("after", is_after_rule)):
        period_prompts = [p for p in prompts if p["platform_source"] == "claude" and period_filter(p)]
        year[f"curse_rate_claude_{label}_rule"] = round(sum(p["is_curse"] for p in period_prompts) / len(period_prompts), 4)

    transcripts = summarize_transcripts(load_transcript_sessions())
    summary = dict(
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        rule_date=RULE_FIRST_VERSION_DATE.date().isoformat(),
        spiral_definition=(f"curse prompts in one session where each next curse lands within {SPIRAL_MAX_PROMPT_GAP} "
                           f"of my prompts and {SPIRAL_MAX_MINUTES_GAP} minutes"),
        year=year,
        transcripts=transcripts,
        estimate=estimate_year_before_rule(year, transcripts),
    )
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "summary.json"), "w") as output_file:
        json.dump(summary, output_file, indent=1)
    print(json.dumps(summary, indent=1))


def command_hook(calm_sample_size=2000, seed=2026):
    """Run the plugin's real hook script on every flagged prompt and a random sample of the rest."""
    import subprocess
    from concurrent.futures import ThreadPoolExecutor
    hook_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks", "frustration-check.sh")
    with open(os.path.join(SCRATCH_DIR, "prompts.jsonl")) as input_file:
        prompts = [p for p in map(json.loads, input_file) if p["session_id"] not in EXCLUDED_SESSION_IDS]
    flagged = [p for p in prompts if p["is_curse"]]
    calm = [p for p in prompts if not p["is_curse"]]
    random.Random(seed).shuffle(calm)
    calm_sample = calm[:calm_sample_size]

    def hook_fires(prompt):
        hook_input = json.dumps(dict(session_id="spirals", transcript_path="", cwd=os.getcwd(),
                                     permission_mode="default", hook_event_name="UserPromptSubmit", prompt=prompt["text"]))
        completed = subprocess.run(["sh", hook_script_path], input=hook_input, capture_output=True, text=True, timeout=10)
        return bool(completed.stdout.strip())

    with ThreadPoolExecutor(12) as pool:
        flagged_fires = sum(pool.map(hook_fires, flagged))
        calm_fires = sum(pool.map(hook_fires, calm_sample))
    estimated_fires = flagged_fires + calm_fires / len(calm_sample) * len(calm)
    result = dict(flagged_prompts=len(flagged), fires_on_flagged=flagged_fires,
                  share_of_flagged=round(flagged_fires / len(flagged), 3),
                  calm_sample=len(calm_sample), fires_on_calm_sample=calm_fires,
                  share_of_calm=round(calm_fires / len(calm_sample), 4),
                  estimated_share_of_all_prompts=round(estimated_fires / len(prompts), 3))
    with open(os.path.join(RESULTS_DIR, "hook.json"), "w") as output_file:
        json.dump(result, output_file, indent=1)
    print(json.dumps(result, indent=1))


def main():
    global OUTPUT_DIR, SCRATCH_DIR, RESULTS_DIR, RULE_FIRST_VERSION_DATE
    parser = argparse.ArgumentParser(description="Measure frustration spirals in your claude-mem history.")
    parser.add_argument("command", choices=["all", "prompts", "sample", "transcripts", "summary", "hook"])
    parser.add_argument("--out", default=OUTPUT_DIR, help="output folder (default: spirals-out)")
    parser.add_argument("--rule-date", default=RULE_FIRST_VERSION_DATE.date().isoformat(),
                        help="YYYY-MM-DD you started asking agents to stop and check when you curse")
    parser.add_argument("--exclude-session", action="append", default=[], help="session id to leave out (repeatable)")
    parser.add_argument("--sample-size", type=int, default=60)
    arguments = parser.parse_args()

    OUTPUT_DIR = RESULTS_DIR = arguments.out
    SCRATCH_DIR = os.path.join(arguments.out, "private")
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    RULE_FIRST_VERSION_DATE = dt.datetime.fromisoformat(arguments.rule_date).replace(tzinfo=dt.timezone.utc)
    EXCLUDED_SESSION_IDS.update(arguments.exclude_session)

    if arguments.command in ("all", "prompts"):
        command_prompts()
    if arguments.command == "sample":
        command_sample(arguments.sample_size)
    if arguments.command in ("all", "transcripts"):
        command_transcripts()
    if arguments.command in ("all", "summary"):
        command_summary()
    if arguments.command == "hook":
        command_hook()


if __name__ == "__main__":
    main()
