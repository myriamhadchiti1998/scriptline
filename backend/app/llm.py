"""LLM gateway — the only module that talks to a model provider.

Responsibilities
- Structured outputs: every call returns JSON constrained by a JSON Schema
  (`output_config.format`) and is re-validated with Pydantic.
- Reliability: transport errors (429/5xx/timeouts) are retried by the SDK with
  exponential backoff; schema/validation failures are retried here with the
  validation error fed back to the model; refusals and truncation are surfaced
  as typed errors instead of silently producing bad data.
- Cost: the stable prefix (stage prompt + client context + Reference Pack) is
  marked for prompt caching, so repeated calls for the same client reuse it.
- Swappable: `LLM_PROVIDER=mock` runs the whole pipeline offline with
  deterministic fixtures (used by the test-suite and for UI work without a key).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError

from .config import Settings, StageModel, settings

log = logging.getLogger("scriptline.llm")
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when a stage cannot get a valid response after all attempts."""


@dataclass
class LLMResult:
    data: BaseModel
    model: str
    attempts: int
    usage: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0


@dataclass
class Prompt:
    """A stage call. `system_blocks` are stable (cached); `user` is per-call."""
    stage: str
    system_blocks: list[str]
    user: str
    schema: dict
    model_cls: type[BaseModel]
    stage_model: StageModel
    mock_context: dict[str, Any] = field(default_factory=dict)  # only read by MockLLM


class AnthropicLLM:
    def __init__(self, cfg: Settings = settings):
        import anthropic  # imported lazily so mock mode needs no key

        if not cfg.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set. Add it to backend/.env or set LLM_PROVIDER=mock.")
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=cfg.anthropic_api_key, max_retries=4, timeout=600)
        self.max_attempts = cfg.llm_max_attempts

    def _system(self, blocks: list[str]) -> list[dict]:
        out = [{"type": "text", "text": b} for b in blocks if b.strip()]
        out[-1]["cache_control"] = {"type": "ephemeral"}  # cache the whole stable prefix
        return out

    def run(self, p: Prompt) -> LLMResult:
        started = time.monotonic()
        user = p.user
        last_err: str = ""
        usage_total: dict[str, int] = {}
        for attempt in range(1, self.max_attempts + 1):
            try:
                with self.client.messages.stream(
                    model=p.stage_model.model,
                    max_tokens=p.stage_model.max_tokens,
                    system=self._system(p.system_blocks),
                    messages=[{"role": "user", "content": user}],
                    output_config={
                        "effort": p.stage_model.effort,
                        "format": {"type": "json_schema", "schema": p.schema},
                    },
                ) as stream:
                    msg = stream.get_final_message()
            except self._anthropic.APIStatusError as e:  # 4xx that the SDK won't retry
                if e.status_code in (400, 401, 403, 404):
                    raise LLMError(f"{p.stage}: API rejected the request ({e.status_code}): {e.message}") from e
                last_err = f"API error {e.status_code}: {e.message}"
                log.warning("%s attempt %s failed: %s", p.stage, attempt, last_err)
                time.sleep(2 ** attempt)
                continue
            except self._anthropic.APIConnectionError as e:
                last_err = f"connection error: {e}"
                log.warning("%s attempt %s failed: %s", p.stage, attempt, last_err)
                time.sleep(2 ** attempt)
                continue

            u = msg.usage
            for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                usage_total[k] = usage_total.get(k, 0) + int(getattr(u, k, 0) or 0)

            if msg.stop_reason == "refusal":
                raise LLMError(f"{p.stage}: model refused the request")
            if msg.stop_reason == "max_tokens":
                last_err = "output truncated at max_tokens"
                log.warning("%s attempt %s: %s", p.stage, attempt, last_err)
                continue

            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            try:
                data = p.model_cls.model_validate(json.loads(text))
            except (json.JSONDecodeError, ValidationError) as e:
                last_err = _short_error(e)
                log.warning("%s attempt %s invalid output: %s", p.stage, attempt, last_err)
                user = (f"{p.user}\n\n---\nIMPORTANT: your previous answer was rejected by validation "
                        f"with this error:\n{last_err}\nReturn a complete, corrected answer.")
                continue
            return LLMResult(data=data, model=p.stage_model.model, attempts=attempt,
                             usage=usage_total, seconds=round(time.monotonic() - started, 1))
        raise LLMError(f"{p.stage}: no valid output after {self.max_attempts} attempts ({last_err})")


class MockLLM:
    """Deterministic offline provider. Never used for the sample outputs."""

    def __init__(self, cfg: Settings = settings):
        from . import mock_llm
        self.handlers: dict[str, Callable[[Prompt], dict]] = mock_llm.HANDLERS

    def run(self, p: Prompt) -> LLMResult:
        raw = self.handlers[p.stage](p)
        data = p.model_cls.model_validate(raw)
        return LLMResult(data=data, model="mock", attempts=1, usage={})


def _short_error(e: Exception) -> str:
    s = str(e)
    return s if len(s) < 1500 else s[:1500] + "…"


_instance: AnthropicLLM | MockLLM | None = None


def get_llm() -> AnthropicLLM | MockLLM:
    global _instance
    if _instance is None:
        _instance = MockLLM() if settings.llm_provider == "mock" else AnthropicLLM()
    return _instance


def set_llm(llm: Any) -> None:
    """Test hook: inject a fake provider."""
    global _instance
    _instance = llm
