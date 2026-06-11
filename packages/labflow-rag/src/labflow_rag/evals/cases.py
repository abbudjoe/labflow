"""Golden eval case loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    """One RAG golden-question eval case."""

    id: str
    category: str
    question: str
    required_sources: tuple[str, ...]
    expected_answer_contains: tuple[str, ...]
    disallowed_answer_contains: tuple[str, ...]
    required_tool_calls: tuple[str, ...]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "question": self.question,
            "required_sources": list(self.required_sources),
            "expected_answer_contains": list(self.expected_answer_contains),
            "disallowed_answer_contains": list(self.disallowed_answer_contains),
            "required_tool_calls": list(self.required_tool_calls),
        }


def load_golden_cases(path: str | Path = "evals/golden_questions.yaml") -> tuple[EvalCase, ...]:
    """Load and validate golden eval cases from the repository YAML subset."""

    raw_cases = _parse_golden_yaml(Path(path).read_text())
    cases = tuple(_case_from_mapping(raw_case, index=index) for index, raw_case in enumerate(raw_cases, start=1))
    _validate_unique_ids(cases)
    return cases


def _case_from_mapping(raw_case: dict[str, object], *, index: int) -> EvalCase:
    required_fields = {
        "id",
        "category",
        "question",
        "required_sources",
        "expected_answer_contains",
        "required_tool_calls",
    }
    missing = sorted(required_fields - set(raw_case))
    if missing:
        msg = f"Eval case {index} is missing required fields: {', '.join(missing)}"
        raise ValueError(msg)
    return EvalCase(
        id=_required_string(raw_case, "id", index=index),
        category=_required_string(raw_case, "category", index=index),
        question=_required_string(raw_case, "question", index=index),
        required_sources=_required_string_tuple(raw_case, "required_sources", index=index),
        expected_answer_contains=_required_string_tuple(
            raw_case,
            "expected_answer_contains",
            index=index,
        ),
        disallowed_answer_contains=_optional_string_tuple(
            raw_case,
            "disallowed_answer_contains",
            index=index,
        ),
        required_tool_calls=_required_string_tuple(raw_case, "required_tool_calls", index=index),
    )


def _required_string(raw_case: dict[str, object], field: str, *, index: int) -> str:
    value = raw_case[field]
    if not isinstance(value, str) or not value:
        msg = f"Eval case {index} field {field!r} must be a non-empty string."
        raise ValueError(msg)
    return value


def _required_string_tuple(
    raw_case: dict[str, object],
    field: str,
    *,
    index: int,
) -> tuple[str, ...]:
    value = raw_case[field]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        msg = f"Eval case {index} field {field!r} must be a list of strings."
        raise ValueError(msg)
    return tuple(value)


def _optional_string_tuple(
    raw_case: dict[str, object],
    field: str,
    *,
    index: int,
) -> tuple[str, ...]:
    if field not in raw_case:
        return ()
    return _required_string_tuple(raw_case, field, index=index)


def _validate_unique_ids(cases: tuple[EvalCase, ...]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for case in cases:
        if case.id in seen:
            duplicates.append(case.id)
        seen.add(case.id)
    if duplicates:
        msg = f"Duplicate eval case IDs: {', '.join(sorted(duplicates))}"
        raise ValueError(msg)


def _parse_golden_yaml(text: str) -> list[dict[str, object]]:
    """Parse the simple golden-case YAML subset used by this repository."""

    cases: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    current_list_key: str | None = None

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("- "):
            if not line.startswith("- id:"):
                msg = f"Unsupported top-level list item at line {line_number}: {line}"
                raise ValueError(msg)
            if current is not None:
                cases.append(current)
            current = {}
            key, value = _split_key_value(line[2:], line_number=line_number)
            current[key] = _parse_scalar(value)
            current_list_key = None
            continue
        if current is None:
            msg = f"Expected eval case before line {line_number}: {line}"
            raise ValueError(msg)
        if not line.startswith("  "):
            msg = f"Unsupported indentation at line {line_number}: {line}"
            raise ValueError(msg)

        stripped = line.strip()
        if stripped.startswith("- "):
            if current_list_key is None:
                msg = f"List item without a list field at line {line_number}: {line}"
                raise ValueError(msg)
            current_value = current.get(current_list_key)
            if not isinstance(current_value, list):
                msg = f"Field {current_list_key!r} is not a list at line {line_number}: {line}"
                raise ValueError(msg)
            parsed_item = _parse_scalar(stripped[2:].strip())
            if not isinstance(parsed_item, str):
                msg = f"Nested lists are not supported at line {line_number}: {line}"
                raise ValueError(msg)
            current_value.append(parsed_item)
            continue

        key, value = _split_key_value(stripped, line_number=line_number)
        parsed = _parse_scalar(value)
        current[key] = parsed
        current_list_key = key if isinstance(parsed, list) else None

    if current is not None:
        cases.append(current)
    if not cases:
        msg = "No eval cases found."
        raise ValueError(msg)
    return cases


def _split_key_value(text: str, *, line_number: int) -> tuple[str, str]:
    if ":" not in text:
        msg = f"Expected key/value pair at line {line_number}: {text}"
        raise ValueError(msg)
    key, value = text.split(":", 1)
    normalized_key = key.strip()
    if not normalized_key:
        msg = f"Empty key at line {line_number}: {text}"
        raise ValueError(msg)
    return normalized_key, value.strip()


def _parse_scalar(value: str) -> str | list[str]:
    if value == "":
        return []
    if value == "[]":
        return []
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value
