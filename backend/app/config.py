"""Runtime settings. Everything is overridable with environment variables (see .env.example)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Minimal .env loader (no extra dependency). Real env vars always win."""
    for candidate in (BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"):
        if not candidate.exists():
            continue
        for raw in candidate.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip()
            if value[:1] in ('"', "'") and value[1:].find(value[0]) >= 0:
                value = value[1:1 + value[1:].find(value[0])]      # quoted: keep everything inside
            else:
                value = re.split(r"\s+#", value, maxsplit=1)[0].strip()  # unquoted: drop inline comment
            os.environ.setdefault(key.strip(), value)


_load_dotenv()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class StageModel:
    model: str
    effort: str          # output_config.effort: low | medium | high | xhigh | max
    max_tokens: int


@dataclass(frozen=True)
class Settings:
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "anthropic"))  # anthropic | mock
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY", ""))

    ideation: StageModel = field(default_factory=lambda: StageModel(
        _env("MODEL_IDEATION", "claude-sonnet-5-5"), _env("EFFORT_IDEATION", "high"), 32000))
    scoring: StageModel = field(default_factory=lambda: StageModel(
        _env("MODEL_SCORING", "claude-sonnet-5-5"), _env("EFFORT_SCORING", "medium"), 24000))
    scripting: StageModel = field(default_factory=lambda: StageModel(
        _env("MODEL_SCRIPTING", "claude-sonnet-5-5"), _env("EFFORT_SCRIPTING", "high"), 24000))
    review: StageModel = field(default_factory=lambda: StageModel(
        _env("MODEL_REVIEW", "claude-sonnet-5-5"), _env("EFFORT_REVIEW", "high"), 24000))

    default_client: str = field(default_factory=lambda: _env("DEFAULT_CLIENT", "sovereign_storefront"))
    batch_size: int = field(default_factory=lambda: int(_env("IDEA_BATCH_SIZE", "12")))
    duplicate_threshold: float = field(default_factory=lambda: float(_env("DUPLICATE_THRESHOLD", "0.62")))
    max_revisions: int = field(default_factory=lambda: int(_env("MAX_REVISIONS", "1")))
    review_pass_score: int = field(default_factory=lambda: int(_env("REVIEW_PASS_SCORE", "4")))
    script_workers: int = field(default_factory=lambda: int(_env("SCRIPT_WORKERS", "2")))
    llm_max_attempts: int = field(default_factory=lambda: int(_env("LLM_MAX_ATTEMPTS", "3")))

    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", str(BACKEND_DIR / "data"))))
    output_dir: Path = field(default_factory=lambda: Path(_env("OUTPUT_DIR", str(BACKEND_DIR.parent / "output"))))
    clients_dir: Path = BACKEND_DIR / "clients"
    prompts_dir: Path = BACKEND_DIR / "prompts"
    knowledge_dir: Path = BACKEND_DIR / "knowledge"
    cors_origins: str = field(default_factory=lambda: _env("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "pipeline.db"


settings = Settings()
