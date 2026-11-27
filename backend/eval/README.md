# Retrieval evaluation

This folder holds the questions Engram's retrieval is measured against, and the commands
that measure it. `docs/phase-2-evaluation.md` reports the results.

## Corpus

All Markdown under `content/en/docs/concepts/` in
[kubernetes/website](https://github.com/kubernetes/website) at commit
`df4b759d54d331622a0003d25e8f713852e98dae`. It is the Kubernetes project's own documentation,
written by its contributors; none of it is synthetic.

It is ingested through the GitHub connector into a source named `kubernetes/website`, with
the commit as the branch and `content/en/docs/concepts/**` as the include path. The include
path matches 187 files. One, `storage/_index.md`, holds only front matter and is rejected as
having no text, so the corpus is **186 documents and 2,533 chunks** (512-token chunks with
a 50-token overlap, embedded with BGE-M3 at revision
`5617a9f61b028005a4858fdac845db406aefb181`).

Each ingested document's path is its path in the repository, such as
`content/en/docs/concepts/workloads/pods/pod-lifecycle.md`.

## Questions

`questions.jsonl` holds 142 questions, one JSON object per line:

| Field | Meaning |
|---|---|
| `id` | Stable identifier, such as `k8s-042` |
| `question` | The question text |
| `kind` | `conceptual`, `exact_term`, `multi_section` or `unanswerable` |
| `gold` | For answerable questions, the sections that answer them: `{"path": ..., "headings": [...]}`. Empty for unanswerable questions |
| `split` | `dev` or `test` |

The questions were written for this project by its author, from the ingested sections. They
were not collected from real users, so they show how retrieval does on questions shaped like
these, not on what people actually ask.

| Kind | Count | What it tests |
|---|---:|---|
| `conceptual` | 62 | A question in plain words, answered by one section |
| `exact_term` | 40 | A question naming a field, flag, label, API kind or status, such as `maxSurge` or `CrashLoopBackOff` |
| `multi_section` | 20 | A question that needs two sections, often from two pages |
| `unanswerable` | 20 | Half unrelated to Kubernetes, half about Kubernetes topics the concepts pages don't cover (installing tools, kubeadm upgrades, etcdctl, minikube, kind, Helm, the docs project itself) |

How they were written:

- Each answerable question was written from a section of the ingested corpus, and its gold
  entry names that section. The exact terms were searched for across the corpus first, so an
  `exact_term` question's gold is the section that defines the term, not one that mentions it
  in passing.
- Each unanswerable question about Kubernetes was checked against the corpus: its key terms
  (`apt-get`, `kubeadm upgrade`, `brew`, `etcdctl`, `minikube start` and so on) appear in no
  chunk.
- `k8s-service-selector` is the Service question Phase 1 asked by hand, kept so the two
  phases can be compared.

## Relevance

A retrieved chunk is relevant to a gold entry when its document path equals the entry's
`path` and its heading path starts with the entry's `headings`, so a chunk in a subsection
counts. Headings start at the page's first `##` heading; the page title is front matter and
isn't part of the path. An entry with no headings covers the whole page.

Gold labels name sections rather than chunk IDs, so they survive re-chunking and
re-ingestion. A question's gold entries may not overlap: no entry repeats another or sits
inside another in the same page.

For NDCG, the first chunk from each gold section earns 2 and the first chunk from elsewhere
in a gold page earns 1.

## Split

Within each kind, questions are split by their position in the file: of every five, the
first and third are `dev` and the other three are `test`. That gives 40% `dev` for every
kind.

Tuning, such as choosing the evidence cutoff or changing a retrieval setting, uses `dev`
only. Every reported number comes from `test`.

## Review

The owner reviews a sample of about 20 questions and their gold labels before any number
counts as a result. The sample is fixed by position, not chosen by results: every seventh
line of `questions.jsonl`, starting with the first, which gives 21 questions. For each one
the reviewer checks that the question is answerable from its gold sections alone (or, for an
unanswerable one, from no concepts page), and that no other section answers it better.

Until then the results document is marked provisional. The review is recorded in
`review.json`:

```json
{"reviewed_on": "2026-11-30", "reviewer": "...", "questions": ["k8s-001", "..."], "notes": "..."}
```

`eval.report` treats the results as reviewed only when that file exists with a
`reviewed_on` date.

## Commands

Run these from `backend/`, with PostgreSQL, Qdrant and OpenSearch running and the corpus
ingested:

| Task | Command |
|---|---|
| Check every gold label against the corpus | `uv run python -m eval.check` |
| Run one configuration (`dense`, `hybrid`, `dense_rerank` or `hybrid_rerank`) | `uv run python -m eval.run --config dense` |
| Choose a reranked configuration's evidence cutoff on `dev` | `uv run python -m eval.calibrate --config hybrid_rerank` |
| Ask the answer-review sample through the model (about 10 requests) | `uv run python -m eval.answers` |
| Rebuild `docs/phase-2-evaluation.md` from the result files | `uv run python -m eval.report` |

`eval.check` exits non-zero and names each question whose gold path has no current document,
or whose gold headings match no current chunk. Run it after editing the questions and after
re-ingesting the corpus.

`eval.run` writes `results/<config>.json`: the settings it ran with, the corpus size, each
question's ranked passages, scores and retrieval time, and a summary of the `test` split. It
asks one warm-up question first, so model loading isn't timed. A configuration that needs a
feature this build lacks is refused rather than run as something else.

`eval.calibrate` reads `results/<config>.json` and records the cutoff, its rule and its
accuracy on `dev` in `results/calibration.json`. Copy the printed cutoff into
`rerank_min_score` and rerun `eval.run` so the `test` gate uses it.

`eval.answers` asks every eighth answerable `test` question, at most 15, with the settings as
configured, and writes `results/answer_review.json` with an empty `review` per citation. The
reviewer fills each with a `verdict` (`supports`, `partly` or `does not support`) and a
`reason`, and lists in each answer's `issues` what per-citation verdicts miss: a statement no
cited passage states, or a claim with no marker. It refuses to overwrite a file whose reviews
have been started.

Set `HF_HOME=E:/Projects/Engram/data/hf` on `eval.run` and `eval.answers`, as on the API, so
the models load from inside the project.
