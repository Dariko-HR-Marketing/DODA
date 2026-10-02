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
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doda.ai.embedding_port import EmbeddingPort
from doda.domain.knowledge.chunking import chunk_text
from doda.domain.knowledge.file_validation import storage_key_for, validate_file
from doda.domain.knowledge.models import Document, DocumentChunk
from doda.domain.knowledge.text_extraction import extract_text
from doda.storage.port import ObjectStoragePort

MAX_PAGE_SIZE = 200


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
