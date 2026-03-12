import sys
sys.path.insert(0, ".")
from src.llm.anthropic_adapter import AnthropicAdapter
from src.llm.base import Message, LLMConfig
from src.models.ivr.flow_model import IVRFlow
import os, json, re

PROMPT = """Eres experto en IVR Genesys. Analiza el flujo IVR que se te proporciona.

INSTRUCCION CRITICA: Responde UNICAMENTE con un objeto JSON valido. Absolutamente nada mas. Sin texto antes ni despues. Sin bloques de codigo. Sin markdown. Solo el JSON puro empezando con { y terminando con }.

Formato exacto requerido:
{"score": 75, "summary": "texto aqui", "critical_issues": ["issue1", "issue2"], "improvements": ["mejora1"], "recommendation": "texto aqui"}"""

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
        response = self.adapter.complete([Message(role="user", content=PROMPT + "\n\nDATO A ANALIZAR:\n" + desc)], self.config)
        raw = response.content.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            raw = match.group(0)
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {"score": 0, "summary": "Error parsing LLM response", "critical_issues": [], "improvements": [], "recommendation": "Check prompt"}
        result["tokens_used"] = {"input": response.input_tokens, "output": response.output_tokens}
        return result
