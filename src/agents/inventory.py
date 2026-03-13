import re
from dataclasses import dataclass, field
from src.models.ivr.flow_model import IVRFlow, NodeType

@dataclass
class FlowInventory:
    total_nodes: int = 0
    menu_nodes: int = 0
    transfer_nodes: int = 0
    task_nodes: int = 0
    exit_nodes: int = 0
    self_service_exits: int = 0
    agent_transfers: int = 0
    unique_queues: list = field(default_factory=list)
    tts_messages: int = 0
    voicemail_nodes: int = 0
    dtmf_input_nodes: int = 0
    speech_input_nodes: int = 0
    api_calls: list = field(default_factory=list)
    auth_services: list = field(default_factory=list)
    data_services: list = field(default_factory=list)
    dynamic_variables: list = field(default_factory=list)
    total_external_deps: int = 0
    migration_complexity_score: int = 0
    migration_level: str = "SIMPLE"
    migration_risk_flags: list = field(default_factory=list)
    self_service_ratio: float = 0.0

class FlowInventoryExtractor:
    def extract(self, flow: IVRFlow) -> FlowInventory:
        inv = FlowInventory()
        inv.total_nodes = len(flow.nodes)
        queues, apis, auth_services, data_services, dynamic_vars = set(), set(), set(), set(), set()
        terminal_exits = 0
        agent_transfers = 0

        for node in flow.nodes.values():
            raw = node.raw_config or {}
            ntype = node.type

            if ntype == NodeType.MENU:
                inv.menu_nodes += 1
            elif ntype == NodeType.TRANSFER:
                inv.transfer_nodes += 1
                agent_transfers += 1
                if node.transfer_target:
                    queues.add(node.transfer_target)
                q = raw.get("queue")
                if q and isinstance(q, str):
                    queues.add(q)
            elif ntype == NodeType.EXIT:
                inv.exit_nodes += 1
                terminal_exits += 1
                inv.self_service_exits += 1
            else:
                inv.task_nodes += 1

            tts = str(raw.get("tts", raw.get("prompt", "")))
            if tts.strip():
                inv.tts_messages += 1
                for v in re.findall(r"\{(\w+)\}", tts):
                    dynamic_vars.add(v)

            if raw.get("choices") or raw.get("maxDigits"):
                inv.dtmf_input_nodes += 1

            for action in raw.get("actions", []):
                if not isinstance(action, dict):
                    continue
                atype = action.get("type", "")
                tts2 = str(action.get("tts", ""))
                for v in re.findall(r"\{(\w+)\}", tts2):
                    dynamic_vars.add(v)
                if atype == "dataQuery":
                    svc = action.get("service", "unknown_service")
                    data_services.add(svc)
                elif atype == "authenticate":
                    svc = action.get("service", "unknown_auth")
                    auth_services.add(svc)
                elif atype == "apiCall":
                    ep = action.get("url", action.get("endpoint", "unknown_api"))
                    apis.add(ep)
                elif atype == "recordMessage":
                    inv.voicemail_nodes += 1
                elif atype == "disconnect":
                    terminal_exits += 1
                    inv.self_service_exits += 1

        inv.unique_queues = sorted(queues)
        inv.api_calls = sorted(apis)
        inv.auth_services = sorted(auth_services)
        inv.data_services = sorted(data_services)
        inv.dynamic_variables = sorted(dynamic_vars)
        inv.total_external_deps = len(apis) + len(auth_services) + len(data_services)
        inv.agent_transfers = agent_transfers

        total_terminals = terminal_exits + agent_transfers
        if total_terminals > 0:
            inv.self_service_ratio = round(inv.self_service_exits / total_terminals * 100, 1)

        sc = 0
        sc += len(apis) * 15
        sc += len(auth_services) * 10
        sc += len(data_services) * 12
        sc += len(queues) * 5
        sc += inv.speech_input_nodes * 10
        sc += len(dynamic_vars) * 8
        sc += inv.voicemail_nodes * 5
        inv.migration_complexity_score = min(sc, 100)

        if inv.migration_complexity_score <= 25:
            inv.migration_level = "SIMPLE"
        elif inv.migration_complexity_score <= 50:
            inv.migration_level = "MODERADO"
        elif inv.migration_complexity_score <= 75:
            inv.migration_level = "COMPLEJO"
        else:
            inv.migration_level = "MUY COMPLEJO"

        flags = []
        if not flow.entry_node_id:
            flags.append("Sin entry node definido — el flujo no tiene punto de entrada claro")
        for node in flow.nodes.values():
            raw = node.raw_config or {}
            if node.type == NodeType.TRANSFER and not raw.get("timeout"):
                flags.append(f"Cola sin timeout: {node.id} — riesgo de llamada colgada en Cloud")
        if inv.speech_input_nodes > 0:
            flags.append(f"{inv.speech_innodes} nodo(s) con speech input — requiere configurar NLP/ASR en Cloud")
        if len(dynamic_vars) > 3:
            flags.append(f"{len(dynamic_vars)} variables dinamicas en TTS — verificar disponibilidad de datos en runtime Cloud")
        if len(data_services) > 0:
            flags.append(f"Integraciones de datos detectadas: {', '.join(data_services)} — requieren reconexion en Cloud")
        if len(auth_services) > 0:
            flags.append(f"Servicios de autenticacion: {', '.join(auth_services)} — validar compatibilidad con Cloud Auth")
        inv.migration_risk_flags = flags

        return inv
