import re
import time
import logging
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq

from app.ai.llm.base import BaseLLM
from app.config.settings import settings

logger = logging.getLogger("app.llm")


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
            max_tokens=512,  # Voice replies are 1-2 sentences; 512 tokens is more than enough
        )
        self._max_retries = 2
        self._base_wait = 6  # seconds

    def _extract_wait_seconds(self, error_msg: str) -> float:
        """Parse the retry wait time from a Groq 429 error message."""
        match = re.search(r'try again in ([\d.]+)s', str(error_msg))
        if match:
            return float(match.group(1)) + 0.5  # add small buffer
        return self._base_wait

    def invoke(
        self,
        messages: list[BaseMessage],
    ) -> str:
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self.llm.invoke(messages)
                return response.content.strip()
            except Exception as e:
                last_error = e
                if "429" in str(e) and attempt < self._max_retries:
                    wait = self._extract_wait_seconds(str(e))
                    logger.warning(f"[GroqLLM] 429 rate limit on invoke (attempt {attempt+1}). Waiting {wait:.1f}s...")
                    time.sleep(wait)
                else:
                    raise
        raise last_error

    def stream(
        self,
        messages: list[BaseMessage],
    ):
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                for chunk in self.llm.stream(messages):
                    if chunk.content:
                        yield chunk.content
                return  # success
            except Exception as e:
                last_error = e
                if "429" in str(e) and attempt < self._max_retries:
                    wait = self._extract_wait_seconds(str(e))
                    logger.warning(f"[GroqLLM] 429 rate limit on stream (attempt {attempt+1}). Waiting {wait:.1f}s...")
                    time.sleep(wait)
                else:
                    raise
        raise last_error