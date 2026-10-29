"""模型网关：走 OpenRouter 的 recursive/flint-v1.0:free（OpenAI 兼容接口）。"""

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.config import openrouter_ready, settings
from app.llm.prompt import SYSTEM_PROMPT


class ModelGateway:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    @property
    def enabled(self) -> bool:
        """Key 没填时返回 False，调用方退回“原文摘录”，避免直接 401 报错。"""
        return openrouter_ready()

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                default_headers={
                    "HTTP-Referer": settings.openrouter_app_url,
                    "X-Title": settings.openrouter_app_name,
                },
            )
        return self._client

    async def astream(self, prompt: str) -> AsyncIterator[str]:
        stream = await self._get_client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            stream=True,
            temperature=0.2,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


gateway = ModelGateway()
