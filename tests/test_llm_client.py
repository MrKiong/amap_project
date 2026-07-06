from __future__ import annotations

import unittest
from unittest.mock import patch

from config.settings import Settings
from core.llm_client import LLMClient


class LLMClientTest(unittest.TestCase):
    def test_non_json_success_response_raises_diagnostic_runtime_error(self) -> None:
        class EmptyResponse:
            status = 200
            headers = {"Content-Type": "text/plain"}

            def __enter__(self):  # type: ignore[no-untyped-def]
                return self

            def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
                return False

            def read(self) -> bytes:
                return b""

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

        with patch("urllib.request.urlopen", return_value=EmptyResponse()):
            with self.assertRaisesRegex(RuntimeError, "not valid JSON"):
                LLMClient(settings)._post_chat_completions({"model": "test-model", "messages": []})
