import os
import json
import re
from ..llm.base import Message, LLMConfig
from ..llm.anthropic_adapter import AnthropicAdapter
from ..models.ivr.flow_model import IVRFlow
from src.agents.inventory import FlowInventoryExtractor

SCORING_RUBRIC = """
SCORING RUBRIC - 100 puntos totales. Evalua CADA dimension por separado:

1. INTEGRIDAD ESTRUCTURAL (max 25 pts)
   - Entry node presente y accesible: +8
   - Sin dead ends (nodos sin salida que no sean EXIT): +7
   - Sin referencias rotas (next_nodes apuntan a nodos existentes): +7
   - Sin nodos huerfanos (nodos no alcanzables desde entry): +3

2. ROBUSTEZ OPERATIVA (max 20 pts)
   - Nodos MENU tienen timeout configurado: +6
   - Nodos TRANSFER tienen ruta de fallback: +6
   - Nodos API_CALL tienen rama de error: +5
   - Nodos INPUT tienen max_retries configurado: +3

3. EXPERIENCIA DE CLIENTE (max 20 pts)
   - Ningun menu tiene mas de 4 opciones: +6
   - Profundidad maxima del flujo <= 3 niveles: +5
   - Existe opcion de transferir a agente humano: +5
   - Prompts/mensajes descriptivos (no genericos): +4

4. GESTION DE APIs (max 15 pts) - si no hay APIs, asigna 10/15 por defecto
   - Todas las APIs tienen rama de error definida: +6
   - APIs tienen timeout configurado: +5
   - Ninguna API esta en ruta critica sin fallback: +4

5. EFICIENCIA DEL FLUJO (max 10 pts)
   - Sin rutas redundantes o duplicadas: +4
   - Sin loops innecesarios (ciclos que no tienen salida): +3
   - Numero de nodos razonable para la funcion del flujo: +3

6. COBERTURA DE CASOS EDGE (max 5 pts)
   - Manejo de no-input (usuario no pulsa nada): +2
   - Manejo de input invalido (opcion no existente): +2
   - Timeout global del flujo configurado: +1

7. TRANSFERENCIAS (max 5 pts)
   - Cola de destino de transferencia especificada: +2
   - Existe opcion de callback o devolucion de llamada: +2
   - Horario de atencion contemplado en el flujo: +1
"""

class IVRAnalyzer:
    def __init__(self):
        try:
            import streamlit as st
            api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        except Exception:
            try:
            import streamlit as st
            api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        except Exception:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.llm = AnthropicAdapter(api_key=api_key)
        self.config = LLMConfig(model="claude-sonnet-4-6", max_tokens=2000, temperature=0.0)

    def analyze(self, flow: IVRFlow) -> dict:
        flow_description = self._describe_flow(flow)

        prompt = """Eres un experto en Genesys IVR con 15 anios de experiencia en diseno de flujos de contact center y experiencia de cliente.

Analiza el siguiente flujo IVR y evalualo usando el rubric de scoring que se indica.

FLUJO A ANALIZAR:
""" + flow_description + """

""" + SCORING_RUBRIC + """

INSTRUCCION CRITICA: Responde UNICAMENTE con un objeto JSON valido. Sin markdown, sin explicaciones, sin texto antes o despues del JSON.

El JSON debe tener exactamente esta estructura:
{
  "score": <numero entero 0-100>,
  "dimension_scores": {
    "integridad_estructural": <0-25>,
    "robustez_operativa": <0-20>,
    "experiencia_cliente": <0-20>,
    "gestion_apis": <0-15>,
    "eficiencia_flujo": <0-10>,
    "cobertura_edge": <0-5>,
    "transferencias": <0-5>
  },
  "summary": "<resumen ejecutivo en 2-3 frases>",
  "critical_issues": ["<problema critico 1>", "<problema critico 2>"],
  "improvements": ["<mejora sugerida 1>", "<mejora sugerida 2>"],
  "api_analysis": {
    "total_api_calls": <numero>,
    "apis_with_error_handling": <numero>,
    "apis_without_error_handling": ["<nombre api 1>"],
    "apis_in_critical_path": ["<nombre api 1>"]
  },
  "recommendation": "<recomendacion principal en 1 frase>"
}"""

        messages = [Message(role="user", content=prompt)]
        response = self.llm.complete(messages, self.config)
        raw = response.content

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                result = json.loads(match.group())
            else:
                result = {
                    "score": 0,
                    "dimension_scores": {},
                    "critical_issues": ["Error parseando respuesta del modelo"],
                    "improvements": [],
                    "api_analysis": {"total_api_calls": 0, "apis_with_error_handling": 0, "apis_without_error_handling": [], "apis_in_critical_path": []},
                    "recommendation": "Revisar el prompt del Analyzer"
                }

        result["tokens_used"] = {
            "input": response.input_tokens,
            "output": response.output_tokens
        }
        inv = FlowInventoryExtractor().extract(flow)
        result["inventory"] = inv
        return result

    def _describe_flow(self, flow: IVRFlow) -> str:
        lines = [f"Nombre del flujo: {flow.flow_name}"]
        lines.append(f"Total de nodos: {len(flow.nodes)}")
        lines.append(f"Errores estructurales detectados por el parser: {len(flow.errors)}")
        lines.append("")
        lines.append("NODOS DEL FLUJO:")
        for node in flow.nodes.values():
            next_nodes = node.next_nodes if node.next_nodes else ["(sin salida)"]
            lines.append(f"  - [{node.type.value}] {node.id} ({node.name})")
            lines.append(f"    Conecta a: {', '.join(next_nodes)}")
            if node.prompt_text:
                lines.append(f"    Prompt: {node.prompt_text}")
            if node.timeout_seconds:
                lines.append(f"    Timeout: {node.timeout_seconds}s")
            if node.max_retries:
                lines.append(f"    Max reintentos: {node.max_retries}")
            if node.transfer_target:
                lines.append(f"    Cola destino: {node.transfer_target}")
            if node.api_endpoint:
                lines.append(f"    API endpoint: {node.api_endpoint}")
        if flow.errors:
            lines.append("")
            lines.append("ERRORES ESTRUCTURALES:")
            for error in flow.errors:
                lines.append(f"  - [{error.severity.value}] {error.error_type}: {error.description}")
        return "\n".join(lines)
