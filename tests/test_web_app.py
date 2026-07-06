from __future__ import annotations

import unittest

from main import build_parser
from web_app import INDEX_HTML


class WebAppTest(unittest.TestCase):
    def test_index_contains_chat_endpoint(self) -> None:
        self.assertIn("/api/chat", INDEX_HTML)
        self.assertIn("餐饮推荐 Agent 测试台", INDEX_HTML)

    def test_web_command_parser_defaults(self) -> None:
        args = build_parser().parse_args(["web"])
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8765)

    def test_add_preference_parser(self) -> None:
        args = build_parser().parse_args(
            [
                "add-preference",
                "--category",
                "scenario",
                "--preference",
                "一个人吃饭偏好安静小店",
                "--sentiment",
                "like",
                "--weight",
                "3",
            ]
        )

        self.assertEqual(args.category, "scenario")
        self.assertEqual(args.preference, "一个人吃饭偏好安静小店")
        self.assertEqual(args.sentiment, "like")
        self.assertEqual(args.weight, 3)
