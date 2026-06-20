# Containerized dev workflow — no host venv. Everything runs in a throwaway container.
PY_IMAGE ?= python:3.12-slim
DOCKER_RUN = docker run --rm -v "$(CURDIR)":/app -w /app $(PY_IMAGE) sh -c

.PHONY: check lint test shell build css

# Lint + tests, the bar for "done". Pulls latest dev deps each run.
check:
	$(DOCKER_RUN) "pip install --no-cache-dir -e '.[dev,web]' -q && ruff check src tests && pytest -q"

lint:
	$(DOCKER_RUN) "pip install --no-cache-dir -e '.[dev,web]' -q && ruff check src tests"

test:
	$(DOCKER_RUN) "pip install --no-cache-dir -e '.[dev,web]' -q && pytest -q"

shell:
	docker run --rm -it -v "$(CURDIR)":/app -w /app $(PY_IMAGE) bash

# Build the runtime image (the actual exporter container).
build:
	docker build -f runtimes/docker/Dockerfile -t beneylu-photo-sync:dev .

# Compile the committed cosmos.css from the vendored Tailwind v4 source.
# Runs the Tailwind v4 CLI in a throwaway Node container (no host Node, no
# Node at runtime). Re-run only when template classes change; commit the output.
CSS_SRC = src/beneylu_photo_sync/web/assets/cosmos/cosmos.src.css
CSS_OUT = src/beneylu_photo_sync/web/static/cosmos.css
css:
	docker run --rm -v "$(CURDIR)":/app -w /app node:22-alpine sh -c \
	  "npm install --no-save --no-package-lock tailwindcss@4 @tailwindcss/cli@4 >/dev/null 2>&1 && \
	   ./node_modules/.bin/tailwindcss -i $(CSS_SRC) -o $(CSS_OUT) --minify; \
	   status=\$$?; rm -rf node_modules; exit \$$status"
	@echo "✅ Wrote $(CSS_OUT)"
