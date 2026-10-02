"""`doda.infrastructure.gemini_gateway` against a real `google.genai.
Client` whose async HTTP transport is replaced with an `httpx.
MockTransport` (google-genai still uses plain `httpx`, unlike openai/
anthropic's `httpx2` — see the adapter's own module docstring) — the
SDK's own SSE decoding and response parsing run for real; only the
network call itself is faked. No real Gemini API key or network access
is used or required (ai.google.dev is blocked by this environment's
network policy — see ADR-009). Explicitly a MOCK test — see
tests/integration/test_conversations_api.py and the eval harness for
what exercises a real key, when one is present.
"""

import base64
import json

import httpx
import pytest

from doda.ai.errors import ModelProviderError, ModelRateLimitedError, ModelTimeoutError
from doda.ai.types import (
    ChatMode,
    ChatRole,
    ChatTurn,
    Completed,
    TextDelta,
    ToolCallReady,
    ToolCallRequest,
    ToolSpec,
)
from doda.infrastructure.gemini_gateway import GeminiGateway

FAKE_API_KEY = "AIzaSuperSecretTestKeyMustNeverLeak"


def _sse_body(chunks: list[dict]) -> bytes:
    return "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks).encode()


def _gateway(handler) -> GeminiGateway:
    return GeminiGateway(
        api_key=FAKE_API_KEY,
        timeout_seconds=5.0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


async def _collect(gateway: GeminiGateway, **kwargs):
    kwargs.setdefault("model", "gemini-3.1-flash-lite")
    kwargs.setdefault("mode", ChatMode.STANDARD)
    kwargs.setdefault("instructions", "")
    kwargs.setdefault("history", [ChatTurn(role=ChatRole.USER, content="salom")])
    kwargs.setdefault("tools", [])
    kwargs.setdefault("max_output_tokens", 256)
    events = []
    async for event in gateway.stream_chat(**kwargs):
        events.append(event)
    return events


async def test_text_streaming_and_completion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert FAKE_API_KEY not in str(
            request.url
        )  # key must be in the header, not the URL/query on the wire mock
        body = _sse_body(
            [
                {"candidates": [{"content": {"role": "model", "parts": [{"text": "Salom"}]}, "index": 0}]},
                {
                    "candidates": [
                        {
                            "content": {"role": "model", "parts": [{"text": ", DODA!"}]},
                            "finishReason": "STOP",
                            "index": 0,
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 10,
                        "candidatesTokenCount": 5,
                        "totalTokenCount": 15,
                        "cachedContentTokenCount": 0,
                    },
                },
            ]
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    gateway = _gateway(handler)
    events = await _collect(gateway)

    text = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert text == "Salom, DODA!"
    completed = [e for e in events if isinstance(e, Completed)]
    assert len(completed) == 1
    assert completed[0].finish_reason == "stop"
    assert completed[0].usage.input_tokens == 10
    assert completed[0].usage.output_tokens == 5


async def test_tool_call_is_surfaced_with_full_arguments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = _sse_body(
            [
                {
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [
                                    {
                                        "functionCall": {
                                            "id": "call_1",
                                            "name": "list_my_open_tasks",
                                            "args": {"limit": 5},
                                        }
                                    }
                                ],
                            },
                            "finishReason": "STOP",
                            "index": 0,
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 20,
                        "candidatesTokenCount": 8,
                        "totalTokenCount": 28,
                        "cachedContentTokenCount": 0,
                    },
                }
            ]
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    gateway = _gateway(handler)
    events = await _collect(
        gateway, tools=[ToolSpec(name="list_my_open_tasks", description="...", parameters_schema={})]
    )

    calls = [e for e in events if isinstance(e, ToolCallReady)]
    assert len(calls) == 1
    assert calls[0].call.call_id == "call_1"
    assert calls[0].call.name == "list_my_open_tasks"
    assert json.loads(calls[0].call.arguments_json) == {"limit": 5}
    completed = [e for e in events if isinstance(e, Completed)]
    assert completed[0].finish_reason == "tool_calls"


async def test_a_tool_calls_thought_signature_is_captured_in_provider_metadata() -> None:
    """Verified against the real API (2026-10-02): Gemini attaches a
    `thoughtSignature` to every function-call Part this model emits —
    `.function_calls` (the SDK's own convenience property) silently
    drops it, since it lives on the Part, not on FunctionCall itself.
    This pins that the gateway reads it from the right place."""
    signature_b64 = base64.b64encode(b"opaque-signature-bytes").decode()

    def handler(request: httpx.Request) -> httpx.Response:
        body = _sse_body(
            [
                {
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [
                                    {
                                        "functionCall": {
                                            "id": "call_1",
                                            "name": "knowledge_search",
                                            "args": {},
                                        },
                                        "thoughtSignature": signature_b64,
                                    }
                                ],
                            },
                            "finishReason": "STOP",
                            "index": 0,
                        }
                    ]
                }
            ]
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    gateway = _gateway(handler)
    events = await _collect(
        gateway, tools=[ToolSpec(name="knowledge_search", description="...", parameters_schema={})]
    )

    calls = [e for e in events if isinstance(e, ToolCallReady)]
    assert len(calls) == 1
    assert calls[0].call.provider_metadata == {"thought_signature": b"opaque-signature-bytes"}


async def test_a_captured_thought_signature_is_echoed_back_on_replay() -> None:
    """The other half of the round-trip: a history turn carrying
    `provider_metadata` from a prior round must have its thought_
    signature reattached to the function-call Part on the NEXT request —
    real API confirmed (2026-10-02) that omitting it here gets the whole
    request rejected (400 INVALID_ARGUMENT), not just degraded quality."""
    captured_bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_bodies.append(request.content)
        body = _sse_body(
            [
                {
                    "candidates": [
                        {"content": {"role": "model", "parts": [{"text": "ok"}]}, "finishReason": "STOP"}
                    ]
                }
            ]
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    gateway = _gateway(handler)
    history = [
        ChatTurn(role=ChatRole.USER, content="salom"),
        ChatTurn(
            role=ChatRole.ASSISTANT,
            content="",
            tool_calls=[
                ToolCallRequest(
                    call_id="call_1",
                    name="knowledge_search",
                    arguments_json="{}",
                    provider_metadata={"thought_signature": b"opaque-signature-bytes"},
                )
            ],
        ),
        ChatTurn(role=ChatRole.TOOL, content="No matching documents found.", tool_call_id="call_1"),
    ]
    await _collect(gateway, history=history)

    assert len(captured_bodies) == 1
    sent = json.loads(captured_bodies[0])
    model_turn = next(c for c in sent["contents"] if c["role"] == "model")
    assert model_turn["parts"][0]["thoughtSignature"] == base64.b64encode(b"opaque-signature-bytes").decode()


async def test_rate_limit_error_is_translated_without_leaking_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"content-type": "application/json"},
            json={"error": {"code": 429, "message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}},
        )

    gateway = _gateway(handler)
    with pytest.raises(ModelRateLimitedError) as exc_info:
        await _collect(gateway)

    assert FAKE_API_KEY not in str(exc_info.value)


async def test_timeout_is_translated_to_model_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout")

    gateway = _gateway(handler)
    with pytest.raises(ModelTimeoutError):
        await _collect(gateway)


async def test_server_error_is_translated_without_leaking_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            headers={"content-type": "application/json"},
            json={"error": {"code": 503, "message": "The model is overloaded", "status": "UNAVAILABLE"}},
        )

    gateway = _gateway(handler)
    with pytest.raises(ModelProviderError) as exc_info:
        await _collect(gateway)

    assert FAKE_API_KEY not in str(exc_info.value)
