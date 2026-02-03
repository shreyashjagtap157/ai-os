PY = python

.PHONY: test lint format

test:
	$(PY) -m pytest -q

lint:
	ruff check . || true

run-agent:
	$(PY) -m agent.agent

run-async:
	$(PY) -m agent.async_agent
