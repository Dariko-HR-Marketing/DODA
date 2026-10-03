"""FR-KNW-004: a trivial, direct test for doda.ai.citation — a pure
string constant, same discipline as test_groundedness.py (FR-KNW-006's
own pairing partner per TRD's EVAL-GRD-010). Real effectiveness is
measured separately, against a live model, by backend/scripts/
citation_eval.py — this test only pins the text itself and that it
actually names the exact locator shape ai_tools.dispatch_read_tool's
knowledge_search branch produces.
"""

from doda.ai.citation import CITATION_INSTRUCTION


def test_the_instruction_is_a_non_empty_string() -> None:
    assert isinstance(CITATION_INSTRUCTION, str)
    assert CITATION_INSTRUCTION.strip() == CITATION_INSTRUCTION
    assert CITATION_INSTRUCTION != ""


def test_the_instruction_names_the_knowledge_search_tool() -> None:
    assert "knowledge_search" in CITATION_INSTRUCTION


def test_the_instruction_matches_the_locator_shape_ai_tools_actually_produces() -> None:
    # A change to ai_tools.py's own "[manba: document_id=..., chunk=...]"
    # format without updating this instruction to match would silently
    # ask the model to copy back a shape that no longer exists anywhere
    # in a real tool result.
    assert "document_id=" in CITATION_INSTRUCTION
    assert "chunk=" in CITATION_INSTRUCTION


def test_the_instruction_tells_the_model_not_to_fabricate_an_unsourced_citation() -> None:
    assert "to'qib chiqarma" in CITATION_INSTRUCTION
