from abc import ABC, abstractmethod
from langchain_core.messages import BaseMessage


class BaseLLM(ABC):

    @abstractmethod
    def invoke(
        self,
        messages: list[BaseMessage],
    ) -> str:
        ...

    @abstractmethod
    def stream(
        self,
        messages: list[BaseMessage],
    ):
        ...