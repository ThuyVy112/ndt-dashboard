.PHONY: compile lint typecheck test ci smoke clean-sdn

compile:
	python3 -m compileall -q src tests

lint:
	python3 -m ruff check src/schemas src/telemetry src/twin src/experiments src/orchestrator/app.py src/orchestrator/current_state.py tests/unit

typecheck:
	python3 -m mypy --ignore-missing-imports src/schemas src/telemetry src/twin src/experiments src/orchestrator/current_state.py tests/unit

test:
	python3 -m unittest discover -s tests/unit -v

ci: compile lint typecheck test

smoke:
	./scripts/smoke_test.sh

clean-sdn:
	./scripts/cleanup.sh
