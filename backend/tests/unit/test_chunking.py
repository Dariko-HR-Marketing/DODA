"""doda.domain.knowledge.chunking — pure, no DB/network dependency."""

import pytest

from doda.domain.knowledge.chunking import chunk_text


def test_short_text_becomes_a_single_chunk() -> None:
    chunks = chunk_text("salom dunyo", chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].content == "salom dunyo"
    assert chunks[0].start_offset == 0
    assert chunks[0].end_offset == len("salom dunyo")


def test_empty_or_whitespace_only_text_produces_no_chunks() -> None:
    assert chunk_text("", chunk_size=100, overlap=10) == []
    assert chunk_text("   \n\t  ", chunk_size=100, overlap=10) == []


def test_long_text_is_split_into_multiple_chunks_with_overlap() -> None:
    text = "a" * 250
    chunks = chunk_text(text, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    # Every chunk after the first starts before the previous one ended —
    # that overlap is the whole point (a sentence straddling a boundary
    # stays findable from either neighboring chunk).
    for previous, current in zip(chunks, chunks[1:], strict=False):  # pairwise, deliberately offset by one
        assert current.start_offset < previous.end_offset
    # The chunks jointly cover the entire source text, start to end.
    assert chunks[0].start_offset == 0
    assert chunks[-1].end_offset == len(text)


def test_offsets_are_reconstructable_lineage_into_the_source_text() -> None:
    text = "0123456789" * 5  # 50 chars
    chunks = chunk_text(text, chunk_size=20, overlap=5)
    for chunk in chunks:
        assert text[chunk.start_offset : chunk.end_offset] == chunk.content


def test_non_positive_chunk_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        chunk_text("hello", chunk_size=0, overlap=0)


def test_overlap_equal_to_or_larger_than_chunk_size_is_rejected() -> None:
    """Otherwise the window would never advance and chunking would hang
    rather than raise — a misconfigured value must fail fast instead."""
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("hello world", chunk_size=10, overlap=10)
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("hello world", chunk_size=10, overlap=-1)
