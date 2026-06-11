from __future__ import annotations

import labflow_core


def test_import_labflow_core() -> None:
    assert labflow_core.__version__ == "0.1.0"
