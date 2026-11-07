# Phase 1 smoke test results

Run on 2026-11-07 on the development machine, with BGE-M3 on the local GPU and OpenRouter's free models. This is a smoke test of 10 questions, not the §10.5 evaluation. It shows that the pipeline works end to end and sets a first evidence cutoff. It doesn't measure Recall@5, faithfulness or p95 latency, which need the Phase 2 dataset.

## Corpus

The corpus is 10 real Kubernetes concept pages from `kubernetes/website` at commit `df4b759d54d331622a0003d25e8f713852e98dae`, under `content/en/docs/concepts/`. None of them is synthetic. Each was renamed after its topic before upload, because uploads keep only the file name:

| Uploaded as | Path under `concepts/` |
|---|---|
| `pods.md` | `workloads/pods/_index.md` |
| `pod-lifecycle.md` | `workloads/pods/pod-lifecycle.md` |
| `deployment.md` | `workloads/controllers/deployment.md` |
| `statefulset.md` | `workloads/controllers/statefulset.md` |
| `daemonset.md` | `workloads/controllers/daemonset.md` |
| `service.md` | `services-networking/service.md` |
| `configmap.md` | `configuration/configmap.md` |
| `secret.md` | `configuration/secret.md` |
| `kube-scheduler.md` | `scheduling-eviction/kube-scheduler.md` |
| `namespaces.md` | `overview/working-with-objects/namespaces.md` |

The pages were uploaded together on the Sources screen. The job ended `succeeded`, with 10 processed and 0 failed, after 25.6 seconds including the model load. It made 302 chunks of 19 to 512 tokens (270 on average). Every chunk has `embedded_at`, and Qdrant holds 302 points.

## Evidence cutoff

`uv run python -m scripts.smoke --retrieval-only` gives the top score after the Postgres recheck:

| Top score | Expects | Top document | Question |
|---:|---|---|---|
| 0.754 | answered | `pods.md` | What is a Pod in Kubernetes, and what does it contain? |
| 0.734 | answered | `pod-lifecycle.md` | What phases can a Pod be in during its lifecycle? |
| 0.722 | answered | `deployment.md` | How does a Deployment roll out a new version of an application? |
| 0.768 | answered | `statefulset.md` | How does a StatefulSet give each Pod a stable network identity? |
| 0.730 | answered | `daemonset.md` | When should I use a DaemonSet? |
| 0.656 | answered | `pod-lifecycle.md` | How does a Service decide which Pods receive its traffic? |
| 0.758 | answered | `configmap.md` | What are the ways a Pod can use a ConfigMap? |
| 0.787 | answered | `kube-scheduler.md` | How does kube-scheduler choose a node for a Pod? |
| 0.343 | insufficient_evidence | `statefulset.md` | What is a good recipe for sourdough bread? |
| 0.266 | insufficient_evidence | `configmap.md` | Who won the 1998 FIFA World Cup? |

Answerable questions scored 0.656 to 0.787, and unrelated ones 0.266 to 0.343. The ranges don't overlap, and the midpoint is 0.499, so `evidence_min_score` is now **0.50**, up from 0.30. The old value would have sent the sourdough question to the model.

Ten questions are too few to trust this value for long. Recalibrate it on the Phase 2 dataset. The cutoff also drops individual passages below 0.50 from the context, not only whole questions.

## Answers from the real model

`uv run python -m scripts.smoke --base-url http://127.0.0.1:8000` ended **PASS**. All 8 answerable questions were answered with citations, and both unrelated questions returned `insufficient_evidence` before reaching the model.

| Seconds | Outcome | Citations | Input tokens | Output tokens | Question |
|---:|---|---:|---:|---:|---|
| 25.9 | answered | 3 | 3,147 | 1,122 | What is a Pod in Kubernetes, and what does it contain? |
| 2.8 | answered | 1 | 3,194 | 168 | What phases can a Pod be in during its lifecycle? |
| 32.4 | answered | 4 | 3,150 | 867 | How does a Deployment roll out a new version of an application? |
| 9.1 | answered | 4 | 2,041 | 1,226 | How does a StatefulSet give each Pod a stable network identity? |
| 7.1 | answered | 4 | 2,175 | 1,003 | When should I use a DaemonSet? |
| 3.4 | answered | 1 | 3,290 | 248 | How does a Service decide which Pods receive its traffic? |
| 2.9 | answered | 1 | 2,948 | 322 | What are the ways a Pod can use a ConfigMap? |
| 7.2 | answered | 2 | 2,667 | 953 | How does kube-scheduler choose a node for a Pod? |
| 0.2 | insufficient_evidence | 0 | | | What is a good recipe for sourdough bread? |
| 0.1 | insufficient_evidence | 0 | | | Who won the 1998 FIFA World Cup? |

The primary model, `nvidia/nemotron-3.5-super-vl:free`, answered every question, so the fallback wasn't exercised. Each answered question sent 8 passages. The first question's time includes loading BGE-M3 in the API process. The run used 8 OpenRouter requests, and the click-through below used a 9th.

## Click-through on the Ask screen

I asked "What phases can a Pod be in during its lifecycle?" on the Ask screen and selected marker [2]. The margin showed `pod-lifecycle.md`, the heading "Pod phase" and lines 96–123. In the downloaded page, those lines are the "Pod phase" section with its table of the five phases, which is what the answer cites.

## Observations

- **A weaker retrieval result.** The Service question's top passage came from `pod-lifecycle.md`, not `service.md`. The question was still answered, with a citation to the eighth passage in the context. Phase 2's hybrid search and reranking target this kind of miss.
- **Passage numbers in the answer text.** One answer said "Passage 1 also describes…". The prompt numbers passages for citation, and the model sometimes repeats that numbering in its prose. Tightening the prompt to keep numbers in markers only is a candidate fix.
- **Hugo markup in snippets.** Shortcodes such as `{{< glossary_tooltip >}}` and `{{< param "version" >}}` stay in the chunk text and the citation snippets. Heading IDs such as `{#pod-phase}` are now removed from heading titles.
- **Latency.** Answers took 2.8 to 32.4 seconds, with a median of about 7 seconds. Long answers take longest, because output tokens dominate. Eight questions are too few for a p95 figure.
