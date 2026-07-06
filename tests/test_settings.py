from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from config.settings import get_settings


class SettingsTest(unittest.TestCase):
    def test_loads_single_llm_config_from_env(self) -> None:
        with patch("config.settings.load_dotenv"), patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "llm-key",
                "LLM_BASE_URL": "https://api.example/v1",
                "LLM_MODEL": "example-chat",
            },
            clear=True,
        ):
            settings = get_settings()

        self.assertTrue(settings.llm_configured)
        self.assertEqual(settings.llm_api_key, "llm-key")
        self.assertEqual(settings.llm_base_url, "https://api.example/v1")
        self.assertEqual(settings.llm_model, "example-chat")

    def test_missing_llm_key_is_not_configured(self) -> None:
        with patch("config.settings.load_dotenv"), patch.dict(
            os.environ,
            {
                "LLM_BASE_URL": "https://api.example/v1",
                "LLM_MODEL": "example-chat",
            },
            clear=True,
        ):
            settings = get_settings()

        self.assertFalse(settings.llm_configured)
