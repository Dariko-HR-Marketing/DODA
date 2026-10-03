"""Knowledge/file endpoints — FR-KNW-001/002. Same authoritative-chain
pattern as api/tasks.py: every handler gets its tenant/authz context only
from RequestContext, never from client-supplied customer_id/actor_id.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import Response

from doda.ai.embedding_factory import get_embedding_port, is_embedding_configured
from doda.ai.embedding_port import EmbeddingNotConfiguredError
from doda.api.dependencies import RequestContext, get_request_context
from doda.api.knowledge_schemas import DocumentChunkOut, DocumentOut
from doda.application.authz_service import authorize_use_knowledge
from doda.application.knowledge_service import (
    create_document_version,
    delete_document,
    index_document,
    ingest_file,
    list_documents_for_workspace,
    search_knowledge,
)
from doda.config import get_settings
from doda.domain.knowledge.file_validation import FileTooLargeError
from doda.domain.knowledge.models import Document
from doda.storage.factory import get_object_storage
from doda.storage.port import ObjectNotFoundError

router = APIRouter(tags=["knowledge"])

_READ_CHUNK_BYTES = 1024 * 1024  # 1 MiB


async def _read_bounded(file: UploadFile, max_size_bytes: int) -> bytes:
    """`UploadFile.read()` with no size argument buffers the ENTIRE body
    into memory before `validate_file`'s own size check ever runs — a
    client can force the server to hold an arbitrarily large body just
    to reject it. Reading in bounded chunks and failing as soon as the
    running total crosses the limit means the server never buffers more
    than `max_size_bytes + 1` bytes, no matter how large the client's
    declared or actual body is. `validate_file`'s own `len(data) >
    max_size_bytes` check is kept as-is (it's exercised directly by unit
    tests that pass raw bytes, not an UploadFile) — this only changes
    how those bytes are accumulated before reaching it."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size_bytes:
            raise FileTooLargeError(f"file exceeds the {max_size_bytes}-byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _to_document_out(document: Document) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        workspace_id=document.workspace_id,
        uploader_id=document.uploader_id,
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        sha256=document.sha256,
        created_at=document.created_at,
        superseded_by_id=document.superseded_by_id,
    )


async def _get_owned_document(ctx: RequestContext, document_id: uuid.UUID) -> Document:
    document = await ctx.db.get(Document, document_id)
    if document is None or document.workspace_id != ctx.workspace.workspace_id:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@router.post("/v1/workspaces/{workspace_id}/documents", response_model=DocumentOut)
async def upload_document(
    file: UploadFile, ctx: RequestContext = Depends(get_request_context)
) -> DocumentOut:
    authorize_use_knowledge(ctx.workspace)
    settings = get_settings()
    data = await _read_bounded(file, settings.knowledge_max_file_size_bytes)
    document = await ingest_file(
        ctx.db,
        get_object_storage(settings),
        customer_id=ctx.workspace.customer_id,
        workspace_id=ctx.workspace.workspace_id,
        uploader_id=f"user:{ctx.workspace.user_id}",
        filename=file.filename or "",
        declared_content_type=file.content_type or "",
        data=data,
        max_size_bytes=settings.knowledge_max_file_size_bytes,
    )
    # Same "not indexed yet is not a failure" posture as an unsupported
    # content type (see index_document's own docstring) — no embedding
    # credential configured means uploads keep working exactly as they
    # did before FR-KNW-002 existed, just without any DocumentChunk rows,
    # rather than NullEmbeddingPort's EmbeddingNotConfiguredError turning
    # every upload into a failure the moment no key is present.
    if is_embedding_configured(settings):
        await index_document(
            ctx.db,
            get_embedding_port(settings),
            document,
            data=data,
            chunk_size=settings.knowledge_chunk_size_chars,
            chunk_overlap=settings.knowledge_chunk_overlap_chars,
        )
    return _to_document_out(document)


@router.get("/v1/workspaces/{workspace_id}/documents", response_model=list[DocumentOut])
async def list_workspace_documents(
    limit: int = Query(default=50, le=200), ctx: RequestContext = Depends(get_request_context)
) -> list[DocumentOut]:
    documents = await list_documents_for_workspace(
        ctx.db, workspace_id=ctx.workspace.workspace_id, limit=limit
    )
    return [_to_document_out(document) for document in documents]


@router.get("/v1/workspaces/{workspace_id}/documents/search", response_model=list[DocumentChunkOut])
async def search_workspace_documents(
    q: str = Query(default=""),
    document_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=5, le=20),
    ctx: RequestContext = Depends(get_request_context),
) -> list[DocumentChunkOut]:
    """FR-KNW-003. Registered BEFORE the `{document_id}` route below —
    Starlette matches routes in registration order, not by specificity
    (the same lesson FR-TASK-002's `/plan` route already taught this
    codebase), so this must come first or "search" would be parsed as
    an (invalid) document_id and 422 instead of running."""
    settings = get_settings()
    if not is_embedding_configured(settings):
        raise EmbeddingNotConfiguredError(
            "Hech qanday embedding provayderi sozlanmagan (hozircha faqat Gemini qo'llab-quvvatlanadi)."
        )
    chunks = await search_knowledge(
        ctx.db,
        get_embedding_port(settings),
        workspace_id=ctx.workspace.workspace_id,
        query=q,
        document_id=document_id,
        limit=limit,
    )
    return [
        DocumentChunkOut(id=chunk.id, document_id=chunk.document_id, content=chunk.content)
        for chunk in chunks
    ]


@router.get("/v1/workspaces/{workspace_id}/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID, ctx: RequestContext = Depends(get_request_context)
) -> DocumentOut:
    document = await _get_owned_document(ctx, document_id)
    return _to_document_out(document)


@router.get("/v1/workspaces/{workspace_id}/documents/{document_id}/content")
async def download_document(
    document_id: uuid.UUID, ctx: RequestContext = Depends(get_request_context)
) -> Response:
    document = await _get_owned_document(ctx, document_id)
    storage = get_object_storage(get_settings())
    try:
        data = await storage.get(document.storage_key)
    except ObjectNotFoundError:
        # The DB row survived but the object did not (e.g. a crash
        # between delete_document's two steps, or manual storage
        # tampering) — a distinct, honest 404 rather than a 500, but
        # deliberately not the ingest_file/delete_document error type
        # (there is no caller input to validate here).
        raise HTTPException(status_code=404, detail="document content not found") from None
    return Response(content=data, media_type=document.content_type)


@router.delete("/v1/workspaces/{workspace_id}/documents/{document_id}", status_code=204)
async def delete_workspace_document(
    document_id: uuid.UUID, ctx: RequestContext = Depends(get_request_context)
) -> None:
    authorize_use_knowledge(ctx.workspace)
    document = await _get_owned_document(ctx, document_id)
    await delete_document(ctx.db, get_object_storage(get_settings()), document)


@router.post("/v1/workspaces/{workspace_id}/documents/{document_id}/versions", response_model=DocumentOut)
async def upload_document_version(
    document_id: uuid.UUID,
    file: UploadFile,
    ctx: RequestContext = Depends(get_request_context),
) -> DocumentOut:
    """FR-KNW-009: `document_id` must be the CURRENT version of its own
    chain (DocumentAlreadySupersededError -> 409 otherwise, see
    create_document_version's own docstring). Same validation/storage/
    indexing path as upload_document above — a new version is not
    treated specially by file_validation or index_document, only by
    which Document row previous_document.superseded_by_id ends up
    pointing at."""
    authorize_use_knowledge(ctx.workspace)
    previous_document = await _get_owned_document(ctx, document_id)
    settings = get_settings()
    data = await _read_bounded(file, settings.knowledge_max_file_size_bytes)
    new_document = await create_document_version(
        ctx.db,
        get_object_storage(settings),
        previous_document,
        uploader_id=f"user:{ctx.workspace.user_id}",
        filename=file.filename or "",
        declared_content_type=file.content_type or "",
        data=data,
        max_size_bytes=settings.knowledge_max_file_size_bytes,
    )
    if is_embedding_configured(settings):
        await index_document(
            ctx.db,
            get_embedding_port(settings),
            new_document,
            data=data,
            chunk_size=settings.knowledge_chunk_size_chars,
            chunk_overlap=settings.knowledge_chunk_overlap_chars,
        )
    return _to_document_out(new_document)
