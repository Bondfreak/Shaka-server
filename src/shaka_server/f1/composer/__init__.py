"""F1-T04 read-only Answer Composer (deterministic, no LLM)."""

from shaka_server.f1.composer.answer import Answer
from shaka_server.f1.composer.api import answer_query
from shaka_server.f1.composer.compose import compose_answer

__all__ = ["Answer", "answer_query", "compose_answer"]
