"""Model adapter factory for LabFlow agent runtime construction."""

from __future__ import annotations

import os
from collections.abc import Mapping

from labflow_agent.answer_model import AnswerModelAdapter
from labflow_agent.models import ModelAdapter
from labflow_agent.openrouter import (
    DEFAULT_OPENROUTER_BASE_URL,
    DEFAULT_OPENROUTER_MODEL,
    OpenRouterConfig,
    OpenRouterError,
    OpenRouterModelAdapter,
)
from labflow_agent.openrouter_answer import OpenRouterAnswerComposer
from labflow_agent.planner import DeterministicFakeModel


class ModelConfigurationError(ValueError):
    """Raised when model provider configuration is invalid."""


def model_from_env(env: Mapping[str, str] | None = None) -> ModelAdapter:
    """Build the configured model adapter, defaulting to deterministic local planning."""

    values = os.environ if env is None else env
    provider = values.get("LABFLOW_MODEL_PROVIDER", "deterministic").strip().casefold()
    if provider in {"", "deterministic", "local", "fake"}:
        return DeterministicFakeModel()
    if provider == "openrouter":
        api_key = values.get("OPENROUTER_API_KEY", "")
        if not api_key.strip():
            raise ModelConfigurationError(
                "OPENROUTER_API_KEY is required when LABFLOW_MODEL_PROVIDER=openrouter."
            )
        try:
            model = _openrouter_model_id(values)
            return OpenRouterModelAdapter(
                _openrouter_config(values, api_key=api_key, model=model)
            )
        except OpenRouterError as exc:
            raise ModelConfigurationError(str(exc)) from exc

    raise ModelConfigurationError(f"Unknown LABFLOW_MODEL_PROVIDER: {provider}")


def answer_model_from_env(env: Mapping[str, str] | None = None) -> AnswerModelAdapter | None:
    """Build the optional answer composer, defaulting to deterministic composition only."""

    values = os.environ if env is None else env
    provider = values.get("LABFLOW_ANSWER_COMPOSER", "deterministic").strip().casefold()
    if provider in {"", "deterministic", "local", "none", "off"}:
        return None
    if provider == "openrouter":
        api_key = values.get("OPENROUTER_API_KEY", "")
        if not api_key.strip():
            raise ModelConfigurationError(
                "OPENROUTER_API_KEY is required when LABFLOW_ANSWER_COMPOSER=openrouter."
            )
        try:
            return OpenRouterAnswerComposer(
                _openrouter_config(values, api_key=api_key, model=_openrouter_model_id(values))
            )
        except OpenRouterError as exc:
            raise ModelConfigurationError(str(exc)) from exc

    raise ModelConfigurationError(f"Unknown LABFLOW_ANSWER_COMPOSER: {provider}")


def _openrouter_model_id(values: Mapping[str, str]) -> str:
    model = values.get("LABFLOW_OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL) or DEFAULT_OPENROUTER_MODEL
    if "=" in model:
        raise ModelConfigurationError(
            "LABFLOW_OPENROUTER_MODEL must be a model id only, for example "
            "nvidia/nemotron-nano-9b-v2:free."
        )
    return model


def _openrouter_timeout_seconds(values: Mapping[str, str]) -> float:
    raw_value = values.get("OPENROUTER_TIMEOUT_SECONDS", "30") or "30"
    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise ModelConfigurationError("OPENROUTER_TIMEOUT_SECONDS must be a number.") from exc
    if timeout <= 0:
        raise ModelConfigurationError("OPENROUTER_TIMEOUT_SECONDS must be greater than 0.")
    return timeout


def _openrouter_config(values: Mapping[str, str], *, api_key: str, model: str) -> OpenRouterConfig:
    return OpenRouterConfig(
        api_key=api_key,
        model=model,
        base_url=values.get("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL)
        or DEFAULT_OPENROUTER_BASE_URL,
        http_referer=values.get("OPENROUTER_HTTP_REFERER") or None,
        app_title=values.get("OPENROUTER_APP_TITLE", "LabFlow AI Studio") or "LabFlow AI Studio",
        timeout_seconds=_openrouter_timeout_seconds(values),
        max_retries=_openrouter_int(values, "OPENROUTER_MAX_RETRIES", 1, minimum=0),
        retry_backoff_seconds=_openrouter_float(
            values, "OPENROUTER_RETRY_BACKOFF_SECONDS", 1.0, minimum=0.0
        ),
        retry_backoff_multiplier=_openrouter_float(
            values, "OPENROUTER_RETRY_BACKOFF_MULTIPLIER", 2.0, minimum=1.0
        ),
        retry_max_backoff_seconds=_openrouter_float(
            values, "OPENROUTER_RETRY_MAX_BACKOFF_SECONDS", 8.0, minimum=0.0
        ),
        fallback_models=_openrouter_fallback_models(values),
        enable_metadata=_openrouter_bool(values, "OPENROUTER_ENABLE_METADATA", default=False),
        response_format=_openrouter_response_format(values),
    )


def _openrouter_int(
    values: Mapping[str, str],
    name: str,
    default: int,
    *,
    minimum: int,
) -> int:
    raw_value = values.get(name, str(default)) or str(default)
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ModelConfigurationError(f"{name} must be an integer.") from exc
    if parsed < minimum:
        raise ModelConfigurationError(f"{name} must be at least {minimum}.")
    return parsed


def _openrouter_float(
    values: Mapping[str, str],
    name: str,
    default: float,
    *,
    minimum: float,
) -> float:
    raw_value = values.get(name, str(default)) or str(default)
    try:
        parsed = float(raw_value)
    except ValueError as exc:
        raise ModelConfigurationError(f"{name} must be a number.") from exc
    if parsed < minimum:
        raise ModelConfigurationError(f"{name} must be at least {minimum:g}.")
    return parsed


def _openrouter_bool(values: Mapping[str, str], name: str, *, default: bool) -> bool:
    raw_value = values.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    normalized = raw_value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ModelConfigurationError(f"{name} must be true or false.")


def _openrouter_fallback_models(values: Mapping[str, str]) -> tuple[str, ...]:
    raw_value = values.get("LABFLOW_OPENROUTER_FALLBACK_MODELS", "") or ""
    models = tuple(model.strip() for model in raw_value.split(",") if model.strip())
    invalid = [model for model in models if "=" in model]
    if invalid:
        raise ModelConfigurationError("LABFLOW_OPENROUTER_FALLBACK_MODELS must contain model ids only.")
    return models


def _openrouter_response_format(values: Mapping[str, str]) -> str:
    raw_value = values.get("LABFLOW_OPENROUTER_RESPONSE_FORMAT", "json_object") or "json_object"
    normalized = raw_value.strip().casefold()
    if normalized not in {"json_object", "json_schema", "off"}:
        raise ModelConfigurationError(
            "LABFLOW_OPENROUTER_RESPONSE_FORMAT must be json_object, json_schema, or off."
        )
    return normalized
