from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Message:
    role: str
    content: str

@dataclass
class LLMConfig:
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 1000

@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int

class LLMAdapter(ABC):
    @abstractmethod
    def complete(self, messages: list[Message], config: LLMConfig) -> LLMResponse:
        pass
