"""FR-KNW-003: the deterministic "reranking" step of hybrid retrieval —
Reciprocal Rank Fusion (RRF). Pure domain logic, independent of how
either input ranking was produced (a keyword SQL query vs a vector
cosine-distance SQL query, both in doda.application.knowledge_service.
search_knowledge) — this module never touches the database or an
embedding provider, which is exactly why it is unit-testable without
either.

RRF is a well-established, deterministic combination technique (Cormack,
Clarke & Buettcher, 2009) — not an ML model, no training data, no eval
set required to validate the ALGORITHM itself. It solves the specific
problem hybrid search has: a keyword leg's score (e.g. "3 matching
words") and a vector leg's score (e.g. cosine similarity 0.84) are not
on comparable scales, so summing or averaging them directly would be
meaningless. RRF sidesteps that by combining each item's RANK (1st,
2nd, 3rd place) within each list, not its raw score — an item ranked
highly by EITHER leg rises to the top of the fused list, which is
exactly what "hybrid" is meant to achieve: catch what pure-vector
search misses via an exact keyword hit, and vice versa.
"""

import uuid

# The constant from the original RRF paper. Deliberately NOT tuned
# against this codebase's own data — there is no eval set large enough
# to tune it against without overfitting to a handful of synthetic
# queries, and the paper's own finding is that the fused ranking is not
# very sensitive to this value in the first place.
RRF_K = 60


def reciprocal_rank_fusion(rank_lists: list[list[uuid.UUID]], *, k: int = RRF_K) -> list[uuid.UUID]:
    """Combines any number of independently-produced rankings (best
    first) into one fused ranking. Each list contributes 1/(k+rank) to
    every id it contains (rank is 1-based); an id absent from a list
    contributes 0 from it. An id that appears in every list accumulates
    the highest score, which is the entire point: it was independently
    judged relevant by every retrieval method, not just one.

    Deterministic and side-effect-free: the same input always produces
    the same output, with no database or network access — this is what
    makes it unit-testable on its own, apart from the SQL queries that
    produce its inputs."""
    scores: dict[uuid.UUID, float] = {}
    for rank_list in rank_lists:
        for rank, item_id in enumerate(rank_list, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda item_id: scores[item_id], reverse=True)
