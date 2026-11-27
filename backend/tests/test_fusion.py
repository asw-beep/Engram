from uuid import uuid4

import pytest

from app.retrieval.fusion import reciprocal_rank_fusion

A, B, C, D = (uuid4() for _ in range(4))


def test_a_chunk_in_both_rankings_comes_first_with_both_terms():
    fused = reciprocal_rank_fusion([[A, B, C], [B, D]], k=60)
    assert [chunk_id for chunk_id, _ in fused] == [B, A, D, C]
    scores = dict(fused)
    assert scores[B] == pytest.approx(1 / 62 + 1 / 61)
    assert scores[A] == pytest.approx(1 / 61)
    assert scores[D] == pytest.approx(1 / 62)
    assert scores[C] == pytest.approx(1 / 63)


def test_a_chunk_in_one_ranking_only_is_kept():
    assert [chunk_id for chunk_id, _ in reciprocal_rank_fusion([[A], [B]])] == [A, B]


def test_ties_go_to_the_first_ranking_that_holds_the_chunk():
    # A and D tie at rank 1; C and B tie at rank 2.
    fused = reciprocal_rank_fusion([[A, C], [D, B]])
    assert [chunk_id for chunk_id, _ in fused] == [A, D, C, B]


def test_an_empty_ranking_changes_nothing():
    assert reciprocal_rank_fusion([[A, B], []]) == reciprocal_rank_fusion([[A, B]])


def test_no_rankings_give_nothing():
    assert reciprocal_rank_fusion([]) == []


def test_k_sets_how_fast_scores_fall_with_rank():
    assert dict(reciprocal_rank_fusion([[A, B]], k=0)) == {A: 1.0, B: 0.5}


def test_a_chunk_listed_twice_in_one_ranking_counts_once():
    assert dict(reciprocal_rank_fusion([[A, A]], k=0)) == {A: 1.0}
