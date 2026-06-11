from __future__ import annotations

import labflow_api


def test_import_labflow_api() -> None:
    assert labflow_api.__version__ == "0.1.0"
