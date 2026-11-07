# Engram

Engram is a multi-tenant, permission-aware retrieval-augmented generation (RAG) platform for engineering knowledge. It ingests documents, finds the passages relevant to a question, and answers with citations to the original sources.

`Plan.md` holds the full proposal, and `docs/specs/` holds the design for each phase.

## Getting started

You need Docker, Python 3.12 and [uv](https://docs.astral.sh/uv/).

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
