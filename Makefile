# Containerized dev workflow — no host venv. Everything runs in a throwaway container.
PY_IMAGE ?= python:3.12-slim
DOCKER_RUN = docker run --rm -v "$(CURDIR)":/app -w /app $(PY_IMAGE) sh -c

.PHONY: check lint test shell build

# Lint + tests, the bar for "done". Pulls latest dev deps each run.
check:
	$(DOCKER_RUN) "pip install --no-cache-dir -e '.[dev]' -q && ruff check src tests && pytest -q"

lint:
	$(DOCKER_RUN) "pip install --no-cache-dir -e '.[dev]' -q && ruff check src tests"

test:
	$(DOCKER_RUN) "pip install --no-cache-dir -e '.[dev]' -q && pytest -q"

shell:
	docker run --rm -it -v "$(CURDIR)":/app -w /app $(PY_IMAGE) bash

# Build the runtime image (the actual exporter container).
build:
	docker build -f runtimes/docker/Dockerfile -t beneylu-photo-sync:dev .
