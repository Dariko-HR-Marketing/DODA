"""The one seam a real speech provider integration enters through —
mirrors doda.ai.port's shape exactly (Protocol + a Null fallback), so
nothing above this layer ever depends on a provider SDK's own shapes
directly (6.2: the AI/voice layer is where an external-provider
connection is allowed to exist, nowhere else).

OD-004 already decided the provider (Google Cloud Speech-to-Text/TTS),
but no real GCP credential has been provided yet — same waiting state
the Telegram bot token and Google OAuth secret were in before they
arrived. `doda.voice.factory.get_speech_to_text`/`get_text_to_speech`
return the Null* implementations below until
`Settings.google_cloud_speech_credentials_json` is set; a real
`GoogleSpeechAdapter` (doda.infrastructure.google_speech, not written
yet) plugs in at that point without this Protocol or any caller of it
needing to change — the same story `doda.ai.port.ModelGateway` already
proved out across three different providers.

Deliberately no caller exists yet either: no HTTP endpoint, no frontend
UI. TRD's own acceptance criteria for voice describe WHAT must hold
once built (provider chosen, language parity risk flagged in
docs/risk-register.md's RISK-010) but not WHERE in the UI it attaches
or what triggers it — building an endpoint/UI now would be guessing at
that, the same mistake OD-002/004/005's own history warns against. This
module is deliberately just the port: the part that is NOT
speculative, because the provider decision it waits on is already
final.
"""

import typing
from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptionResult:
    """One speech-to-text call's result. `detected_language` is the
    provider's own guess (e.g. "uz-UZ", "ru-RU", "en-US") — distinct
    from, and not fed into, `doda.ai.language.detect_language`'s
    text-based FR-CONV-001 detection; whether/how the two should agree
    is exactly the kind of UI-attachment question this module
    deliberately leaves open (see module docstring)."""

    text: str
    detected_language: str | None


@dataclass(frozen=True)
class SynthesisResult:
    audio_bytes: bytes
    mime_type: str


@typing.runtime_checkable
class SpeechToTextPort(typing.Protocol):
    def transcribe(
        self, *, audio_bytes: bytes, mime_type: str, language_hint: str | None = None
    ) -> typing.Awaitable[TranscriptionResult]: ...


@typing.runtime_checkable
class TextToSpeechPort(typing.Protocol):
    def synthesize(
        self, *, text: str, language: str, voice: str | None = None
    ) -> typing.Awaitable[SynthesisResult]: ...


class VoiceNotConfiguredError(Exception):
    """Raised by the Null* implementations below — mirrors
    doda.ai.errors.ModelNotConfiguredError's "tell the truth, never fake
    a result" discipline. Whoever eventually wires an HTTP endpoint on
    top of this converts it to a 503, the same shape
    AI_PROVIDER_NOT_CONFIGURED already uses in doda.api.errors."""


class NullSpeechToText:
    """Always raises — unlike doda.ai.port.NullModelGateway, which
    degrades gracefully with a reply because chat already has a
    well-defined "no provider" turn to show. No caller exists for voice
    yet (see module docstring), so there is no defined degraded
    behavior to return instead; raising loudly is the honest default
    until one is designed."""

    async def transcribe(
        self, *, audio_bytes: bytes, mime_type: str, language_hint: str | None = None
    ) -> TranscriptionResult:
        del audio_bytes, mime_type, language_hint
        raise VoiceNotConfiguredError(
            "Ovoz-matn (STT) provayderi hali sozlanmagan — OD-004: Google "
            "Cloud Speech-to-Text kredensiali kutilmoqda."
        )


class NullTextToSpeech:
    async def synthesize(self, *, text: str, language: str, voice: str | None = None) -> SynthesisResult:
        del text, language, voice
        raise VoiceNotConfiguredError(
            "Matn-ovoz (TTS) provayderi hali sozlanmagan — OD-004: Google "
            "Cloud Text-to-Speech kredensiali kutilmoqda."
        )
