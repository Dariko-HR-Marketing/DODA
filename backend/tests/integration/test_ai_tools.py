"""Integration tests for `doda.application.ai_tools` — the one place a
model's tool call either executes immediately (READ) or proposes an
Action through the existing approval chain (WRITE), never the other way
around, and never skipping argument validation. Uses a real Postgres
session, since `dispatch_read_tool`/`propose_write_tool_action` both go
through application services that query/write real tables.
"""

import json
import uuid

import pytest

from doda.application.ai_tools import (
    ToolArgumentsInvalidError,
    ToolNotFoundError,
    dispatch_read_tool,
    is_read_tool,
    is_write_tool,
    propose_write_tool_action,
)
from doda.application.authz_service import WorkspaceContext
from doda.application.task_service import create_task
from doda.config import Settings
from doda.db import tenant_scoped_session
from doda.domain.action.models import ActionStatus
from doda.domain.identity.models import ActorKind
from doda.domain.knowledge.models import EMBEDDING_DIMENSIONS, Document, DocumentChunk
from doda.domain.security.roles import WorkspaceRole
from tests.integration.conftest import seed_workspace_member


def _test_settings() -> Settings:
    """NOT a module-level singleton — tests/conftest.py's own autouse
    fixture patches Settings.__init__ per-test (so AI provider keys are
    always None regardless of what this sandbox's real .env holds), and
    that patch only takes effect once a test is actually running.
    Constructing a single Settings() at import time would capture
    whatever real key happens to be in .env at collection time instead —
    exactly the bug the autouse fixture's own docstring describes, which
    this function avoids by constructing fresh every call."""
    return Settings()  # type: ignore[call-arg]


def test_tool_categories_are_mutually_exclusive_and_exhaustive_for_the_known_tools() -> None:
    assert is_read_tool("list_my_open_tasks")
    assert not is_write_tool("list_my_open_tasks")
    assert is_write_tool("telegram_send_message")
    assert not is_read_tool("telegram_send_message")
    assert is_read_tool("knowledge_search")
    assert not is_write_tool("knowledge_search")
    assert not is_read_tool("something_nobody_registered")
    assert not is_write_tool("something_nobody_registered")


async def test_dispatching_a_read_tool_with_no_open_tasks_says_so_plainly(db_available: bool) -> None:
    member = await seed_workspace_member()
    async with tenant_scoped_session(member.customer_id) as db:
        result = await dispatch_read_tool(
            db,
            tool_name="list_my_open_tasks",
            arguments_json="{}",
            workspace_id=member.workspace_id,
            settings=_test_settings(),
        )
    assert result == "No open tasks."


async def test_dispatching_a_read_tool_lists_real_open_tasks_from_this_workspace_only(
    db_available: bool,
) -> None:
    member = await seed_workspace_member()
    other = await seed_workspace_member()
    async with tenant_scoped_session(member.customer_id) as db:
        await create_task(
            db,
            customer_id=member.customer_id,
            workspace_id=member.workspace_id,
            owner_id=f"user:{member.user_id}",
            title="Hisobotni tayyorlash",
        )
        await db.commit()

    async with tenant_scoped_session(member.customer_id) as db:
        result = await dispatch_read_tool(
            db,
            tool_name="list_my_open_tasks",
            arguments_json="{}",
            workspace_id=member.workspace_id,
            settings=_test_settings(),
        )
    assert "Hisobotni tayyorlash" in result

    # The other seeded workspace (different customer) must never see it —
    # same FR-CONV-003/NFR-ISO-002 isolation the rest of this codebase
    # enforces everywhere else.
    async with tenant_scoped_session(other.customer_id) as db:
        other_result = await dispatch_read_tool(
            db,
            tool_name="list_my_open_tasks",
            arguments_json="{}",
            workspace_id=other.workspace_id,
            settings=_test_settings(),
        )
    assert "Hisobotni tayyorlash" not in other_result


async def test_dispatching_a_read_tool_with_invalid_arguments_raises_a_typed_error_not_a_crash(
    db_available: bool,
) -> None:
    member = await seed_workspace_member()
    async with tenant_scoped_session(member.customer_id) as db:
        with pytest.raises(ToolArgumentsInvalidError):
            # limit is bounded 1..50 — a model-supplied 9999 must be
            # rejected by Pydantic validation, never silently clamped or
            # passed through to the query.
            await dispatch_read_tool(
                db,
                tool_name="list_my_open_tasks",
                arguments_json='{"limit": 9999}',
                workspace_id=member.workspace_id,
                settings=_test_settings(),
            )


async def test_dispatching_an_unknown_tool_name_raises_tool_not_found(db_available: bool) -> None:
    member = await seed_workspace_member()
    async with tenant_scoped_session(member.customer_id) as db:
        with pytest.raises(ToolNotFoundError):
            await dispatch_read_tool(
                db,
                tool_name="delete_the_whole_workspace",
                arguments_json="{}",
                workspace_id=member.workspace_id,
                settings=_test_settings(),
            )


async def test_knowledge_search_tool_reports_plainly_when_no_embedding_provider_is_configured(
    db_available: bool,
) -> None:
    """`_test_settings()` has no Gemini key (tests/conftest.py's autouse
    fixture forces it to None in every test) — the model must be told so
    in a normal tool result, never crash the turn (same "tell the truth,
    never fake a result" posture as NullEmbeddingPort itself)."""
    member = await seed_workspace_member()
    async with tenant_scoped_session(member.customer_id) as db:
        result = await dispatch_read_tool(
            db,
            tool_name="knowledge_search",
            arguments_json=json.dumps({"query": "anything"}),
            workspace_id=member.workspace_id,
            settings=_test_settings(),
        )
    assert "not available" in result


async def test_knowledge_search_tool_finds_indexed_content(
    db_available: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With an embedding provider configured (faked here, same
    discipline as test_knowledge_api.py's own _FakeEmbeddingPort), the
    tool returns real, workspace-scoped search_knowledge results — not a
    static placeholder."""
    monkeypatch.setattr("doda.application.ai_tools.is_embedding_configured", lambda settings: True)

    class _FixedEmbeddingPort:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            return [[float(i)] * EMBEDDING_DIMENSIONS for i, _ in enumerate(texts)]

    monkeypatch.setattr(
        "doda.application.ai_tools.get_embedding_port", lambda settings: _FixedEmbeddingPort()
    )

    member = await seed_workspace_member()
    needle = "quarterly-roadmap-v7"
    async with tenant_scoped_session(member.customer_id) as db:
        document = Document(
            customer_id=member.customer_id,
            workspace_id=member.workspace_id,
            uploader_id="user:seed",
            filename="roadmap.txt",
            content_type="text/plain",
            size_bytes=40,
            sha256="0" * 64,
            storage_key=f"test/{uuid.uuid4()}",
        )
        db.add(document)
        await db.flush()
        db.add(
            DocumentChunk(
                customer_id=member.customer_id,
                workspace_id=member.workspace_id,
                document_id=document.id,
                chunk_index=0,
                start_offset=0,
                end_offset=40,
                content=f"the {needle} is attached below",
                embedding=[0.0] * EMBEDDING_DIMENSIONS,
            )
        )
        await db.flush()

        result = await dispatch_read_tool(
            db,
            tool_name="knowledge_search",
            arguments_json=json.dumps({"query": needle}),
            workspace_id=member.workspace_id,
            settings=_test_settings(),
        )
    assert needle in result
    assert str(document.id) in result
    # FR-KNW-004: the exact locator shape CITATION_INSTRUCTION asks the
    # model to copy back verbatim — document_id alone isn't enough to
    # resolve to one specific chunk within a multi-chunk document.
    assert f"[manba: document_id={document.id}, chunk=0]" in result


async def test_proposing_a_write_tool_creates_an_r3_action_requiring_approval(db_available: bool) -> None:
    member = await seed_workspace_member()
    ctx = WorkspaceContext(
        customer_id=member.customer_id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        role=WorkspaceRole.MEMBER,
    )
    async with tenant_scoped_session(member.customer_id) as db:
        action, approval = await propose_write_tool_action(
            db,
            tool_name="telegram_send_message",
            arguments_json=json.dumps({"chat_id": "123", "text": "salom"}),
            workspace_context=ctx,
            trace_id=uuid.uuid4(),
            idempotency_key="chat:conv-1:call-1",
            actor_kind=ActorKind.HUMAN,
        )
        await db.commit()

    # Every tool call is a proposal, never a completed action — 9.1/9.2's
    # risk-based approval chain, not something the AI layer decides for
    # itself (6.2: "AI qatlami authoritative avtorizatsiya qarorini
    # chiqarmaydi").
    assert action.tool_name == "telegram.send_message"
    assert action.risk_level.value == "R3"
    assert action.status is ActionStatus.AWAITING_APPROVAL
    assert approval is not None


async def test_a_retried_write_tool_call_collapses_onto_the_same_action_not_a_duplicate(
    db_available: bool,
) -> None:
    """The explicit instruction: a retried gateway call that re-surfaces
    'the same' tool call must never create a second Action — the
    deterministic idempotency key (conversation_id:call_id, built by
    `doda.application.conversation_service`) is what makes this collapse
    onto the existing row via propose_action's own UNIQUE constraint."""
    member = await seed_workspace_member()
    ctx = WorkspaceContext(
        customer_id=member.customer_id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        role=WorkspaceRole.MEMBER,
    )
    args = json.dumps({"chat_id": "123", "text": "salom"})

    async with tenant_scoped_session(member.customer_id) as db:
        first_action, _ = await propose_write_tool_action(
            db,
            tool_name="telegram_send_message",
            arguments_json=args,
            workspace_context=ctx,
            trace_id=uuid.uuid4(),
            idempotency_key="chat:conv-1:call-1",
            actor_kind=ActorKind.HUMAN,
        )
        await db.commit()

    async with tenant_scoped_session(member.customer_id) as db:
        second_action, _ = await propose_write_tool_action(
            db,
            tool_name="telegram_send_message",
            arguments_json=args,
            workspace_context=ctx,
            trace_id=uuid.uuid4(),  # even a different trace_id — the key is what matters
            idempotency_key="chat:conv-1:call-1",
            actor_kind=ActorKind.HUMAN,
        )
        await db.commit()

    assert first_action.id == second_action.id


async def test_a_different_actors_replay_of_a_chat_derived_key_never_returns_the_nonce(
    db_available: bool,
) -> None:
    """Security-review finding: the chat idempotency key
    (f"chat:{conversation_id}:{call_id}") is deterministic and both
    components are visible to every workspace member via GET
    /conversations + GET .../messages — unlike a caller-chosen uuid4()
    key, a different member can realistically reconstruct it. Replaying
    it as someone other than the original proposer must never hand back
    that proposer's one-time approval nonce."""
    member = await seed_workspace_member()
    proposer_ctx = WorkspaceContext(
        customer_id=member.customer_id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        role=WorkspaceRole.MEMBER,
    )
    other_ctx = WorkspaceContext(
        customer_id=member.customer_id,
        workspace_id=member.workspace_id,
        user_id=uuid.uuid4(),  # a different workspace member, not the proposer
        role=WorkspaceRole.MEMBER,
    )
    args = json.dumps({"chat_id": "123", "text": "salom"})
    shared_key = "chat:some-conversation-id:some-call-id"

    async with tenant_scoped_session(member.customer_id) as db:
        proposer_action, proposer_approval = await propose_write_tool_action(
            db,
            tool_name="telegram_send_message",
            arguments_json=args,
            workspace_context=proposer_ctx,
            trace_id=uuid.uuid4(),
            idempotency_key=shared_key,
            actor_kind=ActorKind.HUMAN,
        )
        await db.commit()
    assert proposer_approval is not None  # the real proposer legitimately gets the nonce

    async with tenant_scoped_session(member.customer_id) as db:
        replayed_action, replayed_approval = await propose_write_tool_action(
            db,
            tool_name="telegram_send_message",
            arguments_json=args,
            workspace_context=other_ctx,
            trace_id=uuid.uuid4(),
            idempotency_key=shared_key,
            actor_kind=ActorKind.HUMAN,
        )
        await db.commit()

    assert replayed_action.id == proposer_action.id  # still the correct, idempotent Action
    assert replayed_approval is None  # but the nonce is never disclosed to a different actor


async def test_invalid_write_tool_arguments_are_rejected_before_any_action_is_created(
    db_available: bool,
) -> None:
    member = await seed_workspace_member()
    ctx = WorkspaceContext(
        customer_id=member.customer_id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        role=WorkspaceRole.MEMBER,
    )
    async with tenant_scoped_session(member.customer_id) as db:
        with pytest.raises(ToolArgumentsInvalidError):
            await propose_write_tool_action(
                db,
                tool_name="telegram_send_message",
                arguments_json=json.dumps({"chat_id": "123"}),  # missing required "text"
                workspace_context=ctx,
                trace_id=uuid.uuid4(),
                idempotency_key="chat:conv-2:call-1",
                actor_kind=ActorKind.HUMAN,
            )
