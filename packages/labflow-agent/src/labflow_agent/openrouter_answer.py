"""Optional OpenRouter answer-composer adapter for grounded LabFlow answers."""

from __future__ import annotations

import json
from hashlib import sha256

from pydantic import ValidationError

from labflow_agent.answer_model import (
    ClaimRewriteDraft,
    GroundedAnswerContext,
    GroundedAnswerDraft,
    draft_from_rendered_answer,
    render_grounded_answer_frame,
)
from labflow_agent.models import JsonDict, ModelExecutionMetadata, ModelMetadata
from labflow_agent.openrouter import (
    ChatCompletionClient,
    OpenRouterConfig,
    OpenRouterError,
    UrlLibOpenRouterClient,
    complete_chat_content,
    _metadata_from_error,
)

OPENROUTER_ANSWER_ADAPTER_VERSION = "openrouter-answer-adapter-0.2.0"
OPENROUTER_ANSWER_PROMPT_ID = "labflow_grounded_claim_rewriter"
OPENROUTER_ANSWER_PROMPT_VERSION = "stage18.13"

_SYSTEM_PROMPT = (
    "You are the optional claim rewriter for LabFlow AI Studio. Return only one JSON object. "
    "Deterministic validators and the supplied answer_frame own lab truth, claims, citations, "
    "tool results, unsupported state, artifact eligibility, and approval state. "
    "You may only improve wording for existing claim IDs in answer_frame.claims. "
    "Do not add claim IDs. Do not remove protected terms. Do not cite sources or tools. "
    "Do not include citation IDs, source IDs, tool IDs, approval tokens, artifact IDs, sample IDs, "
    "new concentrations, new wells, standards, blanks, or JANUS rows. "
    "If unsupported is true, return an empty rewrites object. "
    "When validation blocks a batch, preserve the not robot-ready meaning; never rewrite it as robot-ready. "
    "Use readable prose with spaces between words. "
    "The JSON object must match this shape exactly: "
    '{"rewrites":{"claim_id":"rewritten sentence preserving protected terms"},'
    '"next_safe_action_rewrite":null}.'
)
OPENROUTER_ANSWER_PROMPT_SHA256 = sha256(_SYSTEM_PROMPT.encode("utf-8")).hexdigest()


class OpenRouterAnswerComposer:
    """OpenRouter-backed answer composer over fixed grounded context."""

    def __init__(
        self,
        config: OpenRouterConfig,
        *,
        client: ChatCompletionClient | None = None,
    ) -> None:
        if not config.api_key.strip():
            raise OpenRouterError(
                "openrouter_missing_api_key",
                "OPENROUTER_API_KEY is required when OpenRouter answer composition is selected.",
            )
        self._config = config
        self._client = client or UrlLibOpenRouterClient(config)
        self._execution_metadata: ModelExecutionMetadata | None = None
        self.metadata = ModelMetadata(
            model_id=config.model,
            version=OPENROUTER_ANSWER_ADAPTER_VERSION,
            provider="openrouter-answer",
        )

    def last_execution_metadata(self) -> ModelExecutionMetadata | None:
        """Return sanitized metadata for the most recent OpenRouter answer call."""

        return self._execution_metadata

    def draft(self, context: GroundedAnswerContext) -> GroundedAnswerDraft:
        """Return a deterministic draft with optional bounded rewrites."""

        rewrite = self._rewrite_from_messages(_messages_for_context(context))
        return draft_from_rendered_answer(render_grounded_answer_frame(context, rewrite))

    def repair(
        self,
        context: GroundedAnswerContext,
        *,
        rejected_draft: GroundedAnswerDraft,
        validation_reasons: tuple[str, ...],
    ) -> GroundedAnswerDraft:
        """Return one repaired answer draft using deterministic validation feedback."""

        rewrite = self._rewrite_from_messages(
            _messages_for_context(
                context,
                repair_feedback={
                    "validation_reasons": list(validation_reasons),
                    "rejected_answer_preview": rejected_draft.answer[:600],
                    "rejected_claim_citations": [
                        citation.model_dump(mode="json")
                        for citation in rejected_draft.claim_citations
                    ],
                },
            )
        )
        return draft_from_rendered_answer(render_grounded_answer_frame(context, rewrite))

    def _rewrite_from_messages(self, messages: list[JsonDict]) -> ClaimRewriteDraft:
        self._execution_metadata = None
        try:
            content, metadata = complete_chat_content(
                config=self._config,
                client=self._client,
                messages=messages,
                schema=ClaimRewriteDraft.model_json_schema(),
            )
            self._execution_metadata = metadata
            raw_rewrite = json.loads(content)
            if not isinstance(raw_rewrite, dict):
                raise OpenRouterError(
                    "answer_rewrite_not_object",
                    "OpenRouter answer rewrite content did not decode to a JSON object.",
                )
            return ClaimRewriteDraft.model_validate(raw_rewrite)
        except json.JSONDecodeError as exc:
            raise OpenRouterError(
                "answer_rewrite_json_invalid",
                "OpenRouter answer rewrite content was not valid JSON.",
            ) from exc
        except ValidationError as exc:
            raise OpenRouterError(
                "answer_rewrite_schema_invalid",
                f"OpenRouter answer rewrite did not match schema ({exc.error_count()} validation errors).",
            ) from exc
        except OpenRouterError as exc:
            self._execution_metadata = _metadata_from_error(self._config, exc)
            raise


def _messages_for_context(
    context: GroundedAnswerContext,
    *,
    repair_feedback: JsonDict | None = None,
) -> list[JsonDict]:
    evidence_inventory = {
        "prompt_metadata": {
            "prompt_id": OPENROUTER_ANSWER_PROMPT_ID,
            "prompt_version": OPENROUTER_ANSWER_PROMPT_VERSION,
            "prompt_sha256": OPENROUTER_ANSWER_PROMPT_SHA256,
        },
        "authority_boundary": (
            "Return rewrites only. The deterministic renderer owns citations, "
            "tool evidence IDs, blocked reason, unsupported state, and final answer assembly."
        ),
    }
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(evidence_inventory, sort_keys=True)},
        {
            "role": "user",
            "content": json.dumps(context.sanitized_prompt_payload(), sort_keys=True),
        },
    ]
    if repair_feedback is not None:
        messages.append({"role": "user", "content": json.dumps({"repair_feedback": repair_feedback}, sort_keys=True)})
    return messages
