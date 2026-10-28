.PHONY: dev test build lint fmt migrate seed install lock

# ── Local dev ──────────────────────────────────────────────────────────────────
dev:
	docker compose up --build

dev-api:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

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
	alembic upgrade head

migrate-down:
	alembic downgrade -1

migration:
	alembic revision --autogenerate -m "$(name)"

seed:
	python scripts/seed.py

# ── Quality ────────────────────────────────────────────────────────────────────
lint:
	ruff check .

fmt:
	ruff format .

typecheck:
	mypy api orchestrator db

# ── Tests ──────────────────────────────────────────────────────────────────────
test:
	pytest -v --cov=api --cov=orchestrator --cov=db --cov-report=term-missing

test-watch:
	pytest -v -f

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
	python scripts/example_run.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
