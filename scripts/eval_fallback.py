#!/usr/bin/env python3
"""Проверка fallback-логики: честный отказ вместо галлюцинаций."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import settings
from src.output_guard import sanitize_llm_answer
from src.qa_fallback import answer_from_search, should_use_llm, unknown_qa_fallback
from src.rag import KnowledgeChunk, KnowledgeRetriever, format_retrieved_context


@dataclass(frozen=True)
class FallbackCase:
    question: str
    expected_source: str
    must_contain: tuple[str, ...]
    must_not_contain: tuple[str, ...]


@dataclass(frozen=True)
class SanitizeCase:
    answer: str
    rag_context: str
    must_escalate: bool


def _normalize(text: str) -> str:
    return text.strip().lower().replace("ё", "е")


def _load_dataset(path: Path) -> tuple[list[FallbackCase], list[SanitizeCase]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = [
        FallbackCase(
            question=item["question"],
            expected_source=item["expected_source"],
            must_contain=tuple(item.get("must_contain", [])),
            must_not_contain=tuple(item.get("must_not_contain", [])),
        )
        for item in data["cases"]
    ]
    sanitize_cases = [
        SanitizeCase(
            answer=item["answer"],
            rag_context=item["rag_context"],
            must_escalate=bool(item["must_escalate"]),
        )
        for item in data.get("sanitize_cases", [])
    ]
    return cases, sanitize_cases


def _resolve_answer(
    retriever: KnowledgeRetriever,
    question: str,
    *,
    threshold: float,
) -> tuple[str, str]:
    retrieved = retriever.search(question, max_chunks=settings.max_rag_chunks)
    rag_context = format_retrieved_context(retrieved)
    top_score = retrieved[0].similarity if retrieved else 0.0
    search_chunks = [
        KnowledgeChunk(source=item.source, text=item.text) for item in retrieved
    ]

    answer, source = answer_from_search(
        question,
        search_chunks,
        retriever.local_chunks,
        top_score=top_score,
        relevance_threshold=threshold,
    )
    if answer:
        return answer, source or "unknown"

    if should_use_llm(
        top_score=top_score,
        relevance_threshold=threshold,
        rag_context=rag_context,
    ):
        return "LLM_REQUIRED", "llm"

    return unknown_qa_fallback(), "unknown_fallback"


def _check_case(answer: str, source: str, case: FallbackCase) -> list[str]:
    errors: list[str] = []
    normalized = _normalize(answer)

    if case.expected_source == "llm" and source != "llm":
        errors.append(f"expected source llm, got {source}")
    elif case.expected_source != "llm" and source != case.expected_source:
        errors.append(f"expected source {case.expected_source}, got {source}")

    for keyword in case.must_contain:
        if _normalize(keyword) not in normalized:
            errors.append(f"missing keyword: {keyword}")

    for keyword in case.must_not_contain:
        if _normalize(keyword) in normalized:
            errors.append(f"forbidden keyword present: {keyword}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate anti-hallucination fallback")
    parser.add_argument(
        "--dataset",
        default=str(ROOT / "tests" / "fallback_eval.json"),
        help="Path to fallback eval dataset",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    cases, sanitize_cases = _load_dataset(dataset_path)
    retriever = KnowledgeRetriever()
    threshold = settings.rag_similarity_threshold

    failed: list[str] = []

    print(f"Dataset: {dataset_path.name}")
    print(f"Fallback cases: {len(cases)}")
    for case in cases:
        answer, source = _resolve_answer(retriever, case.question, threshold=threshold)
        errors = _check_case(answer, source, case)
        if errors:
            failed.append(f"{case.question} -> {errors}")
            print(f"FAIL: {case.question} | source={source}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"OK: {case.question} | source={source}")

    print(f"Sanitize cases: {len(sanitize_cases)}")
    for index, case in enumerate(sanitize_cases, start=1):
        _, escalated = sanitize_llm_answer(case.answer, case.rag_context)
        if escalated != case.must_escalate:
            failed.append(
                f"sanitize#{index}: expected escalate={case.must_escalate}, got {escalated}"
            )
            print(f"FAIL: sanitize#{index}")
        else:
            print(f"OK: sanitize#{index}")

    if failed:
        print("\nFallback evaluation failed.")
        return 1

    print("\nFallback evaluation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
