"""Paragraph-aware chunking.

Text is split into blocks (paragraphs, or whole tables made of consecutive "|" rows).
Blocks are packed into chunks of roughly `max_chars`; a table is never split, even if
it alone exceeds the limit. Each chunk after the first starts with up to `overlap`
characters of the previous chunk's tail (never taken from a table).
"""

import re
from dataclasses import dataclass

DEFAULT_MAX_CHARS = 800
DEFAULT_OVERLAP = 100
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class _Block:
    text: str
    is_table: bool


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def _split_blocks(text: str) -> list[_Block]:
    blocks: list[_Block] = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        lines = [line.rstrip() for line in paragraph.strip().splitlines() if line.strip()]
        if not lines:
            continue
        # Group consecutive table rows apart from prose lines that share the paragraph.
        group: list[str] = []
        for line in lines:
            if group and _is_table_line(line) != _is_table_line(group[-1]):
                blocks.append(_Block("\n".join(group), _is_table_line(group[0])))
                group = []
            group.append(line)
        blocks.append(_Block("\n".join(group), _is_table_line(group[0])))
    return blocks


def _split_oversized(block: _Block, max_chars: int) -> list[_Block]:
    """Break a long prose block at sentence boundaries, then at words as a last resort."""
    if block.is_table or len(block.text) <= max_chars:
        return [block]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_BOUNDARY.split(block.text):
        for word_run in _hard_wrap(sentence, max_chars):
            if current and len(current) + 1 + len(word_run) > max_chars:
                pieces.append(current)
                current = word_run
            else:
                current = f"{current} {word_run}".strip()
    if current:
        pieces.append(current)
    return [_Block(piece, False) for piece in pieces]


def _hard_wrap(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    runs: list[str] = []
    current = ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > max_chars:
            runs.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        runs.append(current)
    return runs


def _tail(text: str, overlap: int) -> str:
    """Last `overlap` characters of text, advanced to the next word boundary."""
    if overlap <= 0 or len(text) <= overlap:
        return text if overlap > 0 else ""
    tail = text[-overlap:]
    if not text[-overlap - 1].isspace():
        _, _, tail = tail.partition(" ")
    return tail.strip()


def chunk_text(
    text: str, max_chars: int = DEFAULT_MAX_CHARS, overlap: int = DEFAULT_OVERLAP
) -> list[str]:
    blocks = [
        piece for block in _split_blocks(text) for piece in _split_oversized(block, max_chars)
    ]

    chunks: list[str] = []
    parts: list[str] = []
    size = 0
    last_block: _Block | None = None

    def flush() -> None:
        nonlocal parts, size
        if parts:
            chunks.append("\n\n".join(parts))
        parts, size = [], 0

    for block in blocks:
        if parts and size + 2 + len(block.text) > max_chars:
            previous = last_block
            flush()
            if previous is not None and not previous.is_table:
                carried = _tail(previous.text, overlap)
                if carried:
                    parts, size = [carried], len(carried)
        parts.append(block.text)
        size += len(block.text) + (2 if len(parts) > 1 else 0)
        last_block = block
    flush()
    return chunks
