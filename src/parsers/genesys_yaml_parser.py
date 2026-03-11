
import yaml
import uuid
from typing import Any
from src.models.ivr.flow_model import (
    IVRFlow, IVRNode, FlowError, NodeType, Severity
)

GENESYS_TYPE_MAP = {
    "menu": NodeType.MENU,
    "prompt": NodeType.PROMPT,
    "transfer": NodeType.TRANSFER,
    "condition": NodeType.CONDITION,
    "input": NodeType.INPUT,
    "setVariable": NodeType.SET_VARIABLE,
    "apiCall": NodeType.API_CALL,
    "loop": NodeType.LOOP,
    "switch": NodeType.SWITCH,
    "callback": NodeType.CALLBACK,
    "speech": NodeType.SPEECH,
    "exit": NodeType.EXIT,
    "entry": NodeType.ENTRY,
}

class GenesysYAMLParser:
    def parse(self, yaml_content: str, flow_name: str = "Unnamed") -> IVRFlow:
        flow = IVRFlow(flow_id=str(uuid.uuid4()), flow_name=flow_name, provider="genesys")
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            flow.add_error(FlowError(error_type="invalid_yaml", severity=Severity.CRITICAL, affected_node_id="root", description=f"YAML invalido: {str(e)}", recommendation="Verificar sintaxis YAML"))
            return flow
        if not data:
            flow.add_error(FlowError(error_type="empty_config", severity=Severity.CRITICAL, affected_node_id="root", description="YAML vacio", recommendation="Exportar de nuevo desde Genesys"))
            return flow
        nodes_data = data.get("nodes", data.get("steps", data.get("actions", {})))
        if isinstance(nodes_data, list):
            for node_data in nodes_data:
                flow.add_node(self._parse_node(node_data))
        elif isinstance(nodes_data, dict):
            for node_id, node_data in nodes_data.items():
                if isinstance(node_data, dict):
                    node_data["id"] = node_id
                    flow.add_node(self._parse_node(node_data))
        self._validate_flow(flow)
        return flow

    def _parse_node(self, data: dict) -> IVRNode:
        node_id = str(data.get("id", uuid.uuid4()))
        node_type_str = data.get("type", data.get("action", "unknown")).lower()
        node_type = GENESYS_TYPE_MAP.get(node_type_str, NodeType.UNKNOWN)
        next_nodes = []
        if "next" in data:
            next_val = data["next"]
            next_nodes = [next_val] if isinstance(next_val, str) else [str(n) for n in next_val]
        elif "transitions" in data:
            next_nodes = [str(t.get("target", "")) for t in data["transitions"] if t.get("target")]
        return IVRNode(id=node_id, name=data.get("name", f"Node {node_id}"), type=node_type, next_nodes=next_nodes, prompt_text=data.get("prompt", data.get("text")), timeout_seconds=data.get("timeout"), max_retries=data.get("maxRetries", data.get("retries")), transfer_target=data.get("target", data.get("queue")), variable_name=data.get("variable"), api_endpoint=data.get("url", data.get("endpoint")), raw_config=data)

    def _validate_flow(self, flow: IVRFlow) -> None:
        if not flow.entry_node_id:
            flow.add_error(FlowError(error_type="missing_entry_node", severity=Severity.CRITICAL, affected_node_id="root", description="Sin nodo de entrada", recommendation="Añadir nodo tipo entry"))
        all_ids = set(flow.nodes.keys())
        referenced_ids = set()
        for node in flow.nodes.values():
            referenced_ids.update(node.next_nodes)
        for ref in referenced_ids - all_ids:
            flow.add_error(FlowError(error_type="broken_reference", severity=Severity.HIGH, affected_node_id=ref, description=f"Nodo {ref} referenciado pero no existe", recommendation=f"Verificar nodo {ref}"))
        for node in flow.nodes.values():
            if node.type != NodeType.EXIT and not node.next_nodes:
                flow.add_error(FlowError(error_type="dead_end", severity=Severity.CRITICAL, affected_node_id=node.id, description=f"Nodo {node.name} sin salida", recommendation="Añadir transicion o marcar como EXIT"))
