.PHONY: dev test build lint fmt typecheck migrate seed install lock

# ── Local dev ──────────────────────────────────────────────────────────────────
dev:
	docker compose up --build

dev-api:
	uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# ── Dependencies ───────────────────────────────────────────────────────────────
install:
	uv sync --locked

# After editing dependencies in pyproject.toml (add --upgrade to `uv lock` to
# move everything forward). The MCP images install the exported files.
lock:
	uv lock
	for s in file db search api; do \
		uv export --locked --quiet --only-group mcp-$$s --no-emit-project \
			-o mcp_servers/mcp_$$s/requirements.txt || exit 1; \
	done

install-frontend:
	cd frontend && npm install

# ── Database ───────────────────────────────────────────────────────────────────
migrate:
	uv run alembic upgrade head

migrate-down:
	uv run alembic downgrade -1

migration:
	uv run alembic revision --autogenerate -m "$(name)"

seed:
	uv run python scripts/seed.py

# ── Quality ────────────────────────────────────────────────────────────────────
# CI runs `make lint` and `make test`; lefthook runs the same checks (lefthook.yml).
lint:
	uv run --only-dev ruff check .

fmt:
	uv run --only-dev ruff format .

typecheck:
	uv run mypy api orchestrator db rag

# ── Tests ──────────────────────────────────────────────────────────────────────
# Needs a hive_test database (see README "Tests"). -rs prints why anything skipped.
test:
	uv run pytest -v -rs --cov=api --cov=orchestrator --cov=db --cov=rag --cov-report=term-missing

# ── Build ──────────────────────────────────────────────────────────────────────
build:
	docker compose build

push:
	docker compose push

# ── Utilities ──────────────────────────────────────────────────────────────────
logs:
	docker compose logs -f api

psql:
	docker compose exec postgres psql -U hive -d hive

example:
	uv run python scripts/example_run.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
