#!/usr/bin/env python3
"""CLAUDE.md compliance checker for Option Alpha project.

Implements all 17 grepable checks from .claude/rules/claude-md-compliance.md.
Uses only stdlib: re, pathlib, json, sys, subprocess.

Usage:
    python .claude/scripts/claude-md-compliance.py file1.py file2.py ...
    python .claude/scripts/claude-md-compliance.py --staged
    python .claude/scripts/claude-md-compliance.py --all
    python .claude/scripts/claude-md-compliance.py --staged --autofix
    python .claude/scripts/claude-md-compliance.py --staged --human
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath


@dataclass
class Violation:
    check: int
    rule: str
    file: str
    line: int
    text: str
    auto_fixable: bool
    severity: str  # "error" or "warning"


@dataclass
class CheckResult:
    passed: int = 0
    failed: int = 0
    auto_fixable: int = 0
    violations: list[Violation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _posix(p: Path) -> str:
    """Normalise Windows paths to forward-slash for display/matching."""
    return PurePosixPath(p).as_posix()


def _is_dev_tooling(path: Path) -> bool:
    """Check if path is dev tooling (not application code). Skip compliance checks."""
    posix = _posix(path)
    return ".claude/" in posix or posix.startswith(".claude/")


def _in_module(path: Path, module: str) -> bool:
    """Check if path is inside a given module (e.g. 'indicators', 'models')."""
    posix = _posix(path)
    return f"/{module}/" in posix or posix.startswith(f"{module}/")


def _is_comment_or_docstring_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''")


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []


# ---------------------------------------------------------------------------
# Checks 1-17
# ---------------------------------------------------------------------------


def check_01_no_raw_dicts(files: list[Path]) -> list[Violation]:
    """No dict[str, ...] in type annotations crossing module boundaries.

    Targets: function params, return types, Pydantic model fields.
    Excludes: local variables (= {} or = dict()), private attrs (self._),
    indicators/ module, and normalization.py.
    """
    annotation_pattern = re.compile(r":\s*dict\[")
    # Exclusion patterns for internal-only usage
    local_var = re.compile(r":\s*dict\[.*\]\s*=\s*\{")  # x: dict[...] = {
    private_attr = re.compile(r"self\._\w+:\s*dict\[")  # self._cache: dict[...]
    param_pattern = re.compile(r":\s*dict\[.*\]\s*=\s*dict\(")  # x: dict[...] = dict()
    violations = []
    for path in files:
        if _in_module(path, "indicators"):
            continue
        if path.name == "normalization.py":
            continue
        for i, line in enumerate(_read_lines(path), 1):
            if _is_comment_or_docstring_line(line):
                continue
            if not annotation_pattern.search(line):
                continue
            # Skip clearly internal patterns
            if local_var.search(line):
                continue
            if private_attr.search(line):
                continue
            if param_pattern.search(line):
                continue
            violations.append(
                Violation(
                    1,
                    "No raw dicts in type annotations",
                    _posix(path),
                    i,
                    line.strip(),
                    False,
                    "error",
                )
            )
    return violations


def check_02_no_print(files: list[Path]) -> list[Violation]:
    """No print() outside cli.py. Test files excluded."""
    pattern = re.compile(r"\bprint\(")
    violations = []
    for path in files:
        if path.name == "cli.py":
            continue
        posix = _posix(path)
        if "/tests/" in posix or "test_" in path.name or posix.startswith("tests/"):
            continue
        for i, line in enumerate(_read_lines(path), 1):
            if line.lstrip().startswith("#"):
                continue
            if pattern.search(line):
                violations.append(
                    Violation(
                        2,
                        "No print() outside cli.py",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
    return violations


def check_03_bare_except(files: list[Path]) -> list[Violation]:
    """No bare except: — always catch specific types."""
    pattern = re.compile(r"^\s*except\s*:")
    violations = []
    for path in files:
        for i, line in enumerate(_read_lines(path), 1):
            if pattern.match(line):
                violations.append(
                    Violation(
                        3,
                        "No bare except:",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
    return violations


def check_04_no_optional(files: list[Path]) -> list[Violation]:
    """No X | None — use X | None. Auto-fixable."""
    pattern = re.compile(r"Optional\[")
    violations = []
    for path in files:
        for i, line in enumerate(_read_lines(path), 1):
            if pattern.search(line):
                violations.append(
                    Violation(
                        4,
                        "No X | None (use X | None)",
                        _posix(path),
                        i,
                        line.strip(),
                        True,
                        "error",
                    )
                )
    return violations


def check_05_legacy_typing(files: list[Path]) -> list[Violation]:
    """No legacy typing imports (List, Dict, Tuple, Set, FrozenSet, Type)."""
    usage_pattern = re.compile(r"typing\.(List|Dict|Tuple|Set|FrozenSet|Type)\b")
    import_pattern = re.compile(
        r"from\s+typing\s+import\s+.*\b(List|Dict|Tuple|Set|FrozenSet|Type)\b"
    )
    violations = []
    for path in files:
        for i, line in enumerate(_read_lines(path), 1):
            if usage_pattern.search(line) or import_pattern.search(line):
                violations.append(
                    Violation(
                        5,
                        "No legacy typing imports (use lowercase builtins)",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
    return violations


def check_06_decimal_from_float(files: list[Path]) -> list[Violation]:
    """No Decimal(1.05) — use Decimal("1.05")."""
    # Match Decimal( followed by a digit, but NOT Decimal(" (string construction)
    pattern = re.compile(r"Decimal\(\s*\d")
    string_pattern = re.compile(r'Decimal\(\s*"')
    violations = []
    for path in files:
        for i, line in enumerate(_read_lines(path), 1):
            if line.lstrip().startswith("#"):
                continue
            if pattern.search(line) and not string_pattern.search(line):
                violations.append(
                    Violation(
                        6,
                        "No Decimal from float literal (use string)",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
    return violations


def check_07_pydantic_v1(files: list[Path]) -> list[Violation]:
    """No Pydantic v1 patterns (.dict(), @validator, from pydantic.v1, class Config:)."""
    patterns = [
        (re.compile(r"\.dict\(\)"), ".dict() -> .model_dump()"),
        (re.compile(r"@validator\b"), "@validator -> @field_validator"),
        (re.compile(r"from\s+pydantic\.v1"), "from pydantic.v1 -> from pydantic"),
        (re.compile(r"^\s*class\s+Config\s*:"), "class Config: -> model_config = ConfigDict(...)"),
    ]
    violations = []
    for path in files:
        for i, line in enumerate(_read_lines(path), 1):
            for pat, msg in patterns:
                if pat.search(line):
                    violations.append(
                        Violation(
                            7,
                            f"Pydantic v1 pattern: {msg}",
                            _posix(path),
                            i,
                            line.strip(),
                            False,
                            "error",
                        )
                    )
    return violations


# Check 8 (type annotations) is enforced by mypy --strict, not here.


def check_09_api_outside_services(files: list[Path]) -> list[Violation]:
    """No yfinance or httpx.Client/AsyncClient outside services/."""
    yf_pattern = re.compile(r"(?:import\s+yfinance|from\s+yfinance)")
    httpx_pattern = re.compile(r"httpx\.(Client|AsyncClient)")
    violations = []
    for path in files:
        if _in_module(path, "services"):
            continue
        for i, line in enumerate(_read_lines(path), 1):
            if yf_pattern.search(line):
                violations.append(
                    Violation(
                        9,
                        "yfinance imported outside services/",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
            if httpx_pattern.search(line):
                violations.append(
                    Violation(
                        9,
                        "httpx client created outside services/",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
    return violations


def check_10_ai_sdk_outside_agents(files: list[Path]) -> list[Violation]:
    """No ollama/anthropic imports outside agents/."""
    pattern = re.compile(r"(?:import\s+(?:ollama|anthropic)|from\s+(?:ollama|anthropic))")
    violations = []
    for path in files:
        if _in_module(path, "agents"):
            continue
        for i, line in enumerate(_read_lines(path), 1):
            if pattern.search(line):
                violations.append(
                    Violation(
                        10,
                        "AI SDK imported outside agents/",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
    return violations


def check_11_services_in_indicators_analysis(files: list[Path]) -> list[Violation]:
    """indicators/ and analysis/ must never import from services/."""
    pattern = re.compile(r"from\s+\S*services")
    violations = []
    for path in files:
        if not (_in_module(path, "indicators") or _in_module(path, "analysis")):
            continue
        for i, line in enumerate(_read_lines(path), 1):
            if pattern.search(line):
                violations.append(
                    Violation(
                        11,
                        "indicators/ or analysis/ imports from services/",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
    return violations


def check_12_models_no_business_logic(files: list[Path]) -> list[Violation]:
    """models/ must not import logging, httpx, asyncio, or service/agent modules."""
    io_pattern = re.compile(r"^(?:import|from)\s+(?:logging|httpx|asyncio)\b")
    cross_pattern = re.compile(r"from\s+\S*(?:services|agents)")
    violations = []
    for path in files:
        if not _in_module(path, "models"):
            continue
        for i, line in enumerate(_read_lines(path), 1):
            if io_pattern.match(line):
                violations.append(
                    Violation(
                        12,
                        "models/ must not import I/O or business logic",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
            if cross_pattern.search(line):
                violations.append(
                    Violation(
                        12,
                        "models/ must not import from services/ or agents/",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
    return violations


def check_13_models_decimal_for_prices(files: list[Path]) -> list[Violation]:
    """Financial fields in models/ must use Decimal, not float."""
    pattern = re.compile(r"(price|bid|ask|strike|cost|debit|credit|profit|loss):\s*float")
    violations = []
    for path in files:
        if not _in_module(path, "models"):
            continue
        for i, line in enumerate(_read_lines(path), 1):
            if pattern.search(line):
                violations.append(
                    Violation(
                        13,
                        "Financial field uses float in models/ (use Decimal)",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
    return violations


def check_14_agents_max_tokens(files: list[Path]) -> list[Violation]:
    """messages.create() in agents/ — warn to verify max_tokens."""
    pattern = re.compile(r"messages\.create\(")
    violations = []
    for path in files:
        if not _in_module(path, "agents"):
            continue
        for i, line in enumerate(_read_lines(path), 1):
            if pattern.search(line):
                violations.append(
                    Violation(
                        14,
                        "Verify max_tokens is set on messages.create()",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "warning",
                    )
                )
    return violations


def check_15_agents_response_content(files: list[Path]) -> list[Violation]:
    """response.content in agents/ must be indexed (Anthropic API returns a list).

    Only matches the exact variable name 'response.content', not arbitrary
    objects like 'llm_response.content' or 'message.content' which may be strings.
    """
    # Match standalone 'response.content' not followed by '[' (indexing)
    pattern = re.compile(r"\bresponse\.content\b(?!\s*\[)")
    violations = []
    for path in files:
        if not _in_module(path, "agents"):
            continue
        for i, line in enumerate(_read_lines(path), 1):
            if line.lstrip().startswith("#"):
                continue
            if pattern.search(line):
                violations.append(
                    Violation(
                        15,
                        "response.content is a list — index it",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
    return violations


def check_16_indicators_no_models(files: list[Path]) -> list[Violation]:
    """indicators/ must not import Pydantic models."""
    pattern = re.compile(r"(?:from\s+\S*models\s+import|from\s+pydantic)")
    violations = []
    for path in files:
        if not _in_module(path, "indicators"):
            continue
        for i, line in enumerate(_read_lines(path), 1):
            if pattern.search(line):
                violations.append(
                    Violation(
                        16,
                        "indicators/ imports Pydantic models (use pandas)",
                        _posix(path),
                        i,
                        line.strip(),
                        False,
                        "error",
                    )
                )
    return violations


def check_17_reporting_disclaimer(files: list[Path]) -> list[Violation]:
    """reporting/ files must import from disclaimer.py."""
    violations = []
    for path in files:
        if not _in_module(path, "reporting"):
            continue
        if path.name in ("disclaimer.py", "__init__.py"):
            continue
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        if "disclaimer" not in content:
            violations.append(
                Violation(
                    17,
                    "Reporting file missing disclaimer import",
                    _posix(path),
                    0,
                    "(file-level check)",
                    False,
                    "warning",
                )
            )
    return violations


# ---------------------------------------------------------------------------
# All checks
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_01_no_raw_dicts,
    check_02_no_print,
    check_03_bare_except,
    check_04_no_optional,
    check_05_legacy_typing,
    check_06_decimal_from_float,
    check_07_pydantic_v1,
    # check 8 is mypy --strict
    check_09_api_outside_services,
    check_10_ai_sdk_outside_agents,
    check_11_services_in_indicators_analysis,
    check_12_models_no_business_logic,
    check_13_models_decimal_for_prices,
    check_14_agents_max_tokens,
    check_15_agents_response_content,
    check_16_indicators_no_models,
    check_17_reporting_disclaimer,
]

TOTAL_CHECKS = 17  # including check 8 (mypy)


# ---------------------------------------------------------------------------
# Auto-fix
# ---------------------------------------------------------------------------


def autofix_optional(files: list[Path]) -> list[str]:
    """Replace Optional[X] with X | None. Returns list of modified file paths."""
    files = [f for f in files if not _is_dev_tooling(f)]
    pattern = re.compile(r"Optional\[([^\]]+)\]")
    import_pattern = re.compile(r"from\s+typing\s+import\s+(.+)")
    modified: list[str] = []
    for path in files:
        lines = _read_lines(path)
        changed = False
        new_lines: list[str] = []
        for line in lines:
            new_line = pattern.sub(r"\1 | None", line)
            if new_line != line:
                changed = True
            new_lines.append(new_line)

        if changed:
            # Also clean up "from typing import Optional" if it becomes unused
            final_lines: list[str] = []
            for line in new_lines:
                m = import_pattern.match(line)
                if m:
                    imports = [i.strip() for i in m.group(1).split(",")]
                    remaining = [i for i in imports if i != "Optional"]
                    if not remaining:
                        continue  # skip the entire import line
                    if len(remaining) < len(imports):
                        line = f"from typing import {', '.join(remaining)}"
                final_lines.append(line)
            path.write_text("\n".join(final_lines) + "\n", encoding="utf-8")
            modified.append(_posix(path))
    return modified


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------


def get_staged_files() -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "--", "*.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [Path(f.strip()) for f in result.stdout.strip().splitlines() if f.strip()]


def get_all_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--", "src/**/*.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    paths = [Path(f.strip()) for f in result.stdout.strip().splitlines() if f.strip()]
    return [p for p in paths if p.exists()]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_checks(files: list[Path]) -> CheckResult:
    # Exclude dev tooling (.claude/ scripts, hooks, etc.) — not application code
    files = [f for f in files if not _is_dev_tooling(f)]
    if not files:
        return CheckResult(passed=TOTAL_CHECKS)

    result = CheckResult()
    checks_with_violations: set[int] = set()

    for check_fn in ALL_CHECKS:
        violations = check_fn(files)
        result.violations.extend(violations)
        for v in violations:
            checks_with_violations.add(v.check)
            if v.auto_fixable:
                result.auto_fixable += 1

    result.failed = len(checks_with_violations)
    result.passed = TOTAL_CHECKS - result.failed
    return result


def main() -> int:
    args = sys.argv[1:]
    human_mode = "--human" in args
    autofix_mode = "--autofix" in args
    staged_mode = "--staged" in args
    all_mode = "--all" in args

    # Remove flags from args
    file_args = [a for a in args if not a.startswith("--")]

    # Collect files
    if staged_mode:
        files = get_staged_files()
    elif all_mode:
        files = get_all_files()
    elif file_args:
        files = [Path(f) for f in file_args]
    else:
        files = get_staged_files()  # default to staged

    if not files:
        if human_mode:
            print("No Python files to check.")
        else:
            print(
                json.dumps(
                    {"passed": TOTAL_CHECKS, "failed": 0, "auto_fixable": 0, "violations": []}
                )
            )
        return 0

    # Auto-fix before checking
    auto_fixed_files: list[str] = []
    if autofix_mode:
        auto_fixed_files = autofix_optional(files)

    # Run checks
    result = run_checks(files)

    if human_mode:
        error_violations = [v for v in result.violations if v.severity == "error"]
        warning_violations = [v for v in result.violations if v.severity == "warning"]

        if error_violations:
            print(
                f"\nCLAUDE.md compliance: {len(error_violations)} error(s), {len(warning_violations)} warning(s)"
            )
            print()
            for v in error_violations:
                print(f"  [{v.check:02d}] {v.file}:{v.line}")
                print(f"       {v.rule}")
                print(f"       {v.text}")
                if v.auto_fixable:
                    print("       (auto-fixable with --autofix)")
                print()
        if warning_violations:
            for v in warning_violations:
                print(f"  [{v.check:02d}] WARNING {v.file}:{v.line}")
                print(f"       {v.rule}")
                print()
        if auto_fixed_files:
            print(f"Auto-fixed {len(auto_fixed_files)} file(s):")
            for f in auto_fixed_files:
                print(f"  {f}")
            print()
        if not error_violations:
            checks_info = f"{result.passed}/{TOTAL_CHECKS}"
            print(f"CLAUDE.md compliance: PASS ({checks_info} checks)")
        else:
            print(f"CLAUDE.md compliance: FAIL ({result.failed} check(s) failed)")
    else:
        output = {
            "passed": result.passed,
            "failed": result.failed,
            "auto_fixable": result.auto_fixable,
            "auto_fixed_files": auto_fixed_files,
            "violations": [asdict(v) for v in result.violations],
        }
        print(json.dumps(output, indent=2))

    # Exit code: 1 if any error-severity violations remain
    error_count = sum(1 for v in result.violations if v.severity == "error")
    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
