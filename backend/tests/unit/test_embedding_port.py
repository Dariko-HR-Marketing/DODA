"""doda.ai.embedding_port/embedding_factory scaffolding — mirrors
tests/unit/test_ai_port.py's own proof for NullModelGateway: the Null
implementation never fakes a result, and the factory's "no credential
means Null, never a crash" rule holds."""

import pytest

from doda.ai.embedding_factory import get_embedding_port, is_embedding_configured
from doda.ai.embedding_port import EmbeddingNotConfiguredError, EmbeddingPort, NullEmbeddingPort
from doda.config import Settings


def test_null_embedding_port_satisfies_the_protocol() -> None:
    port: EmbeddingPort = NullEmbeddingPort()
    assert isinstance(port, EmbeddingPort)


async def test_null_embedding_port_raises_rather_than_fakes_a_vector() -> None:
    with pytest.raises(EmbeddingNotConfiguredError):
        await NullEmbeddingPort().embed(["hello"])


def test_embedding_is_not_configured_when_no_gemini_key_is_set() -> None:
    settings = Settings()  # type: ignore[call-arg]
    assert is_embedding_configured(settings) is False


def test_factory_returns_the_null_port_when_unconfigured() -> None:
    settings = Settings()  # type: ignore[call-arg]
    assert isinstance(get_embedding_port(settings), NullEmbeddingPort)


def test_embedding_is_configured_once_a_gemini_key_is_set() -> None:
    settings = Settings(gemini_api_key="fake-test-key")  # type: ignore[call-arg]
    assert is_embedding_configured(settings) is True


def test_factory_returns_a_real_gemini_adapter_once_configured() -> None:
    from doda.infrastructure.gemini_embedding import GeminiEmbeddingPort

    settings = Settings(gemini_api_key="fake-test-key")  # type: ignore[call-arg]
    port = get_embedding_port(settings)
    assert isinstance(port, GeminiEmbeddingPort)
