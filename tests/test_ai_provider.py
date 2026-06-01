from __future__ import annotations

import json
import unittest

from unreal_utility_tool.ai_provider import (
    AiProviderConfig,
    AiProviderError,
    OpenAiCompatibleClient,
    api_key_status,
    chat_completions_url,
    extract_chat_message,
    generate_tool_with_repair,
)


class FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, user_prompt: str, system_prompt: str = ""):
        self.prompts.append(user_prompt)
        content = self.responses.pop(0)
        return type(
            "FakeResponse",
            (),
            {
                "content": content,
                "raw_response": json.dumps({"choices": [{"message": {"content": content}}]}),
                "request_url": "fake",
                "model": "fake-model",
            },
        )()


class AiProviderTests(unittest.TestCase):
    def test_missing_api_key_reports_env_names_without_request(self) -> None:
        config = AiProviderConfig(
            base_url="https://example.test/v1",
            model="test-model",
            api_key_env="DEEPSEEK_API_KEY",
        )
        client = OpenAiCompatibleClient(config, environ={})

        with self.assertRaises(AiProviderError) as context:
            client.complete("hello")

        self.assertIn("DEEPSEEK_API_KEY", str(context.exception))
        self.assertIn("EDITORBINDER_API_KEY", str(context.exception))

    def test_api_key_status_uses_primary_or_editorbinder_fallback(self) -> None:
        config = AiProviderConfig(api_key_env="DEEPSEEK_API_KEY")

        self.assertEqual(api_key_status(config, {"EDITORBINDER_API_KEY": "x"})[0], True)
        self.assertEqual(api_key_status(config, {})[0], False)

    def test_chat_url_adds_chat_completions_suffix(self) -> None:
        self.assertEqual(
            chat_completions_url("https://openrouter.ai/api/v1"),
            "https://openrouter.ai/api/v1/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("https://api.deepseek.com/chat/completions"),
            "https://api.deepseek.com/chat/completions",
        )

    def test_extract_chat_message_supports_openai_shape(self) -> None:
        raw = json.dumps({"choices": [{"message": {"content": "hello"}}]})

        self.assertEqual(extract_chat_message(raw), "hello")

    def test_successful_generation_returns_parsed_tool(self) -> None:
        response = """<<<UUT_NAME>>>
Generated Tool
<<<UUT_NOTES>>>
None
<<<UUT_CODE>>>
import unreal
unreal.log("ok")
<<<UUT_END>>>"""
        result = generate_tool_with_repair(
            AiProviderConfig(),
            "make a tool",
            client=FakeClient([response]),
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.parsed)
        self.assertEqual(result.parsed.name, "Generated Tool")
        self.assertFalse(result.repaired)

    def test_malformed_generation_runs_one_repair(self) -> None:
        bad = "Name: Broken\nCode:\nif True\n    pass"
        fixed = """<<<UUT_NAME>>>
Fixed Tool
<<<UUT_NOTES>>>
None
<<<UUT_CODE>>>
import unreal
unreal.log("fixed")
<<<UUT_END>>>"""
        fake = FakeClient([bad, fixed])

        result = generate_tool_with_repair(AiProviderConfig(), "make a tool", client=fake)

        self.assertTrue(result.ok)
        self.assertTrue(result.repaired)
        self.assertEqual(len(fake.prompts), 2)
        self.assertIn("Repair this EditorBinder", fake.prompts[1])

    def test_second_failure_returns_copyable_error(self) -> None:
        fake = FakeClient(["bad", "still bad"])

        result = generate_tool_with_repair(AiProviderConfig(), "make a tool", client=fake)

        self.assertFalse(result.ok)
        self.assertTrue(result.repaired)
        self.assertIn("still invalid after one repair", result.error)
        self.assertEqual(len(fake.prompts), 2)


if __name__ == "__main__":
    unittest.main()
