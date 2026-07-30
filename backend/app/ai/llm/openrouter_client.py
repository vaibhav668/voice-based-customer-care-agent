import time
import logging
import openai
from langchain_core.messages import BaseMessage

from app.ai.llm.base import BaseLLM
from app.config.settings import settings
from app.ai.utils.token_estimator import estimate_tokens

logger = logging.getLogger("app.llm")


class OpenRouterLLM(BaseLLM):

    def __init__(self, model: str = None):
        self.client = openai.OpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.model = model or settings.openrouter_model

    def _convert_messages(self, messages: list[BaseMessage]) -> list[dict]:
        converted = []
        for msg in messages:
            # Handle standard langchain message types
            if msg.type == "human":
                role = "user"
            elif msg.type == "system":
                role = "system"
            elif msg.type == "ai":
                role = "assistant"
            else:
                role = "user"
            converted.append({"role": role, "content": msg.content})
        return converted

    def invoke(
        self,
        messages: list[BaseMessage],
    ) -> str:
        prompt_text = "".join(getattr(msg, "content", "") or "" for msg in messages)
        prompt_tokens = estimate_tokens(prompt_text)
        
        start_time = time.perf_counter()
        openai_messages = self._convert_messages(messages)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=0,
                max_tokens=1024,
                extra_headers={
                    "HTTP-Referer": "https://github.com/vaibhav668/voice-based-customer-care-agent",
                    "X-Title": "SupportAI Platform",
                }
            )
            res_content = response.choices[0].message.content.strip()
            
            # Log metrics without raw texts
            latency = time.perf_counter() - start_time
            response_tokens = estimate_tokens(res_content)
            logger.info(
                f"[LLM Metrics] provider=openrouter, model={self.model}, "
                f"prompt_tokens={prompt_tokens}, response_tokens={response_tokens}, "
                f"retry_count=0, latency={latency:.3f}s"
            )
            return res_content
        except Exception as e:
            latency = time.perf_counter() - start_time
            logger.error(
                f"[LLM Error] provider=openrouter, model={self.model}, "
                f"prompt_tokens={prompt_tokens}, retry_count=0, "
                f"latency={latency:.3f}s, error={type(e).__name__}"
            )
            raise

    def stream(
        self,
        messages: list[BaseMessage],
    ):
        prompt_text = "".join(getattr(msg, "content", "") or "" for msg in messages)
        prompt_tokens = estimate_tokens(prompt_text)
        
        start_time = time.perf_counter()
        openai_messages = self._convert_messages(messages)
        try:
            response_stream = self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=0,
                stream=True,
                max_tokens=1024,
                extra_headers={
                    "HTTP-Referer": "https://github.com/vaibhav668/voice-based-customer-care-agent",
                    "X-Title": "SupportAI Platform",
                }
            )
            collected_chunks = []
            for chunk in response_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    val = chunk.choices[0].delta.content
                    collected_chunks.append(val)
                    yield val
            
            # Log metrics after stream completes
            latency = time.perf_counter() - start_time
            response_content = "".join(collected_chunks)
            response_tokens = estimate_tokens(response_content)
            logger.info(
                f"[LLM Metrics] provider=openrouter, model={self.model}, "
                f"prompt_tokens={prompt_tokens}, response_tokens={response_tokens}, "
                f"retry_count=0, latency={latency:.3f}s"
            )
        except Exception as e:
            latency = time.perf_counter() - start_time
            logger.error(
                f"[LLM Error] provider=openrouter, model={self.model}, "
                f"prompt_tokens={prompt_tokens}, retry_count=0, "
                f"latency={latency:.3f}s, error={type(e).__name__}"
            )
            raise
