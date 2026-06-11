from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
from typing import Any


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "run_model_eval_comparison.py"


def _load_comparison_module() -> Any:
    spec = importlib.util.spec_from_file_location("run_model_eval_comparison_test", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[str(spec.name)] = module
    spec.loader.exec_module(module)
    return module


def test_dotenv_defaults_load_without_overriding_shell_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_comparison_module()
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            (
                "# local LabFlow settings",
                "LABFLOW_OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b:free",
                "OPENROUTER_APP_TITLE='LabFlow Test'",
                "OPENROUTER_TIMEOUT_SECONDS=12",
                "IGNORED_LINE_WITHOUT_EQUALS",
            )
        )
    )
    monkeypatch.delenv("LABFLOW_OPENROUTER_MODEL", raising=False)
    monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "20")

    module._load_dotenv_defaults(env_path)

    assert os.environ["LABFLOW_OPENROUTER_MODEL"] == "nvidia/nemotron-3-super-120b-a12b:free"
    assert os.environ["OPENROUTER_APP_TITLE"] == "LabFlow Test"
    assert os.environ["OPENROUTER_TIMEOUT_SECONDS"] == "20"
