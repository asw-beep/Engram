# Engram

Engram is a multi-tenant, permission-aware retrieval-augmented generation (RAG) platform for engineering knowledge. It ingests documents, finds the passages relevant to a question, and answers with citations to the original sources.

`Plan.md` holds the full proposal, and `docs/specs/` holds the design for each phase.

## Getting started

You need Docker, Python 3.12, [uv](https://docs.astral.sh/uv/) and Node.js 20 or later.

Start Postgres and Qdrant from the repository root:

```bash
docker compose up -d
```

Then run these commands from `backend/`:

| Task | Command |
|---|---|
| Install dependencies | `uv sync` |
| Run the API | `uv run uvicorn app.main:create_app --factory --reload` |
| Run all tests | `uv run pytest` |
| Run one test | `uv run pytest tests/test_health.py::test_health_ok -v` |
| Lint | `uv run ruff check .` |

Tests use the real Postgres and Qdrant services, so start them first.

### Frontend

The frontend has three pages:

| Page | What it is |
|---|---|
| `/` | Landing page: what Engram is, how the pipeline works, and what is built so far |
| `/ask` | Ask a question and read the cited answer |
| `/sources` | Upload documents, connect GitHub repositories and watch ingestion jobs |

The landing page's content lives in `frontend/lib/system.ts`. Each stage, store and phase there is marked `live` or `planned`, and the page draws planned parts dashed. Update that file when a phase lands.

Run these commands from `frontend/`. The development server forwards `/api` requests to the API on port 8000, so start the API before using `/ask` or `/sources`. The landing page works without it.

| Task | Command |
|---|---|
| Install dependencies | `npm install` |
| Run the app on port 3000 | `npm run dev` |
| Run all tests | `npm test` |
| Run one test file | `npm test -- components/AnswerView.test.tsx` |
| Lint | `npm run lint` |
