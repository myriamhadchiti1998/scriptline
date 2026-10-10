"""Contract test for the real Anthropic adapter, run against a local fake HTTP
transport: checks the exact request shape (structured outputs, effort, prompt
caching, no sampling params / prefill) and the streaming + validation path,
including the validation-retry loop."""
import json

import anthropic
try:  # newer SDKs ship on httpx2
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx

from app.config import StageModel
from app.llm import AnthropicLLM, Prompt
from app.schemas import IceScore, ScoringOutput


def _sse(text: str, stop: str = "end_turn") -> bytes:
    events = [
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5", "content": [],
            "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 50, "output_tokens": 1, "cache_read_input_tokens": 40}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                           "usage": {"output_tokens": 30}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in events).encode()


GOOD = {"scores": [{"idea_key": "I1", "impact": 8, "impact_reasoning": "Hits the dominant belief.", "confidence": 7,
                    "confidence_reasoning": "Pack-endorsed angle.", "ease": 9, "ease_reasoning": "Talking head.",
                    "verdict": "Strong.", "risk_flags": []}]}
BAD = {"scores": [{**GOOD["scores"][0], "impact": 42}]}  # out of range → must be retried


def _llm(responses: list[dict], captured: list[dict]) -> AnthropicLLM:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        body = responses[min(len(captured) - 1, len(responses) - 1)]
        return httpx.Response(200, content=_sse(json.dumps(body)), headers={"content-type": "text/event-stream"})

    llm = AnthropicLLM.__new__(AnthropicLLM)
    llm._anthropic = anthropic
    llm.client = anthropic.Anthropic(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    llm.max_attempts = 3
    return llm


def _prompt() -> Prompt:
    return Prompt(stage="scoring", system_blocks=["stage prompt", "playbook", "reference pack"], user="score these",
                  schema={"type": "object"}, model_cls=ScoringOutput,
                  stage_model=StageModel("claude-sonnet-5-5", "medium", 4000))


def test_request_shape_and_parse():
    captured: list[dict] = []
    res = _llm([GOOD], captured).run(_prompt())
    req = captured[0]
    assert req["output_config"] == {"effort": "medium", "format": {"type": "json_schema", "schema": {"type": "object"}}}
    assert req["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "temperature" not in req and "tool_choice" not in req
    assert req["messages"][-1]["role"] == "user"          # no assistant prefill
    assert req["stream"] is True
    assert isinstance(res.data.scores[0], IceScore) and res.data.scores[0].total == 8.0
    assert res.usage["cache_read_input_tokens"] == 40


def test_validation_failure_is_retried_with_error_feedback():
    captured: list[dict] = []
    res = _llm([BAD, GOOD], captured).run(_prompt())
    assert res.attempts == 2
    assert "rejected by validation" in captured[1]["messages"][0]["content"]
