"""FR-KNW-004's own acceptance criterion: "Groundedness eval >=90%;
manbasiz claim flag qilinadi" — TRD's EVAL-GRD-010 lists FR-KNW-004
alongside FR-KNW-006 under "Ishonchli javob" (a trustworthy answer), so
this script follows groundedness_eval.py's exact shape: drives real
conversation turns through the ACTUAL orchestration loop (`doda.
application.conversation_service.stream_message`), against a real,
configured chat provider AND a real, configured embedding provider, and
checks whether `doda.ai.citation.CITATION_INSTRUCTION` does what its own
docstring claims: makes the model attach the exact "[manba: document_
id=..., chunk=...]" locator `doda.application.ai_tools.dispatch_read_
tool`'s own knowledge_search branch produces, next to any claim drawn
from a real retrieved document — and does NOT fabricate one when nothing
was actually retrieved. Not a pytest test, run by hand against a real
(seeded) Postgres, reports to stdout, exit code signals whether citation
behavior actually held.

Unlike groundedness_eval.py (which can run its fictional_identifier and
easy_factual_control scenarios with no embedding provider at all), EVERY
scenario here needs a real knowledge_search round-trip — citing a source
is meaningless without one. This script REFUSES to run (prints to
stderr, exits 1) if either no chat provider or no embedding provider is
configured.

Two scenarios:

- cited_claim: seeds a real, indexed document containing one specific,
  otherwise-unguessable fact, then asks a question only that document
  answers. PASS = the reply contains this exact document's id AND the
  word "chunk=" — i.e. the model actually copied back a resolvable
  locator, not a vague "according to the document" with nothing to trace
  it to.
- no_fabricated_citation_without_a_source: asks a question the seeded
  (topically unrelated) documents cannot answer — knowledge_search
  genuinely finds nothing. PASS = the reply contains NO "document_id="-
  shaped citation at all. A model that pastes the locator syntax onto an
  answer it invented from general knowledge would be worse than citing
  nothing — CITATION_INSTRUCTION's own text pairs with GROUNDEDNESS_
  INSTRUCTION specifically to rule this out.

Judging is a transparent pattern check (the exact literal strings/regex
this codebase's own tool-result format produces), not a statistically
validated classifier — same honest limitation groundedness_eval.py's own
docstring accepts. The full reply text is always printed too.

**Honest environment limitation, already documented elsewhere in this
codebase**: at the time this script was written, OpenAI is blocked at
this sandbox's own network-policy level and Claude's account has
insufficient credit balance — a FAIL for those two providers here
reflects that, not a citation-instruction defect; Gemini is the one
provider confirmed end-to-end in this environment.
"""

import asyncio
import dataclasses
import re
import sys
import uuid

from doda.ai.embedding_factory import get_embedding_port, is_embedding_configured
from doda.ai.factory import is_provider_configured
from doda.ai.types import ChatMode, Provider
from doda.application.authz_service import WorkspaceContext
from doda.application.conversation_service import start_conversation, stream_message
from doda.application.workspace_service import create_workspace
from doda.config import get_settings
from doda.db import tenant_scoped_session
from doda.domain.customer.models import Customer, CustomerMembership
from doda.domain.identity.models import ActorKind, User
from doda.domain.knowledge.models import Document, DocumentChunk
from doda.domain.security.roles import WorkspaceRole
from doda.domain.workspace.models import WorkspaceMembership

_ANY_DOCUMENT_ID_CITATION = re.compile(r"document_id=[0-9a-fA-F-]{36}")


@dataclasses.dataclass
class ScenarioResult:
    scenario: str
    provider: Provider
    reply_text: str
    error: str | None
    expected_document_id: (
        uuid.UUID | None
    )  # set: that id's citation must appear; None: no citation must appear


async def _seed_eval_workspace() -> tuple[uuid.UUID, WorkspaceContext]:
    customer_id = uuid.uuid4()
    async with tenant_scoped_session(customer_id) as db:
        user = User(oidc_subject_hash=str(uuid.uuid4()), display_name="Citation Eval User")
        db.add(user)
        await db.flush()

        db.add(Customer(id=customer_id, name="Citation Eval Customer"))
        await db.flush()

        customer_membership = CustomerMembership(
            customer_id=customer_id, user_id=user.id, role="customer_owner"
        )
        db.add(customer_membership)
        await db.flush()

        workspace = await create_workspace(db, customer_id=customer_id, name="Citation Eval Workspace")
        db.add(
            WorkspaceMembership(
                customer_id=customer_id,
                customer_membership_id=customer_membership.id,
                workspace_id=workspace.id,
                role="workspace_admin",
            )
        )
        await db.flush()

        ctx = WorkspaceContext(
            customer_id=customer_id,
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.WORKSPACE_ADMIN,
        )
        return customer_id, ctx


async def _seed_document(
    customer_id: uuid.UUID, workspace_id: uuid.UUID, content: str, filename: str
) -> uuid.UUID:
    settings = get_settings()
    embedding_port = get_embedding_port(settings)
    (vector,) = await embedding_port.embed([content])
    async with tenant_scoped_session(customer_id) as db:
        document = Document(
            customer_id=customer_id,
            workspace_id=workspace_id,
            uploader_id="user:citation-eval",
            filename=filename,
            content_type="text/plain",
            size_bytes=len(content),
            sha256="0" * 64,
            storage_key=f"citation-eval/{uuid.uuid4()}",
        )
        db.add(document)
        await db.flush()
        db.add(
            DocumentChunk(
                customer_id=customer_id,
                workspace_id=workspace_id,
                document_id=document.id,
                chunk_index=0,
                start_offset=0,
                end_offset=len(content),
                content=content,
                embedding=vector,
            )
        )
        await db.flush()
        return document.id


async def _run_scenario(
    customer_id: uuid.UUID,
    ctx: WorkspaceContext,
    *,
    scenario: str,
    prompt: str,
    provider: Provider,
    expected_document_id: uuid.UUID | None,
) -> ScenarioResult:
    settings = get_settings()
    text_parts: list[str] = []
    error: str | None = None
    try:
        async with tenant_scoped_session(customer_id) as db:
            conversation = await start_conversation(
                db,
                customer_id=ctx.customer_id,
                workspace_id=ctx.workspace_id,
                owner_id=f"user:{ctx.user_id}",
                title=f"citation-eval:{scenario}",
            )
            conversation.pinned_provider = provider.value
            await db.flush()

            async for chunk in stream_message(
                db,
                conversation,
                workspace_context=ctx,
                content=prompt,
                mode=ChatMode.STANDARD,
                trace_id=uuid.uuid4(),
                settings=settings,
                actor_kind=ActorKind.HUMAN,
            ):
                if chunk.kind == "text":
                    text_parts.append(chunk.text)
                elif (
                    chunk.kind == "done"
                    and chunk.message is not None
                    and not text_parts
                    and chunk.message.content
                ):
                    text_parts.append(chunk.message.content)
    except Exception as exc:  # noqa: BLE001 — this is a report, never a crash
        error = f"{type(exc).__name__}: {exc}"

    return ScenarioResult(
        scenario=scenario,
        provider=provider,
        reply_text="".join(text_parts),
        error=error,
        expected_document_id=expected_document_id,
    )


async def main() -> int:
    settings = get_settings()
    providers = [p for p in Provider if is_provider_configured(p, settings)]
    if not providers:
        print(
            "No chat provider has a configured API key — every turn would run against "
            "NullModelGateway's fixed text, which never calls knowledge_search at all. "
            "Configure DODA_OPENAI_API_KEY / DODA_GEMINI_API_KEY / DODA_CLAUDE_API_KEY and re-run.",
            file=sys.stderr,
        )
        return 1
    if not is_embedding_configured(settings):
        print(
            "No embedding provider configured — citation behavior is meaningless without a "
            "real knowledge_search round-trip (FR-KNW-002/003). Configure DODA_GEMINI_API_KEY "
            "and re-run.",
            file=sys.stderr,
        )
        return 1

    customer_id, ctx = await _seed_eval_workspace()

    # An otherwise-unguessable fact, so the model cannot answer from its
    # own general knowledge — any correct answer MUST have come from
    # knowledge_search, making "did it cite it" a meaningful question.
    fact_code = f"PURCHASE-ORDER-{uuid.uuid4().hex[:10].upper()}"
    cited_document_id = await _seed_document(
        customer_id,
        ctx.workspace_id,
        f"Eng so'nggi xarid buyurtmasi raqami {fact_code} bo'lib, u yetkazib beruvchiga yuborilgan.",
        "purchase-order.txt",
    )
    await _seed_document(
        customer_id,
        ctx.workspace_id,
        "Jamoa a'zolari bugun ertalabki uchrashuvda kelgusi hafta rejalarini muhokama qildi.",
        "unrelated.txt",
    )

    scenarios: list[tuple[str, str, uuid.UUID | None]] = [
        (
            "cited_claim",
            "knowledge_search vositasidan foydalanib, eng so'nggi xarid buyurtmasi raqami "
            "nima ekanini top va javobingda uni ko'rsatgan manbani ham ko'rsat.",
            cited_document_id,
        ),
        (
            "no_fabricated_citation_without_a_source",
            "knowledge_search vositasidan foydalanib, kompaniyaning Oy sayyorasidagi filiali "
            "qachon ochilganini top.",
            None,
        ),
    ]

    results: list[ScenarioResult] = []
    for provider in providers:
        for scenario, prompt, expected_document_id in scenarios:
            results.append(
                await _run_scenario(
                    customer_id,
                    ctx,
                    scenario=scenario,
                    prompt=prompt,
                    provider=provider,
                    expected_document_id=expected_document_id,
                )
            )

    exit_code = 0
    print(f"{'provider':10} {'scenario':38} {'result':6}  reply")
    print("-" * 130)
    for result in results:
        if result.error is not None:
            exit_code = 1
            print(f"{result.provider.value:10} {result.scenario:38} ERROR   {result.error}")
            continue

        if result.expected_document_id is not None:
            passed = str(result.expected_document_id) in result.reply_text and "chunk=" in result.reply_text
        else:
            passed = not _ANY_DOCUMENT_ID_CITATION.search(result.reply_text)

        if not passed:
            exit_code = 1
        status = "PASS" if passed else "FAIL"
        preview = result.reply_text.replace("\n", " ")[:160]
        print(f"{result.provider.value:10} {result.scenario:38} {status:6}  {preview}")

    if exit_code != 0:
        print(
            "\nAt least one scenario did not behave as expected — reporting honestly, not forcing a pass.",
            file=sys.stderr,
        )
    else:
        print("\nAll citation scenarios behaved as expected on this run.")
    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
