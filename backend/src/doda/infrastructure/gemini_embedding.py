"""Real Gemini embedding adapter (FR-KNW-002) — the only module besides
gemini_gateway.py allowed to import google-genai (see tests/unit/
test_side_effect_boundary.py's ALLOWED set). See doda.ai.embedding_port's
module docstring for why Gemini is the only real adapter today.

Batches at most `_MAX_TEXTS_PER_CALL` texts into one `embed_content`
call — Google's own limits/pricing pages are blocked by this
environment's network policy (same situation ADR-009 already documents
for the chat models), so this is a conservative, round-number default
rather than a verified maximum; a document with more chunks than that
makes multiple sequential calls instead of one unbounded one.

`contents` is built as one `genai_types.Content` PER TEXT, each holding
exactly one `Part` — never a bare `list[str]`. This was not a style
choice: verified directly against the real API (2026-10-02) that a bare
`list[str]` is flattened by the SDK's own `t_contents` transformer into
a SINGLE multi-part Content (one Content, many Parts — the shape it uses
for one multi-part chat TURN, not N independent documents), and the real
API then returned FEWER embeddings than texts sent for a real two-chunk
document (1 embedding for 2 chunks of 2000/239 chars — reproduced,
understood, and the reverse (one Content per text) confirmed to return
the correct count with genuinely distinct vectors, not a fluke of short
test strings). `embed`'s own length check below is the second,
independent guard against this exact failure mode recurring — e.g. if a
future google-genai version changes `t_contents`'s behavior again.

Same "never leak the raw request" discipline as gemini_gateway.py: the
API key rides as a query parameter for this provider, so every error
path uses only `exc.code`/`exc.message` or `type(exc).__name__`, never
`str(exc)` or the request/response object itself.
"""

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from doda.ai.errors import ModelProviderError, ModelRateLimitedError, ModelTimeoutError

_MAX_TEXTS_PER_CALL = 100
_TASK_TYPE = "RETRIEVAL_DOCUMENT"


def _translate_error(exc: Exception) -> Exception:
    if isinstance(exc, httpx.TimeoutException):
        return ModelTimeoutError("Gemini did not respond within the configured timeout")
    if isinstance(exc, genai_errors.APIError):
        if exc.code == 429:
            return ModelRateLimitedError(f"Gemini rate-limited this request: {exc.message or ''}".strip())
        return ModelProviderError(
            f"Gemini returned an error: {exc.message or type(exc).__name__}", status_code=exc.code
        )
    return ModelProviderError(f"Gemini embedding request failed: {type(exc).__name__}")


class GeminiEmbeddingPort:
    """Holds one `genai.Client`, constructed once with the configured API
    key — same shape as GeminiGateway (`doda.infrastructure.
    gemini_gateway`)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        # `http_client` is a testability seam only (tests/unit/
        # test_gemini_embedding.py injects an httpx.MockTransport-backed
        # client here) — production construction (doda.ai.embedding_
        # factory) never passes it.
        http_options = (
            genai_types.HttpOptions(httpx_async_client=http_client)
            if http_client is not None
            else genai_types.HttpOptions(timeout=round(timeout_seconds * 1000))
        )
        self._client = genai.Client(api_key=api_key, http_options=http_options)
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _MAX_TEXTS_PER_CALL):
            batch = texts[start : start + _MAX_TEXTS_PER_CALL]
            contents = [
                genai_types.Content(parts=[genai_types.Part(text=text)], role="user") for text in batch
            ]
            try:
                result = await self._client.aio.models.embed_content(
                    model=self._model,
                    contents=contents,
                    config=genai_types.EmbedContentConfig(task_type=_TASK_TYPE),
                )
            except Exception as exc:
                raise _translate_error(exc) from None
            embeddings = result.embeddings or []
            if len(embeddings) != len(batch):
                raise ModelProviderError(
                    f"Gemini returned {len(embeddings)} embeddings for {len(batch)} texts"
                )
            vectors.extend(list(embedding.values or []) for embedding in embeddings)
        return vectors
