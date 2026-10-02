"""FR-KNW-006: a trivial, direct test for doda.ai.groundedness — a pure
string constant, but every prompt-building module in this codebase gets
at least a minimal direct test pinning its actual content (see
test_tool_policy.py's own test_telegram_send_message_is_registered_at_r3:
"a change to this value should be a conscious, reviewed edit"). Real
effectiveness is measured separately, against a live model, by
backend/scripts/groundedness_eval.py — this test only pins the text
itself.
"""

from doda.ai.groundedness import GROUNDEDNESS_INSTRUCTION


def test_the_instruction_is_a_non_empty_string() -> None:
    assert isinstance(GROUNDEDNESS_INSTRUCTION, str)
    assert GROUNDEDNESS_INSTRUCTION.strip() == GROUNDEDNESS_INSTRUCTION
    assert GROUNDEDNESS_INSTRUCTION != ""


def test_the_instruction_names_the_knowledge_search_tool() -> None:
    # Pins that the instruction is actually scoped to this codebase's own
    # tool name, not a generic "don't hallucinate" platitude disconnected
    # from what the model can actually check.
    assert "knowledge_search" in GROUNDEDNESS_INSTRUCTION


def test_the_instruction_tells_the_model_not_to_guess() -> None:
    assert "taxmin qilma" in GROUNDEDNESS_INSTRUCTION
