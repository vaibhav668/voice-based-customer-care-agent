from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq

from app.ai.llm.base import BaseLLM
from app.config.settings import settings


class GroqLLM(BaseLLM):

    def __init__(self, model: str = None):
        model = model or settings.groq_model
        # Force switch to llama-3.1-8b-instant to avoid rate limits
        if not model or model == "llama-3.3-70b-versatile":
            model = "llama-3.1-8b-instant"

        self.llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=model,
            temperature=0,
            max_retries=0,
            max_tokens=1024,
        )

    def invoke(
        self,
        messages: list[BaseMessage],
    ) -> str:

        response = self.llm.invoke(messages)

        return response.content.strip()

    def stream(
        self,
        messages: list[BaseMessage],
    ):

        for chunk in self.llm.stream(messages):

            if chunk.content:

                yield chunk.content