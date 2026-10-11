"""LlamaIndex sentence splitting with verifiable original-text offsets."""

from dataclasses import dataclass

from llama_index.core.node_parser import SentenceSplitter


@dataclass(frozen=True)
class Span:
    text: str
    start: int
    end: int


def split_evidence(content: str) -> list[Span]:
    """Split original text and retain exact spans for persisted citations."""
    splitter = SentenceSplitter(
        chunk_size=700, chunk_overlap=100, tokenizer=lambda value: list(value)
    )
    result: list[Span] = []
    previous_end = 0
    for piece in splitter.split_text(content):
        start = content.find(piece, max(0, previous_end - 100))
        if start < 0:
            raise ValueError("Chunk cannot be located verbatim in original content")
        end = start + len(piece)
        result.append(Span(content[start:end], start, end))
        previous_end = end
    return result
