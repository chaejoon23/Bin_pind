.PHONY: dev dev-api dev-web verify test migrate gen-types db-up db-down db-logs help

# ── Settings ──────────────────────────────────────────────────────────────────
API_DIR   := apps/api
WEB_DIR   := apps/web
OPENAPI   := $(API_DIR)/openapi.json
TYPES_OUT := packages/shared-types/src/api.ts

# ── Development ───────────────────────────────────────────────────────────────
dev: db-up dev-api dev-web

dev-api:
	cd $(API_DIR) && uvicorn app.main:app --reload --port 8000

dev-web:
	pnpm --filter=./apps/web dev

# ── Quality / CI ──────────────────────────────────────────────────────────────
verify: verify-api verify-web

verify-api:
	cd $(API_DIR) && ruff check . && ruff format --check . && mypy app

verify-web:
	pnpm --filter=./apps/web typecheck
	pnpm --filter=./apps/web lint

# ── Tests ─────────────────────────────────────────────────────────────────────
test: test-api test-web

test-api:
	cd $(API_DIR) && pytest -x -q --ignore=tests/integration

test-api-integration:
	cd $(API_DIR) && pytest -x -q tests/integration

# ── Type Generation ───────────────────────────────────────────────────────────
# 1. Export OpenAPI spec from running FastAPI
# 2. Generate TS types with openapi-typescript
gen-types:
	@echo "→ Exporting OpenAPI spec..."
	curl -sf http://localhost:8000/openapi.json -o $(OPENAPI) \
		|| (cd $(API_DIR) && python -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > ../../$(OPENAPI))
	@echo "→ Generating TypeScript types..."
	pnpm --filter=@pind/shared-types generate
	@echo "✓ Types written to $(TYPES_OUT)"

# ── Database ──────────────────────────────────────────────────────────────────
db-up:
	docker compose up -d db db_test

db-down:
	docker compose down

db-logs:
	docker compose logs -f db

migrate:
	cd $(API_DIR) && alembic upgrade head

migrate-down:
	cd $(API_DIR) && alembic downgrade -1

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  make dev               Start API + Web dev servers (+ DB)"
	@echo "  make verify            Lint + typecheck all (API + Web)"
	@echo "  make test              Run unit tests"
	@echo "  make gen-types         Export OpenAPI → generate TS types"
	@echo "  make migrate           Run Alembic migrations (head)"
	@echo "  make db-up / db-down   Manage docker-compose DB services"
	@echo ""
