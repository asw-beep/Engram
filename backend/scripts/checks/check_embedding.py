"""Measure BGE-M3 load time, throughput, query latency and peak memory on one device."""

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import psutil  # noqa: E402
import torch  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from app.config import get_settings  # noqa: E402

PASSAGE_COUNT = 100
PASSAGE_TOKENS = 512
QUERY_COUNT = 20
MAX_SEQ_LENGTH = 1024
SEED = 1234

WORDS = """
cluster node pod container scheduler deployment service ingress volume secret replica
controller namespace rollout probe restart latency throughput timeout retry backoff queue
partition broker consumer producer schema migration index query transaction rollback commit
snapshot backup restore failover certificate token permission tenant upstream downstream
endpoint gateway proxy cache eviction memory processor network packet routing storage
configures validates reconciles schedules provisions replicates authenticates monitors
the a an of to in for with when after before during between across each every
""".split()


def build_passage(rng: random.Random, model: SentenceTransformer) -> str:
    words: list[str] = []
    while True:
        words.extend(rng.choices(WORDS, k=25))
        text = " ".join(words)
        if len(model.tokenizer.encode(text, add_special_tokens=False)) >= PASSAGE_TOKENS:
            return text


def peak_rss_mb() -> float:
    peak = getattr(psutil.Process().memory_info(), "peak_wset", None)
    if peak is None:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    return round(peak / 1024**2, 1)


def peak_vram_mb(device: str) -> float | None:
    if not device.startswith("cuda"):
        return None
    return round(torch.cuda.max_memory_reserved() / 1024**2, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    parser.add_argument("--batch-size", type=int, required=True)
    args = parser.parse_args()

    settings = get_settings()
    model_kwargs = {"dtype": torch.float16} if args.device.startswith("cuda") else {}

    started = time.perf_counter()
    model = SentenceTransformer(
        settings.embedding_model_id,
        revision=settings.embedding_model_revision,
        device=args.device,
        model_kwargs=model_kwargs,
    )
    model.max_seq_length = MAX_SEQ_LENGTH
    load_seconds = time.perf_counter() - started

    rng = random.Random(SEED)
    passages = [build_passage(rng, model) for _ in range(PASSAGE_COUNT)]
    queries = [" ".join(rng.choices(WORDS, k=12)) for _ in range(QUERY_COUNT)]

    started = time.perf_counter()
    embeddings = model.encode_document(
        passages, batch_size=args.batch_size, normalize_embeddings=True
    )
    encode_seconds = time.perf_counter() - started

    latencies = []
    for query in queries:
        started = time.perf_counter()
        model.encode_query(query, normalize_embeddings=True)
        latencies.append((time.perf_counter() - started) * 1000)

    print(
        json.dumps(
            {
                "device": args.device,
                "batch_size": args.batch_size,
                "dtype": str(next(model.parameters()).dtype),
                "threads": torch.get_num_threads(),
                "dimension": int(embeddings.shape[1]),
                "load_seconds": round(load_seconds, 1),
                "passages_per_second": round(PASSAGE_COUNT / encode_seconds, 2),
                "query_p50_ms": round(statistics.median(latencies), 1),
                "query_p95_ms": round(
                    statistics.quantiles(latencies, n=20, method="inclusive")[18], 1
                ),
                "peak_rss_mb": peak_rss_mb(),
                "peak_vram_mb": peak_vram_mb(args.device),
            }
        )
    )


if __name__ == "__main__":
    main()
