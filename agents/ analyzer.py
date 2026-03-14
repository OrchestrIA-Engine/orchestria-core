import sys
sys.path.insert(0, '.')

from src.llm.anthropic_adapter import AnthropicAdapter
from src.llm.base import Message, LLMConfig
from src.models.ivr.flow_model import IVRFlow
import os
import json

ANALYZER_PROMPT = """Eres un experto en sistemas IVR de contact center, especializado en Genesys.

Recibes el resumen de un flujo IVR y debes analizarlo para detectar problemas.

Analiza estos aspectos:
1. Errores estructurales (nodos sin salida, bucles infinitos, referencias rotas)
2. Problemas de experiencia de cliente (menús sin timeout, prompts poco claros)
3. Riesgos operativos (transferencias sin fallback, APIs sin manejo de errores)
4. Oportunidades de mejora (simplificación de flujos, reducción de opciones)

Responde SOLO con un JSON con esta estructura exacta:
{
  "score": <número del 0 al 100 donde 100 es perfecto>,
  "summary": "<resumen ejecutivo en 2-3 frases>",
  "critical_issues": ["<issue crítico 1>", "<issue crítico 2>"],
  "improvements": ["<mejora sugerida 1>", "<mejora sugerida 2>"],
  "recommendation": "<recomendación principal>"
}

No incluyas nada fuera del JSON. Sin markdown, sin explicaciones."""


class IVRAnalyzer:
    def __init__(self, api_key: str):
        self.adapter = AnthropicAdapter(api_key=api_key)
        self.config = LLMConfig(
            model="claude-sonnet-4-6",
            max_tokens=1000
        )

    def analyze(self, flow: IVRFlow) -> dict:
        summary = flow.summary()
        
        flow_description = f"""
FLUJO IVR A ANALIZAR:
- Nombre: {flow.flow_name}
- Proveedor: {flow.provider}
- Total nodos: {summary['total_nodes']}
- Tipos de nodo: {summary['node_types']}
- Errores detectados por parser: {summary['total_errors']}
- Errores críticos del parser: {summary['critical_errors']}

DETALLE DE NODOS:
"""
        for node in flow.nodes.values():
            flow_description += f"""
  [{node.type.value.upper()}] {node.name} (id: {node.id})
    - Conecta con: {node.next_nodes if node.next_nodes else 'NINGUNO'}
    - Prompt: {node.prompt_text or 'N/A'}
    - Timeout: {node.timeout_seconds or 'N/A'}s
    - Max reintentos: {node.max_retries or 'N/A'}
"""

        if flow.errors:
            flow_description += "\nERRORES YA DETECTADOS:\n"
            for error in flow.errors:
                flow_description += f"  - [{error.severity.value.upper()}] {error.description}\n"

        messages = [
            Message(role="user", content=flow_description)
        ]

        system_messages = [
            Message(role="user", content=ANALYZER_PROMPT + "\n\n" + flow_description)
        ]

        response = self.adapter.complete(system_messages, self.config)
        
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = {
                "score": 0,
                "summary": "Error al parsear respuesta del LLM",
                "critical_issues": ["Respuesta no válida del modelo"],
                "improvements": [],
                "recommendation": "Revisar el prompt del Analyzer"
            }
        
        result["tokens_used"] = {
            "input": response.input_tokens,
            "output": response.output_tokens
        }
        
        return result