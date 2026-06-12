"""Source lifecycle precedence for LabFlow corpus documents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from labflow_rag.documents import KnowledgeDocument


class SourceStatus(StrEnum):
    """Lifecycle status for corpus documents."""

    CURRENT = "current"
    RETIRED = "retired"
    DRAFT = "draft"
    LEGACY_FIXTURE = "legacy_fixture"


class AuthorityLevel(StrEnum):
    """Policy precedence for corpus documents."""

    LOCKED_DOCTRINE = "locked_doctrine"
    CURRENT_SOP = "current_sop"
    CURRENT_REFERENCE = "current_reference"
    EXAMPLE = "example"
    RETIRED_SOP = "retired_sop"
    LEGACY_FIXTURE = "legacy_fixture"


PRECEDENCE_RANK: dict[AuthorityLevel, int] = {
    AuthorityLevel.LOCKED_DOCTRINE: 100,
    AuthorityLevel.CURRENT_SOP: 80,
    AuthorityLevel.CURRENT_REFERENCE: 70,
    AuthorityLevel.EXAMPLE: 50,
    AuthorityLevel.RETIRED_SOP: 30,
    AuthorityLevel.LEGACY_FIXTURE: 10,
}


@dataclass(frozen=True)
class SourceLifecycle:
    """Derived source lifecycle metadata."""

    source_family: str
    status: SourceStatus
    version: str
    effective_date: str | None
    supersedes: str | None
    authority_level: AuthorityLevel
    stale: bool

    @property
    def precedence_rank(self) -> int:
        return PRECEDENCE_RANK[self.authority_level]

    def to_json_dict(self) -> dict[str, str | int | bool | None]:
        return {
            "source_family": self.source_family,
            "status": self.status.value,
            "version": self.version,
            "effective_date": self.effective_date,
            "supersedes": self.supersedes,
            "authority_level": self.authority_level.value,
            "precedence_rank": self.precedence_rank,
            "stale": self.stale,
        }


def lifecycle_for_document(document: KnowledgeDocument) -> SourceLifecycle:
    """Infer lifecycle metadata from tags and document naming conventions."""

    tags = set(document.tags)
    document_id = document.document_id
    text = document.text
    status = _status(tags, document_id)
    authority = _authority(tags, document_id, status)
    return SourceLifecycle(
        source_family=source_family_for_document(document),
        status=status,
        version=_front_matter_value(text, "version") or "v1",
        effective_date=_front_matter_value(text, "effective_date"),
        supersedes=_front_matter_value(text, "supersedes"),
        authority_level=authority,
        stale=status in {SourceStatus.RETIRED, SourceStatus.LEGACY_FIXTURE},
    )


def source_family_for_document(document: KnowledgeDocument) -> str:
    """Return stable source-family ID independent of filename churn."""

    for tag in document.tags:
        if tag.startswith("source_family:"):
            return tag.split(":", 1)[1].strip() or _family_from_id(document.document_id)
    return _family_from_id(document.document_id)


def lifecycle_for_chunk_tags(
    *,
    document_id: str,
    tags: tuple[str, ...],
    text: str,
) -> SourceLifecycle:
    """Infer lifecycle metadata from chunk-level values."""

    pseudo = KnowledgeDocument(
        document_id=document_id,
        source_path=document_id,
        title=Path(document_id).stem,
        headings=(),
        tags=tags,
        text=text,
    )
    return lifecycle_for_document(pseudo)


def _status(tags: set[str], document_id: str) -> SourceStatus:
    for status in SourceStatus:
        if f"status:{status.value}" in tags or status.value in tags:
            return status
    lowered = document_id.casefold()
    if "retired" in lowered or "stale" in lowered:
        return SourceStatus.RETIRED
    if "draft" in lowered:
        return SourceStatus.DRAFT
    if "fixture" in lowered or "legacy" in lowered:
        return SourceStatus.LEGACY_FIXTURE
    return SourceStatus.CURRENT


def _authority(
    tags: set[str],
    document_id: str,
    status: SourceStatus,
) -> AuthorityLevel:
    for authority in AuthorityLevel:
        if f"authority:{authority.value}" in tags or authority.value in tags:
            return authority
    lowered = document_id.casefold()
    if status is SourceStatus.LEGACY_FIXTURE:
        return AuthorityLevel.LEGACY_FIXTURE
    if status is SourceStatus.RETIRED:
        return AuthorityLevel.RETIRED_SOP
    if any(marker in lowered for marker in ("doctrine", "policy", "guardrail")):
        return AuthorityLevel.LOCKED_DOCTRINE
    if "sop" in lowered:
        return AuthorityLevel.CURRENT_SOP
    if any(marker in lowered for marker in ("reference", "spec", "manual")):
        return AuthorityLevel.CURRENT_REFERENCE
    if any(marker in lowered for marker in ("example", "case")):
        return AuthorityLevel.EXAMPLE
    return AuthorityLevel.CURRENT_REFERENCE


def _family_from_id(document_id: str) -> str:
    stem = Path(document_id).stem.casefold()
    for prefix in ("current_", "updated_", "renamed_", "retired_", "stale_", "draft_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix) :]
    for suffix in ("_v1", "_v2", "_current", "_retired", "_stale", "_copy"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem


def _front_matter_value(text: str, key: str) -> str | None:
    prefix = f"{key}:"
    for line in text.splitlines()[:30]:
        stripped = line.strip()
        if stripped.casefold().startswith(prefix):
            return stripped.split(":", 1)[1].strip() or None
    return None
