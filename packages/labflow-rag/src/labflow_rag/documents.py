"""Markdown document loading for the LabFlow knowledge corpus."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TAG_PATTERN = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class KnowledgeDocument:
    """A loaded markdown document with retrieval metadata."""

    document_id: str
    source_path: str
    title: str
    headings: tuple[str, ...]
    tags: tuple[str, ...]
    text: str


def load_corpus(corpus_dir: str | Path = "knowledge") -> tuple[KnowledgeDocument, ...]:
    """Load all markdown files from a corpus directory in stable path order."""

    root = Path(corpus_dir)
    if not root.exists():
        msg = f"Knowledge corpus directory does not exist: {root}"
        raise FileNotFoundError(msg)
    documents = [
        load_markdown_document(path, corpus_root=root)
        for path in sorted(root.glob("*.md"), key=lambda item: item.name)
    ]
    if not documents:
        msg = f"No markdown files found in knowledge corpus: {root}"
        raise ValueError(msg)
    return tuple(documents)


def load_markdown_document(
    path: str | Path,
    *,
    corpus_root: str | Path | None = None,
) -> KnowledgeDocument:
    """Load one markdown document and extract title, headings, and retrieval tags."""

    source = Path(path)
    text = source.read_text()
    document_id = _document_id(source, corpus_root)
    headings = _extract_headings(text)
    title = _extract_title(headings, document_id)
    return KnowledgeDocument(
        document_id=document_id,
        source_path=source.as_posix(),
        title=title,
        headings=headings,
        tags=_extract_tags(text),
        text=text,
    )


def _document_id(path: Path, corpus_root: str | Path | None) -> str:
    if corpus_root is None:
        return path.name
    try:
        return path.relative_to(Path(corpus_root)).as_posix()
    except ValueError:
        return path.name


def _extract_headings(text: str) -> tuple[str, ...]:
    headings: list[str] = []
    for line in text.splitlines():
        match = HEADING_PATTERN.match(line)
        if match is not None:
            headings.append(match.group(2).strip())
    return tuple(headings)


def _extract_title(headings: tuple[str, ...], fallback: str) -> str:
    if headings:
        return headings[0]
    return Path(fallback).stem.replace("_", " ").title()


def _extract_tags(text: str) -> tuple[str, ...]:
    tag_lines: list[str] = []
    in_tag_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "## Retrieval Tags":
            in_tag_section = True
            continue
        if in_tag_section and stripped.startswith("#"):
            break
        if in_tag_section and stripped:
            tag_lines.append(stripped)

    raw_tags = ",".join(TAG_PATTERN.findall("\n".join(tag_lines)))
    if not raw_tags:
        raw_tags = ",".join(tag_lines)

    tags = []
    for raw_tag in raw_tags.split(","):
        tag = raw_tag.strip().strip("`").lower().replace(" ", "_")
        if tag and tag not in tags:
            tags.append(tag)
    return tuple(tags)
