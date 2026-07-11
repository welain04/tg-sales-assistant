#!/usr/bin/env python3
"""Этап 6: оценка качества vector retrieval по golden dataset."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eval_catalog import expand_eval_keywords
from src.rag import KnowledgeRetriever, RetrievedChunk


@dataclass(frozen=True)
class EvalCase:
    question: str
    expected_sources: tuple[str, ...]
    must_contain: tuple[str, ...]


@dataclass(frozen=True)
class EvalThresholds:
    recall_at_3: float
    recall_at_5: float
    mrr: float


@dataclass(frozen=True)
class CaseResult:
    question: str
    passed_at_3: bool
    passed_at_5: bool
    reciprocal_rank: float
    top_sources: tuple[str, ...]
    top_score: float


def _normalize(text: str) -> str:
    return text.strip().lower().replace("ё", "е")


def _load_dataset(path: Path) -> tuple[list[EvalCase], EvalThresholds]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = [
        EvalCase(
            question=item["question"],
            expected_sources=tuple(item.get("expected_sources", [])),
            must_contain=expand_eval_keywords(item.get("must_contain", [])),
        )
        for item in data["cases"]
    ]
    thresholds = EvalThresholds(
        recall_at_3=float(data["thresholds"]["recall_at_3"]),
        recall_at_5=float(data["thresholds"]["recall_at_5"]),
        mrr=float(data["thresholds"]["mrr"]),
    )
    return cases, thresholds


def _case_passes(results: list[RetrievedChunk], case: EvalCase) -> tuple[bool, bool, float]:
    if not results:
        return False, False, 0.0

    reciprocal_rank = 0.0
    passed_at_3 = False
    passed_at_5 = False

    for index, result in enumerate(results, start=1):
        source_ok = not case.expected_sources or result.source in case.expected_sources
        text = _normalize(result.text)
        keywords_ok = all(_normalize(keyword) in text for keyword in case.must_contain)
        if source_ok and keywords_ok:
            reciprocal_rank = 1.0 / index
            if index <= 3:
                passed_at_3 = True
            if index <= 5:
                passed_at_5 = True
            break

    return passed_at_3, passed_at_5, reciprocal_rank


def evaluate(
    retriever: KnowledgeRetriever,
    cases: list[EvalCase],
    *,
    top_k: int = 5,
) -> list[CaseResult]:
    results: list[CaseResult] = []

    for case in cases:
        retrieved = retriever.search(case.question, max_chunks=top_k)
        passed_at_3, passed_at_5, reciprocal_rank = _case_passes(retrieved, case)
        results.append(
            CaseResult(
                question=case.question,
                passed_at_3=passed_at_3,
                passed_at_5=passed_at_5,
                reciprocal_rank=reciprocal_rank,
                top_sources=tuple(item.source for item in retrieved[:3]),
                top_score=retrieved[0].similarity if retrieved else 0.0,
            )
        )

    return results


def _metric_rate(case_results: list[CaseResult], field: str) -> float:
    if not case_results:
        return 0.0
    passed = sum(1 for result in case_results if getattr(result, field))
    return passed / len(case_results)


def _mean_reciprocal_rank(case_results: list[CaseResult]) -> float:
    if not case_results:
        return 0.0
    return sum(result.reciprocal_rank for result in case_results) / len(case_results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality")
    parser.add_argument(
        "--dataset",
        default=str(ROOT / "tests" / "rag_eval.json"),
        help="Path to golden dataset JSON",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to retrieve per question",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    cases, thresholds = _load_dataset(dataset_path)
    retriever = KnowledgeRetriever()

    if not retriever.vector_enabled:
        print("ERROR: Vector RAG is not configured. Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY.")
        return 1

    case_results = evaluate(retriever, cases, top_k=args.top_k)
    recall_at_3 = _metric_rate(case_results, "passed_at_3")
    recall_at_5 = _metric_rate(case_results, "passed_at_5")
    mrr = _mean_reciprocal_rank(case_results)

    print(f"Dataset: {dataset_path.name}")
    print(f"Cases: {len(case_results)}")
    print(f"Recall@3: {recall_at_3:.2%} (threshold {thresholds.recall_at_3:.0%})")
    print(f"Recall@5: {recall_at_5:.2%} (threshold {thresholds.recall_at_5:.0%})")
    print(f"MRR: {mrr:.3f} (threshold {thresholds.mrr:.2f})")

    failed = [result for result in case_results if not result.passed_at_5]
    if failed:
        print("\nFailed cases:")
        for result in failed:
            print(
                f"- {result.question} | sources={result.top_sources} | score={result.top_score:.3f}"
            )

    metrics_ok = (
        recall_at_3 >= thresholds.recall_at_3
        and recall_at_5 >= thresholds.recall_at_5
        and mrr >= thresholds.mrr
    )
    if not metrics_ok:
        print("\nRAG evaluation failed.")
        return 1

    print("\nRAG evaluation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
