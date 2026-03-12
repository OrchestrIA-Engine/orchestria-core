import anthropic
import os
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
        trace = None
        generation = None
        if self.langfuse:
            try:
                trace = self.langfuse.trace(name="orchestria_complete", metadata={"model": config.model})
                generation = trace.generation(
                    name="llm_call",
                    model=config.model,
                    input=[{"role": m.role, "content": m.content} for m in messages]
                )
            except Exception:
                pass

        response = self.client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            messages=[{"role": m.role, "content": m.content} for m in messages]
        )

        result = LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )

        if generation:
            try:
                generation.end(
                    output=result.content,
                    usage={"input": result.input_tokens, "output": result.output_tokens}
                )
            except Exception:
                pass

        return result
