import re
import time
import logging
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq

from app.ai.llm.base import BaseLLM
from app.config.settings import settings
from app.ai.utils.token_estimator import estimate_tokens

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
        prompt_text = "".join(getattr(msg, "content", "") or "" for msg in messages)
        prompt_tokens = estimate_tokens(prompt_text)
        
        start_time = time.perf_counter()
        last_error = None
        retry_count = 0
        
        # Optimize retries based on fallback availability
        has_fallback = bool(settings.openrouter_api_key)
        max_retries = 1 if has_fallback else self._max_retries

        for attempt in range(max_retries + 1):
            if attempt > 0:
                retry_count += 1
            try:
                response = self.llm.invoke(messages)
                res_content = response.content.strip()
                
                # Log success metrics without sensitive content
                latency = time.perf_counter() - start_time
                response_tokens = estimate_tokens(res_content)
                logger.info(
                    f"[LLM Metrics] provider=groq, model={self.llm.model_name}, "
                    f"prompt_tokens={prompt_tokens}, response_tokens={response_tokens}, "
                    f"retry_count={retry_count}, latency={latency:.3f}s"
                )
                return res_content
            except Exception as e:
                last_error = e
                # Check if retry on 429 is allowed
                if "429" in str(e) and attempt < max_retries:
                    wait = self._extract_wait_seconds(str(e))
                    # Prevent users from waiting for long retry delays if fallback is available
                    if has_fallback and wait > 2.0:
                        logger.warning(
                            f"[GroqLLM] 429 rate limit. Wait of {wait:.1f}s is too long. "
                            f"Aborting retry to trigger immediate OpenRouter fallback."
                        )
                        raise
                    
                    logger.warning(
                        f"[GroqLLM] 429 rate limit on invoke (attempt {attempt+1}). "
                        f"Waiting {wait:.1f}s before short retry..."
                    )
                    time.sleep(wait)
                else:
                    # Log error details and raise
                    latency = time.perf_counter() - start_time
                    logger.error(
                        f"[LLM Error] provider=groq, model={self.llm.model_name}, "
                        f"prompt_tokens={prompt_tokens}, retry_count={retry_count}, "
                        f"latency={latency:.3f}s, error={type(e).__name__}"
                    )
                    raise
        raise last_error

    def stream(
        self,
        messages: list[BaseMessage],
    ):
        prompt_text = "".join(getattr(msg, "content", "") or "" for msg in messages)
        prompt_tokens = estimate_tokens(prompt_text)
        
        start_time = time.perf_counter()
        last_error = None
        retry_count = 0
        
        # Optimize retries based on fallback availability
        has_fallback = bool(settings.openrouter_api_key)
        max_retries = 1 if has_fallback else self._max_retries

        for attempt in range(max_retries + 1):
            if attempt > 0:
                retry_count += 1
            try:
                collected_chunks = []
                for chunk in self.llm.stream(messages):
                    if chunk.content:
                        collected_chunks.append(chunk.content)
                        yield chunk.content
                
                # Log success metrics on completion
                latency = time.perf_counter() - start_time
                response_content = "".join(collected_chunks)
                response_tokens = estimate_tokens(response_content)
                logger.info(
                    f"[LLM Metrics] provider=groq, model={self.llm.model_name}, "
                    f"prompt_tokens={prompt_tokens}, response_tokens={response_tokens}, "
                    f"retry_count={retry_count}, latency={latency:.3f}s"
                )
                return  # success
            except Exception as e:
                last_error = e
                # Check if retry on 429 is allowed
                if "429" in str(e) and attempt < max_retries:
                    wait = self._extract_wait_seconds(str(e))
                    # Prevent users from waiting for long retry delays if fallback is available
                    if has_fallback and wait > 2.0:
                        logger.warning(
                            f"[GroqLLM] 429 rate limit on stream. Wait of {wait:.1f}s is too long. "
                            f"Aborting retry to trigger immediate OpenRouter fallback."
                        )
                        raise
                    
                    logger.warning(
                        f"[GroqLLM] 429 rate limit on stream (attempt {attempt+1}). "
                        f"Waiting {wait:.1f}s before short retry..."
                    )
                    time.sleep(wait)
                else:
                    # Log error details and raise
                    latency = time.perf_counter() - start_time
                    logger.error(
                        f"[LLM Error] provider=groq, model={self.llm.model_name}, "
                        f"prompt_tokens={prompt_tokens}, retry_count={retry_count}, "
                        f"latency={latency:.3f}s, error={type(e).__name__}"
                    )
                    raise
        raise last_error