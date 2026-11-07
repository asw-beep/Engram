# Engram Phase 1: Foundation and Basic RAG

**Status:** Approved on 2026-11-07. Amended on 2026-11-07: the owner moved the AWS server to Phase 4, so Phase 1 ends with production containers verified on the laptop (§9, §11).
**Parent document:** `Plan.md`. § references point to it.

This spec covers Phase 1 only. Each later phase gets its own spec and implementation plan.

## 1. Goal

Load a set of engineering documents, ask a question in a simple chat page, and get an answer with citations to the real sources, running locally both in development and in the production containers. The production containers are ready for one AWS server, which Phase 4 sets up.

### Agreed understanding

**Decided by the project owner:**

- The Phase 1 demo includes a simple chat page, not only an API.
- Phase 1 also runs on AWS, at low cost. Changed on 2026-11-07: the AWS server is deferred to Phase 4.
- OpenRouter's free models provide the LLM.
- Kaggle T4 GPUs are available for bulk embedding.
- The code uses plain libraries in clear modules, not LlamaIndex or LangChain.
- Source code and OpenAPI files stay out of Phase 1.
- Questions stand alone, with no follow-up handling, in Phase 1.

**Assumed from `Plan.md`, open to correction:**

- One developer is building this for a final submission or portfolio.
- Phase 1 data is public or synthetic (Appendix B), so sending it to Kaggle and OpenRouter is acceptable.

### Changes from `Plan.md`

| Topic | `Plan.md` | This spec |
|---|---|---|
| Frontend | Required by §16, but scheduled in no §11 phase | Simple chat page in Phase 1 |
| AWS deployment | Phase 4 | Production containers in Phase 1, verified on the laptop. The AWS server stays in Phase 4 |
| Object storage | S3 or MinIO | Disk volume behind `storage/`, because Phase 1 has no need for an extra service |
| File types | §4.1 lists OpenAPI and code-related sources | `.md`, `.pdf` and `.docx` only |

Source code and OpenAPI ingestion still need a phase. No phase in §11 schedules them, so the next phase spec must assign them.

## 2. Scope

**In scope:** Markdown, PDF and DOCX ingestion from uploads and public GitHub repositories; structure-aware chunking; BGE-M3 dense embeddings; Qdrant search; grounded answers with validated citations; a two-screen web app; production containers for a single server.

**Out of scope:**

| Item | Planned for |
|---|---|
| OpenSearch, hybrid search, RRF, reranking | Phase 2 |
| Query rewriting and follow-up questions | Phase 2 |
| Retrieval and faithfulness evaluation | Phase 2 |
| Login, role-based access, `acl_grants` | Phase 3 |
| Celery workers, webhooks, scheduled sync | Phase 3 |
| Deletion propagation | Phase 3 |
| Monitoring stack, CI/CD, load testing | Phase 4 |
| OCR for scanned PDFs | Not scheduled |

A file removed from a GitHub repository stays searchable until deletion propagation arrives in Phase 3.

## 3. Architecture

```text
engram/
├── backend/
│   ├── app/
│   │   ├── api/          HTTP routes only
│   │   ├── ingestion/    connectors, parsers, chunkers, pipeline
│   │   ├── embedding/    BGE-M3
│   │   ├── retrieval/    Qdrant search
│   │   ├── generation/   prompts, OpenRouter client, citation checks
│   │   ├── storage/      saved original files
│   │   ├── db/           tables and queries
│   │   └── cli.py        export-chunks and import-vectors commands
│   ├── migrations/
│   └── tests/
├── frontend/             Next.js chat page
├── notebooks/            Kaggle embedding notebook
├── deploy/               Caddyfile (server scripts and runbook come in Phase 4)
├── docker-compose.yml        local Postgres and Qdrant
└── docker-compose.prod.yml   all services in containers
```

**Stack:** Python 3.12, `uv`, FastAPI, SQLAlchemy, Alembic, pytest, Next.js, TypeScript, PostgreSQL, Qdrant, Docker Compose, Caddy.

### Boundaries

- Routes hold no business logic.
- `ingestion`, `retrieval` and `generation` do not import each other. They may depend on `db`, `embedding` and `storage`.
- All tenant-owned queries take a tenant ID.

### Interfaces

```python
class Connector(Protocol):
    def list_items(self) -> Iterable[SourceItem]: ...
    def fetch(self, item: SourceItem) -> FetchedFile: ...

class Embedder(Protocol):
    model_id: str
    model_revision: str
    dimension: int
    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...

class Retriever(Protocol):
    def search(self, query: str, scope: AccessScope, limit: int) -> list[RetrievalHit]: ...

class LLMProvider(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...
```

`AccessScope` holds the tenant ID and the caller's principals. Phase 2 adds OpenSearch as a second `Retriever`.

### Runtime environments

| Environment | Runs in Docker | Runs outside Docker | Embedding device |
|---|---|---|---|
| Laptop | Postgres, Qdrant | API and frontend | CUDA |
| Production containers (laptop in Phase 1, AWS in Phase 4) | Caddy, frontend, API, Postgres, Qdrant | Nothing | CPU |

The laptop API runs through `uv` because that gives simpler GPU access on Windows.

### Models and configuration

| Setting | Value |
|---|---|
| Embedding model | `BAAI/bge-m3`, dense vectors only, 1024 dimensions |
| `EMBEDDING_MODEL_REVISION` | `5617a9f61b028005a4858fdac845db406aefb181` |
| `LLM_MODEL` | `nvidia/nemotron-3.5-super-vl:free` |
| `LLM_FALLBACK_MODEL` | `google/gemma-4-31b-it:free` |
| Maximum chunk size | 512 tokens |
| Overlap | 50 tokens, only when splitting a long section |
| Chunks retrieved | 20 |
| Passages sent to the LLM | Up to 8, within about 4,000 tokens |
| `EVIDENCE_MIN_SCORE` | 0.30 as a starting value, recalibrated in build step 5 |
| Maximum question length | 2,000 characters |
| Maximum upload size | 25 MB per file |
| LLM request timeout | 60 seconds |

Also configured by environment: `DATABASE_URL`, `QDRANT_URL`, `STORAGE_DIR`, `EMBEDDING_DEVICE`, `EMBEDDING_BATCH_SIZE`, `OPENROUTER_API_KEY` and an optional `GITHUB_TOKEN`.

OpenRouter's free model list changes, so model names live in configuration. Both models were checked against the live list on 2026-11-07. `gemma-4-31b-it:free` supports JSON mode but not schema-enforced structured output, so all LLM output is validated with Pydantic regardless of model.

The chunking and retrieval numbers are starting values. Phase 2 evaluates them.

## 4. Data model

Every table except `tenants` carries `tenant_id`.

| Table | Main fields |
|---|---|
| `tenants` | `id`, `name` |
| `sources` | `id`, `tenant_id`, `type` (`upload` or `github`), `name`, `config` (repository, branch, include paths) |
| `documents` | `id`, `tenant_id`, `source_id`, `path`, `file_type`, `allowed_principals`, `current_version_id` |
| `document_versions` | `id`, `tenant_id`, `document_id`, `content_hash`, `revision`, `storage_key`, `created_at` |
| `chunks` | `id`, `tenant_id`, `document_version_id`, `position`, `content`, `heading_path`, `start_line`, `end_line`, `page_start`, `page_end`, `token_count`, `embedding_model`, `embedded_at` |
| `ingestion_jobs` | `id`, `tenant_id`, `source_id`, `status`, `input`, `file_counts`, `errors`, `started_at`, `finished_at` |
| `query_logs` | `id`, `tenant_id`, `question`, `answer`, `outcome`, `chunk_ids`, `model`, `input_tokens`, `output_tokens`, `latency_ms`, `created_at` |

**Constraints:**

- `documents`: unique on `tenant_id`, `source_id`, `path`.
- `document_versions`: unique on `document_id`, `content_hash`.
- `chunks`: unique on `document_version_id`, `position`.
- `ingestion_jobs`: at most one open job per source, enforced with a partial unique index on the `pending`, `running` and `awaiting_embedding` statuses.

**Tenant:** a migration creates one default tenant and one default upload source. `get_current_tenant()` returns the default tenant, and Phase 3 replaces it with the logged-in user's tenant.

**Permissions:** `allowed_principals` is a text array defaulting to `{tenant}`, meaning everyone in the tenant. Phase 3 tightens it by updating these values.

### Qdrant

- Collection: `chunks_bge_m3_v1`, 1024 dimensions, cosine distance.
- Point ID: the chunk ID.
- Payload: `tenant_id`, `document_id`, `document_version_id`, `allowed_principals`. The first and last are indexed.
- Chunk text is stored only in Postgres. Search returns IDs, and the text is then loaded from Postgres.
- A different embedding model gets a new collection, so vectors from different models never mix.
- Only the current version of a document stays in Qdrant. Older versions stay in Postgres.

## 5. Ingestion

### API

| Route | Purpose |
|---|---|
| `POST /api/sources` | Create a GitHub source |
| `GET /api/sources` | List sources |
| `POST /api/sources/{id}/documents` | Upload files to an upload source |
| `POST /api/sources/{id}/sync` | Sync a GitHub source |
| `GET /api/jobs`, `GET /api/jobs/{id}` | Show job progress |
| `POST /api/jobs/{id}/retry` | Retry a finished job that didn't succeed |

Each route that starts work creates an `ingestion_jobs` row and returns its ID straight away. A plain `run_ingestion(job_id)` function does the work through FastAPI background tasks, and Celery can call the same function in Phase 3.

Uploaded files are written to `storage/` before the job is created, so an upload job can be retried.

### Pipeline

For each file:

1. **Fetch.** The connector gets the file. The GitHub connector downloads one archive of the commit and keeps only `.md`, `.pdf` and `.docx` files that match the source's include paths. Phase 1 supports public repositories.
2. **Compare.** Hash the content. If it matches a published version, skip the file. If it matches an unpublished version, resume at step 6.
3. **Parse.** Save the original, then convert it to a common format of sections, each with a heading path and a line or page range.
4. **Chunk.** Markdown splits by heading. PDF and DOCX split by headings where available, otherwise by page or paragraph.
5. **Save.** Write the version and chunks to Postgres in one transaction. Chunk IDs are UUIDv5 values derived from the version ID and position.
6. **Embed.** Embed the heading path followed by the chunk text, in batches.
7. **Publish.** Add points to Qdrant, set `current_version_id`, then remove the old version's points.

Search drops any chunk whose version isn't current, so nothing appears twice between the last two parts of step 7.

Job statuses are `pending`, `running`, `awaiting_embedding`, `succeeded`, `partial`, `failed` and `interrupted`.

### Kaggle route

A job can stop after step 5 with the status `awaiting_embedding`:

1. `python -m app.cli export-chunks --job <id> --out <file>` writes the waiting chunks to JSONL with a manifest of the model ID, revision and dimension.
2. You add that file to a private Kaggle dataset and run `notebooks/kaggle_embed.ipynb`.
3. The notebook writes Parquet shards of `chunk_id` and `vector` to `/kaggle/working`, and skips finished shards if it restarts.
4. `python -m app.cli import-vectors --job <id> --in <dir>` checks the model ID, revision, dimension and chunk IDs, then runs step 7.

The laptop GPU is the default. Kaggle is for loads that are too slow locally.

## 6. Questions and citations

`POST /api/questions` takes a question and returns an outcome, answer and citations.

1. **Search.** Embed the question and get the 20 closest chunks from Qdrant, filtered by tenant and `allowed_principals`.
2. **Recheck.** Load the chunks from Postgres, then check tenant, access and current version again.
3. **Evidence check.** If no chunk reaches `EVIDENCE_MIN_SCORE`, return `insufficient_evidence` without calling the LLM.
4. **Build context.** Remove duplicates and keep up to 8 passages within about 4,000 tokens, numbered `[1]` onwards.
5. **Generate.** Call OpenRouter asking for this JSON:

   ```json
   { "status": "answered", "answer": "Text with inline [1] markers." }
   ```

   `status` is `answered` or `insufficient_evidence`.
6. **Validate citations.** Remove markers that don't match a passage. If an `answered` response has no valid marker left, return `unverifiable`.
7. **Respond and log.** Return the answer and citations, and write a `query_logs` row.

Each citation holds the marker number, document path, source name, heading path, line or page range, revision and a text snippet. GitHub citations link to the exact commit and line range.

**Outcomes:** `answered`, `insufficient_evidence`, `unverifiable`, `quota_exhausted`, `llm_error`.

**Citation validation is structural.** Phase 1 confirms that a cited passage exists, not that it supports the claim. Phase 2 measures support through faithfulness evaluation (§10.2).

### Untrusted content

Passages are clearly delimited as data, and the prompt tells the model never to follow instructions inside them. The model has no tools. The frontend renders model output as plain text, and only the backend builds citation links.

### Chat page

- **Ask screen:** a question box, the answer with clickable `[n]` markers, and source details. Answers appear all at once with a loading state, because citations can only be checked once the full answer is back.
- **Sources screen:** uploads, GitHub syncs, job progress and retry.

## 7. Error handling

### Ingestion

| Failure | Behaviour |
|---|---|
| Bad file, such as a scanned PDF with no text | Record the path and reason in `errors`, continue the job |
| GitHub or Qdrant temporary error | Retry up to 3 times with increasing waits |
| Failure before publishing | The old version stays searchable. A retry resumes the remaining work |
| API restart during a job | `running` jobs become `interrupted` at startup and can be retried |
| GPU out of memory | Halve the batch size and try again, failing at batch size 1 |

A job ends as `succeeded` if every file was processed or skipped as unchanged, `partial` if some failed, and `failed` if all failed or the job couldn't start.

### Questions

| Failure | Behaviour |
|---|---|
| OpenRouter daily quota used up | No retry. Return the retrieved passages with outcome `quota_exhausted` |
| Main model error, timeout or invalid output | Try the fallback model once. If that fails, return `llm_error` |
| Postgres or Qdrant unavailable | Return HTTP 503, and never answer without evidence |

An HTTP 429 counts as `quota_exhausted` only when OpenRouter reports its own free-model daily limit. A 429 caused by the upstream provider counts as a model error and uses the fallback.

Assume every attempt counts against the 50 daily requests, including failed ones. Every question writes a `query_logs` row when Postgres is available.

## 8. Testing

Tests are written first, following test-driven development.

| Layer | Covers | Uses |
|---|---|---|
| Unit | Parsers, chunkers, context building, citation checks | Sample files |
| Integration | Full ingestion and question flows, retries, restarts | Real Postgres and Qdrant, fake `Embedder` and `LLMProvider` |
| Tenant isolation | Tenant B can't reach tenant A's data, including when Qdrant returns a foreign chunk | Two test tenants |
| Frontend | Citation display, and model output staying plain text | Component tests |
| Manual smoke test | About 10 real questions through the real model | OpenRouter quota, run only by a separate command |

Normal test runs never call OpenRouter and never download BGE-M3. A document containing injected instructions is part of the sample files, and tests confirm it stays inside the passage delimiters.

## 9. AWS deployment

**Deferred to Phase 4** on 2026-11-07, by the owner's decision. Phase 1 built the production containers (`docker-compose.prod.yml`) and verified them on the laptop. The design below is the starting point for Phase 4.

**Server:** one `m7i-flex.large` (2 vCPU, 8 GiB) with 30 GB of gp3 storage, set up from a short runbook and scripts in `deploy/`. Terraform can wait for Phase 4. The region is a single setting chosen at deployment.

**Security:**

- Phase 1 has no login, so the firewall allows web and SSH access only from the owner's IP address.
- Postgres and Qdrant have no public ports.
- API keys live in a `.env` file on the server, readable only by its owner, and never in the repository.
- The app uses plain HTTP. Sharing it with other people needs a domain, HTTPS and a password, which is a separate piece of work.

**Cost:**

- A timer stops the server every night. A stopped server keeps its data.
- AWS Budgets alerts at $5 and $10.
- A script starts the server and prints its new IP address.
- Expected cost is about $12 a month at 90 running hours, using N. Virginia prices checked on 2026-11-07. New AWS customers may qualify for free-plan credits.

**Memory:** each container gets a memory cap, and a 2 GiB swap file absorbs spikes. If 8 GiB proves too small, `t3.xlarge` offers 16 GiB at about $0.17 an hour, but isn't on the free plan's eligible list.

**Updates:**

- **Code:** the server pulls from GitHub with a read-only deploy key and rebuilds.
- **Data:** the laptop is the source of truth. A script copies a Postgres dump, a Qdrant snapshot and the saved files to the server, replacing the server's data. Anything uploaded only on the server is lost at the next sync.

## 10. Build order

**Early checks**, before depending on these assumptions:

1. BGE-M3 fits on the 6 GB RTX 3050.
2. BGE-M3 runs acceptably with 2 CPUs and 8 GiB, simulated with Docker limits on the laptop.
3. The free model returns usable, structured answers.

**Build steps:**

1. **Project setup:** backend, frontend, Compose, migrations and test tooling.
2. **Database schema:** tables, constraints, default tenant and default upload source.
3. **Markdown upload:** storage, parsing, heading-based chunking, content hashing and job tracking.
4. **Embeddings:** BGE-M3 in batches, publishing to Qdrant.
5. **Question answering:** search, citations and the chat page, then recalibrate `EVIDENCE_MIN_SCORE` with real test questions.
6. **More sources:** PDF, DOCX, the GitHub connector and the Kaggle route.
7. **Production containers:** run the whole stack in containers on the laptop and check it end to end. The AWS server is deferred to Phase 4.

Steps 1 to 5 give a working end-to-end demo, so step 6 can slip without breaking it.

## 11. Definition of done

- A Markdown file uploaded in the chat app can be asked about, and the answer cites it.
- PDF and DOCX uploads work the same way.
- A public GitHub repository can be synced, and its citations link to the exact commit.
- Re-ingesting unchanged content creates no new versions.
- Changing a file publishes a new version, and only that version is searchable.
- A question with no supporting evidence returns `insufficient_evidence` without an LLM call.
- A job can pause for Kaggle embedding and finish through `import-vectors`.
- All automated tests pass, including tenant isolation.
- The production stack starts with one command, publishes only Caddy's port, and answers a question with citations using the CPU, with every container under its memory limit.

Moved to Phase 4 on 2026-11-07:

- The app runs on AWS from the owner's IP address, and the server stops itself overnight.
- The manual smoke test has run against the deployed app, with results recorded.

The §10.5 acceptance targets are not Phase 1 criteria, because Phase 2 creates the evaluation dataset they depend on.
