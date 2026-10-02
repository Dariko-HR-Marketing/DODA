"""Picks which EmbeddingPort implementation backs FR-KNW-002 — mirrors
doda.ai.factory.get_gateway exactly: no credential configured means
NullEmbeddingPort, never a crash. See doda.ai.embedding_port's module
docstring for why Gemini is the only real adapter today.
"""

from functools import lru_cache

from doda.ai.embedding_port import EmbeddingPort, NullEmbeddingPort
from doda.config import Settings, get_settings

_NULL = NullEmbeddingPort()


@lru_cache
def _gemini_embedding_port(api_key: str, model: str, timeout_seconds: float) -> EmbeddingPort:
    from doda.infrastructure.gemini_embedding import GeminiEmbeddingPort

    return GeminiEmbeddingPort(api_key=api_key, model=model, timeout_seconds=timeout_seconds)


def is_embedding_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.gemini_api_key is not None


def get_embedding_port(settings: Settings | None = None) -> EmbeddingPort:
    settings = settings or get_settings()
    if not is_embedding_configured(settings):
        return _NULL
    assert settings.gemini_api_key is not None  # narrowed by is_embedding_configured above
    return _gemini_embedding_port(
        settings.gemini_api_key.get_secret_value(),
        settings.ai_embedding_model_gemini,
        settings.ai_request_timeout_seconds,
    )
