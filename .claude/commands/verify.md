---
allowed-tools: Bash, Read
---

# Verify

Run the self-healing pre-commit verification loop.

## Usage
```text
/verify           # Check staged files only
/verify all       # Check all source files
```

## Instructions

### 1. Run Verification

```bash
if [ -z "$ARGUMENTS" ] || [ "$ARGUMENTS" = "staged" ]; then
    bash .claude/scripts/verify.sh --staged-only
elif [ "$ARGUMENTS" = "all" ]; then
    bash .claude/scripts/verify.sh --all
else
    bash .claude/scripts/verify.sh --all
fi
```

### 2. Report Results

Display the structured output from verify.sh directly. The script produces a formatted summary with per-phase status:

- **RUFF**: Lint and format check (auto-fixable issues are fixed and re-staged)
- **COMPLIANCE**: 17 CLAUDE.md compliance checks (Optional[X] auto-fixed to X | None)
- **MYPY**: Strict type checking
- **PYTEST**: Full test suite (fail-fast)

### 3. Interpret Results

**PASS**: All phases passed. Safe to commit.

**FIXED + PASS**: Auto-fixes were applied and re-staged. Review the changes with `git diff --cached` before committing.

**FAIL**: Manual fixes required. The output shows which phase(s) failed and specific error locations.

### 4. Common Fixes

| Phase | Common Issue | Fix |
|-------|-------------|-----|
| RUFF | Line too long (E501) | Break long strings or expressions across lines |
| RUFF | Unused variable (F841) | Remove the variable or prefix with `_` |
| COMPLIANCE | Raw dict annotation | Replace with a Pydantic model |
| COMPLIANCE | Optional[X] | Auto-fixed to X \| None |
| MYPY | Missing type annotation | Add return type and parameter types |
| PYTEST | Test failure | Fix the failing test or the code it tests |

## Error Handling

- Script not found: "Verify script missing. Check .claude/scripts/verify.sh exists."
- Timeout: The full suite (ruff + mypy + pytest) typically runs in under 2 minutes.
