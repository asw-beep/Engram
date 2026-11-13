# Engram Phase 2: Advanced Retrieval

**Status:** Draft for owner review, 2026-11-13.
**Parent documents:** `Plan.md` (§ references point to it) and `docs/specs/2026-11-07-phase-1-foundation-design.md`.

This spec covers Phase 2 only. Source-code and OpenAPI ingestion follow it as a separate step with its own spec, before Phase 3.

## 1. Goal

Add keyword search, rank fusion and reranking to retrieval, and measure each addition against a documented evaluation dataset, so the system's retrieval quality is a reported number and not a claim.

### Agreed understanding

**Decided by the project owner:**

- Keyword search uses OpenSearch BM25, as `Plan.md` §6.4 describes.
- Work proceeds in a measured order: evaluation dataset and dense-only baseline first, then BM25 with rank fusion, then the reranker. Each step is measured before the next.
- The evaluation corpus is the Kubernetes concepts section, with about 120 answerable and 20 unanswerable questions.
- Source-code and OpenAPI ingestion are not part of Phase 2. They are the next step after it.

**Assumed, open to correction:**

- The laptop (24 GB RAM, 6 GB GPU) runs everything in this phase. The production server's size is a Phase 4 decision (§10).
- OpenRouter's free models stay the only LLM, so anything that needs many model calls is out of reach.

### Success criteria

- `docs/phase-2-evaluation.md` reports dense, hybrid, and hybrid with reranking side by side on the documented dataset.
- Every number in it can be reproduced with one documented command.
- Tenant and permission filtering hold in OpenSearch exactly as they do in Qdrant, proven by tests.
- The §10.5 targets are reported as met or missed. Meeting them is not a condition for finishing the phase.

## 2. Scope

**In scope:** evaluation dataset and harness; OpenSearch as a second projection; hybrid retrieval with Reciprocal Rank Fusion; cross-encoder reranking; recalibrated evidence cutoff; query-log timings; the three issues carried from Phase 1; landing page status updates.

**Out of scope:**

| Item | Why |
|---|---|
| Source-code and OpenAPI ingestion | Separate step after this phase |
| LLM query rewriting | Optional in §5.2, and each rewrite costs a model call from a small free quota |
| LLM-judged faithfulness and answer relevance (§10.2) | The free quota can't cover it. A manual review of a sample stands in |
| Per-document cap on passages (§6.7 source diversity) | Added only if the evaluation shows one document crowding out others |
| Redis, caching, authentication, background workers | Phase 3 |

## 3. Evaluation

### Corpus

All Markdown under `content/en/docs/concepts/` in `kubernetes/website` at commit `df4b759d54d331622a0003d25e8f713852e98dae`, the commit Phase 1 used. It is ingested through the GitHub connector into a source named `kubernetes/website`. None of it is synthetic.

### Dataset

`backend/eval/questions.jsonl`, one question per line:

| Field | Meaning |
|---|---|
| `id` | Stable identifier, such as `k8s-042` |
| `question` | The question text |
| `kind` | `conceptual`, `exact_term` or `multi_section` for answerable questions; `unanswerable` otherwise |
| `gold` | For answerable questions, one or more `{ "path": ..., "headings": [...] }` entries naming the document and the heading path of the section that answers it. Empty for unanswerable questions |
| `split` | `dev` or `test` |

- About 120 answerable questions: roughly half `conceptual`, a third `exact_term` (flags, field names, API kinds, error strings) and the rest `multi_section`, which need two sections.
- About 20 `unanswerable` questions: half unrelated to Kubernetes, half about Kubernetes topics the concepts section doesn't cover.
- Gold labels name sections, not chunk IDs, so they survive re-chunking and re-ingestion.
- 40% of each kind is `dev` and 60% is `test`. Tuning (the evidence cutoff, any parameter change) uses `dev` only. Reported numbers come from `test`.

`backend/eval/README.md` documents the corpus, the commit, how the questions were written, and the split. It states that the questions were written for this project and were not collected from real users. The owner reviews a sample of about 20 questions and their gold labels before any reported number counts.

### Relevance

A retrieved chunk is relevant to a question when its document path equals a gold `path` and its heading path starts with that gold entry's `headings`. For NDCG, a chunk in a gold section has grade 2, and a chunk elsewhere in a gold document has grade 1.

### Metrics

| Metric | Over |
|---|---|
| Recall@5, Recall@10 | Answerable `test` questions: a relevant chunk appears in the top K. For `multi_section`, every gold section must appear |
| MRR@10, NDCG@10 | Answerable `test` questions |
| Evidence gate | Share of answerable questions that pass the cutoff, and share of unanswerable ones that are refused |
| Retrieval latency | Median and p95 per question, with models already loaded, excluding generation |

Each metric is also broken down by `kind`.

### Harness

`uv run python -m eval.run --config <name>` runs retrieval for every question in a configuration and writes `backend/eval/results/<name>.json`. The configurations are `dense`, `hybrid` and `hybrid_rerank`. `uv run python -m eval.report` builds `docs/phase-2-evaluation.md` from the result files. The harness calls the same retrieval code the API uses, through the same settings.

### Answer review

For 15 `test` questions chosen by a fixed rule (every eighth answerable question), the full pipeline runs once with the final configuration. The results doc records each outcome and, by hand, whether each citation supports its claim. This is a manual sample, not a metric.

## 4. OpenSearch projection

OpenSearch joins `docker-compose.yml` as a single node bound to `127.0.0.1`, with a 512 MB heap and its security plugin disabled for local use. The image tag is pinned to an exact version in the plan. Production Compose gains the same service on the internal network only.

`app/db/keyword_index.py` holds a `KeywordIndex` that mirrors `VectorIndex`:

| Method | Behaviour |
|---|---|
| `ensure_index()` | Creates the index with its mappings if missing |
| `upsert(chunks)` | Indexes chunk ID, text, heading text, tenant ID, document ID, version ID and allowed principals |
| `delete_version(version_id)` | Removes every chunk of a version |
| `search(query, scope, limit)` | BM25 over text and headings, filtered by tenant and by at least one shared principal inside the query |
| `count()` | Number of indexed chunks |

- The index name is versioned (`chunks_v1`) and set in settings.
- Text is indexed twice: with the standard analyzer, and with an identifier analyzer that keeps terms such as `kube-scheduler` and `spec.nodeName` whole as well as split. Headings get a boost.
- Unlike Qdrant, the index stores chunk text. It is still a rebuildable projection: PostgreSQL stays canonical.

### Consistency

- A new document version becomes current only after both Qdrant and OpenSearch hold its chunks. Then the old version is deleted from both. A failure partway leaves the old version current, and the job's retry is idempotent.
- The Kaggle route indexes text into OpenSearch when vectors are imported, at the same point Qdrant is written.
- `uv run python -m app.cli reindex-keyword` rebuilds the index from PostgreSQL for every current version. It backfills data ingested before this phase and repairs drift.
- The health endpoint reports OpenSearch alongside PostgreSQL and Qdrant.

## 5. Retrieval

```
question → dense (Qdrant, 50) ─┐
         → keyword (BM25, 50) ─┴→ RRF (k=60) → top 30 → PostgreSQL recheck
         → rerank → evidence cutoff → context (8 passages, 4,000 tokens) → model
```

- **Preprocessing:** the question is trimmed and its whitespace collapsed. Nothing else changes it.
- **Hybrid:** `HybridRetriever` runs the dense and keyword searches in parallel and merges their rankings with `RRF(d) = Σ 1 / (60 + rank)`. A chunk found by both appears once.
- **Recheck:** the existing PostgreSQL recheck runs before reranking, so the reranker only reads text the asker may see.
- **Reranking:** `Reranker` is a protocol with one implementation, BGE-reranker-v2-m3 at a pinned revision, loaded in half precision on the GPU with `HF_HOME` inside `data/`. It scores each question and passage pair, and its score (0 to 1) replaces the passage's score.
- **Evidence cutoff:** applies to the reranker score when reranking is on. Its value is chosen on the `dev` split as the threshold that maximises balanced accuracy between answerable and unanswerable questions, using each question's top score. The value and the rule are recorded in the results doc. Dense-only mode keeps its own cutoff.
- **Settings:** `retrieval_mode` (`dense` or `hybrid`) and `rerank_enabled`. Defaults are `hybrid` and on.

### Degraded operation

| Failure | Behaviour |
|---|---|
| OpenSearch down at question time | Answer from dense search alone, log a warning, record `dense_fallback` in the query log |
| Qdrant down | `retrieval_unavailable`, as today. Keyword search alone isn't offered |
| Reranker fails to load or run | `retrieval_unavailable`. Scores without reranking aren't comparable to the cutoff |
| OpenSearch down during ingestion | The version isn't published, the job retries, and the old version stays current |

## 6. Carried from Phase 1

- **Hugo shortcodes:** the Markdown parser removes shortcode tags such as `{{< glossary_tooltip text="Pod" ... >}}`, keeping a `text` attribute's value where one exists, and removes paired tags while keeping their inner content. Line numbers still refer to the original file.
- **"Passage N" in answers:** the prompt tells the model to refer to evidence only through `[n]` markers and never to name passages in prose.
- **Wrong top hit on the Service question:** it becomes one of the evaluation questions, so the results show whether hybrid search and reranking fix it.

## 7. Query log

A migration adds to `query_logs`: `retrieval_mode` (`dense`, `hybrid` or `dense_fallback`), `reranked` (boolean), and `retrieve_ms`, `rerank_ms` and `generate_ms`. Existing rows get nulls.

## 8. Frontend

When the phase's work is merged, `frontend/lib/system.ts` marks BM25, fusion, reranking, OpenSearch and Phase 2 as `live`. After the evaluation is recorded, the landing page gains a short "Measured" block with Recall@5, MRR@10 and NDCG@10 for the three configurations, the dataset size, and a link to the results doc. The block's numbers live in `system.ts` and are copied from the results doc, never estimated.

## 9. Testing

| Area | Check |
|---|---|
| `KeywordIndex` | Against real OpenSearch: upsert, search, delete by version, identifier terms match |
| Tenant isolation | A chunk from another tenant, or with no shared principal, never comes back from keyword or hybrid search |
| Publish | A version isn't current until both indexes have it. A failure in either leaves the old version current |
| `reindex-keyword` | Rebuilds an emptied index to match PostgreSQL's current versions |
| RRF | Ranking for known inputs, ties, a chunk in one list only, an empty list |
| Hybrid retriever | Falls back to dense when keyword search raises, and records it |
| Reranker | Orders a relevant passage above an irrelevant one. Marked as a slow test that needs the model |
| Question flow | Cutoff applies to reranker scores. Reranker failure gives `retrieval_unavailable` |
| Metrics | Recall, MRR and NDCG for hand-computed cases, including `multi_section` |
| Dataset | Every line is valid, IDs are unique, every gold path exists in the corpus, splits are in proportion |
| Markdown parser | Shortcodes removed, `text` values kept, line numbers unchanged |

Tests need PostgreSQL, Qdrant and OpenSearch running.

## 10. Risks

| Risk | Handling |
|---|---|
| The 8 GiB production server may not hold OpenSearch and the reranker beside the existing services | Phase 4 measures it and picks the server size. `rerank_enabled` and `retrieval_mode` allow a smaller footprint |
| Reranking 30 passages on a 2-vCPU server may be slow | Phase 4 measures it. This phase reports laptop GPU latency only and says so |
| Questions written by the project's author may favour the system | Gold labels name sections, a third of questions are exact-term, the owner reviews a sample, and the doc states how the questions were made |
| 6 GB of GPU memory with two models loaded | Both load in half precision. If memory runs out, the reranker's batch size halves, as embedding already does |

## 11. Downloads

The OpenSearch image goes to Docker's data disk on E:. The reranker model downloads with `HF_HOME=E:/Projects/Engram/data/hf`, and Python packages install with `UV_CACHE_DIR=E:/Projects/Engram/data/uv-cache`. The corpus tarball goes to `data/downloads`. Nothing goes to C:.
