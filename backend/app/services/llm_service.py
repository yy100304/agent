"""统一的 LLM Service.

- 兼容 OpenAI 风格 API（通过环境变量配置模型与地址）
- 未配置 API Key 或调用失败时，调用方必须降级处理
"""
import json
from typing import Any, List, Optional

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger


class LLMService:
    """大模型服务：chat / structured_output.

    所有方法在失败时返回 None（不抛异常），
    调用方据此降级为规则/题库方案。
    """

    def __init__(self) -> None:
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.model = settings.LLM_MODEL
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        """是否配置了有效 API Key（跳过占位符值）."""
        if self._available is None:
            key = (self.api_key or "").strip()
            self._available = bool(key) and not key.startswith("sk-your")
        return self._available

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        """普通对话，失败返回 None."""
        if not self.available:
            return None
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"LLM chat 调用失败（将降级处理）：{e}")
            return None

    def structured_output(
        self,
        messages: List[dict],
        schema_model: type[BaseModel],
        temperature: float = 0.3,
    ) -> Optional[Any]:
        """要求模型输出 JSON 并解析为 schema_model 实例，失败返回 None."""
        schema_str = json.dumps(schema_model.model_json_schema(), ensure_ascii=False)
        system_hint = {
            "role": "system",
            "content": (
                "你必须只输出一个合法的 JSON 对象，不要输出任何其他文字、"
                f"不要使用 markdown 代码块。JSON 必须符合以下结构：\n{schema_str}"
            ),
        }
        content = self.chat(
            [system_hint] + messages, temperature=temperature, max_tokens=3000
        )
        if not content:
            return None
        # 容错：去掉可能的 ```json ``` 包裹
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        try:
            return schema_model.model_validate_json(text)
        except Exception as e:
            logger.warning(f"LLM structured_output 解析失败：{e}")
            return None


# 模块级单例
llm_service = LLMService()