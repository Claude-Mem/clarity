#!/bin/sh
# Runs hooks/frustration-check.sh against prompts that should and should not trigger it.
# Usage: sh tests/frustration-check.test.sh   (needs jq to build the hook input)

hook="$(dirname "$0")/../hooks/frustration-check.sh"
failures=0

check() {
  expectation=$1
  prompt=$2
  hook_input=$(jq -cn --arg prompt "$prompt" \
    '{session_id: "test", transcript_path: "test.jsonl", cwd: "/Users/test/Project", permission_mode: "default", hook_event_name: "UserPromptSubmit", prompt: $prompt}')
  output=$(printf '%s' "$hook_input" | sh "$hook")
  status=$?
  if [ -n "$output" ]; then fired=fires; else fired=silent; fi
  if [ "$status" -ne 0 ] || [ "$fired" != "$expectation" ]; then
    echo "FAIL ($fired, exit $status, expected $expectation): $prompt"
    failures=$((failures + 1))
  fi
  if [ -n "$output" ] && ! printf '%s' "$output" | jq -e '.hookSpecificOutput.additionalContext' >/dev/null; then
    echo "FAIL (output is not valid hook JSON): $prompt"
    failures=$((failures + 1))
  fi
}

check fires "this is fucking broken again"
check fires "what the fuck happened to my shit"
check fires "wtf is this"
check fires "that's bullshit and you know it"
check fires "f*ck this build"
check fires "you're such an idiot"
check fires "you are completely useless right now"
check fires "WHY DID YOU DELETE THE MIGRATION FILE I SAID KEEP IT"
check fires "NO I DID NOT ASK YOU TO SCHEDULE ANYTHING!!!! WHAT DID I JUST ASK YOU"
check fires "can you not fucking be such a dumbass"
check fires "you're about to make a new ass notebook when i wanted the pdf"
check fires "i trashed it when i closed that worktree fml"
check fires "stop pissing around and run the migration"

check silent "please fix the failing test in auth.test.ts"
check silent "use the API key from .env and call the URL in README.md"
check silent "ship it"
check silent "The Assessment class has a bug in its constructor"
check silent "update CLAUDE.md and AGENTS.md with the new rule"
check silent "fix the shift+tab handler so it skips hidden fields"
check silent "assert the assistant passes the class assignment check"
check silent "the bypass flag should pass through to the subprocess"
check silent "that idiom is useless in Python"
check silent ""

if [ "$failures" -eq 0 ]; then
  echo "all frustration-check tests passed"
else
  echo "$failures failing"
  exit 1
fi
