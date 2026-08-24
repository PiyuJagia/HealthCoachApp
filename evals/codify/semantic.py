"""Semantic / human grader specs. Offline CODIFY does not invoke Gemini."""

from __future__ import annotations

from evals.codify.catalog import SEMANTIC_SPECS
from evals.codify.schema import GraderSpec


def semantic_specs() -> tuple[GraderSpec, ...]:
    return SEMANTIC_SPECS


def executable_semantic_specs() -> tuple[GraderSpec, ...]:
    return tuple(item for item in SEMANTIC_SPECS if item.executable)
