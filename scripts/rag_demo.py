#!/usr/bin/env python3
"""Interactive local LabFlow RAG demo."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SRC = REPO_ROOT / "packages" / "labflow-rag" / "src"
if str(RAG_SRC) not in sys.path:
    sys.path.insert(0, str(RAG_SRC))

from labflow_rag import RagAnswer, RagIndex, answer_query  # noqa: E402
from labflow_rag.backends import SUPPORTED_RAG_BACKENDS, build_retriever_from_env  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="knowledge")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument(
        "--rag-backend",
        choices=SUPPORTED_RAG_BACKENDS,
        default="local",
        help="Retrieval backend. Defaults to local; use pinecone explicitly for hosted retrieval.",
    )
    parser.add_argument(
        "--confirm-live-pinecone",
        action="store_true",
        help="Confirm an explicit live Pinecone retrieval run when --rag-backend=pinecone.",
    )
    args = parser.parse_args()

    corpus_dir = _resolve_repo_path(args.corpus)
    index = RagIndex.from_corpus(corpus_dir)
    retriever_build = build_retriever_from_env(
        index,
        corpus_dir=corpus_dir,
        backend_name=args.rag_backend,
        confirm_live_pinecone=args.confirm_live_pinecone,
    )
    retriever = retriever_build.retriever
    interactive = sys.stdin.isatty()

    if interactive:
        print(
            f"LabFlow RAG demo [{retriever_build.backend_name}]. "
            "Type a question, or 'exit' to quit."
        )
    _print_prompt(interactive)

    for line in sys.stdin:
        question = line.strip()
        if question.casefold() in {"exit", "quit"}:
            break
        if not question:
            _print_prompt(interactive)
            continue

        answer = answer_query(question, index, retriever=retriever, top_k=args.top_k)
        _print_answer(answer)
        _print_prompt(interactive)

    return 0


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _print_prompt(interactive: bool) -> None:
    if interactive:
        print("Question: ", end="", flush=True)


def _print_answer(answer: RagAnswer) -> None:
    print()
    print("Answer:")
    print(answer.answer)
    print()
    print("Sources:")
    if answer.citations:
        for citation in answer.citations:
            print(f"- {citation.chunk_id}")
    else:
        print("- none")
    print()
    print("Suggested tools:")
    if answer.tool_call_recommendations:
        for tool_name in answer.tool_call_recommendations:
            print(f"- {tool_name}")
    else:
        print("- none")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
