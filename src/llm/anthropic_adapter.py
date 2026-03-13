import os
import anthropic
from .base import LLMAdapter, Message, LLMConfig, LLMResponse


class AnthropicAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.langfuse = None
        try:
            from langfuse import Langfuse
            self.langfuse = Langfuse(
                public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
                host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
            )
        except Exception:
            pass

    def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        if self.langfuse:
            try:
                self.langfuse.create_event(
                    name="llm_call_start",
                    input=[{"role": m.role, "content": m.content} for m in messages],
                    metadata={"model": config.model}
                )
            except Exception:
                pass

        response = self.client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            messages=[{"role": m.role, "content": m.content} for m in messages]
        )

        result = LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )

        if self.langfuse:
            try:
                self.langfuse.create_event(
                    name="llm_call_end",
                    output=result.content,
                    metadata={
                        "model": config.model,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens
                    }
                )
                self.langfuse.flush()
            except Exception:
                pass

        return result
