"""The real BGE-reranker-v2-m3. Skipped unless its pinned revision is in the Hugging Face
cache, so run it with HF_HOME set to the project's cache (CLAUDE.md, "Downloads"):

    HF_HOME=E:/Projects/Engram/data/hf uv run pytest -m slow tests/test_reranker_model.py
"""

import pytest
from huggingface_hub import try_to_load_from_cache

from app.config import Settings
from app.retrieval.rerank import BgeReranker

SETTINGS = Settings()
CACHED = isinstance(
    try_to_load_from_cache(
        SETTINGS.reranker_model_id, "config.json", revision=SETTINGS.reranker_model_revision
    ),
    str,
)

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not CACHED, reason="the reranker isn't in HF_HOME; download it first"),
]

QUESTION = "How does the kubelet decide to restart a failed container?"
RELEVANT = (
    "Container restart policy > Restart behaviour\n\n"
    "The kubelet restarts a container that exits with an error when the Pod's restartPolicy "
    "is Always or OnFailure, waiting longer after each failure, up to five minutes."
)
IRRELEVANT = (
    "Ingress > TLS\n\n"
    "You can secure an Ingress by specifying a Secret that contains a TLS private key and "
    "certificate."
)


@pytest.fixture(scope="module")
def reranker():
    return BgeReranker(SETTINGS)


def test_a_relevant_passage_outscores_an_irrelevant_one(reranker):
    relevant, irrelevant = reranker.score(QUESTION, [RELEVANT, IRRELEVANT])
    assert relevant > irrelevant


def test_scores_are_probabilities(reranker):
    assert all(0.0 <= score <= 1.0 for score in reranker.score(QUESTION, [RELEVANT, IRRELEVANT]))


def test_a_passage_longer_than_the_model_reads_is_truncated_not_refused(reranker):
    (score,) = reranker.score(QUESTION, [RELEVANT + " filler" * 5000])
    assert 0.0 <= score <= 1.0


def test_no_passages_give_no_scores(reranker):
    assert reranker.score(QUESTION, []) == []
