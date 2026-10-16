#!/bin/sh
# clarity: UserPromptSubmit hook.
# When a prompt shows frustration (cursing, an insult aimed at the agent, or mostly-caps shouting),
# add a short reminder to the agent's context to stop, restate, and ask before acting.
# It never blocks a prompt and stays silent otherwise. Any failure exits 0 with no output.

input=$(cat) || exit 0

prompt=""
if command -v jq >/dev/null 2>&1; then
  prompt=$(printf '%s' "$input" | jq -r '.prompt // empty' 2>/dev/null)
elif command -v python3 >/dev/null 2>&1; then
  prompt=$(printf '%s' "$input" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("prompt", ""))' 2>/dev/null)
fi
[ -n "$prompt" ] || prompt=$input

lowercase_prompt=$(printf '%s' "$prompt" | tr '[:upper:]' '[:lower:]')

cursing_pattern="(^|[^a-z])(f+u+c+k|f[*]+c?k|fck|shit|bullshit|wtf|ffs|stfu|jfc|fml|omfg|goddamn|god damn|dammit|damn it|ass([^a-z]|$)|asshole|dumbass|motherf|piss)"
insult_pattern="(^|[^a-z])(you|u|ur|you're|youre)( are| r)? ((so|such|a|an|fucking|completely) )*(idiot|stupid|dumb|moron|useless|incompetent)([^a-z]|$)"

has_cursing=false
if printf '%s' "$lowercase_prompt" | grep -E -q "$cursing_pattern|$insult_pattern"; then
  has_cursing=true
fi

uppercase_letter_count=$(printf '%s' "$prompt" | tr -cd 'A-Z' | wc -c | tr -d ' ')
lowercase_letter_count=$(printf '%s' "$prompt" | tr -cd 'a-z' | wc -c | tr -d ' ')
is_shouting=false
if [ "${uppercase_letter_count:-0}" -ge 20 ] && [ "${uppercase_letter_count:-0}" -gt $(( ${lowercase_letter_count:-0} * 2 )) ]; then
  is_shouting=true
fi

if [ "$has_cursing" = false ] && [ "$is_shouting" = false ]; then
  exit 0
fi

cat <<'JSON'
{"continue":true,"suppressOutput":true,"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"clarity: this message shows frustration (cursing or shouting). If the user is frustrated with your work, stop before any tool call: write out exactly what you think they want done, ask \"Is this it? Yes, no, or modify?\", and take no other action until they answer. If this message answers a check you already asked, act on the answer and do not ask again. Happy cursing (\"fuck yeah, it works\") needs no check."}}
JSON
exit 0
