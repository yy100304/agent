"""统一的 LLM Service.

- 兼容 OpenAI 风格 API（通过环境变量配置模型与地址）
- 未配置 API Key 或调用失败时，调用方必须降级处理
"""
import json
from typing import Any, AsyncIterator, List, Optional

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
        # 复用连接：出题会并发/多轮调用，省掉每次的 TCP + TLS 握手
        self._client = httpx.Client(
            timeout=self.REQUEST_TIMEOUT,
            limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
        )

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

    # 推理模型会把预算先花在 reasoning_content 上，content 为空时需要放大预算重试
    MAX_TOKENS_LIMIT = 16000
    REQUEST_TIMEOUT = 60

    def chat(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        """普通对话，失败返回 None.

        针对推理模型（如 deepseek 推理版）做了空内容兜底：当 content 为空
        （预算被 reasoning_content 消耗）时，自动放大 token 预算重试一次。
        """
        if not self.available:
            return None

        content = self._chat_once(messages, temperature, max_tokens)
        if content is None or content.strip():
            return content

        bigger = min(max(max_tokens * 3, 6000), self.MAX_TOKENS_LIMIT)
        if bigger <= max_tokens:
            return content
        logger.warning(
            f"LLM 返回空内容（max_tokens={max_tokens}），"
            f"放大到 {bigger} 重试一次"
        )
        retry = self._chat_once(messages, temperature, bigger)
        if retry is not None and retry.strip():
            return retry
        return content

    def _chat_once(
        self,
        messages: List[dict],
        temperature: float,
        max_tokens: int,
    ) -> Optional[str]:
        """单次请求；网络/接口异常返回 None."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = self._client.post(
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

    async def astream_chat(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        """流式对话：按 token 增量产出文本片段（失败时产出空序列，调用方降级）.

        与 `chat` 的区别：不等待整段生成完成，首字延迟约等于模型 TTFT，
        前端可以边生成边展示，显著降低「等待感」。
        """
        if not self.available:
            return

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            choice = (chunk.get("choices") or [{}])[0]
                            text = (choice.get("delta") or {}).get("content") or ""
                        except Exception:  # 单行解析失败不影响整体流
                            continue
                        if text:
                            yield text
        except Exception as e:
            logger.warning(f"LLM 流式调用失败（将降级处理）：{e}")
            return

    def structured_output(
        self,
        messages: List[dict],
        schema_model: type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 3000,
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
            [system_hint] + messages, temperature=temperature, max_tokens=max_tokens
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