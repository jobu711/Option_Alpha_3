# Pre-Commit Verification Workflow

Self-healing verification loop that gates every commit.

## Pipeline

```
Phase 1: RUFF (auto-fix) ←──┐
Phase 2: COMPLIANCE (auto-fix) ←─┤ Loop (max 3x if files changed)
                             ────┘
Phase 3: MYPY (run once)
Phase 4: PYTEST (run once, fail-fast)
```

## How It Works

1. **Phases 1-2 form a self-healing loop**: When ruff auto-fixes formatting or the compliance checker auto-fixes `Optional[X] → X | None`, the changed files are re-staged and phases 1-2 re-run to verify the fix didn't introduce new issues.

2. **Max 3 iterations** prevents infinite loops. If auto-fixes keep producing new violations after 3 rounds, the commit is blocked.

3. **Phases 3-4 run once** after the loop stabilizes. Type errors (mypy) and test failures (pytest) require manual intervention.

## Integration Points

### Git Pre-Commit Hook
`.git/hooks/pre-commit` — Runs on every `git commit`. Not tracked by git.

To reinstall after a fresh clone:
```bash
cp .claude/hooks/pre-commit-guard.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Claude Code PreToolUse Hook
`.claude/hooks/pre-commit-guard.sh` — Registered in `.claude/settings.json`. Intercepts `git commit` commands from the Bash tool. Runs verify.sh in quiet mode (skip tests for speed). Blocks the commit tool call if verification fails (exit 2).

### /verify Slash Command
`.claude/commands/verify.md` — Manual invocation: `/verify` (staged) or `/verify all`.

## Adding New Checks

To add a new compliance check:

1. Add the check function in `.claude/scripts/claude-md-compliance.py` following the `check_NN_` naming pattern.
2. Add it to the `ALL_CHECKS` list.
3. Increment `TOTAL_CHECKS` if it's a new rule number.
4. Document the rule in `.claude/rules/claude-md-compliance.md`.

## Troubleshooting

### "No Python files to check"
No staged `.py` files. Stage some files with `git add` first.

### Ruff keeps auto-fixing in a loop
A ruff rule's auto-fix is producing code that triggers another rule. Check which rules conflict with `uv run ruff check src/ --diff`.

### Mypy errors from untyped third-party libraries
Add stubs: `uv add --dev types-<package>` or add to `mypy.ini` overrides.

### Tests fail but code is correct
Check if test fixtures are outdated. Run `uv run pytest tests/ -v -k "test_name"` for the specific failure.
