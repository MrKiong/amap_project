from __future__ import annotations

import unittest

from config.settings import Settings
from core.llm_client import LLMClient, LLMResponse
from core.message import Message


class LLMClientTest(unittest.TestCase):
    def test_chat_uses_openai_sdk_chat_completions(self) -> None:
        class FakeMessage:
            content = "ok"
            tool_calls = []

        class FakeChoice:
            message = FakeMessage()

        class FakeCompletion:
            choices = [FakeChoice()]

            def model_dump(self, mode: str = "json") -> dict:  # noqa: ARG002
                return {"choices": [{"message": {"content": "ok"}}]}

        class FakeCompletions:
            def __init__(self) -> None:
                self.kwargs = {}

            def create(self, **kwargs):  # type: ignore[no-untyped-def]
                self.kwargs = kwargs
                return FakeCompletion()

        class FakeClient:
            def __init__(self) -> None:
                self.chat = type("Chat", (), {"completions": FakeCompletions()})()

        settings = Settings(
            log_level="INFO",
            llm_api_key="key",
            llm_base_url="https://api.example/v1",
            llm_model="test-model",
            amap_mcp_mode="disabled",
            amap_mcp_url="",
            amap_maps_api_key="",
            database_url="sqlite:///data/test.sqlite",
        )
        client = LLMClient(settings)
        fake_client = FakeClient()
        client._client = fake_client  # type: ignore[assignment]

        response = client._create_chat_completion(
            {"model": "test-model", "messages": [Message(role="user", content="hi").to_openai()]}
        )

        self.assertIsInstance(response, LLMResponse)
        self.assertEqual(response.content, "ok")
        self.assertEqual(fake_client.chat.completions.kwargs["model"], "test-model")
