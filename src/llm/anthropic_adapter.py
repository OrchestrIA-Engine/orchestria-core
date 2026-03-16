import anthropic
from .base import LLMAdapter, Message, LLMConfig, LLMResponse

class AnthropicAdapter(LLMAdapter):
    def __init__(self, api_key: str = None):
        # El SDK lee ANTHROPIC_API_KEY del entorno automaticamente si api_key=None
        self.client = anthropic.Anthropic(api_key=api_key)

    def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        response = self.client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            messages=[{"role": m.role, "content": m.content} for m in messages]
        )
        return LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )
