"""`doda.infrastructure.gemini_embedding` against a real `google.genai.
Client` whose async HTTP transport is replaced with an `httpx.
MockTransport` — same technique and same reason as tests/unit/
test_gemini_gateway.py: the SDK's own request/response parsing runs for
real, only the network call itself is faked. No real Gemini API key or
network access is used or required here — see CLAUDE.md for the one-off,
real-key verification this mirrors.
"""

import json

import httpx
import pytest

from doda.ai.errors import ModelProviderError, ModelRateLimitedError, ModelTimeoutError
from doda.infrastructure.gemini_embedding import GeminiEmbeddingPort

FAKE_API_KEY = "AIzaSuperSecretTestKeyMustNeverLeak"


def _port(handler) -> GeminiEmbeddingPort:
    return GeminiEmbeddingPort(
        api_key=FAKE_API_KEY,
        model="gemini-embedding-2",
        timeout_seconds=5.0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _embeddings_response(vectors: list[list[float]]) -> httpx.Response:
    body = {"embeddings": [{"values": vector} for vector in vectors]}
    return httpx.Response(200, json=body)


async def test_embedding_vectors_are_returned_in_request_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert FAKE_API_KEY not in str(request.url)  # key must be in the header, not the URL
        return _embeddings_response([[0.1, 0.2], [0.3, 0.4]])

    port = _port(handler)
    vectors = await port.embed(["birinchi", "ikkinchi"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


async def test_more_texts_than_the_batch_limit_are_sent_as_multiple_calls() -> None:
    # One `requests[]` entry per text (confirmed via a real MockTransport
    # capture against the adapter's own Content-per-text construction,
    # not assumed) — see the adapter's own module docstring for why a
    # bare list[str] is NOT used here (it collapses into one multi-part
    # Content and the real API then returns too few embeddings).
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        count = len(body["requests"])
        calls.append(count)
        return _embeddings_response([[0.0] for _ in range(count)])

    port = _port(handler)
    texts = [f"chunk {i}" for i in range(150)]
    vectors = await port.embed(texts)

    assert len(vectors) == 150
    assert calls == [100, 50]  # _MAX_TEXTS_PER_CALL=100, then the remainder


async def test_a_rate_limit_response_raises_model_rate_limited_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"code": 429, "message": "quota exceeded"}})

    with pytest.raises(ModelRateLimitedError):
        await _port(handler).embed(["hello"])


async def test_a_server_error_raises_model_provider_error_without_leaking_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"code": 500, "message": "internal error"}})

    with pytest.raises(ModelProviderError) as exc_info:
        await _port(handler).embed(["hello"])
    assert FAKE_API_KEY not in str(exc_info.value)


async def test_fewer_embeddings_than_texts_raises_rather_than_silently_misaligning() -> None:
    """Reproduces, against this exact adapter, a real bug found while
    verifying FR-KNW-002 end to end against the live API: a bare
    list[str] passed as `contents=` collapses into one multi-part
    Content, and Gemini can return fewer embeddings than parts sent —
    silently misaligning every subsequent (chunk, vector) pairing
    downstream (doda.application.knowledge_service.index_document zips
    them together). The adapter's own Content-per-text construction
    (see module docstring) fixes the common case; this length check is
    the second, independent guard."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _embeddings_response([[0.1, 0.2]])  # one vector for two texts

    with pytest.raises(ModelProviderError, match="2 texts"):
        await _port(handler).embed(["chunk one", "chunk two"])


async def test_a_timeout_raises_model_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(ModelTimeoutError):
        await _port(handler).embed(["hello"])
