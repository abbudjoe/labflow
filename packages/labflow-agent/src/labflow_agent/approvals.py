"""Local approval-token store for guarded commit actions."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ApprovalError(ValueError):
    """Raised when an approval token is missing, unknown, or mismatched."""


class ApprovalRecord(BaseModel):
    """Approval granted for a specific dry-run event and action."""

    model_config = ConfigDict(frozen=True)

    approval_token_id: str = Field(min_length=1)
    token: str = Field(min_length=1)
    action: str = Field(min_length=1)
    dry_run_audit_event_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    created_at: str = Field(min_length=1)


class ApprovalStore:
    """In-memory approval token registry for local-first Stage 10 behavior."""

    def __init__(self) -> None:
        self._records_by_token_id: dict[str, ApprovalRecord] = {}

    def issue(
        self,
        *,
        action: str,
        dry_run_audit_event_id: str,
        actor_id: str = "human",
    ) -> ApprovalRecord:
        token = f"approval_token_{uuid4().hex}"
        token_id = approval_token_id(token)
        record = ApprovalRecord(
            approval_token_id=token_id,
            token=token,
            action=action,
            dry_run_audit_event_id=dry_run_audit_event_id,
            actor_id=actor_id,
            created_at=_utc_now(),
        )
        self._records_by_token_id[token_id] = record
        return record

    def require_valid(
        self,
        *,
        token: str | None,
        action: str,
        dry_run_audit_event_id: str,
    ) -> ApprovalRecord:
        if token is None or token == "":
            msg = "Commit requires an approval token."
            raise ApprovalError(msg)
        token_id = approval_token_id(token)
        record = self._records_by_token_id.get(token_id)
        if record is None:
            msg = "Approval token is unknown."
            raise ApprovalError(msg)
        if record.action != action:
            msg = "Approval token action does not match the requested commit."
            raise ApprovalError(msg)
        if record.dry_run_audit_event_id != dry_run_audit_event_id:
            msg = "Approval token does not match the required dry-run event."
            raise ApprovalError(msg)
        return record

    def get(self, token_id: str) -> ApprovalRecord | None:
        return self._records_by_token_id.get(token_id)


def approval_token_id(token: str) -> str:
    """Return the stable, non-secret identifier for an approval token."""

    return f"approval_{sha256(token.encode()).hexdigest()[:12]}"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
