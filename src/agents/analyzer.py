import os
import json
import re
from ..llm.base import Message, LLMConfig
from ..llm.anthropic_adapter import AnthropicAdapter
from ..models.ivr.flow_model import IVRFlow
from src.agents.inventory import FlowInventoryExtractor

SCORING_RUBRIC = """
SCORING RUBRIC - 100 puntos totales.

CONTEXTO CRITICO: Eres un Genesys Engage/Cloud architect con 15 anos de experiencia.
Evalua con el criterio de un arquitecto senior, no de un auditor perfeccionista.
Un flujo bien construido para produccion debe poder sacar entre 80-95 puntos.
Solo los flujos con errores graves estructurales deben bajar de 50.
Solo los flujos completamente rotos o vacios deben bajar de 25.

CALIBRACION OBLIGATORIA antes de puntuar:
- Si el flujo tiene entry node, nodos conectados y sin dead ends criticos: empieza desde 60
- Si ademas tiene timeouts en transfers y manejo de noInput/noMatch: empieza desde 75
- Si ademas tiene maxRetries, fallbacks en APIs y opciones de agente humano: empieza desde 85
- Penaliza desde esa base, no construyas desde 0

---

1. INTEGRIDAD ESTRUCTURAL (max 25 pts)
   REQUISITO: Evalua solo lo que el parser ha detectado explicitamente.
   - Entry node presente y flujo alcanzable desde el: +8 pts
   - Cero dead ends (nodos sin salida que no sean EXIT/disconnect): +8 pts (resta 2 por cada dead end, min 0)
   - Cero referencias rotas (next apunta a nodo inexistente): +5 pts (resta 2 por cada ref rota, min 0)
   - Cero nodos huerfanos (no alcanzables desde entry): +4 pts (resta 1 por cada huerfano, min 0)

2. ROBUSTEZ OPERATIVA (max 25 pts)
   REQUISITO: En Genesys Engage, el timeout en MENU es opcional pero recomendado.
   La ausencia de timeout en MENU es una mejora, NO un error critico.
   - Transfers tienen timeout configurado: +8 pts (critico: sin timeout la cola puede colgar indefinidamente)
   - Menus tienen noInput y noMatch configurados: +7 pts
   - Menus con noInput/noMatch tienen maxRetries o fallback final: +5 pts
   - Transfers tienen onTimeout con ruta de escape (no dead end): +5 pts

3. EXPERIENCIA DE CLIENTE (max 20 pts)
   - Existe al menos una opcion de transferencia a agente humano: +7 pts (critico para produccion)
   - Ningun menu tiene mas de 5 opciones DTMF: +5 pts
   - Prompts TTS son descriptivos y especificos (no genericos como "opcion 1", "opcion 2"): +5 pts
   - Existe nodo de despedida con mensaje antes del disconnect: +3 pts

4. GESTION DE APIs Y DATOS (max 15 pts)
   REQUISITO: Si el flujo NO tiene APIs, asigna automaticamente 12/15 (no penalices la ausencia).
   Si hay APIs:
   - Todas las APIs/dataQuery tienen rama onSuccess y onFailure: +8 pts
   - APIs en ruta critica tienen fallback a agente humano: +4 pts
   - Timeouts configurados en llamadas a APIs: +3 pts

5. ARQUITECTURA Y EFICIENCIA (max 10 pts)
   - Estructura de menus logica y jerarquizada (no mas de 3 niveles de profundidad): +4 pts
   - Sin bucles infinitos (ciclos sin condicion de salida): +4 pts
   - Numero de nodos proporcional a la complejidad del servicio: +2 pts

6. COBERTURA EDGE CASES (max 5 pts)
   - Manejo de voicemail o mensaje alternativo cuando no hay agentes: +3 pts
   - Comportamiento definido para horario fuera de servicio O mensaje de cierre: +2 pts
   NOTA: Si no hay voicemail ni mensaje de cierre, penaliza como maximo 3 pts, no mas.

---

INSTRUCCION FINAL DE CALIBRACION:
Antes de devolver el score, verifica:
- Un flujo con estructura correcta, sin dead ends y con transfers a agente DEBE sacar minimo 65
- Un flujo con lo anterior MAS timeouts en transfers y noInput/noMatch DEBE sacar minimo 78
- Un flujo con todo lo anterior MAS APIs con manejo de errores DEBE sacar minimo 85
- Solo baja de 40 si hay dead ends criticos, referencias rotas o el flujo es basicamente inoperable
"""


class IVRAnalyzer:
    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.llm = AnthropicAdapter(api_key=api_key)
        self.config = LLMConfig(model="claude-sonnet-4-6", max_tokens=2000)

    def analyze(self, flow: IVRFlow) -> dict:
        flow_description = self._describe_flow(flow)

        prompt = """Eres un Genesys IVR Architect con 15 anos de experiencia en diseno de flujos de contact center enterprise.

Analiza el siguiente flujo IVR exportado de Genesys Engage/Cloud y evalualo con el rubric indicado.

FLUJO A ANALIZAR:
""" + flow_description + """

""" + SCORING_RUBRIC + """

INSTRUCCION CRITICA: Responde UNICAMENTE con un objeto JSON valido. Sin markdown, sin explicaciones, sin texto antes o despues del JSON.

El JSON debe tener exactamente esta estructura:
{
  "score": <numero entero 0-100>,
  "dimension_scores": {
    "integridad_estructural": <0-25>,
    "robustez_operativa": <0-25>,
    "experiencia_cliente": <0-20>,
    "gestion_apis": <0-15>,
    "arquitectura_eficiencia": <0-10>,
    "cobertura_edge": <0-5>
  },
  "summary": "<resumen ejecutivo en 2-3 frases, orientado a un CIO de contact center>",
  "critical_issues": ["<problema critico 1 con nodo especifico afectado>", "<problema critico 2>"],
  "improvements": ["<mejora concreta 1>", "<mejora concreta 2>"],
  "api_analysis": {
    "total_api_calls": <numero>,
    "apis_with_error_handling": <numero>,
    "apis_without_error_handling": ["<nombre api>"],
    "apis_in_critical_path": ["<nombre api>"]
  },
  "recommendation": "<recomendacion principal en 1 frase, accionable y especifica>"
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
                    "summary": "Error al parsear la respuesta del modelo.",
                    "critical_issues": ["Error parseando respuesta del modelo"],
                    "improvements": [],
                    "api_analysis": {
                        "total_api_calls": 0,
                        "apis_with_error_handling": 0,
                        "apis_without_error_handling": [],
                        "apis_in_critical_path": []
                    },
                    "recommendation": "Revisar el prompt del Analyzer"
                }

        result["tokens_used"] = {
            "input": response.input_tokens,
            "output": response.output_tokens
        }

        inv = FlowInventoryExtractor().extract(flow)
        result["inventory"] = {
            "total_nodes": inv.total_nodes,
            "menu_nodes": inv.menu_nodes,
            "transfer_nodes": inv.transfer_nodes,
            "task_nodes": inv.task_nodes,
            "exit_nodes": inv.exit_nodes,
            "self_service_exits": inv.self_service_exits,
            "agent_transfers": inv.agent_transfers,
            "self_service_ratio": inv.self_service_ratio,
            "unique_queues": inv.unique_queues,
            "tts_messages": inv.tts_messages,
            "voicemail_nodes": inv.voicemail_nodes,
            "dtmf_input_nodes": inv.dtmf_input_nodes,
            "data_services": inv.data_services,
            "auth_services": inv.auth_services,
            "api_calls": inv.api_calls,
            "dynamic_variables": inv.dynamic_variables,
            "total_external_deps": inv.total_external_deps,
            "migration_complexity_score": inv.migration_complexity_score,
            "migration_level": inv.migration_level,
            "migration_risk_flags": inv.migration_risk_flags,
        }

        return result

    def _describe_flow(self, flow: IVRFlow) -> str:
        lines = [f"Nombre del flujo: {flow.flow_name}"]
        lines.append(f"Total de nodos: {len(flow.nodes)}")
        lines.append(f"Entry node: {flow.entry_node_id or 'NO DEFINIDO'}")
        lines.append(f"Errores estructurales detectados: {len(flow.errors)}")
        lines.append("")
        lines.append("NODOS DEL FLUJO:")

        for node in flow.nodes.values():
            next_nodes = node.next_nodes if node.next_nodes else ["(sin salida - posible dead end)"]
            lines.append(f"  [{node.type.value.upper()}] {node.id} | {node.name}")
            lines.append(f"    Conecta a: {', '.join(next_nodes)}")
            if node.prompt_text:
                lines.append(f"    TTS: {node.prompt_text[:120]}")
            if node.timeout_seconds:
                lines.append(f"    Timeout: {node.timeout_seconds}s")
            if node.max_retries:
                lines.append(f"    Max reintentos: {node.max_retries}")
            if node.transfer_target:
                lines.append(f"    Cola: {node.transfer_target}")
            if node.api_endpoint:
                lines.append(f"    API: {node.api_endpoint}")

        if flow.errors:
            lines.append("")
            lines.append("ERRORES ESTRUCTURALES DETECTADOS POR EL PARSER:")
            for error in flow.errors:
                lines.append(f"  [{error.severity.value.upper()}] {error.error_type}: {error.description}")

        return "\n".join(lines)
