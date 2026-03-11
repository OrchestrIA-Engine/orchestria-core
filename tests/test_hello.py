import os, sys
sys.path.insert(0, 'src')
from llm.anthropic_adapter import AnthropicAdapter
from llm.base import Message, LLMConfig

api_key = os.environ.get("ANTHROPIC_API_KEY")
adapter = AnthropicAdapter(api_key=api_key)
messages = [Message(role="user", content="Di exactamente esto: OrchestrIA operativo.")]
config = LLMConfig(model="claude-sonnet-4-6", max_tokens=50)
response = adapter.complete(messages, config)
print(f"✅ {response.content}")
print(f"   Tokens: {response.input_tokens} in / {response.output_tokens} out")
