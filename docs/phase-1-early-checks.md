# Phase 1 early checks

Measured on 2026-11-07. These are the three early checks from §10 of the Phase 1 design spec. Their results set `embedding_batch_size` and the API memory cap used in Task 18.

**Synthetic data:** the embedding checks use synthetic inputs. They embed 100 generated passages of at least 512 tokens each, made from a fixed list of engineering words with seed 1234, and run 20 generated 12-word queries. This text isn't drawn from real documents, so throughput and latency on the real corpus may differ. The LLM check uses two short passages written for the check.

## Environment

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 3050 6GB Laptop GPU (6,144 MiB) |
| Host | Windows 11, 23.7 GB RAM |
| Docker | Docker Desktop 4.98.0, engine 29.9.2 |
| Model | `BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181` |
| Libraries | sentence-transformers 6.2.0, transformers 5.22.2, huggingface-hub 2.4.0 |
| PyTorch | 2.14.1+cu130 on the host, 2.15.0+cpu in the container |

## Summary

| Check | Pass condition | Result |
|---|---|---|
| 1. BGE-M3 fits on the 6 GB GPU | Dimension 1024 at batch size 8, no out-of-memory error | **Pass** |
| 2. BGE-M3 on 2 CPUs and 8 GiB | Peak RSS ≤ 3,500 MB and query p95 ≤ 2,000 ms | **Pass** |
| 3. The primary free model returns structured, cited answers | Valid JSON, a correct `[1]` citation, and `insufficient_evidence` when the passages don't hold the answer | **Pass** |
| Fallback model | No pass condition in the plan | **Not verified.** It was rate-limited upstream on all three attempts |

## 1. GPU

Command, run from `backend/`:

```
uv run python scripts/checks/check_embedding.py --device cuda --batch-size 8
```

| Measure | Plan command | Rerun with Hub calls disabled |
|---|---|---|
| dtype | float16 | float16 |
| Dimension | 1024 | 1024 |
| Load time | 399.2 s | **4.2 s** |
| Passages per second | 28.91 | 23.89 |
| Query p50 / p95 | 21.7 / 51.2 ms | 21.9 / 83.4 ms |
| Peak VRAM | 1,276 MB | 1,276 MB |
| Peak RSS | 3,987 MB | 3,982 MB |

There were no out-of-memory errors, so batch size 8 needed no halving. Peak VRAM is about a fifth of the GPU's 6 GB.

The rerun set `HF_HUB_OFFLINE=1` and `DISABLE_SAFETENSORS_CONVERSION=1` with the model already cached. The 399-second load time therefore comes from network activity during model loading, not from reading the weights (see Finding 1). An earlier attempt crashed with exit code 139 after the system drive ran out of space, so it is excluded.

## 2. Constrained CPU

Command, run from the repo root after building the image:

```
docker run --rm --cpus=2 --memory=8g -v engram-hf:/models -e HF_HOME=/models engram-api \
  uv run --frozen --no-dev python scripts/checks/check_embedding.py --device cpu --batch-size 4
```

| Measure | Result | Limit |
|---|---|---|
| dtype | float32 | |
| Dimension | 1024 | |
| Peak RSS | 2,631.6 MB | ≤ 3,500 MB |
| Query p50 / p95 | 1,448.1 / 1,593.9 ms | p95 ≤ 2,000 ms |
| Passages per second | 0.09 | |
| Load time | 515.1 s | |
| PyTorch threads | 8 | |

The `engram-hf` volume was pre-filled by copying the local model cache, so the load time doesn't include a download. This matches the GPU run. The load time most likely has the same network cause as the GPU run, but that hasn't been measured with Hub calls disabled.

PyTorch picked 8 threads because it sees all the host's cores rather than the 2-CPU limit. Running 8 threads on 2 CPUs may make these figures somewhat pessimistic compared with a real 2-vCPU server.

## 3. LLM

Command, run from `backend/`:

```
uv run python scripts/checks/check_llm.py
```

**Primary model, `nvidia/nemotron-3.5-super-vl:free`, using `json_schema`:**

| Question | Status | Answer | Completion tokens (reasoning) |
|---|---|---|---|
| Answerable | `answered` | `PostgreSQL [1]` | 211 (192) |
| Unanswerable | `insufficient_evidence` | `The passages do not mention audit log retention.` | 189 (163) |

Both cases matched what the check expects. Most of the output tokens are reasoning tokens, which matters when setting token limits and timeouts in Task 10.

**Fallback model, `google/gemma-4-31b-it:free`, using `json_object`:**

All three attempts between 13:51 and 14:11 returned HTTP 429, so the fallback's structured output is still unverified. The raw error body was:

```json
{
  "message": "Provider returned error",
  "code": 429,
  "metadata": {
    "raw": "google/gemma-4-31b-it:free is temporarily rate-limited upstream. ...",
    "provider_name": "Google AI Studio",
    "limit_source": "upstream_provider_shared_pool"
  }
}
```

The spec counts an upstream-provider 429 as a model error that uses the fallback, rather than as `quota_exhausted`. The `limit_source` field is the evidence Task 10 needs to tell these errors apart from OpenRouter's own free-model daily limit.

## Decisions

- **`embedding_batch_size`:** keep 8 on the GPU and 4 on the CPU, as tested.
- **API memory cap in Task 18:** keep `api` at 4g. The measured peak RSS of 2,632 MB leaves about 1.4 GB for the rest of the API. Task 18, Step 4 will confirm this.

## Findings for later tasks

1. **Task 7, model loading.** The pinned revision has only `pytorch_model.bin`, and transformers loads it from that revision. It then starts a background thread that downloads a safetensors conversion from the Hub pull request `refs/pr/130` (commit `9a0624b`, 2.27 GB). That file is never used, and the thread contacts the Hub on every load. Set `DISABLE_SAFETENSORS_CONVERSION=1`, and also `HF_HUB_OFFLINE=1` once the model is cached. Doing both brought the GPU load from 399 s down to 4.2 s.
2. **Task 18, CPU threads.** Pin the PyTorch thread count to the container's CPU limit.
3. **Task 18, image size.** The API image is 3.96 GB. Its `uv sync` layer is 2.9 GB, of which 1.4 GB is the uv download cache. Using `uv sync --no-cache`, or a build cache mount, removes it.
4. **Task 17, bulk ingestion.** CPU embedding runs at 0.09 passages per second, which is about 3 hours per 1,000 chunks. That makes the GPU or Kaggle route necessary for loading the corpus.
5. **Task 10, fallback.** Before relying on `google/gemma-4-31b-it:free`, retest it or choose another fallback model.
