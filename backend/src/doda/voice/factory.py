"""Picks which SpeechToTextPort/TextToSpeechPort implementation backs
voice — mirrors doda.ai.factory.get_gateway exactly: no credential
configured means the Null* implementation, never a crash.

No real adapter exists yet (see doda.voice.port's module docstring for
why) — `is_voice_configured` can only ever be False today. The
NotImplementedError branches below exist so that if someone sets
`DODA_GOOGLE_CLOUD_SPEECH_CREDENTIALS_JSON` before a real
doda.infrastructure.google_speech adapter is written, that is a loud,
immediate failure at the call site rather than a silent fallback to
Null — the same "fail loudly on an unimplemented-but-configured path"
choice this project has made before (see doda.ai.factory's own
docstring on never silently swapping providers).
"""

from doda.config import Settings, get_settings
from doda.voice.port import NullSpeechToText, NullTextToSpeech, SpeechToTextPort, TextToSpeechPort

_NULL_STT = NullSpeechToText()
_NULL_TTS = NullTextToSpeech()


def is_voice_configured(settings: Settings | None = None) -> bool:
    """Whether a real GCP credential exists — distinct from whether a
    real adapter has been written to use it (see module docstring)."""
    settings = settings or get_settings()
    return settings.google_cloud_speech_credentials_json is not None


def get_speech_to_text(settings: Settings | None = None) -> SpeechToTextPort:
    settings = settings or get_settings()
    if not is_voice_configured(settings):
        return _NULL_STT
    raise NotImplementedError(
        "GCP Speech-to-Text kredensiali sozlangan, lekin haqiqiy adapter "
        "(doda.infrastructure.google_speech) hali yozilmagan."
    )


def get_text_to_speech(settings: Settings | None = None) -> TextToSpeechPort:
    settings = settings or get_settings()
    if not is_voice_configured(settings):
        return _NULL_TTS
    raise NotImplementedError(
        "GCP Text-to-Speech kredensiali sozlangan, lekin haqiqiy adapter "
        "(doda.infrastructure.google_speech) hali yozilmagan."
    )
