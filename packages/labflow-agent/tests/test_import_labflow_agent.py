from __future__ import annotations

import labflow_agent


def test_import_labflow_agent() -> None:
    assert labflow_agent.__version__ == "0.1.0"
