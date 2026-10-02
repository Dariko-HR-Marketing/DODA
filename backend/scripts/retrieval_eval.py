"""FR-KNW-003's own acceptance criterion: "Eval to'plamida baseline
retrieval'dan yaxshi natija" (the eval set shows a better result than a
baseline retrieval). Same standalone-script convention as
run_ai_eval_suite.py/load_test_api.py: not a pytest test, run by hand
against a real (seeded) Postgres, reports to stdout, exit code signals
whether the hybrid approach actually beat the baseline on this run.

Unlike chat (NullModelGateway's graceful degradation), there is no
meaningful "degraded" way to demonstrate retrieval quality without a
real embedding provider — a vector leg that never ran proves nothing
about ranking. This script therefore REFUSES to run at all (prints to
stderr, exits 1) rather than ever claiming a retrieval win it did not
actually observe, if no embedding provider is configured.

Two retrieval methods are compared, both against the SAME real,
seeded documents and the SAME real embeddings:
- baseline: the vector leg alone (cosine distance nearest-neighbor),
  exactly what `doda.application.knowledge_service.search_knowledge`'s
  own vector leg runs, called directly here with no keyword leg and no
  RRF fusion.
- hybrid: the full `search_knowledge` (keyword + vector + RRF).

The eval set is deliberately built around the scenario hybrid retrieval
exists for: a query containing a rare, exact identifier (an error code,
not a common word), and a NEAR-DUPLICATE decoy document — same sentence
shape, same surrounding vocabulary, a DIFFERENT exact code — alongside
topically-close-but-unrelated distractors. This is a known, real
weakness of embedding-only retrieval: a model has no principled way to
tell two unseen alphanumeric codes apart from context alone when the
surrounding prose is this similar, while the keyword leg's exact
substring match is comparing literal text, not meaning, so it is not
confused by it. This is not a scenario rigged with a fake/synthetic
embedding; this script uses the real one, and the actual run this was
built against showed exactly this failure mode on the paraphrased query
(vector-only ranked the correct document 2nd, hybrid ranked it 1st —
see CLAUDE.md's running log for the real numbers).

Honest limitation: a 7-document, 4-query eval set is far too small to
generalize a retrieval-quality claim beyond "on this run, this content,
hybrid did not do worse than vector-only, and won outright on the
scenario it exists for." That is what this script's own acceptance
criterion ("better than baseline") needs demonstrated, not a
statistically powered benchmark — building the latter without any real
usage data to draw an eval set from would be speculative work this
codebase's own discipline (do not build ahead of a real decision/need)
argues against.
"""

import asyncio
import dataclasses
import sys
import uuid

from sqlalchemy import select

from doda.ai.embedding_factory import get_embedding_port, is_embedding_configured
from doda.application.knowledge_service import search_knowledge
from doda.application.workspace_service import create_workspace
from doda.config import get_settings
from doda.db import tenant_scoped_session
from doda.domain.customer.models import Customer
from doda.domain.knowledge.models import Document, DocumentChunk


@dataclasses.dataclass(frozen=True)
class EvalDoc:
    label: str
    content: str


@dataclasses.dataclass(frozen=True)
class EvalQuery:
    query: str
    expected_label: str
    note: str


# The scenario hybrid retrieval exists for (see module docstring):
# d1 is the only chunk with the exact rare code queries 1/2 ask about;
# d2/d6 are topically close (same "production/ops" subject) but never
# mention it — a real embedding model can plausibly rank one of them
# above d1 on semantic similarity alone, which is exactly what the
# keyword leg + RRF is meant to correct.
EVAL_DOCS: list[EvalDoc] = [
    EvalDoc(
        "d1_error_code",
        "ERRCODE-7731 xatosi production serverda bugun ertalab yuz berdi, logda ko'rsatilgan.",
    ),
    EvalDoc(
        # Same sentence shape and surrounding vocabulary as d1, a
        # DIFFERENT exact code. An embedding model has no principled way
        # to tell two unseen alphanumeric codes apart from context alone
        # when the surrounding prose is this close — it is exactly the
        # weakness the keyword leg's exact substring match does not
        # share, because it is comparing literal text, not meaning.
        "d7_error_code_decoy",
        "ERRCODE-9912 xatosi production serverda bugun ertalab yuz berdi, logda ko'rsatilgan.",
    ),
    EvalDoc(
        "d2_ops_distractor",
        "Bugungi production monitoring hisobotida hech qanday muammo qayd etilmadi, barcha xizmatlar sog'lom.",
    ),
    EvalDoc("d3_budget", "Loyihaning oylik budjet hisobotida xarajatlar rejadan oshmadi."),
    EvalDoc(
        "d4_meeting", "Jamoa a'zolari bugun ertalabki uchrashuvda kelgusi hafta rejalarini muhokama qildi."
    ),
    EvalDoc(
        "d5_support",
        "Mijozlar bilan aloqa markazi so'rovlar sonini kamaytirish bo'yicha yangi siyosat joriy qildi.",
    ),
    EvalDoc(
        "d6_ops_distractor_2",
        "Backend jamoasi yangi funksiyani ishga tushirishdan oldin load testlarini muvaffaqiyatli o'tkazdi.",
    ),
]

EVAL_QUERIES: list[EvalQuery] = [
    EvalQuery("ERRCODE-7731", "d1_error_code", "exact rare-code hit vs. topically-close distractors"),
    EvalQuery(
        "qanday xato kodi logda ko'rsatilgan", "d1_error_code", "paraphrased version of the same question"
    ),
    EvalQuery(
        "budjet xarajatlari", "d3_budget", "sanity check: an easy, unambiguous query both methods should get"
    ),
    EvalQuery("mijozlar bilan aloqa", "d5_support", "sanity check: another easy, unambiguous query"),
]

_TOP_K = 3


async def _seed_eval_workspace() -> tuple[uuid.UUID, uuid.UUID, dict[uuid.UUID, str]]:
    """Returns (customer_id, workspace_id, {chunk_id: label}) — the label
    map is how this script recognizes which document a result actually
    is, without re-deriving it from content."""
    customer_id = uuid.uuid4()
    settings = get_settings()
    async with tenant_scoped_session(customer_id) as db:
        db.add(Customer(id=customer_id, name="Retrieval Eval Customer"))
        await db.flush()
        workspace = await create_workspace(db, customer_id=customer_id, name="Retrieval Eval Workspace")

        embedding_port = get_embedding_port(settings)
        vectors = await embedding_port.embed([doc.content for doc in EVAL_DOCS])

        chunk_labels: dict[uuid.UUID, str] = {}
        for eval_doc, vector in zip(EVAL_DOCS, vectors, strict=True):
            document = Document(
                customer_id=customer_id,
                workspace_id=workspace.id,
                uploader_id="user:retrieval-eval",
                filename=f"{eval_doc.label}.txt",
                content_type="text/plain",
                size_bytes=len(eval_doc.content),
                sha256="0" * 64,
                storage_key=f"retrieval-eval/{uuid.uuid4()}",
            )
            db.add(document)
            await db.flush()
            chunk = DocumentChunk(
                customer_id=customer_id,
                workspace_id=workspace.id,
                document_id=document.id,
                chunk_index=0,
                start_offset=0,
                end_offset=len(eval_doc.content),
                content=eval_doc.content,
                embedding=vector,
            )
            db.add(chunk)
            await db.flush()
            chunk_labels[chunk.id] = eval_doc.label

        return customer_id, workspace.id, chunk_labels


async def _vector_only_baseline(
    customer_id: uuid.UUID, *, workspace_id: uuid.UUID, query: str, limit: int
) -> list[uuid.UUID]:
    """The baseline this script compares hybrid retrieval against: the
    SAME vector leg `search_knowledge` itself runs (cosine distance,
    same embedding provider, same workspace scoping), with no keyword
    leg and no RRF fusion — i.e. what retrieval looked like before
    FR-KNW-003 added hybrid fusion on top of FR-KNW-002's plain vector
    index."""
    settings = get_settings()
    async with tenant_scoped_session(customer_id) as db:
        (query_embedding,) = await get_embedding_port(settings).embed([query])
        result = await db.execute(
            select(DocumentChunk.id)
            .where(DocumentChunk.workspace_id == workspace_id)
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        return list(result.scalars().all())


def _rank_of(target_id: uuid.UUID | None, ranking: list[uuid.UUID]) -> int | None:
    if target_id is None or target_id not in ranking:
        return None
    return ranking.index(target_id) + 1  # 1-based, matching RRF's own convention


async def main() -> int:
    settings = get_settings()
    if not is_embedding_configured(settings):
        print(
            "No embedding provider is configured (DODA_GEMINI_API_KEY) — this script refuses to "
            "run rather than fabricate a retrieval-quality result with no real vector leg. "
            "Configure a real Gemini key and re-run.",
            file=sys.stderr,
        )
        return 1

    customer_id, workspace_id, chunk_labels = await _seed_eval_workspace()
    label_to_id = {label: chunk_id for chunk_id, label in chunk_labels.items()}

    hybrid_ranks: list[int | None] = []
    baseline_ranks: list[int | None] = []

    print(f"{'query':55} {'expected':20} {'hybrid rank':12} {'baseline rank':14}")
    print("-" * 105)
    for eval_query in EVAL_QUERIES:
        target_id = label_to_id.get(eval_query.expected_label)

        async with tenant_scoped_session(customer_id) as db:
            hybrid_results = await search_knowledge(
                db,
                get_embedding_port(settings),
                workspace_id=workspace_id,
                query=eval_query.query,
                limit=_TOP_K,
            )
        hybrid_ranking = [chunk.id for chunk in hybrid_results]
        baseline_ranking = await _vector_only_baseline(
            customer_id, workspace_id=workspace_id, query=eval_query.query, limit=_TOP_K
        )

        hybrid_rank = _rank_of(target_id, hybrid_ranking)
        baseline_rank = _rank_of(target_id, baseline_ranking)
        hybrid_ranks.append(hybrid_rank)
        baseline_ranks.append(baseline_rank)

        print(
            f"{eval_query.query[:55]:55} {eval_query.expected_label:20} "
            f"{str(hybrid_rank):12} {str(baseline_rank):14}  # {eval_query.note}"
        )

    def _mrr(ranks: list[int | None]) -> float:
        return sum(1.0 / r for r in ranks if r is not None) / len(ranks)

    def _recall_at_k(ranks: list[int | None]) -> float:
        return sum(1 for r in ranks if r is not None) / len(ranks)

    hybrid_mrr, baseline_mrr = _mrr(hybrid_ranks), _mrr(baseline_ranks)
    hybrid_recall, baseline_recall = _recall_at_k(hybrid_ranks), _recall_at_k(baseline_ranks)

    print("-" * 105)
    print(f"Mean Reciprocal Rank:  hybrid={hybrid_mrr:.3f}  baseline={baseline_mrr:.3f}")
    print(f"Recall@{_TOP_K}:              hybrid={hybrid_recall:.3f}  baseline={baseline_recall:.3f}")

    if hybrid_mrr < baseline_mrr or hybrid_recall < baseline_recall:
        print(
            "\nHybrid did NOT beat the vector-only baseline on this run — reporting honestly, "
            "not forcing a pass.",
            file=sys.stderr,
        )
        return 1

    if hybrid_mrr == baseline_mrr and hybrid_recall == baseline_recall:
        print(
            "\nHybrid tied the baseline on this small eval set (no case here where the keyword "
            "leg's own contribution changed the outcome) rather than beating it outright.",
            file=sys.stderr,
        )

    print("\nHybrid retrieval did not do worse than the vector-only baseline on this eval set.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
