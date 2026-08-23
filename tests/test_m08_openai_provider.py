from __future__ import annotations

import json

import httpx
import pytest

from shaka_server.kai import DisabledKaiProvider, KaiProviderUnavailable
from shaka_server.openai_provider import (
    OPENAI_RESPONSES_URL,
    TOOLS,
    OpenAIResponsesProvider,
    provider_from_env,
)


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def test_provider_from_env_is_disabled_without_explicit_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHAKA_KAI_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    assert isinstance(provider_from_env(), DisabledKaiProvider)


def test_provider_from_env_is_disabled_without_server_side_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHAKA_KAI_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(provider_from_env(), DisabledKaiProvider)


def test_unknown_provider_configuration_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHAKA_KAI_PROVIDER", "anything-else")
    with pytest.raises(RuntimeError, match="Unsupported SHAKA_KAI_PROVIDER"):
        provider_from_env()


def test_openai_provider_uses_only_allowlisted_function_tools_and_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict] = []
    responses = iter(
        [
            FakeResponse(
                {
                    "output": [
                        {
                            "type": "function_call",
                            "name": "get_asset_instance_detail",
                            "call_id": "call_1",
                            "arguments": json.dumps({"instance_id": "AI-D4-BB-SeaWaterPump"}),
                        }
                    ]
                }
            ),
            FakeResponse(
                {
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "Pumpen er en installeret Asset Instance baseret på Core-data.",
                                }
                            ],
                        }
                    ]
                }
            ),
        ]
    )

    def fake_post(url, *, headers, json, timeout, follow_redirects):
        requests.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
                "follow_redirects": follow_redirects,
            }
        )
        return next(responses)

    monkeypatch.setattr(httpx, "post", fake_post)
    tool_calls = []

    def run_tool(name, arguments):
        tool_calls.append((name, arguments))
        return {
            "data": {
                "id": arguments["instance_id"],
                "type": "asset_instance",
                "state": "INSTALLED",
            },
            "meta": {"schemaVersion": "1.0"},
        }

    provider = OpenAIResponsesProvider(api_key="test-secret", model="test-model")
    text = provider.explain(
        context={
            "contextInstanceId": "AI-D4-BB-SeaWaterPump",
            "intent": "explain_selected_context",
        },
        run_tool=run_tool,
    )

    assert text.startswith("Pumpen er")
    assert tool_calls == [
        ("get_asset_instance_detail", {"instance_id": "AI-D4-BB-SeaWaterPump"})
    ]
    assert len(requests) == 2
    assert requests[0]["url"] == OPENAI_RESPONSES_URL
    assert requests[0]["headers"]["Authorization"] == "Bearer test-secret"
    assert requests[0]["json"]["model"] == "test-model"
    assert requests[0]["json"]["tool_choice"] == "required"
    assert requests[0]["json"]["store"] is False
    assert {tool["name"] for tool in requests[0]["json"]["tools"]} == {
        "get_asset_instance_detail",
        "get_direct_relations",
        "get_object_detail",
        "get_canonical_graph",
        "get_canonical_object",
    }
    assert all(tool["strict"] is True for tool in TOOLS)
    assert requests[1]["json"]["tool_choice"] == "auto"
    outputs = [item for item in requests[1]["json"]["input"] if item.get("type") == "function_call_output"]
    assert len(outputs) == 1
    assert outputs[0]["call_id"] == "call_1"
    assert "AI-D4-BB-SeaWaterPump" in outputs[0]["output"]


def test_openai_transport_failure_is_bounded_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", OPENAI_RESPONSES_URL)

    def fake_post(*args, **kwargs):
        raise httpx.ReadTimeout("timeout", request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIResponsesProvider(api_key="test-secret")
    with pytest.raises(KaiProviderUnavailable, match="openai_transport_unavailable"):
        provider.explain(
            context={
                "contextInstanceId": "AI-D4-BB-SeaWaterPump",
                "intent": "explain_selected_context",
            },
            run_tool=lambda name, arguments: {},
        )
