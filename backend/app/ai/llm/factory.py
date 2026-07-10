from app.ai.llm.groq_client import GroqLLM
from app.ai.llm.openrouter_client import OpenRouterLLM
from app.ai.llm.fallback import FallbackLLM
from app.config.settings import settings


def get_llm():

    provider = settings.llm_provider.lower()
    if provider == "groq":
        groq_llm = GroqLLM()
        if settings.openrouter_api_key:
            return FallbackLLM(primary=groq_llm, backup=OpenRouterLLM())
        return groq_llm
    elif provider == "openrouter":
        return OpenRouterLLM()

    raise ValueError("Unsupported LLM Provider")