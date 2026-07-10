from app.ai.llm.groq_client import GroqLLM
from app.ai.llm.openrouter_client import OpenRouterLLM
from app.config.settings import settings


def get_llm():

    provider = settings.llm_provider.lower()
    if provider == "groq":
        return GroqLLM()
    elif provider == "openrouter":
        return OpenRouterLLM()

    raise ValueError("Unsupported LLM Provider")