from __future__ import annotations

import pytest

from labflow_agent import (
    DeterministicFakeModel,
    LabFlowAgentRuntime,
    ModelConfigurationError,
    OpenRouterModelAdapter,
    OpenRouterAnswerComposer,
    answer_model_from_env,
    model_from_env,
)


def test_model_factory_defaults_to_deterministic_without_env() -> None:
    model = model_from_env({})

    assert isinstance(model, DeterministicFakeModel)


def test_answer_model_factory_defaults_to_no_optional_composer() -> None:
    assert answer_model_from_env({}) is None


def test_runtime_uses_factory_default_without_explicit_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LABFLOW_MODEL_PROVIDER", raising=False)
    runtime = LabFlowAgentRuntime()

    assert isinstance(runtime._model, DeterministicFakeModel)


def test_runtime_can_explicitly_disable_answer_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LABFLOW_ANSWER_COMPOSER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    runtime = LabFlowAgentRuntime(answer_model=None)

    assert runtime._answer_model is None


def test_openrouter_provider_requires_api_key() -> None:
    with pytest.raises(ModelConfigurationError) as exc_info:
        model_from_env({"LABFLOW_MODEL_PROVIDER": "openrouter", "OPENROUTER_API_KEY": ""})

    assert "OPENROUTER_API_KEY" in str(exc_info.value)


def test_openrouter_answer_composer_requires_api_key() -> None:
    with pytest.raises(ModelConfigurationError) as exc_info:
        answer_model_from_env({"LABFLOW_ANSWER_COMPOSER": "openrouter", "OPENROUTER_API_KEY": ""})

    assert "OPENROUTER_API_KEY" in str(exc_info.value)


def test_unknown_provider_fails_closed() -> None:
    with pytest.raises(ModelConfigurationError) as exc_info:
        model_from_env({"LABFLOW_MODEL_PROVIDER": "surprise"})

    assert str(exc_info.value) == "Unknown LABFLOW_MODEL_PROVIDER: surprise"


def test_openrouter_provider_uses_env_config_without_exposing_secret() -> None:
    model = model_from_env(
        {
            "LABFLOW_MODEL_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "secret-test-key",
            "LABFLOW_OPENROUTER_MODEL": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "OPENROUTER_BASE_URL": "https://example.invalid/api/v1",
        }
    )

    assert isinstance(model, OpenRouterModelAdapter)
    assert model.metadata.provider == "openrouter"
    assert model.metadata.model_id == "nvidia/nemotron-3-ultra-550b-a55b:free"
    assert "secret-test-key" not in repr(model.metadata)


def test_openrouter_model_id_rejects_embedded_env_assignment() -> None:
    with pytest.raises(ModelConfigurationError) as exc_info:
        model_from_env(
            {
                "LABFLOW_MODEL_PROVIDER": "openrouter",
                "OPENROUTER_API_KEY": "secret-test-key",
                "LABFLOW_OPENROUTER_MODEL": (
                    "LABFLOW_OPENROUTER_MODEL=nvidia/nemotron-nano-9b-v2:free"
                ),
            }
        )

    assert "must be a model id only" in str(exc_info.value)


def test_openrouter_answer_composer_uses_env_config_without_exposing_secret() -> None:
    composer = answer_model_from_env(
        {
            "LABFLOW_ANSWER_COMPOSER": "openrouter",
            "OPENROUTER_API_KEY": "secret-test-key",
            "LABFLOW_OPENROUTER_MODEL": "nvidia/nemotron-nano-9b-v2:free",
            "OPENROUTER_BASE_URL": "https://example.invalid/api/v1",
        }
    )

    assert isinstance(composer, OpenRouterAnswerComposer)
    assert composer.metadata.provider == "openrouter-answer"
    assert composer.metadata.model_id == "nvidia/nemotron-nano-9b-v2:free"
    assert "secret-test-key" not in repr(composer.metadata)


def test_openrouter_timeout_seconds_must_be_numeric() -> None:
    with pytest.raises(ModelConfigurationError) as exc_info:
        model_from_env(
            {
                "LABFLOW_MODEL_PROVIDER": "openrouter",
                "OPENROUTER_API_KEY": "secret-test-key",
                "OPENROUTER_TIMEOUT_SECONDS": "slow",
            }
        )

    assert str(exc_info.value) == "OPENROUTER_TIMEOUT_SECONDS must be a number."


def test_openrouter_timeout_seconds_must_be_positive() -> None:
    with pytest.raises(ModelConfigurationError) as exc_info:
        model_from_env(
            {
                "LABFLOW_MODEL_PROVIDER": "openrouter",
                "OPENROUTER_API_KEY": "secret-test-key",
                "OPENROUTER_TIMEOUT_SECONDS": "0",
            }
        )

    assert str(exc_info.value) == "OPENROUTER_TIMEOUT_SECONDS must be greater than 0."
