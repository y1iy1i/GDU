from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gdu.adapter_v1 import (
    OpenAICompatibleRemoteTransport,
    RemoteTransportConfig,
    load_remote_transport_config,
)
from gdu.builder_v0.types import TechnicalFailure


ROOT = Path(__file__).resolve().parents[1]
API_CONFIG = ROOT / "configs" / "api"
SCHEMA = API_CONFIG / "remote-adapter-v1.schema.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def enabled_config() -> RemoteTransportConfig:
    return RemoteTransportConfig(
        enabled=True,
        provider_id="test-provider",
        base_url="https://api.example.test/v1",
        model="test-model",
        api_key_env="GDU_TEST_API_KEY",
        json_output_mode="native",
        thinking_mode="provider_default",
        max_calls=1,
        timeout_seconds=10,
        max_output_tokens=1000,
        authorization_id="user-approved-test",
    )


def permitted_request() -> dict[str, object]:
    return {
        "contract_version": "gdu-adapter-v1",
        "policy": {
            "paid_remote_calls_allowed": True,
            "max_remote_calls": 1,
        },
    }


class FakeResponse:
    def __init__(self, value: object) -> None:
        self.payload = json.dumps(value).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class RemoteConfigTests(unittest.TestCase):
    def test_disabled_example_loads_as_closed(self) -> None:
        path = API_CONFIG / "disabled.example.json"
        config = load_remote_transport_config(path, SCHEMA, digest(path))
        self.assertFalse(config.enabled)
        with self.assertRaisesRegex(TechnicalFailure, "disabled"):
            OpenAICompatibleRemoteTransport(config).invoke(permitted_request())

    def test_config_hash_mismatch_is_rejected(self) -> None:
        path = API_CONFIG / "disabled.example.json"
        with self.assertRaisesRegex(TechnicalFailure, "SHA-256 mismatch"):
            load_remote_transport_config(path, SCHEMA, "0" * 64)

    def test_aliyun_deepseek_example_is_native_json_and_call_capped(self) -> None:
        path = API_CONFIG / (
            "aliyun-token-plan-deepseek-v4-flash-0731.example.json"
        )
        config = load_remote_transport_config(path, SCHEMA, digest(path))
        self.assertTrue(config.enabled)
        self.assertEqual(config.provider_id, "aliyun-bailian-token-plan-beijing")
        self.assertEqual(
            config.base_url,
            "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        )
        self.assertEqual(config.model, "deepseek-v4-flash-0731")
        self.assertEqual(config.api_key_env, "DASHSCOPE_API_KEY")
        self.assertEqual(config.json_output_mode, "native")
        self.assertEqual(config.thinking_mode, "disabled")
        self.assertEqual(config.max_calls, 1)

    def test_non_https_remote_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "remote.json"
            value = {
                "enabled": True,
                "provider_id": "test",
                "base_url": "http://api.example.test/v1",
                "model": "test",
                "api_key_env": "GDU_TEST_API_KEY",
                "api_style": "openai_chat_completions",
                "json_output_mode": "native",
                "thinking_mode": "provider_default",
                "max_calls": 1,
                "timeout_seconds": 10,
                "max_output_tokens": 1000,
                "temperature": 0,
                "authorization_id": "test-only",
            }
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(TechnicalFailure, "invalid remote config"):
                load_remote_transport_config(path, SCHEMA, digest(path))


class RemoteTransportTests(unittest.TestCase):
    def test_explicit_authorization_is_required(self) -> None:
        transport = OpenAICompatibleRemoteTransport(enabled_config())
        with self.assertRaisesRegex(TechnicalFailure, "authorization is missing"):
            transport.invoke(permitted_request())

    def test_request_policy_is_required(self) -> None:
        transport = OpenAICompatibleRemoteTransport(
            enabled_config(), explicit_authorization=True
        )
        with self.assertRaisesRegex(TechnicalFailure, "policy forbids"):
            transport.invoke({"policy": {"paid_remote_calls_allowed": False}})

    def test_semantic_call_requires_response_contract_before_network(self) -> None:
        transport = OpenAICompatibleRemoteTransport(
            enabled_config(), explicit_authorization=True
        )
        request = permitted_request()
        request["mode"] = "propose"
        with patch("urllib.request.urlopen") as urlopen:
            with self.assertRaisesRegex(TechnicalFailure, "response contract"):
                transport.invoke(request)
            urlopen.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key_stops_before_network(self) -> None:
        transport = OpenAICompatibleRemoteTransport(
            enabled_config(), explicit_authorization=True
        )
        with patch("urllib.request.urlopen") as urlopen:
            with self.assertRaisesRegex(TechnicalFailure, "environment variable"):
                transport.invoke(permitted_request())
            urlopen.assert_not_called()

    @patch.dict(os.environ, {"GDU_TEST_API_KEY": "secret-test-key"}, clear=True)
    def test_fake_response_is_parsed_and_call_limit_is_hard(self) -> None:
        envelope = {
            "choices": [{"message": {"content": json.dumps({"stage": "cp1"})}}]
        }
        transport = OpenAICompatibleRemoteTransport(
            enabled_config(), explicit_authorization=True
        )
        with patch(
            "urllib.request.urlopen", return_value=FakeResponse(envelope)
        ) as urlopen:
            self.assertEqual(transport.invoke(permitted_request()), {"stage": "cp1"})
            sent = urlopen.call_args.args[0]
            self.assertEqual(sent.full_url, "https://api.example.test/v1/chat/completions")
            self.assertEqual(sent.get_header("Authorization"), "Bearer secret-test-key")
            body = json.loads(sent.data.decode("utf-8"))
            self.assertEqual(body["response_format"], {"type": "json_object"})
            with self.assertRaisesRegex(TechnicalFailure, "limit exhausted"):
                transport.invoke(permitted_request())
            self.assertEqual(urlopen.call_count, 1)

    @patch.dict(os.environ, {"GDU_TEST_API_KEY": "secret-test-key"}, clear=True)
    def test_response_contract_is_supplied_to_semantic_model(self) -> None:
        envelope = {
            "choices": [{"message": {"content": json.dumps({"stage": "cp1"})}}]
        }
        transport = OpenAICompatibleRemoteTransport(
            enabled_config(),
            explicit_authorization=True,
            response_contract={"type": "object", "required": ["stage"]},
        )
        request = permitted_request()
        request["mode"] = "propose"
        with patch(
            "urllib.request.urlopen", return_value=FakeResponse(envelope)
        ) as urlopen:
            transport.invoke(request)
            sent = urlopen.call_args.args[0]
            body = json.loads(sent.data.decode("utf-8"))
            system = body["messages"][0]["content"]
            self.assertIn("RESPONSE_JSON_SCHEMA=", system)
            self.assertIn('"required":["stage"]', system)

    @patch.dict(os.environ, {"GDU_TEST_API_KEY": "secret-test-key"}, clear=True)
    def test_prompt_only_mode_omits_native_json_parameter(self) -> None:
        envelope = {
            "choices": [{"message": {"content": json.dumps({"stage": "cp1"})}}]
        }
        config = RemoteTransportConfig(
            **{**enabled_config().__dict__, "json_output_mode": "prompt_only"}
        )
        transport = OpenAICompatibleRemoteTransport(
            config, explicit_authorization=True
        )
        with patch(
            "urllib.request.urlopen", return_value=FakeResponse(envelope)
        ) as urlopen:
            transport.invoke(permitted_request())
            sent = urlopen.call_args.args[0]
            body = json.loads(sent.data.decode("utf-8"))
            self.assertNotIn("response_format", body)

    @patch.dict(os.environ, {"GDU_TEST_API_KEY": "secret-test-key"}, clear=True)
    def test_disabled_thinking_is_sent_to_provider(self) -> None:
        envelope = {
            "choices": [{"message": {"content": json.dumps({"stage": "cp1"})}}]
        }
        config = RemoteTransportConfig(
            **{**enabled_config().__dict__, "thinking_mode": "disabled"}
        )
        transport = OpenAICompatibleRemoteTransport(
            config, explicit_authorization=True
        )
        with patch(
            "urllib.request.urlopen", return_value=FakeResponse(envelope)
        ) as urlopen:
            transport.invoke(permitted_request())
            sent = urlopen.call_args.args[0]
            body = json.loads(sent.data.decode("utf-8"))
            self.assertIs(body["enable_thinking"], False)

    @patch.dict(os.environ, {"GDU_TEST_API_KEY": "secret-test-key"}, clear=True)
    def test_malformed_remote_envelope_is_a_technical_failure(self) -> None:
        transport = OpenAICompatibleRemoteTransport(
            enabled_config(), explicit_authorization=True
        )
        with patch(
            "urllib.request.urlopen", return_value=FakeResponse({"choices": []})
        ):
            with self.assertRaisesRegex(TechnicalFailure, "remote response failed"):
                transport.invoke(permitted_request())
