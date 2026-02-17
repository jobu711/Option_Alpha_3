#!/usr/bin/env bash
# Self-healing pre-commit verification loop.
#
# Runs up to MAX_RETRIES iterations:
#   Phase 1 (ruff)       — auto-fix lint/format, re-stage
#   Phase 2 (compliance) — CLAUDE.md checks, auto-fix Optional→union
#   Phase 3 (mypy)       — strict type checking (run once)
#   Phase 4 (pytest)     — test suite, fail-fast (run once)
#
# Exit codes: 0 = pass, 1 = fail
#
# Usage:
#   bash .claude/scripts/verify.sh                  # staged files only (default)
#   bash .claude/scripts/verify.sh --all            # all source files
#   bash .claude/scripts/verify.sh --quiet          # minimal output
#   bash .claude/scripts/verify.sh --max-retries 5  # override retry limit
#   bash .claude/scripts/verify.sh --skip-tests     # skip pytest phase

set -uo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_RETRIES=3
MODE="staged"
QUIET=false
SKIP_TESTS=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Phase results
RUFF_STATUS=""
COMPLIANCE_STATUS=""
MYPY_STATUS=""
PYTEST_STATUS=""
OVERALL_EXIT=0
TOTAL_AUTO_FIXES=0

# Colors (disabled if not a terminal)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[0;33m'
    CYAN='\033[0;36m'
    NC='\033[0m'  # No Color
else
    GREEN='' RED='' YELLOW='' CYAN='' NC=''
fi

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)        MODE="all";       shift ;;
        --staged-only) MODE="staged";   shift ;;
        --quiet)      QUIET=true;       shift ;;
        --skip-tests) SKIP_TESTS=true;  shift ;;
        --max-retries)
            MAX_RETRIES="$2"; shift 2 ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
    if [ "$QUIET" = false ]; then
        echo -e "$@"
    fi
}

status_tag() {
    local phase="$1" status="$2" detail="$3"
    case "$status" in
        PASS)  log "  ${GREEN}[${phase}]${NC}       PASS ${detail}" ;;
        FIXED) log "  ${YELLOW}[${phase}]${NC}       FIXED ${detail}" ;;
        FAIL)  log "  ${RED}[${phase}]${NC}       FAIL ${detail}" ;;
        SKIP)  log "  ${CYAN}[${phase}]${NC}       SKIP ${detail}" ;;
    esac
}

get_python_files() {
    cd "$PROJECT_ROOT" || exit 1
    if [ "$MODE" = "staged" ]; then
        git diff --cached --name-only --diff-filter=ACM -- '*.py' 2>/dev/null
    else
        git ls-files -- 'src/**/*.py' 2>/dev/null
    fi
}

# ---------------------------------------------------------------------------
# Phase 1: Ruff (lint + format, auto-fixable)
# ---------------------------------------------------------------------------
phase_ruff() {
    local files="$1"
    local ruff_output changed_files

    cd "$PROJECT_ROOT" || exit 1

    # Snapshot working-tree state before ruff so we only detect ruff's changes
    local before_hash
    before_hash=$(git diff -- '*.py' 2>/dev/null | git hash-object --stdin)

    # Run ruff check with auto-fix (suppress output — we only care about file changes)
    if [ "$MODE" = "staged" ]; then
        echo "$files" | xargs uv run ruff check --fix --force-exclude >/dev/null 2>&1 || true
        echo "$files" | xargs uv run ruff format --force-exclude >/dev/null 2>&1 || true
    else
        uv run ruff check src/ --fix >/dev/null 2>&1 || true
        uv run ruff format src/ >/dev/null 2>&1 || true
    fi

    # Compare working-tree diff to detect only ruff's changes (not pre-existing dirty files)
    local after_hash
    after_hash=$(git diff -- '*.py' 2>/dev/null | git hash-object --stdin)

    if [ "$before_hash" != "$after_hash" ]; then
        # Ruff changed files — find which ones
        changed_files=$(git diff --name-only -- '*.py' 2>/dev/null || true)

        # Re-stage changed files
        if [ "$MODE" = "staged" ] && [ -n "$changed_files" ]; then
            echo "$changed_files" | xargs git add 2>/dev/null
        fi

        local fix_count
        fix_count=$(echo "$changed_files" | wc -l)
        TOTAL_AUTO_FIXES=$((TOTAL_AUTO_FIXES + fix_count))
        RUFF_STATUS="FIXED"
        status_tag "RUFF" "FIXED" "(${fix_count} file(s) auto-fixed, re-staged)"
        return 1  # signal: needs recheck
    fi

    # Verify clean
    local ruff_exit
    if [ "$MODE" = "staged" ]; then
        ruff_output=$(echo "$files" | xargs uv run ruff check --force-exclude 2>&1)
        ruff_exit=$?
    else
        ruff_output=$(uv run ruff check src/ 2>&1)
        ruff_exit=$?
    fi

    if [ "$ruff_exit" -ne 0 ]; then
        local error_count
        error_count=$(echo "$ruff_output" | grep -c "Found [0-9]" || echo "?")
        RUFF_STATUS="FAIL"
        OVERALL_EXIT=1
        status_tag "RUFF" "FAIL" "(unfixable lint errors)"
        if [ "$QUIET" = false ]; then
            # Show only error lines (file:line:col: CODE message)
            echo "$ruff_output" | grep -E "^[^ ].*:[0-9]+:[0-9]+:" | head -10 | while IFS= read -r line; do
                echo "    $line"
            done
        fi
        return 0  # don't retry, these need manual fix
    fi

    RUFF_STATUS="PASS"
    status_tag "RUFF" "PASS" "(0 issues)"
    return 0
}

# ---------------------------------------------------------------------------
# Phase 2: CLAUDE.md Compliance (partially auto-fixable)
# ---------------------------------------------------------------------------
phase_compliance() {
    local files="$1"
    local compliance_args=""
    local compliance_output compliance_exit
    local auto_fixed_count

    cd "$PROJECT_ROOT" || exit 1

    if [ "$MODE" = "staged" ]; then
        compliance_args="--staged --autofix"
    else
        compliance_args="--all --autofix"
    fi

    compliance_output=$(uv run python .claude/scripts/claude-md-compliance.py $compliance_args 2>/dev/null)
    compliance_exit=$?

    # Fail closed: if the compliance tool crashed or produced invalid JSON, treat as FAIL
    if [ "$compliance_exit" -ne 0 ] && [ "$compliance_exit" -ne 1 ]; then
        COMPLIANCE_STATUS="FAIL"
        OVERALL_EXIT=1
        status_tag "COMPLIANCE" "FAIL" "(compliance tool crashed, exit $compliance_exit)"
        return 0
    fi

    # Validate JSON output
    local json_valid
    json_valid=$(echo "$compliance_output" | python3 -c "import json,sys; json.load(sys.stdin); print('ok')" 2>/dev/null || \
                 echo "$compliance_output" | python -c "import json,sys; json.load(sys.stdin); print('ok')" 2>/dev/null || \
                 echo "fail")
    if [ "$json_valid" != "ok" ]; then
        COMPLIANCE_STATUS="FAIL"
        OVERALL_EXIT=1
        status_tag "COMPLIANCE" "FAIL" "(invalid JSON output from compliance tool)"
        return 0
    fi

    # Parse JSON output for auto-fixed file count
    auto_fixed_count=$(echo "$compliance_output" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    fixed = d.get('auto_fixed_files', [])
    print(len(fixed))
except Exception:
    print(0)
" 2>/dev/null || echo "$compliance_output" | python -c "
import json, sys
try:
    d = json.load(sys.stdin)
    fixed = d.get('auto_fixed_files', [])
    print(len(fixed))
except Exception:
    print(0)
" 2>/dev/null)

    # Re-stage auto-fixed files
    if [ "$auto_fixed_count" -gt 0 ]; then
        local fixed_files
        fixed_files=$(echo "$compliance_output" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    for f in d.get('auto_fixed_files', []):
        print(f)
except Exception:
    pass
" 2>/dev/null || echo "$compliance_output" | python -c "
import json, sys
try:
    d = json.load(sys.stdin)
    for f in d.get('auto_fixed_files', []):
        print(f)
except Exception:
    pass
" 2>/dev/null)
        if [ -n "$fixed_files" ] && [ "$MODE" = "staged" ]; then
            echo "$fixed_files" | xargs git add 2>/dev/null
        fi
        TOTAL_AUTO_FIXES=$((TOTAL_AUTO_FIXES + auto_fixed_count))
        COMPLIANCE_STATUS="FIXED"
        status_tag "COMPLIANCE" "FIXED" "(${auto_fixed_count} auto-fixed, re-staged)"
        return 1  # signal: needs recheck
    fi

    # Check for remaining errors
    local error_count
    error_count=$(echo "$compliance_output" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    errs = [v for v in d.get('violations', []) if v.get('severity') == 'error']
    print(len(errs))
except Exception:
    print(0)
" 2>/dev/null || echo "$compliance_output" | python -c "
import json, sys
try:
    d = json.load(sys.stdin)
    errs = [v for v in d.get('violations', []) if v.get('severity') == 'error']
    print(len(errs))
except Exception:
    print(0)
" 2>/dev/null)

    if [ "$error_count" -gt 0 ]; then
        COMPLIANCE_STATUS="FAIL"
        OVERALL_EXIT=1
        status_tag "COMPLIANCE" "FAIL" "(${error_count} violation(s))"
        if [ "$QUIET" = false ]; then
            # Show violations in human-readable form
            echo "$compliance_output" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    for v in d.get('violations', []):
        if v.get('severity') == 'error':
            print(f\"    [{v['check']:02d}] {v['file']}:{v['line']} — {v['rule']}\")
except Exception:
    pass
" 2>/dev/null || echo "$compliance_output" | python -c "
import json, sys
try:
    d = json.load(sys.stdin)
    for v in d.get('violations', []):
        if v.get('severity') == 'error':
            print(f\"    [{v['check']:02d}] {v['file']}:{v['line']} — {v['rule']}\")
except Exception:
    pass
" 2>/dev/null
        fi
        return 0
    fi

    local passed total
    passed=$(echo "$compliance_output" | python3 -c "import json,sys; print(json.load(sys.stdin).get('passed',0))" 2>/dev/null || \
             echo "$compliance_output" | python -c "import json,sys; print(json.load(sys.stdin).get('passed',0))" 2>/dev/null)
    total=17
    COMPLIANCE_STATUS="PASS"
    status_tag "COMPLIANCE" "PASS" "(${passed}/${total} checks)"
    return 0
}

# ---------------------------------------------------------------------------
# Phase 3: Mypy (not auto-fixable, run once)
# ---------------------------------------------------------------------------
phase_mypy() {
    cd "$PROJECT_ROOT" || exit 1

    local mypy_output mypy_exit
    mypy_output=$(uv run mypy src/ --strict 2>&1)
    mypy_exit=$?

    if [ "$mypy_exit" -ne 0 ]; then
        MYPY_STATUS="FAIL"
        OVERALL_EXIT=1
        local error_count
        error_count=$(echo "$mypy_output" | grep -c "^.*: error:" || true)
        status_tag "MYPY" "FAIL" "(${error_count} error(s))"
        if [ "$QUIET" = false ]; then
            echo "$mypy_output" | grep ": error:" | head -10 | while read -r line; do
                echo "    $line"
            done
            local remaining=$((error_count - 10))
            if [ "$remaining" -gt 0 ]; then
                echo "    ... and $remaining more"
            fi
        fi
        return 1
    fi

    MYPY_STATUS="PASS"
    status_tag "MYPY" "PASS" "(0 errors)"
    return 0
}

# ---------------------------------------------------------------------------
# Phase 4: Pytest (not auto-fixable, run once)
# ---------------------------------------------------------------------------
phase_pytest() {
    if [ "$SKIP_TESTS" = true ]; then
        PYTEST_STATUS="SKIP"
        status_tag "PYTEST" "SKIP" "(--skip-tests)"
        return 0
    fi

    cd "$PROJECT_ROOT" || exit 1

    local pytest_output pytest_exit
    pytest_output=$(uv run pytest tests/ -x -q 2>&1)
    pytest_exit=$?

    if [ "$pytest_exit" -ne 0 ]; then
        PYTEST_STATUS="FAIL"
        OVERALL_EXIT=1
        local summary_line
        summary_line=$(echo "$pytest_output" | tail -1)
        status_tag "PYTEST" "FAIL" "($summary_line)"
        if [ "$QUIET" = false ]; then
            echo "$pytest_output" | grep -E "^(FAILED|ERROR)" | head -5 | while read -r line; do
                echo "    $line"
            done
        fi
        return 1
    fi

    local test_count
    test_count=$(echo "$pytest_output" | tail -1 | grep -oP '\d+ passed' || echo "? passed")
    PYTEST_STATUS="PASS"
    status_tag "PYTEST" "PASS" "($test_count)"
    return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    cd "$PROJECT_ROOT" || exit 1

    # Fast path: no Python files to check
    local FILES
    FILES=$(get_python_files)
    if [ -z "$FILES" ]; then
        log "No Python files to check."
        exit 0
    fi

    local file_count
    file_count=$(echo "$FILES" | wc -l)
    log "${CYAN}=== Verify: ${file_count} Python file(s) in ${MODE} mode ===${NC}"
    log ""

    # Self-healing loop (phases 1-2 only)
    local ITERATION=0
    while [ "$ITERATION" -lt "$MAX_RETRIES" ]; do
        ITERATION=$((ITERATION + 1))
        local NEEDS_RECHECK=false

        log "${CYAN}--- Iteration ${ITERATION}/${MAX_RETRIES} ---${NC}"

        # Phase 1: Ruff
        phase_ruff "$FILES"
        if [ $? -eq 1 ]; then
            NEEDS_RECHECK=true
        fi

        # Phase 2: Compliance
        phase_compliance "$FILES"
        if [ $? -eq 1 ]; then
            NEEDS_RECHECK=true
        fi

        # Re-loop if auto-fixes were applied
        if [ "$NEEDS_RECHECK" = true ] && [ "$ITERATION" -lt "$MAX_RETRIES" ]; then
            FILES=$(get_python_files)
            log ""
            continue
        fi
        break
    done

    log ""

    # Phase 3: Mypy (run once)
    phase_mypy

    # Phase 4: Pytest (run once)
    phase_pytest

    # Summary
    log ""
    if [ "$OVERALL_EXIT" -eq 0 ]; then
        if [ "$TOTAL_AUTO_FIXES" -gt 0 ]; then
            log "${GREEN}=== RESULT: PASS (${TOTAL_AUTO_FIXES} auto-fix(es) applied in ${ITERATION} iteration(s)) ===${NC}"
        else
            log "${GREEN}=== RESULT: PASS ===${NC}"
        fi
    else
        log "${RED}=== RESULT: FAIL ===${NC}"
        log ""
        log "Fix the issues above before committing."
        log "Run 'bash .claude/scripts/verify.sh --all' for details."
    fi

    exit "$OVERALL_EXIT"
}

main
