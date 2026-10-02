"""FR-KNW-003: hybrid retrieval, at the application layer (`doda.
application.knowledge_service.search_knowledge`), against real Postgres
with a real pgvector `cosine_distance` query — the vector leg's own
embedding call is the only thing faked (`_BagOfWordsEmbeddingPort`
below), same discipline as test_knowledge_api.py's `_FakeEmbeddingPort`.

Unlike that fixture (one vector per BATCH POSITION, with no relationship
to content — fine for its own call-recording tests, useless here),
`_BagOfWordsEmbeddingPort` is a deterministic hashing-trick bag-of-words
embedding: two texts sharing vocabulary get genuinely closer cosine
distance, texts sharing none get further apart. That is what actually
lets these tests exercise the vector leg's real ranking behavior — and
specifically the scenario hybrid retrieval exists for: an exact,
rare-term keyword match the vector leg alone would rank low (or miss
the top-k of entirely) must still surface once RRF fuses it in.
"""

import hashlib
import math
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from doda.application.knowledge_service import search_knowledge
from doda.application.workspace_service import create_workspace
from doda.db import tenant_scoped_session
from doda.domain.customer.models import Customer
from doda.domain.knowledge.models import EMBEDDING_DIMENSIONS, Document, DocumentChunk


class _BagOfWordsEmbeddingPort:
    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self._dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for word in re.findall(r"\w+", text.lower()):
            bucket = int(hashlib.sha256(word.encode()).hexdigest(), 16) % self._dimensions
            vector[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


async def _seed_chunk(
    session: AsyncSession, *, customer_id: uuid.UUID, workspace_id: uuid.UUID, content: str
) -> uuid.UUID:
    """Inserts one Document (one chunk each, for simplicity — the chunk
    boundary itself is FR-KNW-002's own concern, not this one's) with a
    real embedding from `_BagOfWordsEmbeddingPort`. Returns the chunk's
    own id, since that is what `search_knowledge` returns rankings of."""
    document = Document(
        customer_id=customer_id,
        workspace_id=workspace_id,
        uploader_id="user:seed",
        filename="seed.txt",
        content_type="text/plain",
        size_bytes=len(content),
        sha256="0" * 64,
        storage_key=f"test/{uuid.uuid4()}",
    )
    session.add(document)
    await session.flush()

    (vector,) = await _BagOfWordsEmbeddingPort().embed([content])
    chunk = DocumentChunk(
        customer_id=customer_id,
        workspace_id=workspace_id,
        document_id=document.id,
        chunk_index=0,
        start_offset=0,
        end_offset=len(content),
        content=content,
        embedding=vector,
    )
    session.add(chunk)
    await session.flush()
    return chunk.id


async def test_a_rare_keyword_hit_the_vector_leg_alone_would_miss_still_surfaces(
    db_available: bool,
) -> None:
    """The scenario hybrid retrieval exists for: a chunk containing the
    query's own rare, exact term, but with otherwise unrelated
    vocabulary (so the fake vector leg ranks it far from the query),
    must still rise into the fused top-k — a vector-only baseline would
    miss it entirely, since none of its own words overlap the query."""
    customer_id = uuid.uuid4()
    async with tenant_scoped_session(customer_id) as db:
        db.add(Customer(id=customer_id, name="Retrieval Test Customer"))
        await db.flush()
        workspace = await create_workspace(db, customer_id=customer_id, name="Retrieval Test Workspace")

        exact_match_id = await _seed_chunk(
            db,
            customer_id=customer_id,
            workspace_id=workspace.id,
            content="Butunlay bog'liq bo'lmagan mavzu ERRCODE-4471 haqida alohida gap.",
        )
        await _seed_chunk(
            db,
            customer_id=customer_id,
            workspace_id=workspace.id,
            content="Loyihaning umumiy maqsadlari va rejalari haqida umumiy ma'lumot bor.",
        )
        await _seed_chunk(
            db,
            customer_id=customer_id,
            workspace_id=workspace.id,
            content="Jamoaning navbatdagi uchrashuvi va kun tartibi haqida eslatma.",
        )

        results = await search_knowledge(
            db,
            _BagOfWordsEmbeddingPort(),
            workspace_id=workspace.id,
            query="ERRCODE-4471",
            limit=2,
        )
        assert exact_match_id in [chunk.id for chunk in results]


async def test_results_rank_by_shared_vocabulary_via_the_vector_leg(db_available: bool) -> None:
    """With no shared rare keyword at all, the vector leg alone must
    still surface the chunk that shares the MOST vocabulary with the
    query above one that shares none — proving the vector leg's own
    ranking is real, not a no-op that only ever returns insertion
    order."""
    customer_id = uuid.uuid4()
    async with tenant_scoped_session(customer_id) as db:
        db.add(Customer(id=customer_id, name="Retrieval Test Customer"))
        await db.flush()
        workspace = await create_workspace(db, customer_id=customer_id, name="Retrieval Test Workspace")

        close_id = await _seed_chunk(
            db,
            customer_id=customer_id,
            workspace_id=workspace.id,
            content="budjet reja xarajat moliya hisobot",
        )
        far_id = await _seed_chunk(
            db,
            customer_id=customer_id,
            workspace_id=workspace.id,
            content="ob-havo bugun quyoshli va issiq bo'ladi",
        )

        results = await search_knowledge(
            db,
            _BagOfWordsEmbeddingPort(),
            workspace_id=workspace.id,
            query="budjet moliya xarajat",
            limit=2,
        )
        result_ids = [chunk.id for chunk in results]
        assert close_id in result_ids
        assert result_ids.index(close_id) < (
            result_ids.index(far_id) if far_id in result_ids else len(result_ids)
        )


async def test_the_document_id_filter_narrows_results_to_one_documents_own_chunks(
    db_available: bool,
) -> None:
    customer_id = uuid.uuid4()
    async with tenant_scoped_session(customer_id) as db:
        db.add(Customer(id=customer_id, name="Retrieval Test Customer"))
        await db.flush()
        workspace = await create_workspace(db, customer_id=customer_id, name="Retrieval Test Workspace")

        doc_a = Document(
            customer_id=customer_id,
            workspace_id=workspace.id,
            uploader_id="user:seed",
            filename="a.txt",
            content_type="text/plain",
            size_bytes=10,
            sha256="0" * 64,
            storage_key=f"test/{uuid.uuid4()}",
        )
        doc_b = Document(
            customer_id=customer_id,
            workspace_id=workspace.id,
            uploader_id="user:seed",
            filename="b.txt",
            content_type="text/plain",
            size_bytes=10,
            sha256="1" * 64,
            storage_key=f"test/{uuid.uuid4()}",
        )
        db.add_all([doc_a, doc_b])
        await db.flush()

        shared_text = "byudjet hisobot"
        (vector,) = await _BagOfWordsEmbeddingPort().embed([shared_text])
        chunk_a = DocumentChunk(
            customer_id=customer_id,
            workspace_id=workspace.id,
            document_id=doc_a.id,
            chunk_index=0,
            start_offset=0,
            end_offset=len(shared_text),
            content=shared_text,
            embedding=vector,
        )
        chunk_b = DocumentChunk(
            customer_id=customer_id,
            workspace_id=workspace.id,
            document_id=doc_b.id,
            chunk_index=0,
            start_offset=0,
            end_offset=len(shared_text),
            content=shared_text,
            embedding=vector,
        )
        db.add_all([chunk_a, chunk_b])
        await db.flush()

        results = await search_knowledge(
            db,
            _BagOfWordsEmbeddingPort(),
            workspace_id=workspace.id,
            query="byudjet",
            document_id=doc_a.id,
            limit=10,
        )
        result_ids = {chunk.id for chunk in results}
        assert chunk_a.id in result_ids
        assert chunk_b.id not in result_ids


async def test_a_sibling_workspaces_chunk_never_leaks_into_search_results(
    db_available: bool,
) -> None:
    """The case RLS cannot cover on its own (see test_cross_workspace_
    record_access.py's own docstring): two workspaces under the SAME
    customer. search_knowledge's `DocumentChunk.workspace_id ==
    workspace_id` filter is this function's own version of that
    explicit, non-RLS guard — proven here the same way that file proves
    it for single-id lookups, applied to a query instead."""
    customer_id = uuid.uuid4()
    async with tenant_scoped_session(customer_id) as db:
        db.add(Customer(id=customer_id, name="Retrieval Test Customer"))
        await db.flush()
        workspace_a = await create_workspace(db, customer_id=customer_id, name="A")
        workspace_b = await create_workspace(db, customer_id=customer_id, name="B")

        # Same exact wording in both workspaces, so a leak would be
        # unmistakable: workspace A's own search would only legitimately
        # return workspace_a's chunk.
        shared_wording = "maxfiy byudjet hisobot"
        chunk_a_id = await _seed_chunk(
            db, customer_id=customer_id, workspace_id=workspace_a.id, content=shared_wording
        )
        chunk_b_id = await _seed_chunk(
            db, customer_id=customer_id, workspace_id=workspace_b.id, content=shared_wording
        )

        results_a = await search_knowledge(
            db, _BagOfWordsEmbeddingPort(), workspace_id=workspace_a.id, query="byudjet", limit=10
        )
        result_ids_a = {chunk.id for chunk in results_a}
        assert chunk_a_id in result_ids_a
        assert chunk_b_id not in result_ids_a


async def test_a_blank_query_returns_no_results(db_available: bool) -> None:
    customer_id = uuid.uuid4()
    async with tenant_scoped_session(customer_id) as db:
        db.add(Customer(id=customer_id, name="Retrieval Test Customer"))
        await db.flush()
        workspace = await create_workspace(db, customer_id=customer_id, name="Retrieval Test Workspace")
        await _seed_chunk(db, customer_id=customer_id, workspace_id=workspace.id, content="har qanday matn")

        results = await search_knowledge(
            db, _BagOfWordsEmbeddingPort(), workspace_id=workspace.id, query="   ", limit=10
        )
        assert results == []
