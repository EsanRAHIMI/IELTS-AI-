"""Concrete AI providers: OpenAI, Anthropic, Ollama."""
from __future__ import annotations
import logging

import httpx

from config import settings
from ai.base import AIProvider

logger = logging.getLogger("ielts.ai")


class OpenAIProvider(AIProvider):
    name = "openai"

    @property
    def configured(self) -> bool:
        return bool(settings.openai_api_key)

    async def complete(self, prompt: str, *, system: str | None = None, json_mode: bool = False) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        kwargs: dict = {"model": settings.openai_model, "messages": messages, "temperature": 0.3}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""


class AnthropicProvider(AIProvider):
    name = "anthropic"

    @property
    def configured(self) -> bool:
        return bool(settings.anthropic_api_key)

    async def complete(self, prompt: str, *, system: str | None = None, json_mode: bool = False) -> str:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        sys = system or ""
        if json_mode:
            sys = (sys + "\nRespond ONLY with valid JSON, no prose.").strip()
        resp = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2000,
            temperature=0.3,
            system=sys or None,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts)


class OllamaProvider(AIProvider):
    name = "ollama"

    @property
    def configured(self) -> bool:
        return bool(settings.ollama_base_url)

    async def complete(self, prompt: str, *, system: str | None = None, json_mode: bool = False) -> str:
        payload: dict = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3},
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{settings.ollama_base_url.rstrip('/')}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")
