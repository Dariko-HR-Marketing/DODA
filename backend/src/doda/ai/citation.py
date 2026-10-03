"""FR-KNW-004: "Citation-required rejim: har muhim claim source locator
bilan" — a deterministic system instruction telling the model to attach
a traceable source locator to any claim it draws from `doda.application.
ai_tools`' `knowledge_search` read-tool results, rather than presenting
retrieved information as if it were the model's own unsourced knowledge.

The locator format this instruction asks for — `[manba: document_id=...,
chunk=...]` — matches exactly what `ai_tools.dispatch_read_tool`'s own
`knowledge_search` branch now prepends to every returned chunk (document_
id + chunk_index — the same source-lineage fields `doda.domain.knowledge.
models.DocumentChunk` has carried since FR-KNW-002: "each chunk of a
Document's extracted text... with its own source lineage"). The model is
asked to copy that exact bracketed string back verbatim rather than
paraphrase a citation, so the locator stays traceable to one real
DocumentChunk row instead of degrading into free text a human (or this
instruction's own eval) can no longer resolve back to a source.

Like GROUNDEDNESS_INSTRUCTION (doda.ai.groundedness, which this pairs
with — TRD's own EVAL-GRD-010 lists FR-KNW-004 and FR-KNW-006 together
under "Ishonchli javob"), this is a PROMPT, not a code-enforced gate:
nothing here can statically prove the model will actually cite every
claim. Effectiveness is measured the same way groundedness is — see
`backend/scripts/citation_eval.py`, which runs it against a real Gemini
call answering from a real uploaded document and checks the resulting
text for the expected locator.

Always included in `doda.application.conversation_service.stream_message`
unconditionally (not conditioned on `knowledge_search` being called this
turn) — same reasoning as GROUNDEDNESS_INSTRUCTION's own docstring: the
discipline it asks for applies whether or not this particular turn ends
up retrieving anything, and conditioning it on tool use would require
inspecting the turn's own tool-call history before the model has
produced any output to inspect.
"""

CITATION_INSTRUCTION = (
    "Agar javobingda knowledge_search natijasidagi biror hujjatdan olingan "
    "ma'lumotga asoslangan da'vo bo'lsa, o'sha da'vodan darhol keyin "
    "knowledge_search natijasida ko'rsatilgan manba belgisini ANIQ, "
    "o'zgartirmasdan ko'chirib qo'y (masalan: \"[manba: document_id=..., "
    "chunk=...]\"). Hujjatdan olingan hech qanday ma'lumotni shu "
    "belgisiz taqdim qilma — agar manbani aniq ko'rsata olmasang, buni "
    "ochiq ayt (groundedness ko'rsatmasiga qarang), o'zingdan to'qib "
    "chiqarma."
)
