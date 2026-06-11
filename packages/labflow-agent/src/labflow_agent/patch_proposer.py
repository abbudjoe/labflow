"""Typed dry-run patch proposal models for repair-planning evals."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PatchProposalMode(StrEnum):
    """Supported repair proposal modes."""

    PATCH = "patch"
    SAFE_REFUSAL = "safe_refusal"


class LabFlowPatchOperation(BaseModel):
    """One explicit workflow patch operation."""

    model_config = ConfigDict(frozen=True)

    op: str = Field(pattern="^(add|replace|remove)$")
    path: str = Field(min_length=1)
    value: Any | None = None
    reason: str = Field(min_length=1)
    evidence: tuple[str, ...] = Field(default_factory=tuple)


class PatchProposal(BaseModel):
    """Dry-run-only repair proposal returned by an inference composer or fixture."""

    model_config = ConfigDict(frozen=True)

    mode: PatchProposalMode
    dry_run: bool = True
    requires_approval_before_commit: bool = True
    operations: tuple[LabFlowPatchOperation, ...] = Field(default_factory=tuple)
    refusal_reason: str | None = None
    audit_expectation: str = Field(
        default="Patch proposal must be audited as a dry-run before commit approval."
    )

    @model_validator(mode="after")
    def _validate_mode_contract(self) -> PatchProposal:
        if not self.dry_run:
            raise ValueError("Repair proposals must be dry-run only.")
        if self.mode is PatchProposalMode.SAFE_REFUSAL:
            if self.operations:
                raise ValueError("Safe refusals must not include patch operations.")
            if not self.refusal_reason:
                raise ValueError("Safe refusals require a refusal reason.")
        if self.mode is PatchProposalMode.PATCH and not self.operations:
            raise ValueError("Patch proposals require at least one operation.")
        return self
