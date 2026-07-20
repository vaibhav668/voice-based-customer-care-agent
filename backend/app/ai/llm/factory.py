import logging
from langchain_core.messages import BaseMessage
from app.ai.llm.base import BaseLLM
from app.ai.llm.groq_client import GroqLLM
from app.ai.llm.openrouter_client import OpenRouterLLM
from app.config.settings import settings

logger = logging.getLogger("app.llm")

# Global instances cache to prevent client recreation on every request
_groq_cache = {}
_openrouter_cache = {}

def get_groq_client(model: str = None) -> GroqLLM:
    key = model or "default"
    if key not in _groq_cache:
        _groq_cache[key] = GroqLLM(model=model)
    return _groq_cache[key]

def get_openrouter_client(model: str = None) -> OpenRouterLLM:
    key = model or "default"
    if key not in _openrouter_cache:
        _openrouter_cache[key] = OpenRouterLLM(model=model)
    return _openrouter_cache[key]

class RoutingLLM(BaseLLM):
    # Map tasks to optimized models (speed-to-quality ratio)
    TASK_ROUTING = {
        "intent": {
            "provider": "groq",
            "model": "llama-3.1-8b-instant",
            "backup_provider": "openrouter",
            "backup_model": "google/gemini-2.5-flash"
        },
        "understanding": {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",  # high-performance JSON extraction
            "backup_provider": "groq",
            "backup_model": "llama-3.1-8b-instant"
        },
        "rag": {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "backup_provider": "groq",
            "backup_model": "llama-3.1-8b-instant"
        },
        "response": {
            "provider": "groq",
            "model": "llama-3.1-8b-instant",  # low latency streaming for vocal responses
            "backup_provider": "openrouter",
            "backup_model": "google/gemini-2.5-flash"
        },
        "context": {
            "provider": "groq",
            "model": "llama-3.1-8b-instant",
            "backup_provider": "openrouter",
            "backup_model": "google/gemini-2.5-flash"
        },
        "default": {
            "provider": "groq",
            "model": "llama-3.1-8b-instant",
            "backup_provider": "openrouter",
            "backup_model": "google/gemini-2.5-flash"
        }
    }

    def _classify_task_type(self, messages: list[BaseMessage]) -> str:
        text = ""
        for msg in messages:
            text += getattr(msg, "content", "") or ""
        text_lower = text.lower()
        
        if "intent classifier" in text_lower or "classify the user's query" in text_lower:
            return "intent"
        elif "understanding" in text_lower or "extracted entities" in text_lower:
            return "understanding"
        elif "policy" in text_lower or "knowledge base" in text_lower or "faq" in text_lower:
            return "rag"
        elif "empathetic" in text_lower or "customer support agent" in text_lower:
            return "response"
        elif "context" in text_lower or "follow-up" in text_lower:
            return "context"
        return "default"

    def _get_client_for_provider(self, provider: str, model: str) -> BaseLLM:
        if provider == "groq":
            return get_groq_client(model)
        elif provider == "openrouter":
            return get_openrouter_client(model)
        raise ValueError(f"Unknown provider: {provider}")

    def _get_active_clients(self, messages: list[BaseMessage]) -> tuple[BaseLLM, BaseLLM]:
        # Classify the task type
        task = self._classify_task_type(messages)
        routing = self.TASK_ROUTING.get(task, self.TASK_ROUTING["default"])
        
        # Override providers if setting forces it, but keep the model optimization if possible
        configured_provider = settings.llm_provider.lower()
        
        primary_provider = routing["provider"]
        primary_model = routing["model"]
        backup_provider = routing["backup_provider"]
        backup_model = routing["backup_model"]
        
        if configured_provider == "groq" and primary_provider != "groq":
            # Force primary to be Groq
            primary_provider = "groq"
            primary_model = settings.groq_model
        elif configured_provider == "openrouter" and primary_provider != "openrouter":
            # Force primary to be OpenRouter
            primary_provider = "openrouter"
            primary_model = settings.openrouter_model
            
        primary_client = self._get_client_for_provider(primary_provider, primary_model)
        
        # Determine backup client
        backup_client = None
        if settings.openrouter_api_key and (backup_provider or backup_model):
            backup_client = self._get_client_for_provider(backup_provider, backup_model)
            
        return primary_client, backup_client

    def invoke(self, messages: list[BaseMessage]) -> str:
        primary, backup = self._get_active_clients(messages)
        try:
            return primary.invoke(messages)
        except Exception as e:
            logger.warning(f"[RoutingLLM] Primary client failed: {e}. Falling back...")
            if backup:
                try:
                    return backup.invoke(messages)
                except Exception as backup_err:
                    logger.error(f"[RoutingLLM] Backup client also failed: {backup_err}")
                    raise backup_err
            raise e

    def stream(self, messages: list[BaseMessage]):
        primary, backup = self._get_active_clients(messages)
        try:
            # Check primary stream
            generator = primary.stream(messages)
            first_chunk = next(generator)
            yield first_chunk
            for chunk in generator:
                yield chunk
        except Exception as e:
            logger.warning(f"[RoutingLLM] Primary client stream failed: {e}. Falling back...")
            if backup:
                try:
                    for chunk in backup.stream(messages):
                        yield chunk
                    return
                except Exception as backup_err:
                    logger.error(f"[RoutingLLM] Backup client stream also failed: {backup_err}")
                    raise backup_err
            raise e

# Global single instance of RoutingLLM
_routing_llm = RoutingLLM()

def get_llm():
    return _routing_llm