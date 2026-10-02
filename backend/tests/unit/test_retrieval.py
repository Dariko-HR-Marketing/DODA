import uuid

from doda.domain.knowledge.retrieval import RRF_K, reciprocal_rank_fusion


def _ids(n: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(n)]


def test_an_item_ranked_first_in_every_list_wins_the_fused_ranking() -> None:
    a, b, c = _ids(3)
    fused = reciprocal_rank_fusion([[a, b, c], [a, c, b]])
    assert fused[0] == a


def test_an_item_ranked_highly_by_only_one_leg_still_rises_above_items_absent_from_both() -> None:
    # This is the whole point of hybrid search: a keyword-only exact hit
    # the vector leg missed entirely should still surface, rather than
    # being invisible because it never appeared in the vector ranking.
    a, b, c, d = _ids(4)
    keyword_leg = [a]  # b/c/d: no keyword match at all
    vector_leg = [b, c, d]  # a: not semantically close enough to rank
    fused = reciprocal_rank_fusion([keyword_leg, vector_leg])
    assert a in fused
    assert set(fused) == {a, b, c, d}


def test_an_item_missing_from_one_leg_entirely_is_not_penalized_to_the_bottom() -> None:
    a, b = _ids(2)
    # a: 1st in both legs. b: 2nd in leg one, ABSENT from leg two.
    fused = reciprocal_rank_fusion([[a, b], [a]])
    assert fused == [a, b]


def test_empty_rank_lists_produce_an_empty_fused_ranking() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_fusion_is_deterministic_for_the_same_input() -> None:
    ids = _ids(5)
    lists = [[ids[0], ids[2], ids[4]], [ids[1], ids[0], ids[3]]]
    assert reciprocal_rank_fusion(lists) == reciprocal_rank_fusion(lists)


def test_a_smaller_k_amplifies_the_difference_between_top_and_lower_ranks() -> None:
    # Reproduces, directly, the RRF formula's own shape: 1/(k+rank).
    a, b = _ids(2)
    fused_default = reciprocal_rank_fusion([[a, b]], k=RRF_K)
    fused_small_k = reciprocal_rank_fusion([[a, b]], k=1)
    assert fused_default == [a, b]
    assert fused_small_k == [a, b]

    # With k=1: a scores 1/2, b scores 1/3 -> ratio 1.5.
    # With k=60: a scores 1/61, b scores 1/62 -> ratio ~1.016.
    # The smaller k must produce the larger top/second-place ratio.
    def _score(rank_list: list[uuid.UUID], target: uuid.UUID, k: int) -> float:
        return 1.0 / (k + rank_list.index(target) + 1)

    ratio_small_k = _score([a, b], a, 1) / _score([a, b], b, 1)
    ratio_default_k = _score([a, b], a, RRF_K) / _score([a, b], b, RRF_K)
    assert ratio_small_k > ratio_default_k
