# Engram

Engram is a multi-tenant, permission-aware retrieval-augmented generation (RAG) platform for engineering knowledge. It ingests documents, finds the passages relevant to a question, and answers with citations to the original sources.

`Plan.md` holds the full proposal, and `docs/specs/` holds the design for each phase.

## Getting started

You need Docker, Python 3.12, [uv](https://docs.astral.sh/uv/) and Node.js 20 or later.

Start the services from the repository root:

```bash
docker compose up -d
```

| Service | Role | Address |
|---|---|---|
| PostgreSQL | Canonical record: tenants, sources, documents, chunks, jobs, query log | `127.0.0.1:15432` |
| Qdrant | Dense vectors (BGE-M3), a projection of PostgreSQL | `127.0.0.1:6333` |
| OpenSearch | BM25 keyword index, a projection of PostgreSQL | `127.0.0.1:9200` |

Then run these commands from `backend/`:

| Task | Command |
|---|---|
| Install dependencies | `uv sync` |
| Run the API | `uv run uvicorn app.main:create_app --factory --reload` |
| Run all tests | `uv run pytest` |
| Run one test | `uv run pytest tests/test_health.py::test_health_ok -v` |
| Lint | `uv run ruff check .` |
| Rebuild the keyword index from PostgreSQL | `uv run python -m app.cli reindex-keyword` |

Tests use the real PostgreSQL, Qdrant and OpenSearch services, so start them first. The tests
that load the real reranker are marked `slow` and skip unless its weights are already in the
Hugging Face cache (`HF_HOME`).

A question runs dense search in Qdrant and BM25 search in OpenSearch in parallel, merges the
two rankings with Reciprocal Rank Fusion, and rescores the candidates with
BGE-reranker-v2-m3. The reranker's score decides whether there is enough evidence to answer
(`rerank_min_score`, chosen on the evaluation's `dev` split). The API downloads BGE-M3 and the
reranker into `HF_HOME` on first use. Set it to keep them on a disk with room for about 6 GB.

`reindex-keyword` fills an empty or rebuilt OpenSearch index with the current version of every
document, for example after the first production start with an existing database.

### Evaluation

`backend/eval/` holds 142 questions about the Kubernetes concepts documentation, with gold
sections, and the harness that measures retrieval on them. `backend/eval/README.md` describes
the corpus, how the questions were written and the split rule. Run these from `backend/` with
the services up and the corpus ingested:

| Task | Command |
|---|---|
| Check every gold label against the corpus | `uv run python -m eval.check` |
| Measure one configuration (`dense`, `hybrid`, `dense_rerank` or `hybrid_rerank`) | `uv run python -m eval.run --config hybrid_rerank` |
| Choose the evidence cutoff on the `dev` split | `uv run python -m eval.calibrate --config hybrid_rerank` |
| Ask the answer-review sample through the model | `uv run python -m eval.answers` |
| Rebuild the results document | `uv run python -m eval.report` |

The results are in [`docs/phase-2-evaluation.md`](docs/phase-2-evaluation.md). They stay
provisional until the owner has reviewed a sample of the questions and their gold labels.

### Frontend

The frontend has three pages:

| Page | What it is |
|---|---|
| `/` | Landing page: what Engram is, how the pipeline works, and what is built so far |
| `/ask` | Ask a question and read the cited answer |
| `/sources` | Upload documents, connect GitHub repositories and watch ingestion jobs |

The landing page's content lives in `frontend/lib/system.ts`. Each stage, store and phase there is marked `live` or `planned`, and the page draws planned parts dashed. Update that file when a phase lands. Its `MEASURED` numbers are copied from `backend/eval/results/*.json`, and a test fails if they drift, so update them after rerunning `eval.run`.

Run these commands from `frontend/`. The development server forwards `/api` requests to the API on port 8000, so start the API before using `/ask` or `/sources`. The landing page works without it.

| Task | Command |
|---|---|
| Install dependencies | `npm install` |
| Run the app on port 3000 | `npm run dev` |
| Run all tests | `npm test` |
| Run one test file | `npm test -- components/AnswerView.test.tsx` |
| Lint | `npm run lint` |
