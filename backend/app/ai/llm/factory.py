from app.ai.llm.groq_client import GroqLLM
from app.config.settings import settings


def get_llm():

    if settings.llm_provider.lower() == "groq":
        return GroqLLM()

    raise ValueError("Unsupported LLM Provider")