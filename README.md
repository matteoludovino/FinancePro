# FinancePro

Personal finance from your bank statements: import the CSV your bank exports, get the spending categorized (rules first, Claude for what no rule covers, always confirmed by you), and follow budgets on a dashboard. Credit cards are modeled as liabilities, so paying the bill never counts the same spending twice, and installments ("parcela 3/10") are tracked across statements.

The interface is in Brazilian Portuguese; code and docs are in English.

> Work in progress.

## Stack

FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · Next.js 16 · React 19 · Tailwind 4 · uv.

## Local development

```bash
docker compose up -d                       # PostgreSQL on :5437

cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn financepro.main:app --port 8020 --reload   # API on :8020, docs on /api/docs

cd ../frontend
npm install
npm run dev                                # http://localhost:3010 (proxies /api to :8020)
```

## Checks

```bash
cd backend
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests migrations
uv run alembic check
uv run pytest                              # against the PostgreSQL above (database financepro_test)

cd ../frontend
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```
