"""The seam a real embedding-provider integration enters through —
mirrors doda.ai.port.ModelGateway's own "Protocol + Null fallback"
shape, so FR-KNW-002's chunking/indexing pipeline never depends on a
provider SDK's shapes directly.

Unlike chat (ADR-008/009: all three providers implement ModelGateway),
embeddings are NOT symmetric across providers: Anthropic's API has no
embedding endpoint at all, and this environment's own network policy
still blocks api.openai.com (see CLAUDE.md's running log). `doda.
infrastructure.gemini_embedding.GeminiEmbeddingPort` is the one real
adapter for v1 — a deliberate, documented scope narrowing, not a
universal "pick whichever provider is configured" abstraction built
ahead of providers that either can't serve this capability at all or
haven't been proven reachable for it.
"""

import typing


@typing.runtime_checkable
class EmbeddingPort(typing.Protocol):
    def embed(self, texts: list[str]) -> typing.Awaitable[list[list[float]]]: ...


class EmbeddingNotConfiguredError(Exception):
    """Mirrors doda.ai.errors.ModelNotConfiguredError's "tell the truth,
    never fake a result" discipline."""


class NullEmbeddingPort:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise EmbeddingNotConfiguredError(
            "Hech qanday embedding provayderi sozlanmagan (hozircha faqat Gemini qo'llab-quvvatlanadi)."
        )
