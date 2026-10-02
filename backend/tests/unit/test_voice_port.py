"""doda.voice.port/factory scaffolding (OD-004) — mirrors
tests/unit/test_ai_port.py's own proof for doda.ai.port.NullModelGateway:
the Null* implementations never fake a result, and the factory's
"no credential means Null, never a crash" rule holds."""

import pytest

from doda.config import Settings
from doda.voice.factory import get_speech_to_text, get_text_to_speech, is_voice_configured
from doda.voice.port import (
    NullSpeechToText,
    NullTextToSpeech,
    SpeechToTextPort,
    TextToSpeechPort,
    VoiceNotConfiguredError,
)


def test_null_implementations_satisfy_their_protocols() -> None:
    stt: SpeechToTextPort = NullSpeechToText()
    tts: TextToSpeechPort = NullTextToSpeech()
    assert isinstance(stt, SpeechToTextPort)
    assert isinstance(tts, TextToSpeechPort)


async def test_null_speech_to_text_raises_rather_than_fakes_a_transcript() -> None:
    with pytest.raises(VoiceNotConfiguredError):
        await NullSpeechToText().transcribe(audio_bytes=b"not-real-audio", mime_type="audio/wav")


async def test_null_text_to_speech_raises_rather_than_fakes_audio() -> None:
    with pytest.raises(VoiceNotConfiguredError):
        await NullTextToSpeech().synthesize(text="salom", language="uz")


def test_voice_is_not_configured_when_no_credential_is_set() -> None:
    settings = Settings()  # type: ignore[call-arg]
    assert is_voice_configured(settings) is False


def test_factory_returns_the_null_implementations_when_unconfigured() -> None:
    settings = Settings()  # type: ignore[call-arg]
    assert isinstance(get_speech_to_text(settings), NullSpeechToText)
    assert isinstance(get_text_to_speech(settings), NullTextToSpeech)


def test_voice_is_configured_once_a_credential_is_set() -> None:
    settings = Settings(google_cloud_speech_credentials_json="{}")  # type: ignore[call-arg]
    assert is_voice_configured(settings) is True


def test_factory_fails_loudly_rather_than_silently_falling_back_to_null() -> None:
    """A configured-but-unimplemented provider must never silently behave
    as if it were simply absent — the same "never silently swap/degrade
    a deliberate choice" discipline doda.ai.factory's own docstring
    states for model providers."""
    settings = Settings(google_cloud_speech_credentials_json="{}")  # type: ignore[call-arg]
    with pytest.raises(NotImplementedError):
        get_speech_to_text(settings)
    with pytest.raises(NotImplementedError):
        get_text_to_speech(settings)
