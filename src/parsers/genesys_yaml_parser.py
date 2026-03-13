import yaml
import uuid
from src.models.ivr.flow_model import IVRFlow, IVRNode, FlowError, NodeType, Severity

GENESYS_TYPE_MAP = {
    "menu": NodeType.MENU, "prompt": NodeType.PROMPT,
    "transfer": NodeType.TRANSFER, "condition": NodeType.CONDITION,
    "input": NodeType.INPUT, "setVariable": NodeType.SET_VARIABLE,
    "apiCall": NodeType.API_CALL, "loop": NodeType.LOOP,
    "switch": NodeType.SWITCH, "callback": NodeType.CALLBACK,
    "speech": NodeType.SPEECH, "exit": NodeType.EXIT,
    "entry": NodeType.ENTRY, "task": NodeType.MENU,
}

class GenesysYAMLParser:
    def parse(self, yaml_content, flow_name="Unnamed"):
        flow = IVRFlow(flow_id=str(uuid.uuid4()), flow_name=flow_name, provider="genesys")
        try:
            data = yaml.safe_load(yaml_content)
        except Exception as e:
            flow.add_error(FlowError(error_type="invalid_yaml", severity=Severity.CRITICAL, affected_node_id="root", description=str(e), recommendation="Verificar sintaxis YAML"))
            return flow
        if not data or not isinstance(data, dict):
            flow.add_error(FlowError(error_type="empty_config", severity=Severity.CRITICAL, affected_node_id="root", description="YAML vacio", recommendation="Revisar contenido"))
            return flow
        for section in ["menus", "tasks", "transfers", "tasks_extra", "tasks_voicemail"]:
            for node_id, node_data in data.get(section, {}).items():
                if isinstance(node_data, dict):
                    node_data["id"] = node_id
                    node_data["type"] = "transfer" if section == "transfers" else "menu"
                    flow.add_node(self._parse_node(node_data))
        if not flow.nodes:
            nodes_data = data.get("nodes", data.get("steps", data.get("actions", {})))
            if isinstance(nodes_data, list):
                for nd in nodes_data:
                    flow.add_node(self._parse_node(nd))
            elif isinstance(nodes_data, dict):
                for nid, nd in nodes_data.items():
                    if isinstance(nd, dict):
                        nd["id"] = nid
                        flow.add_node(self._parse_node(nd))
        self._validate_flow(flow)
        return flow

    def _ref(self, val):
        if isinstance(val, str) and val:
            return val.strip("./").split("/")[-1]
        return None

    def _extract_refs(self, data):
        refs = []
        r = self._ref(data.get("next"))
        if r: refs.append(r)
        for c in data.get("choices", []):
            r = self._ref(c.get("next")) if isinstance(c, dict) else None
            if r: refs.append(r)
        for key in ["noInput","noMatch","onTimeout","onSuccess","onFailure","onComplete"]:
            val = data.get(key, {})
            if isinstance(val, dict):
                r = self._ref(val.get("next"))
                if r: refs.append(r)
                sub = val.get("onMaxRetries", {})
                if isinstance(sub, dict):
                    r = self._ref(sub.get("next"))
                    if r: refs.append(r)
        for v in data.get("onInput", {}).values():
            r = self._ref(v)
            if r: refs.append(r)
        for action in data.get("actions", []):
            if isinstance(action, dict):
                refs.extend(self._extract_refs(action))
        return list(set(refs))

    def _parse_node(self, data):
        nid = str(data.get("id", uuid.uuid4()))
        ntype = GENESYS_TYPE_MAP.get(data.get("type", "unknown").lower(), NodeType.UNKNOWN)
        return IVRNode(id=nid, name=data.get("name", nid), type=ntype,
            next_nodes=self._extract_refs(data),
            prompt_text=data.get("tts", data.get("prompt", data.get("text"))),
            timeout_seconds=data.get("timeout"), max_retries=data.get("maxRetries"),
            transfer_target=data.get("queue", data.get("target")),
            variable_name=data.get("variable"), api_endpoint=data.get("url"), raw_config=data)

    def _validate_flow(self, flow):
        all_ids = set(flow.nodes.keys())
        refs = set()
        for node in flow.nodes.values():
            refs.update(node.next_nodes)
        for ref in refs - all_ids:
            flow.add_error(FlowError(error_type="broken_reference", severity=Severity.HIGH,
                affected_node_id=ref, description="Nodo referenciado no existe: " + ref, recommendation="Verificar nodo"))
        for node in flow.nodes.values():
            if node.type != NodeType.EXIT and not node.next_nodes:
                flow.add_error(FlowError(error_type="dead_end", severity=Severity.CRITICAL,
                    affected_node_id=node.id, description="Nodo sin salida: " + node.name, recommendation="Añadir transicion"))
