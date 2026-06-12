"""Policy-critical conflict and staleness detection for retrieved sources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from labflow_rag.retrieval import RetrievalResult
from labflow_rag.source_precedence import lifecycle_for_chunk_tags


class ConflictResolution(StrEnum):
    """How a policy-critical conflict should be handled."""

    NO_CONFLICT = "no_conflict"
    LOCKED_DOCTRINE_RESOLVED = "locked_doctrine_resolved"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True)
class SourceConflict:
    """A detected conflict on a policy-critical topic."""

    topic: str
    resolution: ConflictResolution
    message: str
    source_document_ids: tuple[str, ...]

    def to_json_dict(self) -> dict[str, str | list[str]]:
        return {
            "topic": self.topic,
            "resolution": self.resolution.value,
            "message": self.message,
            "source_document_ids": list(self.source_document_ids),
        }


@dataclass(frozen=True)
class StaleSourceNotice:
    """A stale or retired source returned by retrieval."""

    document_id: str
    source_family: str
    status: str
    authority_level: str

    def to_json_dict(self) -> dict[str, str]:
        return {
            "document_id": self.document_id,
            "source_family": self.source_family,
            "status": self.status,
            "authority_level": self.authority_level,
        }


@dataclass(frozen=True)
class ConflictDetectionReport:
    """Conflict/staleness report for a retrieval result set."""

    conflicts: tuple[SourceConflict, ...]
    stale_sources: tuple[StaleSourceNotice, ...]

    @property
    def has_blocking_conflict(self) -> bool:
        return any(conflict.resolution is ConflictResolution.NEEDS_REVIEW for conflict in self.conflicts)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "conflicts": [conflict.to_json_dict() for conflict in self.conflicts],
            "stale_sources": [source.to_json_dict() for source in self.stale_sources],
        }


POLICY_TOPICS: dict[str, tuple[str, ...]] = {
    "missing_concentration": ("missing concentration", "invent concentration", "guess concentration"),
    "janus_invalid_batch": ("janus", "invalid batch", "robot-ready", "worklist"),
    "split_below_1ul": ("below 1 ul", "below 1 microliter", "split workflow", "0.4 ul"),
    "rna_requant_downstream": ("rna", "re-quant", "downstream concentration"),
    "molarity_exclusion": ("molar", "nm", "fmol", "pmol"),
    "in_place_normalization": ("in-place", "in place", "no destination"),
    "sample_ancestry": ("ancestry", "parent", "child"),
    "downstream_qc_provenance": ("downstream qc", "provenance", "lineage", "root cause"),
}

NEGATIVE_MARKERS = (
    "must not",
    "cannot",
    "do not",
    "not allowed",
    "blocked",
    "out of scope",
    "manual review",
)
POSITIVE_MARKERS = (
    "may",
    "can",
    "allowed",
    "generate",
    "infer",
    "estimate",
)


def detect_conflicts(results: tuple[RetrievalResult, ...]) -> ConflictDetectionReport:
    """Detect policy-critical conflicts and stale source usage."""

    conflicts: list[SourceConflict] = []
    stale_sources: list[StaleSourceNotice] = []
    for result in results:
        lifecycle = lifecycle_for_chunk_tags(
            document_id=result.document_id,
            tags=result.chunk.tags,
            text=result.chunk.text,
        )
        if lifecycle.stale:
            stale_sources.append(
                StaleSourceNotice(
                    document_id=result.document_id,
                    source_family=lifecycle.source_family,
                    status=lifecycle.status.value,
                    authority_level=lifecycle.authority_level.value,
                )
            )

    for topic, topic_terms in POLICY_TOPICS.items():
        relevant = tuple(result for result in results if _topic_present(result, topic_terms))
        if len(relevant) < 2:
            continue
        negative = tuple(result for result in relevant if _has_any(result.chunk.text, NEGATIVE_MARKERS))
        positive = tuple(result for result in relevant if _has_any(result.chunk.text, POSITIVE_MARKERS))
        if not negative or not positive:
            continue
        locked_negative = tuple(
            result
            for result in negative
            if lifecycle_for_chunk_tags(
                document_id=result.document_id,
                tags=result.chunk.tags,
                text=result.chunk.text,
            ).authority_level.value
            == "locked_doctrine"
        )
        source_ids = tuple(dict.fromkeys(result.document_id for result in relevant))
        if locked_negative:
            conflicts.append(
                SourceConflict(
                    topic=topic,
                    resolution=ConflictResolution.LOCKED_DOCTRINE_RESOLVED,
                    message=(
                        "Retrieved sources conflict, but locked doctrine takes precedence "
                        "over lower-authority sources."
                    ),
                    source_document_ids=source_ids,
                )
            )
        else:
            conflicts.append(
                SourceConflict(
                    topic=topic,
                    resolution=ConflictResolution.NEEDS_REVIEW,
                    message="Retrieved policy-critical sources conflict and require review.",
                    source_document_ids=source_ids,
                )
            )
    return ConflictDetectionReport(conflicts=tuple(conflicts), stale_sources=tuple(stale_sources))


def conflict_notice_for_results(results: tuple[RetrievalResult, ...]) -> str | None:
    """Return an answer-facing conflict/staleness notice when needed."""

    report = detect_conflicts(results)
    if report.has_blocking_conflict:
        missing_concentration_notice = _missing_concentration_notice(results)
        if missing_concentration_notice is not None:
            return missing_concentration_notice
        topics = ", ".join(conflict.topic for conflict in report.conflicts)
        return (
            "Conflict detected in retrieved LabFlow sources. "
            f"({topics}). The answer requires manual review before relying on these sources."
        )
    if report.stale_sources:
        families = ", ".join(source.source_family for source in report.stale_sources)
        return f"Retrieved stale corpus sources for {families}; verify current policy before relying on them."
    return None


def _topic_present(result: RetrievalResult, terms: tuple[str, ...]) -> bool:
    haystack = f"{result.chunk.title} {' '.join(result.chunk.tags)} {result.chunk.text}".casefold()
    return any(term in haystack for term in terms)


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in markers)


def _missing_concentration_notice(results: tuple[RetrievalResult, ...]) -> str | None:
    documents = {result.document_id for result in results}
    if "legacy_missing_concentration_sop.md" not in documents:
        return None
    current_sources = [
        result.document_id
        for result in results
        if result.document_id != "legacy_missing_concentration_sop.md"
        and (
            "no_invention" in result.chunk.tags
            or "trusted_concentration_source" in result.chunk.tags
            or "deterministic_validation" in result.chunk.tags
            or "guardrails" in result.chunk.tags
            or "current guardrail" in result.chunk.text.casefold()
            or "manual review" in result.chunk.text.casefold()
        )
    ]
    if not current_sources:
        return None
    sources = ", ".join(["legacy_missing_concentration_sop.md", *dict.fromkeys(current_sources)])
    return (
        "Conflict detected in retrieved LabFlow sources. "
        "A retired source permits estimating a missing concentration, while current "
        "guardrail policy requires measured trusted data. Resolution: Current "
        "guardrail policy and deterministic validation take precedence. "
        f"Sources: {sources}."
    )
