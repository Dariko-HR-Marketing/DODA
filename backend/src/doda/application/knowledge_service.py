"""FR-KNW-001/002: file ingest and indexing. `ingest_file` validates
(doda.domain.knowledge.file_validation), stores (doda.storage.port.
ObjectStoragePort) and records (Document row) an upload. `index_document`
is the separate, explicitly-called next step (FR-KNW-002): parses,
chunks and embeds that same upload's content into DocumentChunk rows —
kept apart from `ingest_file` so the two can be tested and reasoned
about independently (a Document can exist with zero chunks; that is
never, on its own, a sign something went wrong — see index_document's
own docstring).

Ordering note (accepted, documented limitation, not a gap this task
closes): storage happens BEFORE the Document row is inserted, so a
crash between the two leaves an orphaned object with no DB row pointing
at it (harmless — nothing can ever reach it) rather than a DB row
pointing at a file that was never written (which would be a broken
reference every read of it hits). The reverse ordering trades one
failure mode for the other; this one was chosen because it fails safe.
"""

import hashlib
import re
import uuid

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from doda.ai.embedding_port import EmbeddingPort
from doda.domain.knowledge.chunking import chunk_text
from doda.domain.knowledge.file_validation import storage_key_for, validate_file
from doda.domain.knowledge.models import Document, DocumentChunk
from doda.domain.knowledge.retrieval import reciprocal_rank_fusion
from doda.domain.knowledge.text_extraction import extract_text
from doda.storage.port import ObjectStoragePort

MAX_PAGE_SIZE = 200
# How many candidates each leg (keyword, vector) contributes to the
# fusion step before it trims down to the caller's own `limit` — wider
# than `limit` so RRF (doda.domain.knowledge.retrieval) actually has
# material from BOTH legs to fuse rather than just re-ranking whichever
# leg happened to return the most rows.
_CANDIDATE_POOL_MULTIPLIER = 4
_MIN_CANDIDATE_POOL = 20
# Keyword terms shorter than this are skipped — matching connective
# words ("va", "bu", "the") in every chunk would make the keyword leg
# contribute noise rather than signal to the fused ranking.
_MIN_KEYWORD_TERM_LENGTH = 3


def _escape_like(term: str) -> str:
    """Same escaping discipline as conversation_service.
    search_messages_in_workspace (FR-CONV-006) — a caller's own literal
    `%`/`_`/`\\` must never be read as a SQL LIKE wildcard."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def ingest_file(
    session: AsyncSession,
    storage: ObjectStoragePort,
    *,
    customer_id: uuid.UUID,
    workspace_id: uuid.UUID,
    uploader_id: str,
    filename: str,
    declared_content_type: str,
    data: bytes,
    max_size_bytes: int,
) -> Document:
    content_type = validate_file(
        filename=filename,
        declared_content_type=declared_content_type,
        data=data,
        max_size_bytes=max_size_bytes,
    )
    document_id = uuid.uuid4()
    storage_key = storage_key_for(customer_id=customer_id, workspace_id=workspace_id, document_id=document_id)
    await storage.put(storage_key, data)

    document = Document(
        id=document_id,
        customer_id=customer_id,
        workspace_id=workspace_id,
        uploader_id=uploader_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_key=storage_key,
    )
    session.add(document)
    await session.flush()
    return document


async def index_document(
    session: AsyncSession,
    embedding_port: EmbeddingPort,
    document: Document,
    *,
    data: bytes,
    chunk_size: int,
    chunk_overlap: int,
) -> int:
    """FR-KNW-002: parses, chunks, embeds and indexes `document`'s own
    content. Returns the number of chunks created — 0 is a valid,
    non-error result for a content type with no extractor yet (see
    doda.domain.knowledge.text_extraction's own docstring), not a
    failure. Deliberately the OPPOSITE failure-mode choice from
    ingest_file's own "storage before DB row" ordering note above: this
    runs in the SAME transaction as the Document insert (the caller is
    responsible for that), so a real extraction/embedding error rolls
    back the whole upload rather than leaving a Document that can never
    be indexed and has no retry path — FR-KNW-008's async retry/progress
    reporting doesn't exist yet to recover from that any other way.
    """
    text = extract_text(content_type=document.content_type, data=data)
    if not text:
        return 0

    chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
    if not chunks:
        return 0

    vectors = await embedding_port.embed([chunk.content for chunk in chunks])
    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        session.add(
            DocumentChunk(
                customer_id=document.customer_id,
                workspace_id=document.workspace_id,
                document_id=document.id,
                chunk_index=index,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                content=chunk.content,
                embedding=vector,
            )
        )
    await session.flush()
    return len(chunks)


async def search_knowledge(
    session: AsyncSession,
    embedding_port: EmbeddingPort,
    *,
    workspace_id: uuid.UUID,
    query: str,
    document_id: uuid.UUID | None = None,
    limit: int = 5,
) -> list[DocumentChunk]:
    """FR-KNW-003: hybrid retrieval. Runs two independent legs scoped to
    `workspace_id` (never relies on RLS alone for the workspace boundary
    — RLS here enforces only `customer_id`, not which workspace within
    it, the same NFR-ISO-002 discipline as every other repository query
    in this codebase) and fuses them with Reciprocal Rank Fusion (doda.
    domain.knowledge.retrieval):

    - keyword leg: a DocumentChunk matches if it contains ANY of the
      query's own significant (>= 3 char) words, ordered by how MANY
      distinct words it matched — the same ILIKE-escaping discipline as
      conversation_service.search_messages_in_workspace (FR-CONV-006),
      split per-word here (rather than one whole-phrase substring match)
      because a knowledge query is rarely phrased as a literal substring
      of the document it should retrieve, the way a chat-history search
      term usually is.
    - vector leg: cosine distance against the query's own embedding
      (same `embedding_port` FR-KNW-002 indexing uses), ordered nearest
      first.

    `document_id` is the "metadata filter" leg of FR-KNW-003's four
    parts (metadata filter + keyword + vector + reranking) — narrows the
    search to one Document's own chunks when given.

    A blank/whitespace-only query returns no results, mirroring FR-CONV-
    006's own choice: the caller almost certainly wants "nothing
    matched" over an unbounded scan nobody asked for.
    """
    stripped = query.strip()
    if not stripped:
        return []

    filters = [DocumentChunk.workspace_id == workspace_id]
    if document_id is not None:
        filters.append(DocumentChunk.document_id == document_id)

    candidate_pool = max(limit * _CANDIDATE_POOL_MULTIPLIER, _MIN_CANDIDATE_POOL)

    keyword_terms = {
        word
        for word in re.findall(r"\w+", stripped, flags=re.UNICODE)
        if len(word) >= _MIN_KEYWORD_TERM_LENGTH
    }
    keyword_ids: list[uuid.UUID] = []
    if keyword_terms:
        like_patterns = [f"%{_escape_like(term)}%" for term in keyword_terms]
        # Ranked by how many DISTINCT query words a chunk matched, not
        # just whether it matched at all — a chunk hitting 3 of the
        # query's words is a stronger keyword candidate than one hitting
        # only 1, and this is the ordering the keyword leg hands to RRF.
        # Built via a fold rather than sum(...) — `like_patterns` is
        # guaranteed non-empty here (the `if keyword_terms:` guard
        # above), but sum()'s own stub still types its result as a union
        # with its int `start=0` default, which loses the `.desc()`
        # method mypy needs below.
        term_match_cases = [
            case((DocumentChunk.content.ilike(pattern, escape="\\"), 1), else_=0) for pattern in like_patterns
        ]
        match_count: ColumnElement[int] = term_match_cases[0]
        for term_match in term_match_cases[1:]:
            match_count = match_count + term_match
        keyword_result = await session.execute(
            select(DocumentChunk.id)
            .where(*filters, or_(*(DocumentChunk.content.ilike(p, escape="\\") for p in like_patterns)))
            .order_by(match_count.desc())
            .limit(candidate_pool)
        )
        keyword_ids = list(keyword_result.scalars().all())

    (query_embedding,) = await embedding_port.embed([stripped])
    vector_result = await session.execute(
        select(DocumentChunk.id)
        .where(*filters)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(candidate_pool)
    )
    vector_ids = list(vector_result.scalars().all())

    fused_ids = reciprocal_rank_fusion([keyword_ids, vector_ids])[:limit]
    if not fused_ids:
        return []

    chunk_result = await session.execute(select(DocumentChunk).where(DocumentChunk.id.in_(fused_ids)))
    chunks_by_id = {chunk.id: chunk for chunk in chunk_result.scalars().all()}
    # Preserve the fused rank order — `IN (...)` gives no ordering
    # guarantee of its own.
    return [chunks_by_id[chunk_id] for chunk_id in fused_ids if chunk_id in chunks_by_id]


async def list_documents_for_workspace(
    session: AsyncSession, *, workspace_id: uuid.UUID, limit: int = 50
) -> list[Document]:
    result = await session.scalars(
        select(Document)
        .where(Document.workspace_id == workspace_id)
        .order_by(Document.created_at.desc())
        .limit(min(limit, MAX_PAGE_SIZE))
    )
    return list(result.all())


async def delete_document(session: AsyncSession, storage: ObjectStoragePort, document: Document) -> None:
    """Deletes the DB row first, then the stored object — the same
    fail-safe direction as ingest_file's own ordering note: a crash
    between the two leaves an orphaned object with no row pointing at
    it, never a row pointing at a file that no longer exists."""
    await session.delete(document)
    await session.flush()
    await storage.delete(document.storage_key)
