import anthropic
from .base import LLMAdapter, Message, LLMConfig, LLMResponse

class AnthropicAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        response = self.client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            messages=[{"role": m.role, "content": m.content} for m in messages]
        )
        return LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )
