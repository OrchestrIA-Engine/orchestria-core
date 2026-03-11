import sys
sys.path.insert(0, ".")
from src.llm.anthropic_adapter import AnthropicAdapter
from src.llm.base import Message, LLMConfig
from src.models.ivr.flow_model import IVRFlow
import os, json

PROMPT = """Eres experto en IVR Genesys. Analiza el flujo y responde SOLO con JSON sin markdown:
{"score": <0-100>, "summary": "<2-3 frases>", "critical_issues": ["<issue1>"], "improvements": ["<mejora1>"], "recommendation": "<recomendacion>"}"""

class IVRAnalyzer:
    def __init__(self, api_key: str):
        self.adapter = AnthropicAdapter(api_key=api_key)
        self.config = LLMConfig(model="claude-sonnet-4-6", max_tokens=1000)

    def analyze(self, flow: IVRFlow) -> dict:
        summary = flow.summary()
        desc = f"Flujo: {flow.flow_name}\nNodos: {summary['total_nodes']}\nTipos: {summary['node_types']}\nErrores parser: {summary['total_errors']}\n\nNODOS:\n"
        for node in flow.nodes.values():
            desc += f"[{node.type.value.upper()}] {node.name} -> {node.next_nodes}\n"
        if flow.errors:
            desc += "\nERRORES:\n"
            for e in flow.errors:
                desc += f"[{e.severity.value}] {e.description}\n"
        response = self.adapter.complete([Message(role="user", content=PROMPT + "\n\n" + desc)], self.config)
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = {"score": 0, "summary": "Error parsing LLM response", "critical_issues": [], "improvements": [], "recommendation": "Check prompt"}
        result["tokens_used"] = {"input": response.input_tokens, "output": response.output_tokens}
        return result
