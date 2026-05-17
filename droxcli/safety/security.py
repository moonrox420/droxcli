"""Static security scanner — regex pattern matching."""

import re
from typing import Dict, List
from . import Result

_PATTERNS: List[Dict] = [
    {
        "name": "SQL injection",
        "pattern": re.compile(r"\bexecute\s*\(\s*[\"']?\s*.*%s|%\([^)]+\)s", re.I),
        "severity": "HIGH",
    },
    {
        "name": "Shell injection (shell=True)",
        "pattern": re.compile(
            r"subprocess\.(run|call|Popen)\s*\(.*shell\s*=\s*True", re.I
        ),
        "severity": "HIGH",
    },
    {
        "name": "Hardcoded AWS key",
        "pattern": re.compile(r"AKIA[0-9A-Z]{16}"),
        "severity": "CRITICAL",
    },
    {
        "name": "Hardcoded API token",
        "pattern": re.compile(r"(ghp_|gho_|github_pat_|sk-)[A-Za-z0-9_-]{16,}", re.I),
        "severity": "CRITICAL",
    },
    {
        "name": "eval() usage",
        "pattern": re.compile(r"\beval\s*\(", re.I),
        "severity": "MEDIUM",
    },
    {
        "name": "Pickle load",
        "pattern": re.compile(r"\bpickle\.load\s*\(", re.I),
        "severity": "MEDIUM",
    },
    {
        "name": "Debug mode enabled",
        "pattern": re.compile(r"debug\s*=\s*True", re.I),
        "severity": "LOW",
    },
]


def analyse_code(patches: List[Dict]) -> Result:
    findings: List[str] = []
    for patch in patches:
        fname = patch.get("file", "?")
        content = patch.get("new", "")
        for rule in _PATTERNS:
            if rule["pattern"].search(content):
                findings.append(f"[{rule['severity']}] {rule['name']} → {fname}")

    if not findings:
        return Result(True, "No security issues detected ✓", None)

    critical = [f for f in findings if f.startswith("[CRITICAL]")]
    if critical:
        return Result(
            False, f"{len(findings)} security issue(s) found", "\n".join(findings)
        )
    return Result(False, f"{len(findings)} security warning(s)", "\n".join(findings))
