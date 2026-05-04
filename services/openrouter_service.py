from __future__ import annotations

from typing import Any

import httpx

from src.config.settings import get_settings


class OpenRouterService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://cuidafamilia.app",
            "X-Title": "CuidaFamília",
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
            response = await client.post(f"{self.settings.openrouter_base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
