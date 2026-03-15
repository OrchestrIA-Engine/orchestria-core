import os
import anthropic
from .base import LLMAdapter, Message, LLMConfig, LLMResponse

class AnthropicAdapter(LLMAdapter):
    def __init__(self, api_key: str = None):
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get("ANTHROPIC_API_KEY")
            except Exception:
                pass
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
