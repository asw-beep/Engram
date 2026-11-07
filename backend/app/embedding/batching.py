from app.embedding.base import Embedder, EmbeddingOutOfMemory


def embed_in_batches(embedder: Embedder, texts: list[str], batch_size: int) -> list[list[float]]:
    """Embed in batches, halving the batch size for the rest of the run on out of memory.

    Out of memory at batch size 1 is raised.
    """
    vectors: list[list[float]] = []
    start = 0
    while start < len(texts):
        batch = texts[start : start + batch_size]
        try:
            vectors.extend(embedder.embed_passages(batch, batch_size))
        except EmbeddingOutOfMemory:
            if batch_size == 1:
                raise
            batch_size //= 2
            continue
        start += len(batch)
    return vectors
