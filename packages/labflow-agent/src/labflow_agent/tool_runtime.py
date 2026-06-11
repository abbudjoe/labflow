"""Controlled execution of deterministic LabFlow core tools."""

from __future__ import annotations

from labflow_agent.approvals import ApprovalError, ApprovalStore
from labflow_agent.artifacts import ArtifactRecord, ArtifactStore
from labflow_agent.audit import AuditEvent, AuditStore, error_result, hash_payload
from labflow_agent.models import ExecutedToolCall, JsonDict, ToolCallMode, ToolCallPlan
from labflow_agent.observability import tool_observability_payload
from labflow_agent.policies import ActionClass, ToolPolicy, ToolPolicyError
from labflow_agent.tracing import TraceTimer, new_trace_id
from labflow_core.tools.registry import call_tool, list_tools


class GuardrailViolation(ToolPolicyError):
    """Raised when a tool call fails Stage 10 guardrails after audit recording."""

    def __init__(self, message: str, *, audit_event_id: str) -> None:
        super().__init__(message)
        self.audit_event_id = audit_event_id


class AgentToolRuntime:
    """Execute known tools while enforcing read-only, dry-run, approval, and audit policy."""

    def __init__(
        self,
        *,
        audit_store: AuditStore | None = None,
        approval_store: ApprovalStore | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self._tool_definitions = {tool["name"]: tool for tool in list_tools()}
        self.policy = ToolPolicy(self._tool_definitions)
        self.audit_store = audit_store or AuditStore()
        self.approval_store = approval_store or ApprovalStore()
        self.artifact_store = artifact_store or ArtifactStore()

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tool_definitions))

    @property
    def audit_events(self) -> tuple[AuditEvent, ...]:
        return self.audit_store.list_events()

    @property
    def artifact_records(self) -> tuple[ArtifactRecord, ...]:
        return self.artifact_store.list_records()

    def approve_commit(
        self,
        *,
        action: str,
        dry_run_audit_event_id: str,
        actor_id: str = "human",
    ) -> str:
        return self.approval_store.issue(
            action=action,
            dry_run_audit_event_id=dry_run_audit_event_id,
            actor_id=actor_id,
        ).token

    def execute_plan(self, plan: tuple[ToolCallPlan, ...]) -> tuple[ExecutedToolCall, ...]:
        return tuple(self.execute_tool_call(call) for call in plan)

    def execute_tool_call(self, planned: ToolCallPlan) -> ExecutedToolCall:
        timer = TraceTimer()
        self.policy = ToolPolicy(self._tool_definitions)
        try:
            decision = self.policy.classify(planned)
        except ToolPolicyError as exc:
            audit_event = self.audit_store.record_policy_block(
                planned=planned,
                result_status="blocked",
                exception_code="POLICY_VIOLATION",
                approval_token=_optional_string_arg(planned.arguments, "approval_token"),
                dry_run_audit_event_id=_optional_string_arg(
                    planned.arguments,
                    "dry_run_audit_event_id",
                ),
            )
            result = error_result(
                tool_name=planned.tool_name,
                status="blocked",
                code="POLICY_VIOLATION",
                message=str(exc),
            )
            result = _with_agent_audit(result, audit_event, latency_ms=timer.elapsed_ms())
            return ExecutedToolCall(
                tool_name=planned.tool_name,
                arguments=planned.arguments,
                mode=planned.mode,
                result=result,
                audit_event_id=audit_event.audit_event_id,
            )

        if decision.action_class is ActionClass.COMMIT:
            return self._execute_commit(planned, timer=timer)

        result = call_tool(planned.tool_name, **planned.arguments)
        audit_event = self.audit_store.record_tool_result(planned=planned, result=result)
        result = _with_agent_audit(result, audit_event, latency_ms=timer.elapsed_ms())
        return ExecutedToolCall(
            tool_name=planned.tool_name,
            arguments=planned.arguments,
            mode=planned.mode,
            result=result,
            audit_event_id=audit_event.audit_event_id,
        )

    def _execute_commit(self, planned: ToolCallPlan, *, timer: TraceTimer) -> ExecutedToolCall:
        dry_run_audit_event_id = _string_arg(planned.arguments, "dry_run_audit_event_id")
        approval_token = _optional_string_arg(planned.arguments, "approval_token")
        if dry_run_audit_event_id is None:
            return self._block_commit(
                planned,
                message="Commit requires a prior dry-run audit event ID.",
                code="COMMIT_REQUIRES_DRY_RUN",
                dry_run_audit_event_id=None,
                approval_token=approval_token,
                timer=timer,
            )

        try:
            dry_run_event = self.audit_store.require(dry_run_audit_event_id)
            dry_run_result = self.audit_store.require_tool_result(dry_run_audit_event_id)
        except KeyError as exc:
            return self._block_commit(
                planned,
                message=str(exc),
                code="UNKNOWN_DRY_RUN_AUDIT_EVENT",
                dry_run_audit_event_id=dry_run_audit_event_id,
                approval_token=approval_token,
                timer=timer,
            )

        if dry_run_event.tool_name != planned.tool_name or dry_run_event.mode is not ToolCallMode.DRY_RUN:
            return self._block_commit(
                planned,
                message="Commit dry-run event must come from the same tool in dry_run mode.",
                code="DRY_RUN_EVENT_MISMATCH",
                dry_run_audit_event_id=dry_run_audit_event_id,
                approval_token=approval_token,
                timer=timer,
            )
        if dry_run_event.result_status != "ok":
            return self._block_commit(
                planned,
                message="Commit requires a successful dry-run result.",
                code="DRY_RUN_NOT_SUCCESSFUL",
                dry_run_audit_event_id=dry_run_audit_event_id,
                approval_token=approval_token,
                timer=timer,
            )
        if dry_run_event.input_hash != hash_payload(_dry_run_arguments_for_commit(planned)):
            return self._block_commit(
                planned,
                message="Commit inputs must match the prior dry-run inputs.",
                code="DRY_RUN_INPUT_MISMATCH",
                dry_run_audit_event_id=dry_run_audit_event_id,
                approval_token=approval_token,
                timer=timer,
            )

        try:
            self.approval_store.require_valid(
                token=approval_token,
                action=planned.tool_name,
                dry_run_audit_event_id=dry_run_audit_event_id,
            )
        except ApprovalError as exc:
            return self._block_commit(
                planned,
                message=str(exc),
                code="COMMIT_REQUIRES_APPROVAL",
                dry_run_audit_event_id=dry_run_audit_event_id,
                approval_token=approval_token,
                timer=timer,
            )

        audit_event = self.audit_store.record_tool_result(
            planned=planned,
            result=dry_run_result,
            result_status="ok",
            approval_token=approval_token,
            dry_run_audit_event_id=dry_run_audit_event_id,
        )
        records = self.artifact_store.commit_from_tool_result(
            result=dry_run_result,
            dry_run_audit_event_id=dry_run_audit_event_id,
            commit_audit_event_id=audit_event.audit_event_id,
        )
        artifact_ids = tuple(record.artifact_record_id for record in records)
        audit_event = self.audit_store.attach_artifact_ids(
            audit_event_id=audit_event.audit_event_id,
            artifact_ids=artifact_ids,
        )
        result = _with_agent_audit(dry_run_result, audit_event, latency_ms=timer.elapsed_ms())
        result["artifact_records"] = [record.to_json_dict() for record in records]
        return ExecutedToolCall(
            tool_name=planned.tool_name,
            arguments=planned.arguments,
            mode=planned.mode,
            result=result,
            audit_event_id=audit_event.audit_event_id,
        )

    def _block_commit(
        self,
        planned: ToolCallPlan,
        *,
        message: str,
        code: str,
        dry_run_audit_event_id: str | None,
        approval_token: str | None,
        timer: TraceTimer | None = None,
    ) -> ExecutedToolCall:
        audit_event = self.audit_store.record_policy_block(
            planned=planned,
            result_status="blocked",
            exception_code=code,
            approval_token=approval_token,
            dry_run_audit_event_id=dry_run_audit_event_id,
        )
        result = error_result(
            tool_name=planned.tool_name,
            status="blocked",
            code=code,
            message=message,
        )
        result = _with_agent_audit(
            result,
            audit_event,
            latency_ms=timer.elapsed_ms() if timer is not None else 0.0,
        )
        return ExecutedToolCall(
            tool_name=planned.tool_name,
            arguments=planned.arguments,
            mode=planned.mode,
            result=result,
            audit_event_id=audit_event.audit_event_id,
        )


def _with_agent_audit(result: JsonDict, audit_event: AuditEvent, *, latency_ms: float) -> JsonDict:
    enriched = dict(result)
    core_audit_event_id = enriched.get("audit_event_id")
    if isinstance(core_audit_event_id, str) and core_audit_event_id:
        enriched["core_audit_event_id"] = core_audit_event_id
    enriched["audit_event_id"] = audit_event.audit_event_id
    enriched["audit_event"] = audit_event.to_json_dict()
    enriched["observability"] = tool_observability_payload(
        trace_id=new_trace_id("trace_tool"),
        tool_name=audit_event.tool_name,
        latency_ms=latency_ms,
        status=audit_event.result_status,
    )
    return enriched


def _string_arg(arguments: JsonDict, key: str) -> str | None:
    value = arguments.get(key)
    return value if isinstance(value, str) and value else None


def _optional_string_arg(arguments: JsonDict, key: str) -> str | None:
    value = arguments.get(key)
    return value if isinstance(value, str) and value else None


def _dry_run_arguments_for_commit(planned: ToolCallPlan) -> JsonDict:
    dry_run_args = dict(planned.arguments)
    dry_run_args["dry_run"] = True
    dry_run_args["approval_token"] = None
    dry_run_args.pop("dry_run_audit_event_id", None)
    return dry_run_args
