import json
import uuid
from ..models.ivr.flow_model import IVRFlow, IVRNode, NodeType, FlowError, Severity

CLOUD_TYPE_MAP = {
    "transfer": NodeType.TRANSFER,
    "menu": NodeType.MENU,
    "prompt": NodeType.PROMPT,
    "input": NodeType.INPUT,
    "condition": NodeType.CONDITION,
    "loop": NodeType.LOOP,
    "set": NodeType.SET_VARIABLE,
    "callData": NodeType.API_CALL,
    "disconnect": NodeType.EXIT,
    "endFlow": NodeType.EXIT,
}

class GenesysCloudParser:
    def parse(self, json_content: str) -> IVRFlow:
        data = json.loads(json_content)
        flow_name = data.get("name", "Unknown Flow")
        flow = IVRFlow(flow_id=str(uuid.uuid4()), flow_name=flow_name)
        nodes_data = data.get("flow", {}).get("states", [])
        node_ids = set()

        for node_data in nodes_data:
            node_id = node_data.get("refId", node_data.get("id", str(uuid.uuid4())))
            node_type = CLOUD_TYPE_MAP.get(node_data.get("type", "unknown"), NodeType.UNKNOWN)
            next_nodes = [t.get("targetStateRefId", "") for t in node_data.get("transitions", []) if t.get("targetStateRefId")]
            node = IVRNode(
                id=node_id,
                name=node_data.get("name", node_id),
                type=node_type,
                next_nodes=next_nodes,
                raw_config=node_data
            )
            flow.add_node(node)
            node_ids.add(node_id)

        for n in flow.nodes.values():
            for ref in n.next_nodes:
                if ref and ref not in node_ids:
                    flow.add_error(FlowError(
                        error_type="broken_reference",
                        severity=Severity.CRITICAL,
                        affected_node=ref,
                        description=f"Referencia rota: nodo '{ref}' no existe",
                        recommendation="Verificar transiciones en Genesys Cloud"
                    ))
        return flow
