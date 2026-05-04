from __future__ import annotations

from typing import Any

import httpx

from src.config.settings import get_settings


class OpenRouterService:
    def __init__(self) -> None:
        self.settings = get_settings()

    @staticmethod
    def _ensure_ascii_header(value: str, header_name: str) -> str:
        """Garante que valores de header sejam ASCII válidos para transporte HTTP."""
        sanitized = value.strip()
        try:
            sanitized.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError(f"Header '{header_name}' contém caracteres não-ASCII: {sanitized!r}") from exc
        return sanitized

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        api_key = self.settings.openrouter_api_key.strip()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://cuidafamilia.app",
            "X-Title": "CuidaFamilia",
        }
        payload: dict[str, Any] = {
            "model": self.settings.openrouter_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                f"{self.settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
