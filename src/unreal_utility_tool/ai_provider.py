from __future__ import annotations

import ipaddress
import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Sequence

from .ai_parser import ParsedAiTool, parse_ai_tool_response
from .prompts import PromptExample, build_ai_prompt, build_generation_repair_prompt
from .validation import validate_tool_code, validate_tool_fields


DEFAULT_PROVIDER = "Custom OpenAI-Compatible"
DEFAULT_API_KEY_ENV = "EDITORBINDER_API_KEY"
SYSTEM_PROMPT = (
    "You generate small Unreal Engine Python Console tools for EditorBinder. "
    "Return only the requested marker format."
)


@dataclass(frozen=True, slots=True)
class AiProviderPreset:
    name: str
    base_url: str
    model: str
    api_key_env: str


PROVIDER_PRESETS: tuple[AiProviderPreset, ...] = (
    AiProviderPreset(DEFAULT_PROVIDER, "", "", DEFAULT_API_KEY_ENV),
    AiProviderPreset("DeepSeek", "https://api.deepseek.com", "deepseek-v4-flash", "DEEPSEEK_API_KEY"),
    AiProviderPreset("OpenRouter", "https://openrouter.ai/api/v1", "", "OPENROUTER_API_KEY"),
    AiProviderPreset("OpenAI", "https://api.openai.com/v1", "", "OPENAI_API_KEY"),
)


@dataclass(frozen=True, slots=True)
class AiProviderConfig:
    provider: str = DEFAULT_PROVIDER
    base_url: str = ""
    model: str = ""
    api_key_env: str = DEFAULT_API_KEY_ENV
    timeout_seconds: int = 45
    temperature: float = 0.2
    max_tokens: int = 3000


@dataclass(frozen=True, slots=True)
class AiProviderResponse:
    content: str
    raw_response: str
    request_url: str
    model: str


@dataclass(frozen=True, slots=True)
class AiToolGenerationResult:
    ok: bool
    response_text: str
    raw_response_text: str
    parsed: ParsedAiTool | None
    diagnostics: tuple[str, ...]
    repaired: bool = False
    error: str = ""


class AiProviderError(RuntimeError):
    pass


class MissingApiKeyError(AiProviderError):
    pass


class OpenAiCompatibleClient:
    def __init__(
        self,
        config: AiProviderConfig,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.config = config
        self.environ = os.environ if environ is None else environ

    def complete(self, user_prompt: str, system_prompt: str = SYSTEM_PROMPT) -> AiProviderResponse:
        base_url = self.config.base_url.strip()
        model = self.config.model.strip()
        if not base_url:
            raise AiProviderError("AI base URL is required.")
        if not model:
            raise AiProviderError("AI model is required.")

        temperature = float(self.config.temperature)
        if not math.isfinite(temperature) or not 0.0 <= temperature <= 2.0:
            raise AiProviderError("AI temperature must be a finite value between 0 and 2.")

        api_key = self._api_key()
        request_url = chat_completions_url(base_url)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": int(self.config.max_tokens),
            "stream": False,
        }
        raw_response = self._post_json(request_url, payload, api_key)
        try:
            content = extract_chat_message(raw_response)
        except AiProviderError as exc:
            raise AiProviderError(_redact_secret(str(exc), api_key)) from exc
        return AiProviderResponse(content=content, raw_response=raw_response, request_url=request_url, model=model)

    def _api_key(self) -> str:
        for env_name in api_key_env_candidates(self.config.api_key_env):
            value = self.environ.get(env_name, "").strip()
            if value:
                return value
        names = " or ".join(api_key_env_candidates(self.config.api_key_env))
        raise MissingApiKeyError(f"Missing API key. Set {names} in environment variables.")

    def _post_json(self, url: str, payload: dict[str, object], api_key: str) -> str:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=max(1, int(self.config.timeout_seconds))) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            detail = _redact_secret(detail, api_key)
            suffix = f": {detail[:800]}" if detail else ""
            raise AiProviderError(f"AI HTTP error {exc.code}{suffix}") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise AiProviderError("AI request timed out.") from exc
            reason = _redact_secret(str(exc.reason), api_key)
            raise AiProviderError(f"AI connection error: {reason}") from exc
        except TimeoutError as exc:
            raise AiProviderError("AI request timed out.") from exc
        except OSError as exc:
            detail = _redact_secret(str(exc), api_key)
            raise AiProviderError(f"AI request failed: {detail}") from exc


def provider_names() -> list[str]:
    return [preset.name for preset in PROVIDER_PRESETS]


def provider_preset(name: str) -> AiProviderPreset:
    normalized = name.strip().casefold()
    for preset in PROVIDER_PRESETS:
        if preset.name.casefold() == normalized:
            return preset
    return PROVIDER_PRESETS[0]


def api_key_env_candidates(primary: str) -> tuple[str, ...]:
    cleaned = "".join(char for char in str(primary or "").strip() if char.isalnum() or char == "_")
    names = [cleaned or DEFAULT_API_KEY_ENV]
    if DEFAULT_API_KEY_ENV not in names:
        names.append(DEFAULT_API_KEY_ENV)
    return tuple(names)


def api_key_status(config: AiProviderConfig, environ: Mapping[str, str] | None = None) -> tuple[bool, str]:
    source = os.environ if environ is None else environ
    for env_name in api_key_env_candidates(config.api_key_env):
        if source.get(env_name, "").strip():
            return True, f"API key found in {env_name}."
    names = " or ".join(api_key_env_candidates(config.api_key_env))
    return False, f"Set {names} before using Generate."


_LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}


def _is_loopback_host(hostname: str) -> bool:
    if not hostname:
        return False
    if hostname in _LOOPBACK_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def chat_completions_url(base_url: str) -> str:
    cleaned = base_url.strip()
    try:
        parsed = urllib.parse.urlparse(cleaned)
    except ValueError as exc:
        raise AiProviderError(f"Invalid AI base URL: {exc}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise AiProviderError(f"Unsupported AI base URL scheme: '{scheme}'. Use https or http.")

    try:
        hostname = (parsed.hostname or "").lower()
    except ValueError as exc:
        raise AiProviderError(f"Invalid AI base URL host: {exc}") from exc

    if not parsed.netloc or not hostname:
        raise AiProviderError("AI base URL must include a valid host.")

    if scheme == "http" and not _is_loopback_host(hostname):
        raise AiProviderError(
            "Insecure HTTP is only permitted for local loopback hosts (localhost, 127.0.0.1). Use HTTPS for remote providers."
        )

    path = parsed.path.rstrip("/")
    if not path.endswith("/chat/completions"):
        path = f"{path}/chat/completions" if path else "/chat/completions"
    return urllib.parse.urlunparse(parsed._replace(path=path))


def _redact_secret(value: str, secret: str) -> str:
    if not secret:
        return value
    return value.replace(secret, "[REDACTED]")


def extract_chat_message(raw_response: str) -> str:
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise AiProviderError(f"AI returned invalid JSON: {exc}") from exc

    if isinstance(payload, dict) and payload.get("error"):
        raise AiProviderError(f"AI error: {payload['error']}")

    choices = payload.get("choices") if isinstance(payload, dict) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        finish_reason = str(choices[0].get("finish_reason") or "").casefold()
        if finish_reason in {"length", "max_tokens"}:
            raise AiProviderError(
                "AI response was truncated at the output token limit. Increase Max tokens or shorten the request."
            )

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AiProviderError("AI response did not contain choices[0].message.content.") from exc

    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    parts.append(value)
        text = "\n".join(parts).strip()
    else:
        text = ""

    if not text:
        raise AiProviderError("AI response content was empty.")
    return text


def generate_tool_with_repair(
    config: AiProviderConfig,
    tool_request: str,
    examples: Sequence[PromptExample] = (),
    *,
    client: OpenAiCompatibleClient | None = None,
    tool_type: str = "",
) -> AiToolGenerationResult:
    active_client = client or OpenAiCompatibleClient(config)
    prompt = build_ai_prompt(tool_request=tool_request, examples=examples, tool_type=tool_type)
    first_response = active_client.complete(prompt)
    first_parsed = parse_ai_tool_response(first_response.content)
    first_errors = validate_generated_tool(first_parsed)
    if not first_errors:
        return AiToolGenerationResult(
            ok=True,
            response_text=first_response.content,
            raw_response_text=first_response.raw_response,
            parsed=first_parsed,
            diagnostics=first_parsed.diagnostics,
        )

    repair_prompt = build_generation_repair_prompt(
        tool_request,
        first_response.content,
        first_errors,
        examples=examples,
        tool_type=tool_type,
    )
    repair_response = active_client.complete(repair_prompt)
    repair_parsed = parse_ai_tool_response(repair_response.content)
    repair_errors = validate_generated_tool(repair_parsed)
    if not repair_errors:
        return AiToolGenerationResult(
            ok=True,
            response_text=repair_response.content,
            raw_response_text=repair_response.raw_response,
            parsed=repair_parsed,
            diagnostics=repair_parsed.diagnostics,
            repaired=True,
        )

    return AiToolGenerationResult(
        ok=False,
        response_text=repair_response.content,
        raw_response_text=repair_response.raw_response,
        parsed=repair_parsed,
        diagnostics=tuple(repair_errors),
        repaired=True,
        error=f"AI response is still invalid after one repair: {' / '.join(repair_errors)}",
    )


def validate_generated_tool(parsed: ParsedAiTool) -> tuple[str, ...]:
    errors = list(validate_tool_fields(parsed.name, parsed.code))
    if parsed.code.strip():
        syntax = validate_tool_code(parsed.code)
        if not syntax.ok:
            errors.append(syntax.message)
    return tuple(errors)
