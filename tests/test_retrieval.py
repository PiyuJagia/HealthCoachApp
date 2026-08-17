"""Offline tests for the retrieval layer (mocked — no network)."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rag.retrieval import (
    DEFAULT_MIN_RELEVANCE_SCORE,
    DEFAULT_TOP_K,
    describe_retrieval_config,
    filter_by_min_score,
    get_min_relevance_score,
    get_top_k,
    map_match_to_result,
    retrieve,
)
from rag.schemas import RetrievalResult


def _make_match(
    *,
    vector_id: str = "doc__chunk_0001",
    score: float = 0.8,
    metadata: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=vector_id,
        score=score,
        metadata=metadata
        or {
            "text": "Sample chunk about aerobic training and resting heart rate.",
            "document_id": "healthcoach_correlation_modeling",
            "source_title": "Correlation Modeling",
            "section_heading": "R-05 · Aerobic exercise consistency and resting heart rate",
            "chunk_index": 25,
            "version": "L2-CR-002",
            "evidence_level": "curated_evidence_synthesis",
            "evidence_grade": "verified_with_constraints",
            "verification_status": "verified_with_constraints",
        },
    )


class RetrievalConfigTests(unittest.TestCase):
    def test_default_top_k(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RAG_TOP_K", None)
            self.assertEqual(get_top_k(), DEFAULT_TOP_K)

    def test_default_min_score(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RAG_MIN_RELEVANCE_SCORE", None)
            self.assertEqual(get_min_relevance_score(), DEFAULT_MIN_RELEVANCE_SCORE)

    def test_invalid_top_k_raises(self) -> None:
        with patch.dict(os.environ, {"RAG_TOP_K": "zero"}):
            with self.assertRaises(ValueError):
                get_top_k()

    def test_invalid_min_score_raises(self) -> None:
        with patch.dict(os.environ, {"RAG_MIN_RELEVANCE_SCORE": "1.5"}):
            with self.assertRaises(ValueError):
                get_min_relevance_score()

    def test_describe_retrieval_config_includes_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RAG_TOP_K", None)
            os.environ.pop("RAG_MIN_RELEVANCE_SCORE", None)
            config = describe_retrieval_config()
            self.assertEqual(config["top_k"], DEFAULT_TOP_K)
            self.assertEqual(config["min_relevance_score"], DEFAULT_MIN_RELEVANCE_SCORE)


class RetrievalMappingTests(unittest.TestCase):
    def test_map_match_to_result_maps_core_fields(self) -> None:
        result = map_match_to_result(_make_match())
        self.assertEqual(result.document_id, "healthcoach_correlation_modeling")
        self.assertEqual(result.version, "L2-CR-002")
        self.assertIn("aerobic training", result.text)

    def test_map_match_handles_missing_optional_metadata(self) -> None:
        result = map_match_to_result(
            _make_match(
                metadata={
                    "text": "Minimal chunk.",
                    "document_id": "healthcoach_trend_detection",
                }
            )
        )
        self.assertEqual(result.source_title, "")
        self.assertEqual(result.chunk_index, 0)
        self.assertEqual(result.relationship_id, "")
        self.assertEqual(result.evidence_grade, "")

    def test_filter_by_min_score(self) -> None:
        results = [
            RetrievalResult(
                vector_id="a",
                score=0.5,
                text="a",
                document_id="d",
                source_title="",
                section_heading="",
                chunk_index=1,
                version="",
                evidence_level="",
                evidence_grade="",
                verification_status="",
                relationship_id="",
                relationship_status="",
                evidence_strength="",
                measurement_transfer_risk="",
                max_product_level="",
                recommendation_eligible="",
                modifier_suppressor_only="",
                mandatory_contradiction_suppression="",
            ),
            RetrievalResult(
                vector_id="b",
                score=0.2,
                text="b",
                document_id="d",
                source_title="",
                section_heading="",
                chunk_index=2,
                version="",
                evidence_level="",
                evidence_grade="",
                verification_status="",
                relationship_id="",
                relationship_status="",
                evidence_strength="",
                measurement_transfer_risk="",
                max_product_level="",
                recommendation_eligible="",
                modifier_suppressor_only="",
                mandatory_contradiction_suppression="",
            ),
        ]
        filtered = filter_by_min_score(results, min_score=0.35)
        self.assertEqual([item.vector_id for item in filtered], ["a"])


class RetrieveFunctionTests(unittest.TestCase):
    @patch("rag.retrieval.query_similar")
    @patch("rag.retrieval.embed_query", return_value=[0.1] * 1536)
    def test_retrieve_applies_top_k_and_score_filter(
        self,
        mock_embed: MagicMock,
        mock_query: MagicMock,
    ) -> None:
        mock_query.return_value = [
            _make_match(vector_id="high", score=0.72),
            _make_match(vector_id="low", score=0.21),
        ]

        results = retrieve("aerobic exercise and resting heart rate", top_k=2, min_score=0.35)

        mock_embed.assert_called_once()
        mock_query.assert_called_once()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].vector_id, "high")

    @patch("rag.retrieval.query_similar")
    @patch("rag.retrieval.embed_query", return_value=[0.0] * 1536)
    def test_retrieve_returns_empty_when_all_below_threshold(
        self,
        mock_embed: MagicMock,
        mock_query: MagicMock,
    ) -> None:
        mock_query.return_value = [_make_match(score=0.1)]
        results = retrieve("off topic query", top_k=3, min_score=0.35)
        self.assertEqual(results, [])

    def test_retrieve_rejects_blank_query(self) -> None:
        with self.assertRaises(ValueError):
            retrieve("   ")

    @patch("rag.retrieval.query_similar")
    @patch("rag.retrieval.embed_query", return_value=[0.0] * 1536)
    def test_retrieve_does_not_import_llm_completion(
        self,
        mock_embed: MagicMock,
        mock_query: MagicMock,
    ) -> None:
        """Retrieval module must not call chat/completion APIs."""
        import rag.retrieval as retrieval_module

        mock_query.return_value = [_make_match()]
        retrieve("test query", top_k=1, min_score=0.0)
        source = Path(retrieval_module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("ChatOpenAI", source)
        self.assertNotIn("chat.completions", source)
        self.assertNotIn("OpenAI(", source)


if __name__ == "__main__":
    unittest.main()
