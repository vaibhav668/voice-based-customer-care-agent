from langchain_core.messages import BaseMessage
from app.ai.llm.base import BaseLLM

class FallbackLLM(BaseLLM):

    def __init__(self, primary: BaseLLM, backup: BaseLLM):
        self.primary = primary
        self.backup = backup

    def invoke(
        self,
        messages: list[BaseMessage],
    ) -> str:
        try:
            return self.primary.invoke(messages)
        except Exception as e:
            print(f"[FallbackLLM] Primary LLM failed: {e}. Falling back to OpenRouter...")
            try:
                return self.backup.invoke(messages)
            except Exception as backup_error:
                print(f"[FallbackLLM] Backup LLM also failed: {backup_error}")
                raise backup_error

    def stream(
        self,
        messages: list[BaseMessage],
    ):
        try:
            # Try to get the generator and first chunk to verify connection
            generator = self.primary.stream(messages)
            first_chunk = next(generator)
            yield first_chunk
            for chunk in generator:
                yield chunk
        except Exception as e:
            print(f"[FallbackLLM] Primary LLM stream failed: {e}. Falling back to OpenRouter...")
            try:
                for chunk in self.backup.stream(messages):
                    yield chunk
            except Exception as backup_error:
                print(f"[FallbackLLM] Backup LLM stream also failed: {backup_error}")
                raise backup_error
