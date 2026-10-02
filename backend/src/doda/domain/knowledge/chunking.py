"""FR-KNW-002's "chunking" stage — pure, deterministic, no DB/network
dependency (same reason doda.ai.language's text-only heuristics are
pure functions: easy to unit-test in isolation from the pipeline that
calls them).

Character-based fixed-window chunking with overlap — the same "no
tokenizer dependency needed for a first-pass budget" reasoning as
Settings.ai_max_context_chars, not a semantic/paragraph-aware splitter.
`start_offset`/`end_offset` are exactly what FR-KNW-002's own acceptance
criterion asks for ("Har chunk source lineage (source_id, version_id,
offset) saqlaydi") — source_id/version_id are the caller's job
(doda.domain.knowledge.models.DocumentChunk.document_id; no versioning
mechanism exists yet — FR-KNW-009 — so every document is implicitly its
own single version today, a deliberate scope limit, not an oversight).
"""

import dataclasses


@dataclasses.dataclass(frozen=True)
class TextChunk:
    content: str
    start_offset: int
    end_offset: int


def chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[TextChunk]:
    """`overlap` must be strictly smaller than `chunk_size`, or the
    window would never advance — enforced here rather than trusted from
    Settings, since a misconfigured value would otherwise hang."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    stripped = text.strip()
    if not stripped:
        return []

    chunks: list[TextChunk] = []
    start = 0
    step = chunk_size - overlap
    length = len(stripped)
    while start < length:
        end = min(start + chunk_size, length)
        content = stripped[start:end].strip()
        if content:
            chunks.append(TextChunk(content=content, start_offset=start, end_offset=end))
        if end == length:
            break
        start += step
    return chunks
