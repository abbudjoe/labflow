PYTHON ?= $(shell command -v python3.12 2>/dev/null || command -v python3 2>/dev/null || command -v python)
UV ?= $(shell command -v uv 2>/dev/null)

ifdef UV
	PYTEST ?= $(UV) run --python $(PYTHON) --with pytest --with pydantic --with pyyaml --with fastapi --with httpx python -m pytest
	RUFF ?= $(UV) run --python $(PYTHON) --with ruff python -m ruff
	MYPY ?= $(UV) run --python $(PYTHON) --with mypy --with pydantic --with pyyaml --with types-PyYAML --with fastapi python -m mypy
	EVAL_LADDER ?= $(UV) run --python $(PYTHON) --with pytest --with pydantic --with pyyaml --with fastapi --with httpx python scripts/run_inference_eval_ladder.py
else
PYTEST ?= $(PYTHON) -m pytest
RUFF ?= $(PYTHON) -m ruff
MYPY ?= $(PYTHON) -m mypy
EVAL_LADDER ?= $(PYTHON) scripts/run_inference_eval_ladder.py
endif

PYTHONPATH := packages/labflow-core/src:packages/labflow-rag/src:packages/labflow-agent/src:apps/api/src
PYTHON_SRC := packages/labflow-core/src packages/labflow-rag/src packages/labflow-agent/src apps/api/src
PYTHON_TESTS := packages/labflow-core/tests packages/labflow-rag/tests packages/labflow-agent/tests apps/api/tests

.PHONY: test lint type type-python type-vscode portfolio-check eval-summary demo-portfolio eval-ladder eval-ladder-live

test:
	PYTHONPATH="$(PYTHONPATH)" $(PYTEST) --rootdir=. $(PYTHON_TESTS)

lint:
	$(RUFF) check $(PYTHON_SRC) $(PYTHON_TESTS)

type: type-python type-vscode

type-python:
	PYTHONPATH="$(PYTHONPATH)" $(MYPY) --strict $(PYTHON_SRC)

type-vscode:
	@if [ ! -d apps/vscode-extension/node_modules ]; then \
		npm install --prefix apps/vscode-extension --no-package-lock; \
	fi
	npm --prefix apps/vscode-extension run compile

portfolio-check:
	PYTHONPATH="$(PYTHONPATH)" $(PYTHON) scripts/portfolio_check.py

eval-summary:
	PYTHONPATH="$(PYTHONPATH)" $(PYTHON) scripts/summarize_portfolio_evals.py

demo-portfolio:
	PYTHONPATH="$(PYTHONPATH)" $(PYTHON) scripts/run_demo.py --output-dir /tmp/labflow-portfolio-demo
	PYTHONPATH="$(PYTHONPATH)" $(PYTHON) scripts/summarize_portfolio_evals.py

eval-ladder:
	@PYTHONUNBUFFERED=1 PYTHONPATH="$(PYTHONPATH)" $(EVAL_LADDER) --no-live

eval-ladder-live:
	@set -a; [ ! -f .env ] || . ./.env; set +a; \
	PYTHONUNBUFFERED=1 PYTHONPATH="$(PYTHONPATH)" $(EVAL_LADDER) \
		--live-openrouter \
		--confirm-live-openrouter \
		--openrouter-timeout-seconds 20 \
		--max-case-seconds 45 \
		--verbose
