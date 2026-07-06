from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq

from app.ai.llm.base import BaseLLM
from app.config.settings import settings


class GroqLLM(BaseLLM):

    def __init__(self):

        self.llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            temperature=0,
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