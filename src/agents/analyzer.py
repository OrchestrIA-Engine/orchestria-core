from dotenv import load_dotenv
load_dotenv()
import os
import json
import re
from src.models.ivr.flow_model import IVRFlow
from src.agents.inventory import FlowInventoryExtractor
from src.llm.anthropic_adapter import AnthropicAdapter
from src.llm.base import Message, LLMConfig

ANALYSIS_PROMPT = """Eres un experto en contact center y soluciones IVR de Genesys.
Analiza el siguiente flujo IVR y proporciona un análisis detallado.
Responde ÚNICAMENTE con JSON válido sin markdown ni texto adicional:
{
  "score": <número entre 0 y 100>,
  "summary": "<resumen ejecutivo de 2-3 frases>",
  "critical_issues": ["<issue crítico 1>", "<issue crítico 2>"],
  "improvements": ["<mejora recomendada 1>", "<mejora recomendada 2>"],
  "recommendation": "<recomendación principal>"
}

Criterios de scoring:
- 90-100: Flujo ejemplar, robusto, bien estructurado
- 70-89: Buen flujo con mejoras menores
- 50-69: Flujo funcional con deficiencias importantes
- 30-49: Flujo problemático con riesgos operativos
- 0-29: Flujo crítico, requiere rediseño"""


class IVRAnalyzer:
    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.llm = AnthropicAdapter(api_key=api_key)
        self.config = LLMConfig(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            temperature=0.0
        )

    def analyze(self, flow: IVRFlow) -> dict:
        inv = FlowInventoryExtractor().extract(flow)
        flow_desc = self._describe_flow(flow, inv)
        messages = [Message(
            role="user",
            content=ANALYSIS_PROMPT + "\n\nFLUJO:\n" + flow_desc
        )]

        result = {
            "score": 0,
            "summary": "",
            "critical_issues": [],
            "improvements": [],
            "recommendation": "",
            "inventory": inv,
            "tokens_used": {"input": 0, "output": 0}
        }

        try:
            response = self.llm.complete(messages, self.config)
            result["tokens_used"] = {
                "input": response.input_tokens,
                "output": response.output_tokens
            }
            raw = response.content.strip()
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                raw = match.group(0)
            parsed = json.loads(raw)
            result.update(parsed)
        except Exception as e:
            result["critical_issues"] = [f"Error en análisis: {str(e)}"]

        return result

    def _describe_flow(self, flow: IVRFlow, inv: dict) -> str:
        lines = [
            f"Nombre del flujo: {flow.flow_name}",
            f"Total nodos: {inv.get('total_nodes', 0)}",
            f"Nodos menú: {inv.get('menu_nodes', 0)}",
            f"Transfers: {inv.get('transfer_nodes', 0)}",
            f"Self-service ratio: {inv.get('self_service_ratio', 0)}%",
            f"APIs de datos: {inv.get('data_services', [])}",
            f"Auth services: {inv.get('auth_services', [])}",
            f"Colas: {inv.get('unique_queues', [])}",
            f"Variables TTS: {inv.get('dynamic_variables', [])}",
            f"Dead ends: {inv.get('dead_ends', [])}",
            f"Missing fallbacks: {inv.get('missing_fallbacks', [])}",
            f"Migration level: {inv.get('migration_level', 'N/A')}",
            f"Migration score: {inv.get('migration_complexity_score', 0)}/100",
        ]
        for node_id, node in list(flow.nodes.items())[:20]:
            lines.append(
                f"  Nodo {node_id}: type={node.type}, next={node.next_nodes[:3]}"
            )
        return "\n".join(lines)
