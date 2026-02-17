# Pre-Commit Workflow

Self-healing verification loop that runs before every commit.

## Automated Pipeline

The pre-commit workflow is now automated via hooks and scripts:

```
┌─────────────────────────────────────────────────────────────┐
│  TRIGGER: git commit / Claude Code Bash / /verify command   │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  verify.sh — Self-Healing Loop (max 3 iterations)           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Phase 1: RUFF (auto-fixable)                               │
│    - ruff check --fix (lint violations)                     │
│    - ruff format (code style)                               │
│    - Re-stage fixed files → loop back if changes made       │
│                                                             │
│  Phase 2: CLAUDE.md COMPLIANCE (partially auto-fixable)     │
│    - 17 grepable checks (raw dicts, print(), Optional, etc) │
│    - Auto-fix: Optional[X] → X | None                      │
│    - Re-stage fixed files → loop back if changes made       │
│                                                             │
│  Phase 3: MYPY (run once, not auto-fixable)                 │
│    - mypy --strict on src/                                  │
│                                                             │
│  Phase 4: PYTEST (run once, not auto-fixable)               │
│    - pytest tests/ -x -q (fail-fast)                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  DECISION                                                   │
│  - All pass → commit proceeds                               │
│  - Auto-fixed only → files re-staged, commit proceeds       │
│  - Unfixable errors → commit blocked                        │
└─────────────────────────────────────────────────────────────┘
```

## Trigger Points

| Source | Hook/Script | Mode |
|--------|-------------|------|
| `git commit` | `.git/hooks/pre-commit` | staged, full pipeline |
| Claude Code Bash (`git commit`) | `.claude/hooks/pre-commit-guard.sh` | staged, quiet, skip tests |
| `/verify` command | `.claude/commands/verify.md` | staged or all |

## Scripts

| File | Purpose |
|------|---------|
| `.claude/scripts/verify.sh` | Self-healing loop orchestrator |
| `.claude/scripts/claude-md-compliance.py` | 17 CLAUDE.md compliance checks |
| `.claude/hooks/pre-commit-guard.sh` | Claude Code PreToolUse hook |
| `.git/hooks/pre-commit` | Git pre-commit hook |

## Expected Output

```
=== Verify: 12 Python file(s) in staged mode ===

--- Iteration 1/3 ---
  [RUFF]       FIXED (2 file(s) auto-fixed, re-staged)
  [COMPLIANCE] PASS (16/17 checks)

--- Iteration 2/3 ---
  [RUFF]       PASS (0 issues)
  [COMPLIANCE] PASS (16/17 checks)

  [MYPY]       PASS (0 errors)
  [PYTEST]     PASS (1023 passed)

=== RESULT: PASS (2 auto-fix(es) applied in 2 iteration(s)) ===
```

## Manual Invocation

```bash
# Staged files only (same as pre-commit hook)
bash .claude/scripts/verify.sh --staged-only

# All source files
bash .claude/scripts/verify.sh --all

# Quick check (skip pytest)
bash .claude/scripts/verify.sh --all --skip-tests

# Compliance only (human-readable)
uv run python .claude/scripts/claude-md-compliance.py --all --human
```

## Bypassing

```bash
# Git: skip the hook
git commit --no-verify -m "message"

# Claude Code: the PreToolUse hook respects --no-verify
```

## Relationship to Other Workflows

```
pre-commit.md  ← YOU ARE HERE (fast, automated)
  ⊂ /pm:review    (deeper: dual-agent compliance + technical review)
    ⊂ pre-deploy.md  (deploy readiness: env, deps, build)
      ⊂ release-prep.md  (full: 11 auditors + fix cycle)
```

The pre-commit workflow is the **fast path** — it catches the most common issues
(lint, types, compliance, tests) in seconds. Deeper review happens via `/pm:review`
or the full audit workflow.
