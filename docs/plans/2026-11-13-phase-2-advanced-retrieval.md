# Phase 2: Advanced Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OpenSearch BM25, Reciprocal Rank Fusion and cross-encoder reranking to retrieval, and report each addition's effect on a documented evaluation dataset.

**Architecture:** Retrieval moves into one function, `retrieve_passages`, that the API and the evaluation harness both call. OpenSearch becomes a second rebuildable projection beside Qdrant, written at the same publish step. The evaluation harness runs three configurations through settings switches and writes result files that a report command turns into `docs/phase-2-evaluation.md`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Qdrant, OpenSearch 3.9.0 with `opensearch-py`, sentence-transformers `CrossEncoder` (BGE-reranker-v2-m3), pytest.

**Spec:** `docs/specs/2026-11-13-phase-2-advanced-retrieval-design.md`

## Global Constraints

- Run backend commands from `backend/`. Set `UV_CACHE_DIR=E:/Projects/Engram/data/uv-cache` on every `uv` command that can install, and `HF_HOME=E:/Projects/Engram/data/hf` on every command that can load a model. Nothing downloads to C:.
- Use `127.0.0.1`, never `localhost`, for local services.
- OpenSearch image: `opensearchproject/opensearch:3.9.0`. Client: `opensearch-py>=3.2`.
- Reranker: `BAAI/bge-reranker-v2-m3` at revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`.
- Corpus: `kubernetes/website`, commit `df4b759d54d331622a0003d25e8f713852e98dae`, include path `content/en/docs/concepts/**`.
- Retrieval numbers: 50 dense and 50 keyword candidates, RRF `k = 60`, 30 candidates to the recheck and reranker, 8 passages and 4,000 tokens of context.
- Every keyword and hybrid search filters by tenant and principals inside the query. PostgreSQL stays canonical.
- Tuning uses the `dev` split only. Reported numbers come from the `test` split.
- No number is reported as achieved unless a result file produced by `eval.run` contains it.
- Tests need PostgreSQL, Qdrant and OpenSearch running (`docker compose up -d` from the repository root).
- Commits carry no co-author or tooling lines. Commit and push to `origin main` after each task.

## Review Focus

1. **A question made only of punctuation or OpenSearch query syntax** (`"AND OR ("`, `foo:bar`, `*`): keyword search must not raise or match everything. Pinned in Task 5 (`search` uses a `match` query, never `query_string`).
2. **A chunk indexed in OpenSearch whose document version is no longer current:** it must never reach an answer. Pinned in Task 7 (hybrid result passes the PostgreSQL recheck).
3. **Fewer candidates than requested** (tiny corpus, or one search returns nothing): fusion and reranking must work with 0 or 1 candidates. Pinned in Tasks 7 and 9.
4. **A very long passage or question pair for the reranker:** it must truncate, not fail. Pinned in Task 9 (`max_length=512` and a test with a 5,000-word passage).
5. **Shortcodes inside code fences:** they are content, not markup, and must stay. Pinned in Task 1.

---

### Task 1: Remove Hugo shortcodes in the Markdown parser

**Files:**
- Modify: `app/ingestion/parsers/markdown.py`
- Test: `tests/test_markdown_parser.py`

**Interfaces:**
- Produces: `parse_markdown` output whose section text has no shortcode tags outside code fences. Line ranges are unchanged, because the replacement happens within each line.

- [ ] **Step 1: Write failing tests**

```python
def test_shortcode_with_text_keeps_the_text():
    doc = parse_markdown(b'# T\n\nA {{< glossary_tooltip text="Pod" term_id="pod" >}} runs.\n')
    assert doc.sections[-1].text.endswith("A Pod runs.")

def test_shortcode_without_text_is_removed():
    doc = parse_markdown(b'# T\n\nVersion {{< param "version" >}} here.\n')
    assert "{{" not in doc.sections[-1].text

def test_paired_shortcode_keeps_inner_content():
    doc = parse_markdown(b"# T\n\n{{< note >}}\nKeep this.\n{{< /note >}}\n")
    assert "Keep this." in doc.sections[-1].text and "note" not in doc.sections[-1].text

def test_percent_shortcodes_are_removed():
    doc = parse_markdown(b"# T\n\n{{% alert %}}Careful{{% /alert %}}\n")
    assert doc.sections[-1].text.endswith("Careful")

def test_shortcode_in_a_code_fence_stays():
    doc = parse_markdown(b"# T\n\n```\n{{< note >}}\n```\n")
    assert "{{< note >}}" in doc.sections[-1].text

def test_line_numbers_are_unchanged_by_shortcodes():
    doc = parse_markdown(b"# A\n\n{{< note >}}\nx\n{{< /note >}}\n\n# B\n\ny\n")
    assert (doc.sections[-1].start_line, doc.sections[-1].end_line) == (7, 9)
```

- [ ] **Step 2:** Run `uv run pytest tests/test_markdown_parser.py -v`. Expected: the six new tests FAIL.
- [ ] **Step 3:** Implement `_strip_shortcodes(lines: list[str]) -> list[str]`, applied after `_blank_front_matter`. It skips lines inside fenced code blocks (``` or ~~~), replaces `{{< ... text="X" ... >}}` and `{{% ... text="X" ... %}}` with `X`, and removes every other `{{< ... >}}` or `{{% ... %}}` tag. A line left empty stays as an empty line.
- [ ] **Step 4:** Run `uv run pytest tests/test_markdown_parser.py -v`. Expected: PASS.
- [ ] **Step 5:** Commit `fix: remove Hugo shortcodes from Markdown text`, push.

### Task 2: Evaluation dataset loader and metrics

**Files:**
- Create: `eval/__init__.py`, `eval/dataset.py`, `eval/metrics.py`, `tests/test_eval_dataset.py`, `tests/test_eval_metrics.py`

**Interfaces:**
- Produces:

```python
# eval/dataset.py
KINDS = ("conceptual", "exact_term", "multi_section", "unanswerable")
@dataclass(frozen=True)
class Gold: path: str; headings: tuple[str, ...]
@dataclass(frozen=True)
class Question: id: str; question: str; kind: str; gold: tuple[Gold, ...]; split: str  # "dev" | "test"
def load_questions(path: Path) -> list[Question]  # ValueError naming the line on any defect

# eval/metrics.py
@dataclass(frozen=True)
class Ranked: path: str; headings: tuple[str, ...]
def in_section(item: Ranked, gold: Gold) -> bool          # same path, headings start with gold.headings
def recall_at(k: int, ranked: list[Ranked], gold: tuple[Gold, ...]) -> float   # 1.0 only if every gold section is in the top k
def reciprocal_rank(ranked: list[Ranked], gold: tuple[Gold, ...], k: int = 10) -> float
def ndcg_at(k: int, ranked: list[Ranked], gold: tuple[Gold, ...]) -> float
def percentile(values: list[float], p: float) -> float    # nearest-rank
def balanced_accuracy(answerable_top: list[float], unanswerable_top: list[float], cutoff: float) -> float
def best_cutoff(answerable_top: list[float], unanswerable_top: list[float]) -> float
```

- `load_questions` rejects: invalid JSON, unknown `kind` or `split`, a repeated `id`, an answerable question without `gold`, an unanswerable question with `gold`, a `multi_section` question with fewer than two gold entries.
- NDCG gains: the first ranked chunk from each gold section earns 2; the first ranked chunk from each gold document outside its gold sections earns 1; everything else earns 0. The ideal ranking is one 2 per gold section followed by one 1 per gold document. This refines the spec's grading so a section with many chunks isn't counted many times.
- `best_cutoff` tries the midpoints between consecutive distinct scores and returns the one with the highest balanced accuracy, the lowest such value on a tie.

- [ ] **Step 1: Write failing tests**, including these hand-computed cases:

```python
G = (Gold("a.md", ("A", "B")),)
def r(path, *headings): return Ranked(path, tuple(headings))

def test_recall_counts_a_chunk_in_a_subsection():
    assert recall_at(5, [r("x.md"), r("a.md", "A", "B", "C")], G) == 1.0
def test_recall_misses_the_right_document_wrong_section():
    assert recall_at(5, [r("a.md", "A", "Z")], G) == 0.0
def test_recall_respects_k():
    assert recall_at(1, [r("x.md"), r("a.md", "A", "B")], G) == 0.0
def test_multi_section_needs_every_section():
    two = (Gold("a.md", ("A",)), Gold("b.md", ("B",)))
    assert recall_at(5, [r("a.md", "A")], two) == 0.0
    assert recall_at(5, [r("a.md", "A"), r("b.md", "B")], two) == 1.0
def test_reciprocal_rank_of_third_place():
    assert reciprocal_rank([r("x.md"), r("y.md"), r("a.md", "A", "B")], G) == pytest.approx(1 / 3)
def test_ndcg_is_one_for_the_ideal_order():
    assert ndcg_at(10, [r("a.md", "A", "B"), r("a.md", "Z")], G) == pytest.approx(1.0)
def test_ndcg_for_gold_in_second_place():
    # DCG = 2/log2(3); IDCG = 2/log2(2) + 1/log2(3)
    expected = (2 / math.log2(3)) / (2 + 1 / math.log2(3))
    assert ndcg_at(10, [r("x.md"), r("a.md", "A", "B")], G) == pytest.approx(expected)
def test_ndcg_counts_a_section_once():
    once = ndcg_at(10, [r("a.md", "A", "B")], G)
    assert ndcg_at(10, [r("a.md", "A", "B"), r("a.md", "A", "B")], G) == pytest.approx(once)
def test_best_cutoff_separates_two_groups():
    assert best_cutoff([0.9, 0.8, 0.7], [0.2, 0.1]) == pytest.approx(0.45)
def test_percentile_nearest_rank():
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
```

Plus one `load_questions` test per rejection rule and one for a valid file.

- [ ] **Step 2:** Run `uv run pytest tests/test_eval_dataset.py tests/test_eval_metrics.py -v`. Expected: FAIL, module not found.
- [ ] **Step 3:** Implement both modules.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat: add evaluation dataset loader and metrics`, push.

### Task 3: Shared retrieval function and the harness

**Files:**
- Create: `app/retrieval/pipeline.py`, `eval/run.py`, `eval/report.py`, `tests/test_retrieval_pipeline.py`, `tests/test_eval_run.py`
- Modify: `app/questions.py`, `app/types.py`

**Interfaces:**
- Produces:

```python
# app/types.py
@dataclass(frozen=True)
class RetrievalOutcome:
    passages: list[Passage]   # ranked, after the PostgreSQL recheck, before the evidence cutoff
    mode: str                 # "dense" | "hybrid" | "dense_fallback"
    reranked: bool
    retrieve_ms: int
    rerank_ms: int

# app/retrieval/pipeline.py
def retrieve_passages(session, question: str, scope: AccessScope, retriever: Retriever,
                      settings: Settings, reranker: Reranker | None = None) -> RetrievalOutcome
```

- In this task `retrieve_passages` normalises the question (strip, collapse whitespace), calls `retriever.search(question, scope, settings.retrieval_limit)`, runs `load_passages`, and returns mode `"dense"`, `reranked=False`. `answer_question` calls it in place of its own search and recheck, and behaves as before.
- `eval/run.py`: `python -m eval.run --config dense|hybrid|hybrid_rerank [--questions eval/questions.jsonl] [--out eval/results]`. It builds services with `build_services`, overrides `retrieval_mode` and `rerank_enabled` for the configuration, asks one warm-up question, then for each question records the ranked passages (path, headings, score), the top score and `retrieve_ms + rerank_ms`. It writes `<out>/<config>.json` with `config`, `settings` used, `corpus` (document and chunk counts from PostgreSQL), `per_question`, and `summary` for the `test` split: Recall@5, Recall@10, MRR@10, NDCG@10 overall and by kind, latency median and p95, and the evidence gate at the configured cutoff. It uses the default tenant scope from `app/api/deps.py`.
- `summarise(per_question, questions, cutoff) -> dict` is a pure function in `eval/run.py`, tested without services.
- `eval/report.py`: `python -m eval.report` reads every result file present and writes `docs/phase-2-evaluation.md` with the dataset description, one comparison table, the per-kind table, latency, the cutoff and its rule, and a "Limits" section. A configuration with no result file is listed as "not run".

- [ ] **Step 1:** Write failing tests: `retrieve_passages` collapses whitespace before searching and returns rechecked passages in rank order (with the fakes in `tests/fakes.py`); `summarise` gives the expected Recall@5 and gate numbers for a three-question fixture, and ignores `dev` questions.
- [ ] **Step 2:** Run `uv run pytest tests/test_retrieval_pipeline.py tests/test_eval_run.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement. Move the search and recheck out of `answer_question`.
- [ ] **Step 4:** Run `uv run pytest`. Expected: every test passes, including the existing `test_questions.py`.
- [ ] **Step 5:** Commit `feat: share retrieval between the API and the evaluation harness`, push.

### Task 4: Corpus, questions and the dense baseline

**Files:**
- Create: `eval/questions.jsonl`, `eval/README.md`, `eval/check.py`, `eval/results/dense.json`, `docs/phase-2-evaluation.md`
- Test: `tests/test_eval_dataset.py` (add)

**Interfaces:**
- Produces: the ingested corpus in the development database under a GitHub source named `kubernetes/website`; about 140 questions; `python -m eval.check`, which loads the questions and exits non-zero, naming each one, when a gold `path` has no current document or a gold `headings` prefix matches no chunk of it.

- [ ] **Step 1:** Add a failing test: the tracked `eval/questions.jsonl` loads, has at least 110 answerable and 18 unanswerable questions, and each kind is 35% to 45% `dev`.
- [ ] **Step 2:** Start the services and the API. Create the GitHub source for `kubernetes/website` pinned to the corpus commit with include path `content/en/docs/concepts/**`, sync it, and wait for the job to succeed. Record document and chunk counts.
- [ ] **Step 3:** Write the questions from the ingested sections, following the spec's mix, and assign splits by position within each kind (two `dev` in every five). Include the Phase 1 Service question as `k8s-service-selector`.
- [ ] **Step 4:** Run `uv run python -m eval.check`. Expected: exit 0. Fix any label it names.
- [ ] **Step 5:** Write `eval/README.md`: corpus, commit, counts, how questions were written (for this project, not collected from users), kinds, split rule, relevance rule, and the commands.
- [ ] **Step 6:** Run `uv run pytest tests/test_eval_dataset.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `uv run python -m eval.run --config dense`, then `uv run python -m eval.report`. Expected: `eval/results/dense.json` and the results doc exist, with hybrid and reranking listed as "not run". The doc is marked provisional until the owner has reviewed the question sample.
- [ ] **Step 8:** Commit `feat: add evaluation dataset and dense baseline`, push.

### Task 5: OpenSearch service and keyword index

**Files:**
- Modify: `../docker-compose.yml`, `pyproject.toml`, `app/config.py`, `tests/conftest.py`
- Create: `app/db/keyword_index.py`, `tests/test_keyword_index.py`

**Interfaces:**
- Produces:

```python
# app/config.py additions
opensearch_url: str = "http://127.0.0.1:9200"
opensearch_index: str = "chunks_v1"

# app/db/keyword_index.py
@dataclass(frozen=True)
class IndexedText:
    chunk_id: UUID; content: str; headings: str
    tenant_id: UUID; document_id: UUID; document_version_id: UUID; allowed_principals: list[str]

def is_transient_opensearch_error(error: Exception) -> bool   # connection errors, 429, 5xx

class KeywordIndex:
    def __init__(self, client: OpenSearch, index: str)
    def ensure_index(self) -> None
    def upsert(self, items: list[IndexedText]) -> None       # bulk, refresh="wait_for"
    def delete_version(self, version_id: UUID) -> None       # delete_by_query, refresh
    def search(self, query: str, scope: AccessScope, limit: int) -> list[tuple[UUID, float]]
    def count(self) -> int
    def ping(self) -> bool
```

- Compose service `opensearch`: `discovery.type=single-node`, `DISABLE_SECURITY_PLUGIN=true`, `DISABLE_INSTALL_DEMO_CONFIG=true`, `OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m`, port `127.0.0.1:9200:9200`, a named volume, and a health check on `/_cluster/health`.
- Mapping: `content` and `headings` are `text` with the standard analyzer, each with a subfield `.ident` using a custom analyzer (whitespace tokenizer, `word_delimiter_graph` with `preserve_original`, lowercase). `tenant_id`, `document_id`, `document_version_id`, `allowed_principals` are `keyword`. The document `_id` is the chunk ID.
- `search` sends a `bool` query: `must` is a `multi_match` over `content`, `content.ident`, `headings^2`, `headings.ident^2` with `type: "most_fields"`; `filter` is a `term` on `tenant_id` and a `terms` on `allowed_principals`. A blank query returns `[]` without calling OpenSearch.
- Test fixture `keyword_index` creates an index named `chunks_test_<random>` and deletes it afterwards.

- [ ] **Step 1:** Add the Compose service and run `docker compose up -d` from the repository root. Expected: `curl http://127.0.0.1:9200` answers with version 3.9.0.
- [ ] **Step 2:** `UV_CACHE_DIR=E:/Projects/Engram/data/uv-cache uv add "opensearch-py>=3.2"`.
- [ ] **Step 3:** Write failing tests: upsert then search finds a chunk by a word in its content; a heading match outranks a body match; `kube-scheduler` and `spec.nodeName` are found by those exact terms; another tenant's chunk never comes back; a chunk with no shared principal never comes back; `delete_version` removes only that version; upserting the same chunk twice leaves `count()` unchanged; the queries `"AND OR ("`, `"foo:bar"`, `"*"` and `"   "` return without raising, and `"*"` doesn't match every chunk.
- [ ] **Step 4:** Run `uv run pytest tests/test_keyword_index.py -v`. Expected: FAIL.
- [ ] **Step 5:** Implement.
- [ ] **Step 6:** Run `uv run pytest tests/test_keyword_index.py -v`. Expected: PASS.
- [ ] **Step 7:** Commit `feat: add OpenSearch keyword index`, push.

### Task 6: Publish to both indexes, rebuild command, health

**Files:**
- Modify: `app/ingestion/pipeline.py`, `app/ingestion/transfer.py`, `app/services.py`, `app/cli.py`, `app/api/health.py`, `app/main.py` (ensure the index at startup where the collection is ensured), `tests/conftest.py`, `tests/fakes.py`
- Create: `app/ingestion/reindex.py`
- Test: `tests/test_pipeline_publish.py`, `tests/test_transfer.py`, `tests/test_health.py`, `tests/test_reindex.py`

**Interfaces:**
- Consumes: `KeywordIndex`, `IndexedText`, `is_transient_opensearch_error` (Task 5).
- Produces:
  - `IngestionDeps` gains `keyword_index: KeywordIndex`.
  - `publish_version(session, version, vectors, index, keyword_index, model_id, retry_wait=1.0)`: upserts to Qdrant, then to OpenSearch (`headings` is the heading path joined with `" > "`), then makes the version current and commits, then deletes the old version from both. A failure in either upsert raises before the version becomes current. A failure deleting old entries is logged, as today.
  - `PublishError` message for an OpenSearch failure: `"could not save text to the keyword index"`.
  - `import_vectors(session, job_id, in_dir, index, keyword_index, settings)`.
  - `reindex_keyword(session, keyword_index, batch_size=500) -> int` in `app/ingestion/reindex.py`: upserts every chunk of every current version and returns the count.
  - CLI: `python -m app.cli reindex-keyword` prints `Indexed <n> chunks.`
  - Health returns 503 when `keyword_index.ping()` is false.
  - `tests/fakes.py` gains `FailingKeywordIndex`, whose `upsert` raises.

- [ ] **Step 1:** Write failing tests: after publishing, both indexes hold the version's chunks; when the keyword upsert fails, the document's current version is unchanged and the job reports the failure; publishing a second version removes the first from both; `reindex_keyword` on an emptied index restores exactly the current versions' chunks; health is 503 when OpenSearch doesn't answer; the Kaggle import writes to both.
- [ ] **Step 2:** Run `uv run pytest tests/test_pipeline_publish.py tests/test_transfer.py tests/test_health.py tests/test_reindex.py -v`. Expected: new tests FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest`. Expected: all pass.
- [ ] **Step 5:** Run `uv run python -m app.cli reindex-keyword` against the development database. Expected: the printed count equals the chunk count recorded in Task 4.
- [ ] **Step 6:** Commit `feat: publish chunks to the keyword index`, push.

### Task 7: Rank fusion and hybrid retrieval

**Files:**
- Create: `app/retrieval/fusion.py`, `app/retrieval/keyword.py`, `app/retrieval/hybrid.py`, `tests/test_fusion.py`, `tests/test_hybrid.py`
- Modify: `app/retrieval/base.py`, `app/retrieval/dense.py`, `app/retrieval/pipeline.py`, `app/services.py`, `app/config.py`, `tests/test_tenant_isolation.py`

**Interfaces:**
- Produces:

```python
# app/config.py additions
retrieval_mode: str = "hybrid"        # "dense" | "hybrid"
candidate_limit: int = 50
rrf_k: int = 60
retrieval_limit: int = 30             # was 20

# app/retrieval/base.py
@dataclass(frozen=True)
class SearchResult: hits: list[RetrievalHit]; mode: str
class Retriever(Protocol):
    def search(self, query: str, scope: AccessScope, limit: int) -> SearchResult: ...

# app/retrieval/fusion.py
def reciprocal_rank_fusion(rankings: list[list[UUID]], k: int = 60) -> list[tuple[UUID, float]]

# app/retrieval/keyword.py
class KeywordRetriever:  # wraps KeywordIndex.search, mode "keyword"

# app/retrieval/hybrid.py
class HybridRetriever:
    def __init__(self, dense: Retriever, keyword: Retriever, candidate_limit: int, rrf_k: int)
```

- `reciprocal_rank_fusion` scores each ID as the sum of `1 / (k + rank)` over the rankings it appears in (rank starts at 1) and sorts by score descending, breaking ties by first appearance in the first ranking that contains the ID.
- `HybridRetriever.search` runs both searches in a two-worker thread pool with `candidate_limit` each, fuses them, and returns the top `limit` with mode `"hybrid"`. If keyword search raises, it logs a warning and returns the dense hits with mode `"dense_fallback"`. If dense search raises, the error propagates.
- `DenseRetriever.search` returns `SearchResult(hits, "dense")`. `retrieve_passages` copies the mode into `RetrievalOutcome`.
- `build_services` builds `HybridRetriever` when `retrieval_mode == "hybrid"`, else `DenseRetriever`.

- [ ] **Step 1:** Write failing tests. Fusion: two rankings `[a, b, c]` and `[b, d]` give `b` first with score `1/62 + 1/61`, then `a`, `d`, `c` in score order; an ID in one list only is kept; an empty ranking is ignored; no rankings give `[]`. Hybrid: a chunk found by both appears once; keyword failure gives `dense_fallback` with the dense hits; dense failure raises; with zero or one candidates it returns them. Recheck: a chunk present in OpenSearch for a version that is no longer current is absent from `retrieve_passages` output. Tenant isolation: hybrid search for tenant A never returns tenant B's chunks.
- [ ] **Step 2:** Run `uv run pytest tests/test_fusion.py tests/test_hybrid.py tests/test_tenant_isolation.py -v`. Expected: new tests FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest`. Expected: all pass.
- [ ] **Step 5:** Run `uv run python -m eval.run --config hybrid` and `uv run python -m eval.report`. Expected: `eval/results/hybrid.json` exists and the results doc shows dense and hybrid side by side.
- [ ] **Step 6:** Commit `feat: add hybrid retrieval with rank fusion`, push.

### Task 8: Query log timings

**Files:**
- Create: a new Alembic migration under `migrations/versions/`
- Modify: `app/db/models.py`, `app/questions.py`
- Test: `tests/test_questions.py`, `tests/test_schema.py`

**Interfaces:**
- Produces: `query_logs` columns `retrieval_mode` (text, nullable), `reranked` (boolean, nullable), `retrieve_ms`, `rerank_ms`, `generate_ms` (integer, nullable). `answer_question` fills them from `RetrievalOutcome` and times the `llm.generate` call. When retrieval fails, they stay null.

- [ ] **Step 1:** Write failing tests: an answered question's log row has `retrieval_mode`, `reranked` false, and non-null `retrieve_ms` and `generate_ms`; a refused question has null `generate_ms`; a fallback is logged as `dense_fallback`.
- [ ] **Step 2:** Run `uv run pytest tests/test_questions.py tests/test_schema.py -v`. Expected: new tests FAIL.
- [ ] **Step 3:** Write the migration and the code. Run `uv run alembic upgrade head` on the development database.
- [ ] **Step 4:** Run `uv run pytest`. Expected: all pass.
- [ ] **Step 5:** Commit `feat: record retrieval mode and stage timings in the query log`, push.

### Task 9: Reranker and the evidence cutoff

**Files:**
- Create: `app/retrieval/rerank.py`, `eval/calibrate.py`, `tests/test_rerank.py`, `tests/test_reranker_model.py`
- Modify: `app/retrieval/pipeline.py`, `app/questions.py`, `app/services.py`, `app/config.py`, `app/main.py` (preload), `pyproject.toml` (register the `slow` marker), `tests/fakes.py`

**Interfaces:**
- Produces:

```python
# app/config.py additions
rerank_enabled: bool = True
reranker_model_id: str = "BAAI/bge-reranker-v2-m3"
reranker_model_revision: str = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
reranker_batch_size: int = 16
rerank_min_score: float   # set from calibration in Step 7
dense_min_score: float = 0.50   # renamed from evidence_min_score

# app/retrieval/rerank.py
class RerankError(Exception): ...
class Reranker(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]: ...   # one score in [0, 1] per passage
class BgeReranker:   # CrossEncoder, max_length=512, float16 on cuda, float32 on cpu, lazy load
```

- `BgeReranker.score` returns `[]` for no passages, scores what `embedding_text(heading_path, content)` would produce for each passage, and on a CUDA out-of-memory error halves the batch size down to 1 before raising `RerankError`.
- `retrieve_passages`, when given a reranker, scores the rechecked passages, replaces each `Passage.score`, sorts by it descending, sets `reranked=True` and `rerank_ms`. A `RerankError` propagates, and `answer_question` turns it into `retrieval_unavailable`.
- `answer_question` uses `rerank_min_score` when the outcome is reranked and `dense_min_score` otherwise.
- `eval/calibrate.py`: `python -m eval.calibrate --config hybrid_rerank` reads that result file, takes each `dev` question's top score, and prints `best_cutoff` with its balanced accuracy on `dev`.
- `tests/fakes.py` gains `FakeReranker` (scores by shared words) and `FailingReranker`.
- `tests/test_reranker_model.py` is marked `slow` and skipped unless the model is in `HF_HOME`.

- [ ] **Step 1:** Write failing tests: with `FakeReranker`, passages come back ordered by reranker score with those scores; zero and one passage work; `FailingReranker` gives `retrieval_unavailable`; the cutoff applied is `rerank_min_score` when reranked and `dense_min_score` otherwise. Slow tests: the real model scores a relevant passage above an irrelevant one, returns values in `[0, 1]`, and accepts a 5,000-word passage.
- [ ] **Step 2:** Run `uv run pytest tests/test_rerank.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement. Rename `evidence_min_score` everywhere, including `tests/conftest.py`.
- [ ] **Step 4:** Download the model once: `HF_HOME=E:/Projects/Engram/data/hf uv run python -c "from app.config import get_settings; from app.retrieval.rerank import BgeReranker; print(BgeReranker(get_settings()).score('q', ['p']))"`. Expected: one number between 0 and 1.
- [ ] **Step 5:** Run `HF_HOME=E:/Projects/Engram/data/hf uv run pytest -m slow tests/test_reranker_model.py -v` and then `uv run pytest`. Expected: all pass.
- [ ] **Step 6:** Run `uv run python -m eval.run --config hybrid_rerank`, then `uv run python -m eval.calibrate --config hybrid_rerank`.
- [ ] **Step 7:** Set `rerank_min_score` to the printed cutoff. Rerun `eval.run --config hybrid_rerank` so the gate numbers use it, then `eval.report`. Expected: the results doc shows all three configurations, the cutoff, the rule, and its balanced accuracy on `dev` and on `test`.
- [ ] **Step 8:** Commit `feat: rerank candidates and recalibrate the evidence cutoff`, push.

### Task 10: Prompt fix and answer review

**Files:**
- Modify: `app/generation/prompts.py`, `docs/phase-2-evaluation.md` (through `eval/report.py` reading `eval/results/answer_review.json`)
- Create: `eval/answers.py`, `eval/results/answer_review.json`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Produces: a system prompt rule: "Refer to passages only through markers such as [1]. Never write 'Passage 1' or 'the first passage' in the answer." `python -m eval.answers` asks every eighth answerable `test` question (at most 15) through `answer_question` with the final configuration and writes question, outcome, answer, citations (marker, path, headings) and timings to `eval/results/answer_review.json`, with an empty `review` field per citation.

- [ ] **Step 1:** Write a failing test that the system prompt contains the new rule.
- [ ] **Step 2:** Run `uv run pytest tests/test_prompts.py -v`. Expected: FAIL. Implement. Expected: PASS.
- [ ] **Step 3:** Run `uv run python -m eval.answers`. It needs `OPENROUTER_API_KEY` in `backend/.env` and uses at most 15 requests. If the quota is exhausted, record which questions ran and stop.
- [ ] **Step 4:** Read each answer against its cited sections and fill each `review` field with `supports`, `partly` or `does not support` and a one-line reason. Count answers that say "Passage N".
- [ ] **Step 5:** Run `uv run python -m eval.report`. Expected: the results doc gains the answer-review table, labelled as a manual sample.
- [ ] **Step 6:** Commit `feat: keep passage numbers in markers and record the answer review`, push.

### Task 11: Production Compose, landing page and docs

**Files:**
- Modify: `../docker-compose.prod.yml`, `../frontend/lib/system.ts`, `../frontend/lib/system.test.ts`, `../frontend/app/page.tsx`, `../frontend/app/landing.css`, `../README.md`, `../frontend/components/landing/landing.test.tsx`
- Create: `../frontend/components/landing/Measured.tsx`

**Interfaces:**
- Produces: an `opensearch` service in production Compose on the internal network with a memory cap and no published port, and the API's `OPENSEARCH_URL`. In `system.ts`: `sparse`, `fuse`, `rerank`, OpenSearch and Phase 2 become `live`, and a new export:

```ts
export type Measurement = { config: string; recallAt5: number; mrrAt10: number; ndcgAt10: number };
export const MEASURED: { questions: number; documents: number; rows: Measurement[]; note: string };
```

`<Measured data={MEASURED} />` renders a table of the three configurations between the Specimen and System sections, with the dataset size and a link to `docs/phase-2-evaluation.md` on GitHub. Numbers are copied from the `test` summaries in `eval/results/*.json`.

- [ ] **Step 1:** Update the frontend tests first: the status test expects Phase 1 and 2 `live`; the diagram test expects no "planned" tag; a new test checks `Measured` shows three rows and the question count. Run `npm test` from `frontend/`. Expected: FAIL.
- [ ] **Step 2:** Implement the frontend changes. Run `npm test && npm run lint && npm run build`. Expected: PASS.
- [ ] **Step 3:** Add OpenSearch to production Compose. Run `docker compose -f docker-compose.prod.yml config`. Expected: it validates.
- [ ] **Step 4:** Update the root README: OpenSearch in the service list, the evaluation commands, the `reindex-keyword` command, and a link to the results doc.
- [ ] **Step 5:** Run `uv run pytest` and `uv run ruff check .` from `backend/`. Expected: all pass.
- [ ] **Step 6:** Commit `feat: show Phase 2 as built and report measured retrieval`, push.
