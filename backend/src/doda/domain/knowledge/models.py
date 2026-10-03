"""Knowledge domain — FR-KNW. FR-KNW-001: a validated file has been
accepted and stored (doda.storage.port.ObjectStoragePort). FR-KNW-002:
DocumentChunk below — each chunk of a Document's extracted text, with
its own embedding vector and source lineage (start/end character
offset within the document). FR-KNW-003: hybrid retrieval (application.
knowledge_service.search_knowledge).

A Document row never represents a rejected upload: validation (doda.
domain.knowledge.file_validation) runs and can raise BEFORE any Document
is constructed, so this table only ever holds files that passed it. A
Document can have zero DocumentChunk rows — either its content type has
no text extractor yet (images; see doda.domain.knowledge.
text_extraction) or extraction found no text — neither is an error.

FR-KNW-009: `superseded_by_id` is how versioning is modeled — NOT a
separate `version`/`version_id` integer or a shared "lineage" row.
`application.knowledge_service.create_document_version` creates a brand
new Document row (its own fresh id, chunks, embeddings) and points the
PREVIOUS document's `superseded_by_id` at it; "current version" is
simply `superseded_by_id IS NULL`. A superseded Document is never
deleted or stripped of its chunks — it stays fully downloadable (FR-
KNW-005's deletion semantics are untouched and orthogonal) — only
`search_knowledge` excludes its chunks from retrieval, which is the
entirety of what FR-KNW-009's own acceptance criterion ("superseded
version is not used as a source in the answer") asks for.
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from doda.domain.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

# gemini-embedding-2's own output dimensionality (Settings.
# ai_embedding_model_gemini), verified against the real API 2026-10-02.
# A schema-level constant, not a Settings field: changing the embedding
# model to one with a different dimension requires a migration to widen
# this column anyway, so it is not something an operator can tune via
# an env var without a code change regardless.
EMBEDDING_DIMENSIONS = 3072


class Document(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "knowledge_documents"

    customer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    uploader_id: Mapped[str] = mapped_column(String(256))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int]
    # sha256 of the file's own bytes — an integrity checksum, not a
    # dedup key (two different uploads of the same content are allowed
    # to become two different Document rows; TRD does not ask for
    # dedup and inventing that behavior would be a change request,
    # QOIDA 2).
    sha256: Mapped[str] = mapped_column(String(64))
    # doda.domain.knowledge.file_validation.storage_key_for's output —
    # never derived from the caller-supplied filename.
    storage_key: Mapped[str] = mapped_column(String(256))
    # FR-KNW-009: NULL means "this is the current version". See module
    # docstring for the full versioning model.
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="SET NULL"), index=True
    )


class DocumentChunk(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "knowledge_document_chunks"

    customer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    # Position among this document's own chunks, in extraction order —
    # distinct from start_offset/end_offset (character positions in the
    # source text), useful for reconstructing reading order without
    # re-sorting by offset.
    chunk_index: Mapped[int]
    start_offset: Mapped[int]
    end_offset: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
