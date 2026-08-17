"""Live retrieval smoke-test against the Pinecone corpus."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.retrieval import DEFAULT_MIN_RELEVANCE_SCORE, DEFAULT_TOP_K, describe_retrieval_config, retrieve

PREVIEW_LENGTH = 280

REPRESENTATIVE_QUERIES = [
    {
        "id": "D2-A",
        "query": "How much moderate-intensity physical activity should adults get each week?",
        "expected": "HHS",
    },
    {
        "id": "D2-B",
        "query": "How should a health application determine whether a change is a real trend rather than normal day-to-day variation?",
        "expected": "L2-TD",
    },
    {
        "id": "D2-C",
        "query": "What can we infer when aerobic exercise consistency increases and resting heart rate decreases?",
        "expected": "L2-CR R-05",
    },
    {
        "id": "D2-D",
        "query": "Does sleeping less cause HRV to decrease?",
        "expected": "L2-CR (association limits)",
    },
    {
        "id": "D2-E",
        "query": "When should the health coach avoid making a recommendation or escalate?",
        "expected": "L3-SF",
    },
    {
        "id": "D2-F",
        "query": "Who won the FIFA World Cup?",
        "expected": "none / below threshold",
    },
]


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _preview(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= PREVIEW_LENGTH:
        return collapsed
    return collapsed[: PREVIEW_LENGTH - 3] + "..."


RELATIONSHIP_PREVIEW_FIELDS = (
    "relationship_id",
    "relationship_status",
    "evidence_strength",
    "measurement_transfer_risk",
    "max_product_level",
    "recommendation_eligible",
    "modifier_suppressor_only",
    "mandatory_contradiction_suppression",
)


def _print_result(rank: int, result) -> None:
    print(f"  [{rank}] score={result.score:.4f}  doc={result.document_id}")
    print(f"      vector_id={result.vector_id}")
    print(f"      section={result.section_heading or '(none)'}")
    if result.relationship_id or result.document_id == "healthcoach_correlation_modeling":
        rel_fields = {
            field: getattr(result, field)
            for field in RELATIONSHIP_PREVIEW_FIELDS
            if getattr(result, field, "")
        }
        if rel_fields:
            print(f"      relationship_metadata={rel_fields}")
    print(f"      preview={_preview(result.text)!r}")


def run_query(query: str, *, top_k: int, min_score: float) -> None:
    print(f"Query: {query}")
    print(f"top_k={top_k}  min_score={min_score}")
    results = retrieve(query, top_k=top_k, min_score=min_score)
    print(f"results_above_threshold={len(results)}")
    if not results:
        print("  (no results)")
        return
    for rank, result in enumerate(results, start=1):
        _print_result(rank, result)
    print()


def main() -> None:
    _configure_stdout()
    load_dotenv(PROJECT_ROOT / ".env")

    parser = argparse.ArgumentParser(description="Retrieval smoke-test against Pinecone.")
    parser.add_argument("--query", help="Run a single query instead of the representative set.")
    parser.add_argument("--top-k", type=int, default=None, help="Override RAG_TOP_K.")
    parser.add_argument(
        "--min-score",
        type=float,
        default=None,
        help="Override RAG_MIN_RELEVANCE_SCORE.",
    )
    parser.add_argument(
        "--representative",
        action="store_true",
        help="Run the Phase D2 representative query set.",
    )
    args = parser.parse_args()

    config = describe_retrieval_config()
    top_k = args.top_k if args.top_k is not None else int(config["top_k"])
    min_score = (
        args.min_score if args.min_score is not None else float(config["min_relevance_score"])
    )

    print("Retrieval smoke test")
    print("=" * 72)
    print(f"index={config['index_name']}  namespace={config['namespace']}")
    print(f"defaults: top_k={DEFAULT_TOP_K}  min_score={DEFAULT_MIN_RELEVANCE_SCORE}")
    print(f"active:   top_k={top_k}  min_score={min_score}")
    print()

    if args.query:
        run_query(args.query, top_k=top_k, min_score=min_score)
        return

    if args.representative or not args.query:
        for item in REPRESENTATIVE_QUERIES:
            print("-" * 72)
            print(f"[{item['id']}] expected: {item['expected']}")
            run_query(item["query"], top_k=top_k, min_score=min_score)


if __name__ == "__main__":
    main()
