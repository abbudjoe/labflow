#!/usr/bin/env python3
"""Portfolio share-readiness checks for LabFlow AI Studio."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = (
    "README.md",
    "DOCTRINE.md",
    "docs/case_study.md",
    "docs/demo_script_starlims_role.md",
    "docs/eval_summary.md",
    "docs/role_alignment_starlims.md",
    "docs/share_readiness_checklist.md",
)

REQUIRED_GITIGNORE_PATTERNS = (
    ".env",
    ".codex_build/",
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
    "node_modules/",
    "artifacts/",
    "**/.terraform/",
    "*.tfstate",
)

PUBLIC_DOC_GLOBS = (
    "README.md",
    "DOCTRINE.md",
    "ENGINEERING.md",
    "PROJECT_PLAN.md",
    "PRODUCT_REQUIREMENTS.md",
    "docs/agent_failure_taxonomy.md",
    "docs/api_contract.md",
    "docs/aws_architecture_decisions.md",
    "docs/baseline_rotation.md",
    "docs/case_study.md",
    "docs/demo_script_starlims_role.md",
    "docs/eval_summary.md",
    "docs/interview_review_quiz.md",
    "docs/limitations_and_disclosure.md",
    "docs/resume_bullets.md",
    "docs/role_alignment_starlims.md",
    "docs/share_readiness_checklist.md",
    "docs/threat_model.md",
)

RISKY_CLAIM_PATTERNS = (
    re.compile(r"\bclinical(?:ly)?\s+(?:ready|validated|approved|deployed)\b", re.IGNORECASE),
    re.compile(r"\bdiagnostic(?:ally)?\s+(?:ready|validated|approved|deployed)\b", re.IGNORECASE),
    re.compile(r"\bproduction(?:-|\s)?(?:ready|deployed|validated)\b", re.IGNORECASE),
    re.compile(r"\b(?:real|live)\s+(?:production\s+)?LIMS\b", re.IGNORECASE),
    re.compile(r"\brobot\s+controller\b", re.IGNORECASE),
    re.compile(r"\brobot(?:-|\s)?ready\s+(?:artifact|worklist|output|csv)\b", re.IGNORECASE),
    re.compile(r"\bSTARLIMS\s+clone\b", re.IGNORECASE),
    re.compile(r"\bproprietary\s+(?:STARLIMS|SOP|workflow|LIMS)\b", re.IGNORECASE),
)

DISCLAIMER_TERMS = (
    "not",
    "no ",
    "non-",
    "without",
    "out of scope",
    "excluded",
    "avoid",
    "never",
    "cannot",
    "must not",
    "future work",
    "skeleton",
    "synthetic",
    "disclaimer",
)

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"OPENROUTER_API_KEY[ \t]*=[ \t]*[^ \t\r\n]+"),
    re.compile(r"ANTHROPIC_API_KEY[ \t]*=[ \t]*[^ \t\r\n]+"),
    re.compile(r"OPENAI_API_KEY[ \t]*=[ \t]*[^ \t\r\n]+"),
)

SECRET_SCAN_GLOBS = (
    ".env.example",
    "README.md",
    "docs/*.md",
    "scripts/*.py",
    "packages/**/*.py",
    "apps/**/*.py",
    "apps/**/*.ts",
)


def main() -> int:
    failures: list[str] = []
    failures.extend(_required_docs_failures())
    failures.extend(_gitignore_failures())
    failures.extend(_env_tracking_failures())
    failures.extend(_claim_safety_failures())
    failures.extend(_secret_scan_failures())

    if failures:
        print("Portfolio check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Portfolio check passed.")
    print(f"Required docs: {len(REQUIRED_DOCS)}")
    print("Claim-safety scan: passed")
    print("Secret scan: passed")
    return 0


def _required_docs_failures() -> list[str]:
    failures = []
    for relative in REQUIRED_DOCS:
        path = REPO_ROOT / relative
        if not path.exists():
            failures.append(f"Missing required portfolio doc: {relative}")
    return failures


def _gitignore_failures() -> list[str]:
    path = REPO_ROOT / ".gitignore"
    if not path.exists():
        return ["Missing .gitignore"]
    text = path.read_text()
    failures = []
    for pattern in REQUIRED_GITIGNORE_PATTERNS:
        if pattern not in text:
            failures.append(f".gitignore missing required pattern: {pattern}")
    return failures


def _env_tracking_failures() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", ".env"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"Could not verify tracked .env status: {exc}"]
    if result.stdout.strip():
        return [".env is tracked by Git; remove it before sharing."]
    return []


def _claim_safety_failures() -> list[str]:
    failures: list[str] = []
    for path in _paths_for_globs(PUBLIC_DOC_GLOBS):
        lines = path.read_text(errors="replace").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if not any(pattern.search(line) for pattern in RISKY_CLAIM_PATTERNS):
                continue
            lowered = line.casefold()
            if any(term in lowered for term in DISCLAIMER_TERMS):
                continue
            context = "\n".join(lines[max(0, line_number - 8) : line_number]).casefold()
            if any(term in context for term in DISCLAIMER_TERMS):
                continue
            failures.append(
                f"Risky public claim without disclaimer at {path.relative_to(REPO_ROOT)}:{line_number}: "
                f"{line.strip()}"
            )
    return failures


def _secret_scan_failures() -> list[str]:
    failures: list[str] = []
    for path in _paths_for_globs(SECRET_SCAN_GLOBS):
        text = path.read_text(errors="replace")
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(0)
                if _is_placeholder_secret(value):
                    continue
                failures.append(
                    f"Potential secret in {path.relative_to(REPO_ROOT)}: {pattern.pattern}"
                )
                break
    return failures


def _is_placeholder_secret(value: str) -> bool:
    normalized = value.strip().strip("'\"")
    if normalized.endswith("="):
        return True
    if normalized.endswith("=...") or normalized.endswith("=<redacted>"):
        return True
    if "[REDACTED]" in normalized:
        return True
    if "sk-or-v1-secret" in normalized:
        return True
    return False


def _paths_for_globs(globs: tuple[str, ...]) -> tuple[Path, ...]:
    paths: dict[Path, None] = {}
    for pattern in globs:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file() and _is_public_source(path):
                paths[path] = None
    return tuple(sorted(paths))


def _is_public_source(path: Path) -> bool:
    parts = set(path.relative_to(REPO_ROOT).parts)
    return not bool(parts & {".git", ".venv", "node_modules", ".pytest_cache", ".ruff_cache", ".mypy_cache"})


if __name__ == "__main__":
    sys.exit(main())
