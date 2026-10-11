"""Compatibility exports for the phase-one consultation and report code."""

from app.rag.qa_chain import (
    Claim,
    GroundedAnswer,
    answer_question,
    validate_claims,
)

__all__ = ["Claim", "GroundedAnswer", "answer_question", "validate_claims"]
