"""
Genesys YAML Parser v0.1
=========================
Convierte configuración YAML de Genesys Engage
al Universal IVR Flow Model de OrchestrIA.
"""

import yaml
import uuid
from typing import Any
from src.models.ivr.flow_model import (
    IVRFlow, IVRNode, FlowError, NodeType, Severity
)

# Mapeo de tipos Genesys → NodeType universal
GENESYS_TYPE_MAP = {
    "menu":         NodeType.MENU,
    "prompt":       NodeType.PROMPT,
    "transfer":     NodeType.TRANSFER,
    "condition":    NodeType.CONDITION,
    "input":        NodeType.INPUT,
    "setVariable":  NodeType.SET_VARIABLE,
    "apiCall":      NodeType.API_CALL,
    "loop":         NodeType.LOOP,
    "switch":       NodeType.SWITCH,
    "callback":     NodeType.CALLBACK,
    "speech":       NodeType.SPEECH,
    "exit":         NodeType.EXIT,
    "entry":        NodeType.ENTRY,
}


class GenesysYAMLParser:
    """Parser de configuraciones Genesys Engage en formato YAML."""

    def parse(self, yaml_content: str, flow_name: str = "Unnamed") -> IVRFlow:
        """
        Parsea un string YAML y devuelve un IVRFlow.
        Punto de entrada principal del parser.
        """
        flow = IVRFlow(
            flow_id=str(uuid.uuid4()),
            flow_name=flow_name,
            provider="genesys"
        )

        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            flow.add_error(FlowError(
                error_type="invalid_yaml",
                severity=Severity.CRITICAL,
                affected_node_id="root",
                description=f"El YAML no es válido: {str(e)}",
                recommendation="Verificar la sintaxis del archivo YAML exportado de Genesys"
            ))
            return flow

        if not data:
            flow.add_error(FlowError(
                error_type="empty_config",
                severity=Severity.CRITICAL,
                affected_node_id="root",
                description="El archivo YAML está vacío",
                recommendation="Exportar de nuevo la configuración desde Genesys"
            ))
            return flow

        # Parsear nodos
        nodes_data = data.get("nodes", data.get("steps", data.get("actions", {})))
        
        if isinstance(nodes_data, list):
            for node_data in nodes_data:
                node = self._parse_node(node_data)
                flow.add_node(node)
        elif isinstance(nodes_data, dict):
            for node_id, node_data in nodes_data.items():
                if isinstance(node_data, dict):
                    node_data["id"] = node_id
                    node = self._parse_node(node_data)
                    flow.add_node(node)

        # Validaciones básicas
        self._validate_flow(flow)

        return flow

    def _parse_node(self, data: dict[str, Any]) -> IVRNode:
        """Convierte un nodo del YAML al modelo IVRNode."""
        node_id = str(data.get("id", uuid.uuid4()))
        node_type_str = data.get("type", data.get("action", "unknown")).lower()
        node_type = GENESYS_TYPE_MAP.get(node_type_str, NodeType.UNKNOWN)

        next_nodes = []
        if "next" in data:
            next_val = data["next"]
            if isinstance(next_val, str):
                next_nodes = [next_val]
            elif isinstance(next_val, list):
                next_nodes = [str(n) for n in next_val]
        elif "transitions" in data:
            next_nodes = [str(t.get("target", "")) for t in data["transitions"] if t.get("target")]

        return IVRNode(
            id=node_id,
            name=data.get("name", f"Node {node_id}"),
            type=node_type,
            next_nodes=next_nodes,
            prompt_text=data.get("prompt", data.get("text")),
            timeout_seconds=data.get("timeout"),
            max_retries=data.get("maxRetries", data.get("retries")),
            transfer_target=data.get("target", data.get("queue")),
            variable_name=data.get("variable"),
            api_endpoint=data.get("url", data.get("endpoint")),
            raw_config=data
        )

    def _validate_flow(self, flow: IVRFlow) -> None:
        """Validaciones básicas del flujo completo."""

        # Sin nodo de entrada
        if not flow.entry_node_id:
            flow.add_error(FlowError(
                error_type="missing_entry_node",
                severity=Severity.CRITICAL,
                affected_node_id="root",
                description="El flujo no tiene nodo de entrada definido",
                recommendation="Añadir un nodo de tipo 'entry' al flujo"
            ))

        # Nodos huérfanos y referencias rotas
        all_ids = set(flow.nodes.keys())
        referenced_ids = set()
        for node in flow.nodes.values():
            referenced_ids.update(node.next_nodes)

        broken_refs = referenced_ids - all_ids
        for ref in broken_refs:
            flow.add_error(FlowError(
                error_type="broken_reference",
                severity=Severity.HIGH,
                affected_node_id=ref,
                description=f"El nodo '{ref}' es referenciado pero no existe en el flujo",
                recommendation=f"Verificar si el nodo '{ref}' fue eliminado o renombrado"
            ))

        # Nodos sin salida que no son EXIT
        for node in flow.nodes.values():
            if node.type != NodeType.EXIT and not node.next_nodes:
                flow.add_error(FlowError(
                    error_type="dead_end",
                    severity=Severity.CRITICAL,
                    affected_node_id=node.id,
                    description=f"El nodo '{node.name}' no tiene salida y no es un nodo EXIT",
                    recommendation="Añadir transición al nodo o marcarlo como EXIT"
                ))