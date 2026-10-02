"""FR-KNW-006: "Manba topilmasa DODA buni ochiq aytadi" — a deterministic
system instruction telling the model what to do when `doda.application.
ai_tools`' `knowledge_search` read-tool finds nothing (that tool's own
"No matching documents found." string) or it otherwise lacks enough
grounding to answer confidently: say so plainly rather than guessing or
fabricating an answer from its own general knowledge.

This is a PROMPT, not a code-enforced gate — unlike an authorization
check, nothing here can statically prove the model will actually comply.
`doda.domain.knowledge.file_validation`'s own docstring draws exactly
this distinction for "malware validation" (a real, checkable control)
versus something that can only be measured, not assumed. This
instruction's effectiveness is measured the same way — see
`backend/scripts/groundedness_eval.py`, which runs it against a real
Gemini call on a question with no supporting document and checks the
resulting text for an honest insufficient-information acknowledgement
rather than a fabricated specific answer.

Always included in `doda.application.conversation_service.stream_message`
(not conditioned on `knowledge_search` being configured or even called
this turn) — the same honesty discipline applies to any question the
model might otherwise be tempted to guess at, a weaker but still
Must-level fallback for turns that never touch the tool at all.
"""

GROUNDEDNESS_INSTRUCTION = (
    "Agar knowledge_search vositasi hech qanday mos hujjat topmasa yoki "
    "savolga ishonchli javob berish uchun yetarli ma'lumot bo'lmasa, buni "
    "ochiq va aniq ayt (masalan: \"Bu savolga javob berish uchun ma'lumot "
    "yetarli emas\") — taxmin qilma va o'z umumiy bilimingdan to'qib "
    "chiqarilgan javob berma."
)
