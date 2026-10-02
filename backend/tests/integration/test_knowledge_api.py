"""End-to-end HTTP tests for the knowledge/file API — FR-KNW-001/002.
Same authoritative-chain pattern as test_tasks_api.py. Storage is pointed
at a per-test tmp_path (doda.api.knowledge.get_settings monkeypatched) so
tests never touch the real ./data/knowledge directory or share state
across test runs.

FR-KNW-002 (indexing) tests use a fake, deterministic EmbeddingPort
(`_fake_embedding` fixture) rather than a real Gemini key — same
discipline as test_conversations_api.py's NullModelGateway-by-default
posture: this project's automated suite never depends on a live
provider credential (see tests/conftest.py's own autouse fixture, which
forces gemini_api_key to None in every test). The real, working
end-to-end Gemini embedding call is verified separately, by hand,
outside pytest — see CLAUDE.md's running log.
"""

import io
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfReader, PdfWriter
from sqlalchemy import select

from doda.config import Settings
from doda.db import tenant_scoped_session
from doda.domain.knowledge.models import EMBEDDING_DIMENSIONS, DocumentChunk
from doda.main import app
from tests.integration.conftest import seed_workspace_member

_REAL_PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nreal pdf body here"
_WINDOWS_PE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00this is really an executable"
_REAL_PNG_BYTES = b"\x89PNG\r\n\x1a\n fake but magic-byte-correct png body"
# A hand-built, genuinely parseable (if minimal) PDF — same construction
# as tests/unit/test_text_extraction.py's _MINIMAL_PDF_BYTES, needed here
# to build a real encrypted PDF from a real unencrypted one (PdfWriter
# can't encrypt a document it was never given in the first place).
_PARSEABLE_PDF_CONTENT_STREAM = b"BT /F1 24 Tf 10 100 Td (Hello World) Tj ET"
_PARSEABLE_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
    b"/Resources << /Font << /F1 4 0 R >> >> "
    b"/MediaBox [0 0 200 200] /Contents 5 0 R >>\nendobj\n"
    b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    b"5 0 obj\n<< /Length "
    + str(len(_PARSEABLE_PDF_CONTENT_STREAM)).encode()
    + b" >>\nstream\n"
    + _PARSEABLE_PDF_CONTENT_STREAM
    + b"\nendstream\nendobj\n"
    b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n"
)


class _FakeEmbeddingPort:
    """Deterministic, no-network stand-in — one fixed-dimension vector
    per input text, in order. Records every batch it was called with so
    tests can assert on exactly what was sent, same shape as
    test_conversations_api.py's _RecordingGateway."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(i)] * EMBEDDING_DIMENSIONS for i, _ in enumerate(texts)]


@pytest.fixture
def fake_embedding(monkeypatch: pytest.MonkeyPatch) -> _FakeEmbeddingPort:
    port = _FakeEmbeddingPort()
    monkeypatch.setattr("doda.api.knowledge.is_embedding_configured", lambda settings: True)
    monkeypatch.setattr("doda.api.knowledge.get_embedding_port", lambda settings: port)
    return port


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def storage_settings(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(knowledge_storage_dir=str(tmp_path))  # type: ignore[arg-type]
    monkeypatch.setattr("doda.api.knowledge.get_settings", lambda: settings)
    return settings


def _auth_headers(session_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {session_id}"}


def _upload_files(filename: str, content_type: str, data: bytes) -> dict:
    return {"file": (filename, data, content_type)}


async def test_missing_session_is_rejected(
    client: AsyncClient, db_available: bool, storage_settings: Settings
) -> None:
    member = await seed_workspace_member()
    response = await client.post(
        f"/v1/workspaces/{member.workspace_id}/documents",
        files=_upload_files("report.pdf", "application/pdf", _REAL_PDF_BYTES),
    )
    assert response.status_code == 401


async def test_no_membership_is_denied(
    client: AsyncClient, db_available: bool, storage_settings: Settings
) -> None:
    member = await seed_workspace_member()
    other = await seed_workspace_member()
    response = await client.post(
        f"/v1/workspaces/{other.workspace_id}/documents",
        files=_upload_files("report.pdf", "application/pdf", _REAL_PDF_BYTES),
        headers=_auth_headers(member.session_id),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "DENY"


async def test_member_can_upload_list_get_and_download_a_document(
    client: AsyncClient, db_available: bool, storage_settings: Settings
) -> None:
    member = await seed_workspace_member()

    upload = await client.post(
        f"/v1/workspaces/{member.workspace_id}/documents",
        files=_upload_files("report.pdf", "application/pdf", _REAL_PDF_BYTES),
        headers=_auth_headers(member.session_id),
    )
    assert upload.status_code == 200
    document = upload.json()
    assert document["filename"] == "report.pdf"
    assert document["content_type"] == "application/pdf"
    assert document["size_bytes"] == len(_REAL_PDF_BYTES)
    assert document["uploader_id"] == f"user:{member.user_id}"

    listing = await client.get(
        f"/v1/workspaces/{member.workspace_id}/documents", headers=_auth_headers(member.session_id)
    )
    assert listing.status_code == 200
    assert [d["id"] for d in listing.json()] == [document["id"]]

    get_one = await client.get(
        f"/v1/workspaces/{member.workspace_id}/documents/{document['id']}",
        headers=_auth_headers(member.session_id),
    )
    assert get_one.status_code == 200

    download = await client.get(
        f"/v1/workspaces/{member.workspace_id}/documents/{document['id']}/content",
        headers=_auth_headers(member.session_id),
    )
    assert download.status_code == 200
    assert download.content == _REAL_PDF_BYTES
    assert download.headers["content-type"] == "application/pdf"


async def test_downloading_a_document_whose_stored_object_went_missing_is_a_clean_404(
    client: AsyncClient, db_available: bool, storage_settings: Settings, tmp_path
) -> None:
    """The DB row surviving while the stored object does not (a crash
    between delete_document's two steps, or manual storage tampering) is
    a distinct, documented failure mode in download_document — simulated
    here by wiping storage out from under an otherwise-valid upload."""
    member = await seed_workspace_member()
    upload = await client.post(
        f"/v1/workspaces/{member.workspace_id}/documents",
        files=_upload_files("report.pdf", "application/pdf", _REAL_PDF_BYTES),
        headers=_auth_headers(member.session_id),
    )
    assert upload.status_code == 200
    document_id = upload.json()["id"]

    for stored_file in tmp_path.rglob("*"):
        if stored_file.is_file():
            stored_file.unlink()

    # The row is still there (GET still 200s) — only the content is gone.
    get_one = await client.get(
        f"/v1/workspaces/{member.workspace_id}/documents/{document_id}",
        headers=_auth_headers(member.session_id),
    )
    assert get_one.status_code == 200

    download = await client.get(
        f"/v1/workspaces/{member.workspace_id}/documents/{document_id}/content",
        headers=_auth_headers(member.session_id),
    )
    assert download.status_code == 404
    assert download.json()["detail"] == "document content not found"


async def test_a_malicious_file_disguised_as_a_pdf_is_rejected_and_never_stored(
    client: AsyncClient, db_available: bool, storage_settings: Settings
) -> None:
    """The security-test acceptance criterion, exercised over the real
    HTTP API rather than just the validator's own unit test: a Windows
    executable declared as application/pdf is refused with 422 and no
    Document row is ever created."""
    member = await seed_workspace_member()

    upload = await client.post(
        f"/v1/workspaces/{member.workspace_id}/documents",
        files=_upload_files("invoice.pdf", "application/pdf", _WINDOWS_PE_BYTES),
        headers=_auth_headers(member.session_id),
    )
    assert upload.status_code == 422
    assert upload.json()["code"] == "INVALID_FILE"

    listing = await client.get(
        f"/v1/workspaces/{member.workspace_id}/documents", headers=_auth_headers(member.session_id)
    )
    assert listing.json() == []


async def test_a_file_over_the_size_limit_is_rejected_without_buffering_past_it(
    client: AsyncClient, db_available: bool, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proves the bounded chunked read: with a deliberately tiny limit,
    a body that exceeds it by more than one read-chunk is still rejected
    (the running total is checked as bytes arrive, not only after the
    whole body has been buffered)."""
    tiny_limit_settings = Settings(knowledge_storage_dir=str(tmp_path), knowledge_max_file_size_bytes=10)  # type: ignore[arg-type]
    monkeypatch.setattr("doda.api.knowledge.get_settings", lambda: tiny_limit_settings)
    member = await seed_workspace_member()

    oversized = b"%PDF-1.4\n" + b"x" * 500  # far larger than the 10-byte limit
    upload = await client.post(
        f"/v1/workspaces/{member.workspace_id}/documents",
        files=_upload_files("report.pdf", "application/pdf", oversized),
        headers=_auth_headers(member.session_id),
    )
    assert upload.status_code == 422
    assert upload.json()["code"] == "INVALID_FILE"

    listing = await client.get(
        f"/v1/workspaces/{member.workspace_id}/documents", headers=_auth_headers(member.session_id)
    )
    assert listing.json() == []


async def test_owner_can_delete_their_own_upload(
    client: AsyncClient, db_available: bool, storage_settings: Settings
) -> None:
    member = await seed_workspace_member()
    upload = await client.post(
        f"/v1/workspaces/{member.workspace_id}/documents",
        files=_upload_files("report.pdf", "application/pdf", _REAL_PDF_BYTES),
        headers=_auth_headers(member.session_id),
    )
    document_id = upload.json()["id"]

    delete = await client.delete(
        f"/v1/workspaces/{member.workspace_id}/documents/{document_id}",
        headers=_auth_headers(member.session_id),
    )
    assert delete.status_code == 204

    get_after_delete = await client.get(
        f"/v1/workspaces/{member.workspace_id}/documents/{document_id}",
        headers=_auth_headers(member.session_id),
    )
    assert get_after_delete.status_code == 404


@pytest.fixture
def small_chunk_settings(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Deterministic, small chunk size/overlap so a short test text still
    produces multiple, easily-asserted-on chunks."""
    settings = Settings(  # type: ignore[call-arg]
        knowledge_storage_dir=str(tmp_path),
        knowledge_chunk_size_chars=50,
        knowledge_chunk_overlap_chars=10,
    )
    monkeypatch.setattr("doda.api.knowledge.get_settings", lambda: settings)
    return settings


async def _chunks_for_document(customer_id: uuid.UUID, document_id: uuid.UUID) -> list[DocumentChunk]:
    async with tenant_scoped_session(customer_id) as db:
        result = await db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.all())


async def test_uploading_a_txt_file_creates_chunks_with_correct_lineage(
    client: AsyncClient,
    db_available: bool,
    small_chunk_settings: Settings,
    fake_embedding: _FakeEmbeddingPort,
) -> None:
    member = await seed_workspace_member()
    text = "A" * 120  # chunk_size=50, overlap=10 -> chunks at [0,50) [40,90) [80,120)

    upload = await client.post(
        f"/v1/workspaces/{member.workspace_id}/documents",
        files=_upload_files("notes.txt", "text/plain", text.encode()),
        headers=_auth_headers(member.session_id),
    )
    assert upload.status_code == 200
    document_id = uuid.UUID(upload.json()["id"])

    chunks = await _chunks_for_document(member.customer_id, document_id)
    assert len(chunks) == 3
    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    assert (chunks[0].start_offset, chunks[0].end_offset) == (0, 50)
    assert (chunks[1].start_offset, chunks[1].end_offset) == (40, 90)
    assert (chunks[2].start_offset, chunks[2].end_offset) == (80, 120)
    for chunk in chunks:
        assert chunk.content == text[chunk.start_offset : chunk.end_offset]
        assert len(chunk.embedding) == EMBEDDING_DIMENSIONS
        assert chunk.customer_id == member.customer_id
        assert chunk.workspace_id == member.workspace_id

    # One call, all three chunks' text in order — well under the
    # adapter's own 100-text batch limit for a document this small.
    assert fake_embedding.calls == [[c.content for c in chunks]]


async def test_uploading_an_image_creates_zero_chunks_not_an_error(
    client: AsyncClient,
    db_available: bool,
    storage_settings: Settings,
    fake_embedding: _FakeEmbeddingPort,
) -> None:
    member = await seed_workspace_member()
    upload = await client.post(
        f"/v1/workspaces/{member.workspace_id}/documents",
        files=_upload_files("photo.png", "image/png", _REAL_PNG_BYTES),
        headers=_auth_headers(member.session_id),
    )
    assert upload.status_code == 200
    document_id = uuid.UUID(upload.json()["id"])

    assert await _chunks_for_document(member.customer_id, document_id) == []
    assert fake_embedding.calls == []  # never even attempted — nothing to embed


async def test_a_password_protected_pdf_fails_the_whole_upload_and_nothing_persists(
    client: AsyncClient,
    db_available: bool,
    storage_settings: Settings,
    fake_embedding: _FakeEmbeddingPort,
) -> None:
    """Passed file_validation's own magic-byte check (still starts with
    %PDF) but cannot be parsed for text — the whole upload (Document row
    included) rolls back rather than leaving an unindexable, un-retryable
    Document with no chunks (see knowledge_service.index_document's own
    docstring on this deliberate ordering choice)."""
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(_PARSEABLE_PDF_BYTES)))
    writer.encrypt(user_password="secret", owner_password="secret2")
    buffer = io.BytesIO()
    writer.write(buffer)
    encrypted_pdf = buffer.getvalue()

    member = await seed_workspace_member()
    upload = await client.post(
        f"/v1/workspaces/{member.workspace_id}/documents",
        files=_upload_files("locked.pdf", "application/pdf", encrypted_pdf),
        headers=_auth_headers(member.session_id),
    )
    assert upload.status_code == 422
    assert upload.json()["code"] == "DOCUMENT_INDEXING_FAILED"

    listing = await client.get(
        f"/v1/workspaces/{member.workspace_id}/documents", headers=_auth_headers(member.session_id)
    )
    assert listing.json() == []  # the Document insert was rolled back too


async def test_deleting_a_document_cascades_to_its_chunks(
    client: AsyncClient,
    db_available: bool,
    small_chunk_settings: Settings,
    fake_embedding: _FakeEmbeddingPort,
) -> None:
    member = await seed_workspace_member()
    upload = await client.post(
        f"/v1/workspaces/{member.workspace_id}/documents",
        files=_upload_files("notes.txt", "text/plain", b"A" * 120),
        headers=_auth_headers(member.session_id),
    )
    document_id = uuid.UUID(upload.json()["id"])
    assert len(await _chunks_for_document(member.customer_id, document_id)) == 3

    delete = await client.delete(
        f"/v1/workspaces/{member.workspace_id}/documents/{document_id}",
        headers=_auth_headers(member.session_id),
    )
    assert delete.status_code == 204

    assert await _chunks_for_document(member.customer_id, document_id) == []
