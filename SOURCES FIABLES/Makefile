.PHONY: test test-changed test-failed lint format help

PYTHON = .venv\Scripts\python.exe

help:
	@echo "CERTUS Makefile targets:"
	@echo "  make test          - Run the full test suite"
	@echo "  make test-changed  - Run tests only for changed files in Git"
	@echo "  make test-failed   - Rerun tests that failed last time (--lf)"
	@echo "  make lint          - Run Ruff linter check"
	@echo "  make format        - Run Ruff formatter"

test:
	$(PYTHON) scripts/run_certus_tests.py

test-changed:
	$(PYTHON) scripts/run_certus_tests.py --changed-only

test-failed:
	$(PYTHON) scripts/run_certus_tests.py --lf

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .
