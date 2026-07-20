import openai
from langchain_core.messages import BaseMessage

from app.ai.llm.base import BaseLLM
from app.config.settings import settings


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
        openai_messages = self._convert_messages(messages)
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
        return response.choices[0].message.content.strip()

    def stream(
        self,
        messages: list[BaseMessage],
    ):
        openai_messages = self._convert_messages(messages)
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
        for chunk in response_stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
