import math

import pytest

from eval.dataset import Gold
from eval.metrics import (
    Ranked,
    balanced_accuracy,
    best_cutoff,
    in_section,
    ndcg_at,
    percentile,
    recall_at,
    reciprocal_rank,
)

G = (Gold("a.md", ("A", "B")),)


def r(path, *headings):
    return Ranked(path, tuple(headings))


def test_in_section_matches_the_heading_prefix():
    assert in_section(r("a.md", "A", "B", "C"), G[0])
    assert not in_section(r("a.md", "A"), G[0])
    assert not in_section(r("b.md", "A", "B"), G[0])


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


def test_recall_without_gold_is_an_error():
    with pytest.raises(ValueError):
        recall_at(5, [r("a.md")], ())


def test_reciprocal_rank_of_third_place():
    assert reciprocal_rank([r("x.md"), r("y.md"), r("a.md", "A", "B")], G) == pytest.approx(1 / 3)


def test_reciprocal_rank_is_zero_past_k():
    assert reciprocal_rank([r("x.md"), r("a.md", "A", "B")], G, k=1) == 0.0


def test_ndcg_is_one_for_the_ideal_order():
    assert ndcg_at(10, [r("a.md", "A", "B"), r("a.md", "Z")], G) == pytest.approx(1.0)


def test_ndcg_for_gold_in_second_place():
    # DCG = 2/log2(3); IDCG = 2/log2(2) + 1/log2(3)
    expected = (2 / math.log2(3)) / (2 + 1 / math.log2(3))
    assert ndcg_at(10, [r("x.md"), r("a.md", "A", "B")], G) == pytest.approx(expected)


def test_ndcg_counts_a_section_once():
    once = ndcg_at(10, [r("a.md", "A", "B")], G)
    assert ndcg_at(10, [r("a.md", "A", "B"), r("a.md", "A", "B")], G) == pytest.approx(once)


def test_ndcg_counts_a_document_once():
    # Two chunks elsewhere in the gold document earn 1 between them, not 2.
    once = ndcg_at(10, [r("a.md", "Z")], G)
    assert ndcg_at(10, [r("a.md", "Z"), r("a.md", "Y")], G) == pytest.approx(once)


def test_ndcg_is_one_when_a_whole_document_is_gold():
    # A gold entry with no headings covers the whole document, so no chunk can earn 1.
    assert ndcg_at(10, [r("a.md", "Any")], (Gold("a.md", ()),)) == pytest.approx(1.0)


def test_ndcg_is_zero_with_nothing_relevant():
    assert ndcg_at(10, [r("x.md")], G) == 0.0


def test_best_cutoff_separates_two_groups():
    assert best_cutoff([0.9, 0.8, 0.7], [0.2, 0.1]) == pytest.approx(0.45)


def test_best_cutoff_takes_the_lowest_on_a_tie():
    # The midpoints 0.2 and 0.5 both give balanced accuracy 0.75.
    assert best_cutoff([0.6, 0.3], [0.4, 0.1]) == pytest.approx(0.2)


def test_balanced_accuracy_averages_both_rates():
    # answerable: 2 of 3 pass; unanswerable: 1 of 2 refused.
    assert balanced_accuracy([0.9, 0.6, 0.2], [0.7, 0.1], 0.5) == pytest.approx((2 / 3 + 1 / 2) / 2)


def test_a_score_equal_to_the_cutoff_passes():
    assert balanced_accuracy([0.5], [0.5], 0.5) == pytest.approx(0.5)


def test_percentile_nearest_rank():
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert percentile([5, 1, 3], 50) == 3


def test_percentile_of_nothing_is_an_error():
    with pytest.raises(ValueError):
        percentile([], 50)


def test_ndcg_is_one_when_the_gold_document_has_nothing_outside_its_section():
    # The harness says which gold documents have chunks outside their gold sections.
    assert ndcg_at(10, [r("a.md", "A", "B")], G, outside=frozenset()) == pytest.approx(1.0)


def test_ndcg_still_expects_the_rest_of_a_document_that_has_more():
    assert ndcg_at(10, [r("a.md", "A", "B")], G, outside=frozenset({"a.md"})) < 1.0


def test_percentile_rejects_a_share_outside_zero_to_hundred():
    with pytest.raises(ValueError):
        percentile([1, 2], 101)
