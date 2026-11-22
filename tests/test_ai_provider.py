from __future__ import annotations

import io
import json
import urllib.error
import unittest
from unittest.mock import patch

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

    def test_chat_completions_url_remote_https_succeeds(self) -> None:
        self.assertEqual(
            chat_completions_url("https://api.openai.com/v1"),
            "https://api.openai.com/v1/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("https://api.deepseek.com"),
            "https://api.deepseek.com/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("https://api.deepseek.com/"),
            "https://api.deepseek.com/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("https://api.deepseek.com/chat/completions"),
            "https://api.deepseek.com/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("https://api.deepseek.com/chat/completions/"),
            "https://api.deepseek.com/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("https://api.example.com/v1?api-version=2025-01-01"),
            "https://api.example.com/v1/chat/completions?api-version=2025-01-01",
        )
        self.assertEqual(
            chat_completions_url("https://api.example.com/v1/chat/completions?api-version=2025-01-01"),
            "https://api.example.com/v1/chat/completions?api-version=2025-01-01",
        )

    def test_chat_completions_url_local_loopback_http_succeeds(self) -> None:
        self.assertEqual(
            chat_completions_url("http://localhost:11434/v1"),
            "http://localhost:11434/v1/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("http://127.0.0.1:1234/v1"),
            "http://127.0.0.1:1234/v1/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("http://[::1]:8080/v1"),
            "http://[::1]:8080/v1/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("http://localhost:11434/chat/completions"),
            "http://localhost:11434/chat/completions",
        )

    def test_chat_completions_url_rejects_remote_http(self) -> None:
        remote_urls = (
            "http://api.openai.com/v1",
            "http://api.deepseek.com",
            "http://example.com/v1",
            "http://192.168.1.100:8000/v1",
        )
        for url in remote_urls:
            with self.subTest(url=url):
                with self.assertRaises(AiProviderError) as ctx:
                    chat_completions_url(url)
                self.assertEqual(
                    str(ctx.exception),
                    "Insecure HTTP is only permitted for local loopback hosts (localhost, 127.0.0.1). Use HTTPS for remote providers.",
                )

    def test_chat_completions_url_rejects_non_http_schemes(self) -> None:
        cases = (
            ("file:///etc/hosts", "file"),
            ("ftp://files.example.com/v1", "ftp"),
            ("data:text/plain;base64,SGVsbG8=", "data"),
            ("api.openai.com/v1", ""),
            ("   ", ""),
        )
        for url, expected_scheme in cases:
            with self.subTest(url=url):
                with self.assertRaises(AiProviderError) as ctx:
                    chat_completions_url(url)
                self.assertEqual(
                    str(ctx.exception),
                    f"Unsupported AI base URL scheme: '{expected_scheme}'. Use https or http.",
                )

    def test_chat_completions_url_rejects_malformed_urls(self) -> None:
        malformed_urls = (
            "https://",
            "http://",
            "http://:8080",
            "http://[::1",
            "http://[invalid-ipv6]",
        )
        for url in malformed_urls:
            with self.subTest(url=url):
                with self.assertRaises(AiProviderError):
                    chat_completions_url(url)

    def test_client_complete_rejects_insecure_remote_http(self) -> None:
        config = AiProviderConfig(
            base_url="http://api.openai.com/v1",
            model="gpt-4o",
            api_key_env="OPENAI_API_KEY",
        )
        client = OpenAiCompatibleClient(config, environ={"OPENAI_API_KEY": "sk-test"})
        with self.assertRaises(AiProviderError) as ctx:
            client.complete("hello")
        self.assertIn("Insecure HTTP is only permitted for local loopback hosts", str(ctx.exception))

    def test_extract_chat_message_supports_openai_shape(self) -> None:
        raw = json.dumps({"choices": [{"message": {"content": "hello"}}]})

        self.assertEqual(extract_chat_message(raw), "hello")

    def test_extract_chat_message_rejects_token_truncated_response(self) -> None:
        raw = json.dumps(
            {"choices": [{"finish_reason": "length", "message": {"content": "import unreal\n# partial"}}]}
        )
        with self.assertRaisesRegex(AiProviderError, "truncated at the output token limit"):
            extract_chat_message(raw)

    def test_http_error_redacts_api_key_from_response_body(self) -> None:
        secret = "sk-test-secret-123"
        error = urllib.error.HTTPError(
            "https://api.example.test/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            io.BytesIO(f'{{"error":"invalid token {secret}"}}'.encode("utf-8")),
        )
        client = OpenAiCompatibleClient(
            AiProviderConfig(base_url="https://api.example.test/v1", model="test"),
            environ={"EDITORBINDER_API_KEY": secret},
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(AiProviderError) as context:
                client._post_json("https://api.example.test/v1/chat/completions", {}, secret)
        self.assertNotIn(secret, str(context.exception))
        self.assertIn("[REDACTED]", str(context.exception))

    def test_url_error_wrapped_timeout_has_timeout_message(self) -> None:
        client = OpenAiCompatibleClient(
            AiProviderConfig(base_url="https://api.example.test/v1", model="test"),
            environ={"EDITORBINDER_API_KEY": "secret"},
        )
        wrapped_timeout = urllib.error.URLError(TimeoutError("timed out"))
        with patch("urllib.request.urlopen", side_effect=wrapped_timeout):
            with self.assertRaisesRegex(AiProviderError, "AI request timed out"):
                client._post_json("https://api.example.test/v1/chat/completions", {}, "secret")

    def test_client_rejects_non_finite_or_out_of_range_temperature(self) -> None:
        for temperature in (-5.0, 2.1, float("nan"), float("inf")):
            with self.subTest(temperature=temperature):
                client = OpenAiCompatibleClient(
                    AiProviderConfig(base_url="https://api.example.test/v1", model="test", temperature=temperature),
                    environ={"EDITORBINDER_API_KEY": "secret"},
                )
                with self.assertRaisesRegex(AiProviderError, "temperature must be a finite value between 0 and 2"):
                    client.complete("hello")

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
