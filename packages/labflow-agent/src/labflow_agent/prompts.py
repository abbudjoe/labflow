"""Prompt registry with stable content hashes."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

REQUIRED_PROMPT_IDS = frozenset(
    {"rag_answer", "agent_planner", "diagnostic_explainer", "patch_proposer"}
)


@dataclass(frozen=True)
class PromptMetadata:
    """Versioned prompt metadata."""

    prompt_id: str
    version: str
    sha256: str
    created_at: str
    notes: str
    path: str

    def to_json_dict(self) -> dict[str, str]:
        return {
            "prompt_id": self.prompt_id,
            "version": self.version,
            "sha256": self.sha256,
            "created_at": self.created_at,
            "notes": self.notes,
            "path": self.path,
        }


class PromptRegistry:
    """Load runtime prompt files and expose version/hash metadata."""

    def __init__(self, prompt_dir: str | Path | None = None) -> None:
        self.prompt_dir = Path(prompt_dir) if prompt_dir is not None else default_prompt_dir()
        self._prompts = {
            metadata.prompt_id: metadata
            for metadata in (
                self._load_prompt(path)
                for path in sorted(self.prompt_dir.glob("*.md"))
            )
        }
        missing = REQUIRED_PROMPT_IDS - set(self._prompts)
        if missing:
            msg = f"Missing required runtime prompts in {self.prompt_dir}: {sorted(missing)}"
            raise FileNotFoundError(msg)

    def get(self, prompt_id: str) -> PromptMetadata:
        try:
            return self._prompts[prompt_id]
        except KeyError as exc:
            msg = f"Unknown prompt: {prompt_id}"
            raise KeyError(msg) from exc

    def list_prompts(self) -> tuple[PromptMetadata, ...]:
        return tuple(self._prompts[prompt_id] for prompt_id in sorted(self._prompts))

    def to_json_dict(self) -> dict[str, dict[str, str]]:
        return {
            prompt_id: metadata.to_json_dict()
            for prompt_id, metadata in sorted(self._prompts.items())
        }

    def _load_prompt(self, path: Path) -> PromptMetadata:
        text = path.read_text()
        frontmatter, _body = _split_frontmatter(text)
        metadata = _parse_frontmatter(frontmatter)
        prompt_id = metadata.get("prompt_id", path.stem)
        return PromptMetadata(
            prompt_id=prompt_id,
            version=metadata.get("version", "0.1.0"),
            sha256=hash_prompt_text(text),
            created_at=metadata.get("created_at", ""),
            notes=metadata.get("notes", ""),
            path=str(path),
        )


def hash_prompt_text(text: str) -> str:
    """Return the canonical prompt content hash."""

    return f"sha256:{sha256(text.encode()).hexdigest()}"


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    try:
        _empty, frontmatter, body = text.split("---\n", 2)
    except ValueError:
        return "", text
    return frontmatter, body


def _parse_frontmatter(frontmatter: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def default_prompt_metadata() -> dict[str, dict[str, str]]:
    """Return default runtime prompt metadata for API/eval output."""

    return PromptRegistry().to_json_dict()


def default_prompt_dir() -> Path:
    """Resolve the runtime prompt directory independent of process cwd."""

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "prompts" / "runtime"
        if candidate.exists():
            return candidate
    return Path("prompts/runtime").resolve()
