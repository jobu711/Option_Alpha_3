#!/usr/bin/env bash
# Hook: PreToolUse (Bash)
# Intercepts git commit commands and runs verify.sh before allowing them.
# Exit 0 = allow, Exit 2 = block
#
# This hook is registered in .claude/settings.json under PreToolUse.
# It reads the Claude Code hook JSON protocol from stdin.

# Read JSON input from stdin
INPUT=$(cat)

# Extract the command using Python (jq not available on this system)
COMMAND=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
    print(data.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
" <<< "$INPUT" 2>/dev/null || python -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
    print(data.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
" <<< "$INPUT" 2>/dev/null)

# Only intercept git commit commands
if ! echo "$COMMAND" | grep -qE '\bgit\s+commit\b'; then
    exit 0
fi

# Respect --no-verify escape hatch
if echo "$COMMAND" | grep -q -- '--no-verify'; then
    exit 0
fi

# Run the self-healing verification loop in staged-only, quiet mode
bash .claude/scripts/verify.sh --staged-only --quiet --skip-tests
VERIFY_EXIT=$?

if [ "$VERIFY_EXIT" -ne 0 ]; then
    echo "" >&2
    echo "BLOCKED: Pre-commit verification failed." >&2
    echo "Run '/verify' or 'bash .claude/scripts/verify.sh --staged-only' for details." >&2
    exit 2
fi

exit 0
