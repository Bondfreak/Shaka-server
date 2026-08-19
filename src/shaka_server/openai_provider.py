from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from .kai import DisabledKaiProvider, KaiProviderContractError, KaiProviderUnavailable

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.6"
MAX_PROVIDER_ROUNDS = 6

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "get_asset_instance_detail",
        "description": "Read the authoritative detail for one installed Shaka Asset Instance.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"instance_id": {"type": "string"}},
            "required": ["instance_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_direct_relations",
        "description": "Read the authoritative depth=1 typed relations for one Asset Instance.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"instance_id": {"type": "string"}},
            "required": ["instance_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_object_detail",
        "description": "Read authoritative bounded detail for a Shaka System or Location object.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"object_id": {"type": "string"}},
            "required": ["object_id"],
            "additionalProperties": False,
        },
    },
]

INSTRUCTIONS = """You are KAI, the bounded AI assistant for Navigator.
Explain only the currently selected Atlas context.
Use only the provided read-only tools for Shaka facts. Tool results are authoritative; your own interpretation is not.
Do not invent objects, relations, continuity, provenance, source documents, procedures, maintenance instructions, fault causes, or manual pages.
If the available tool results do not support a claim, say that the available Core data does not support it.
Distinguish facts from interpretation. Keep the answer concise and in Danish.
You must use at least one tool before answering.
"""


@dataclass
class OpenAIResponsesProvider:
    api_key: str
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 30.0

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                OPENAI_RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_seconds,
                follow_redirects=False,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise KaiProviderUnavailable("openai_transport_unavailable") from exc

        if response.status_code != 200:
            raise KaiProviderUnavailable(f"openai_http_{response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise KaiProviderContractError("openai_invalid_json") from exc
        if not isinstance(body, dict) or not isinstance(body.get("output"), list):
            raise KaiProviderContractError("openai_invalid_response")
        return body

    @staticmethod
    def _function_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
        calls = []
        for item in response.get("output", []):
            if isinstance(item, dict) and item.get("type") == "function_call":
                calls.append(item)
        return calls

    @staticmethod
    def _output_text(response: dict[str, Any]) -> str | None:
        parts: list[str] = []
        for item in response.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    parts.append(part["text"])
        text = "\n".join(part.strip() for part in parts if part.strip()).strip()
        return text or None

    def explain(
        self,
        *,
        context: dict[str, str],
        run_tool: Callable[[str, dict[str, str]], dict[str, Any]],
    ) -> str:
        context_id = context.get("contextInstanceId")
        if not isinstance(context_id, str):
            raise KaiProviderContractError("missing_context")

        input_items: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    "Forklar den valgte Atlas-kontekst. "
                    f"Den valgte Asset Instance er {context_id}. "
                    "Brug Core-værktøjerne til at hente de fakta, du behøver."
                ),
            }
        ]
        tool_choice = "required"

        for _ in range(MAX_PROVIDER_ROUNDS):
            response = self._post(
                {
                    "model": self.model,
                    "instructions": INSTRUCTIONS,
                    "input": input_items,
                    "tools": TOOLS,
                    "tool_choice": tool_choice,
                    "parallel_tool_calls": True,
                    "store": False,
                }
            )
            calls = self._function_calls(response)
            if calls:
                input_items.extend(item for item in response["output"] if isinstance(item, dict))
                for call in calls:
                    name = call.get("name")
                    call_id = call.get("call_id")
                    raw_arguments = call.get("arguments")
                    if not isinstance(name, str) or not isinstance(call_id, str) or not isinstance(raw_arguments, str):
                        raise KaiProviderContractError("invalid_function_call")
                    try:
                        arguments = json.loads(raw_arguments)
                    except json.JSONDecodeError as exc:
                        raise KaiProviderContractError("invalid_function_arguments") from exc
                    if not isinstance(arguments, dict) or not all(
                        isinstance(key, str) and isinstance(value, str)
                        for key, value in arguments.items()
                    ):
                        raise KaiProviderContractError("invalid_function_arguments")
                    result = run_tool(name, arguments)
                    input_items.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                        }
                    )
                tool_choice = "auto"
                continue

            text = self._output_text(response)
            if text:
                return text
            raise KaiProviderContractError("openai_missing_text")

        raise KaiProviderContractError("openai_tool_round_limit")


def provider_from_env():
    provider_name = os.getenv("SHAKA_KAI_PROVIDER", "").strip().lower()
    if not provider_name:
        return DisabledKaiProvider()
    if provider_name != "openai":
        raise RuntimeError("Unsupported SHAKA_KAI_PROVIDER")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return DisabledKaiProvider()
    model = os.getenv("SHAKA_KAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return OpenAIResponsesProvider(api_key=api_key, model=model)
