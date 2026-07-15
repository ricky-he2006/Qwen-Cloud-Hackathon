"""
LLM client wrapper for OpenAI-compatible APIs.
Supports Qwen Cloud (DashScope) and local LLMs (Ollama) via the OpenAI SDK.
"""

from typing import Any, Dict, Generator, List, Optional

from openai import AsyncOpenAI, OpenAI

from config import settings


def _dashscope_extra_body(*, stream: bool) -> Optional[Dict[str, Any]]:
    """
    Qwen3.x hybrid-thinking models require enable_thinking=false for
    non-streaming chat.completions calls on DashScope.
    """
    base = settings.API_BASE_URL.lower()
    model = settings.MODEL_NAME.lower()
    if "dashscope" not in base and "aliyuncs.com" not in base:
        return None
    if not any(x in model for x in ("qwen3", "qwen-plus", "qwen-max", "qwen-turbo")):
        return None
    if stream:
        return None
    return {"enable_thinking": False}


class Message:
    """Represents a chat message."""

    def __init__(self, role: str, content: str, name: Optional[str] = None):
        self.role = role
        self.content = content
        self.name = name


class LLMClient:
    """Client for interacting with OpenAI-compatible LLM APIs."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.MODEL_NAME
        self.total_tokens: int = 0
        timeout = float(getattr(settings, "LLM_TIMEOUT", 120.0))

        self.client = OpenAI(
            base_url=settings.API_BASE_URL,
            api_key=settings.API_KEY,
            timeout=timeout,
        )
        self.async_client = AsyncOpenAI(
            base_url=settings.API_BASE_URL,
            api_key=settings.API_KEY,
            timeout=timeout,
        )

    @staticmethod
    def _build_messages(
        messages: List,
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        msg_list: List[Dict[str, str]] = []
        if system_prompt:
            msg_list.append({"role": "system", "content": system_prompt})

        for msg in messages:
            if isinstance(msg, Message):
                msg_dict = {"role": msg.role, "content": msg.content}
                if msg.name:
                    msg_dict["name"] = msg.name
            else:
                msg_dict = {"role": msg["role"], "content": msg["content"]}
                if msg.get("name"):
                    msg_dict["name"] = msg["name"]
            msg_list.append(msg_dict)
        return msg_list

    def _completion_kwargs(
        self,
        msg_list: List[Dict[str, str]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        *,
        stream: bool = False,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "messages": msg_list,
            "model": self.model_name,
        }
        if stream:
            kwargs["stream"] = True
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        extra = _dashscope_extra_body(stream=stream)
        if extra:
            kwargs["extra_body"] = extra
        return kwargs

    @staticmethod
    def _extract_content(response) -> str:
        try:
            content = response.choices[0].message.content
        except (IndexError, AttributeError) as e:
            raise RuntimeError(f"LLM returned empty/invalid response: {e}") from e
        return (content or "").strip()

    def generate(
        self,
        messages: List,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        msg_list = self._build_messages(messages, system_prompt)
        kwargs = self._completion_kwargs(msg_list, temperature, max_tokens)

        try:
            response = self.client.chat.completions.create(**kwargs)
            if getattr(response, "usage", None):
                self.total_tokens += response.usage.total_tokens or 0
            content = self._extract_content(response)
            if not content:
                raise RuntimeError("LLM returned empty content")
            return content
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"LLM generation failed: {e}") from e

    async def generate_async(
        self,
        messages: List,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        msg_list = self._build_messages(messages, system_prompt)
        kwargs = self._completion_kwargs(msg_list, temperature, max_tokens)

        try:
            response = await self.async_client.chat.completions.create(**kwargs)
            if getattr(response, "usage", None):
                self.total_tokens += response.usage.total_tokens or 0
            content = self._extract_content(response)
            if not content:
                raise RuntimeError("LLM returned empty content")
            return content
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"LLM generation failed: {e}") from e

    def generate_stream(
        self,
        messages: List,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        msg_list = self._build_messages(messages, system_prompt)
        kwargs = self._completion_kwargs(msg_list, temperature, max_tokens, stream=True)

        try:
            response = self.client.chat.completions.create(**kwargs)
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise RuntimeError(f"LLM streaming failed: {e}") from e


llm = LLMClient()
