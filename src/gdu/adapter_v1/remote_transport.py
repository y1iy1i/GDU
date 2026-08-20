from __future__ import annotations

import copy
import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from gdu.builder_v0.types import TechnicalFailure


@dataclass(frozen=True)
class RemoteTransportConfig:
    enabled: bool
    provider_id: str = ""
    base_url: str = ""
    model: str = ""
    api_key_env: str = ""
    json_output_mode: str = ""
    max_calls: int = 0
    timeout_seconds: int = 0
    max_output_tokens: int = 0
    authorization_id: str = ""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_remote_transport_config(
    path: Path, schema_path: Path, expected_sha256: str
) -> RemoteTransportConfig:
    if sha256_file(path) != expected_sha256:
        raise TechnicalFailure("adapter_transport", "remote config SHA-256 mismatch")
    try:
        import jsonschema

        value = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ModuleNotFoundError) as exc:
        raise TechnicalFailure("adapter_transport", str(exc)) from exc
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(value),
        key=lambda error: list(error.path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "$"
        raise TechnicalFailure(
            "adapter_transport",
            f"invalid remote config at {location}: {first.message}",
        )
    if not value["enabled"]:
        return RemoteTransportConfig(enabled=False)
    return RemoteTransportConfig(
        enabled=True,
        provider_id=value["provider_id"],
        base_url=value["base_url"].rstrip("/"),
        model=value["model"],
        api_key_env=value["api_key_env"],
        json_output_mode=value["json_output_mode"],
        max_calls=value["max_calls"],
        timeout_seconds=value["timeout_seconds"],
        max_output_tokens=value["max_output_tokens"],
        authorization_id=value["authorization_id"],
    )


class OpenAICompatibleRemoteTransport:
    """Explicitly authorized, call-capped Chat Completions transport."""

    def __init__(
        self,
        config: RemoteTransportConfig,
        *,
        explicit_authorization: bool = False,
        response_contract: Mapping[str, Any] | None = None,
    ) -> None:
        self.config = config
        self.explicit_authorization = explicit_authorization
        self.response_contract = (
            copy.deepcopy(dict(response_contract))
            if response_contract is not None
            else None
        )
        self.calls_made = 0

    def invoke(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        if not self.config.enabled:
            raise TechnicalFailure("adapter_transport", "remote transport is disabled")
        if not self.explicit_authorization:
            raise TechnicalFailure(
                "adapter_transport", "explicit remote-call authorization is missing"
            )
        if request.get("mode") in {"propose", "revise"} and self.response_contract is None:
            raise TechnicalFailure(
                "adapter_transport",
                "a response contract is required for semantic model calls",
            )
        policy = request.get("policy")
        if not isinstance(policy, Mapping) or not policy.get(
            "paid_remote_calls_allowed", False
        ):
            raise TechnicalFailure(
                "adapter_transport", "request policy forbids remote paid calls"
            )
        request_limit = policy.get("max_remote_calls")
        if not isinstance(request_limit, int) or request_limit < 1:
            raise TechnicalFailure(
                "adapter_transport", "request has no positive remote-call limit"
            )
        effective_limit = min(self.config.max_calls, request_limit)
        if self.calls_made >= effective_limit:
            raise TechnicalFailure("adapter_transport", "remote-call limit exhausted")
        api_key = os.environ.get(self.config.api_key_env)
        if not api_key:
            raise TechnicalFailure(
                "adapter_transport",
                f"API key environment variable {self.config.api_key_env} is missing",
            )

        system_content = (
            "Return only one JSON object conforming to the supplied GDU Adapter "
            "response contract. Do not use markdown."
        )
        if self.response_contract is not None:
            system_content += " RESPONSE_JSON_SCHEMA=" + json.dumps(
                self.response_contract,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        body = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_content,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        copy.deepcopy(dict(request)),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": self.config.max_output_tokens,
            "stream": False,
        }
        if self.config.json_output_mode == "native":
            body["response_format"] = {"type": "json_object"}
        wire_request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        self.calls_made += 1
        try:
            with urllib.request.urlopen(
                wire_request, timeout=self.config.timeout_seconds
            ) as response:
                envelope = json.loads(response.read().decode("utf-8"))
            content = envelope["choices"][0]["message"]["content"]
            value = json.loads(content)
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise TechnicalFailure(
                "adapter_transport", f"remote response failed: {type(exc).__name__}"
            ) from exc
        if not isinstance(value, Mapping):
            raise TechnicalFailure(
                "adapter_transport", "remote response content must be a JSON object"
            )
        return copy.deepcopy(dict(value))
