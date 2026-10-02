import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    uploader_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class DocumentChunkOut(BaseModel):
    """FR-KNW-003's own search result shape — deliberately NOT
    DocumentOut: a search hit is a snippet of ONE document's content
    (content + its own document_id for linking back), not the document's
    metadata."""

    id: uuid.UUID
    document_id: uuid.UUID
    content: str
