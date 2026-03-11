from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class NodeType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"
    MENU = "menu"
    PROMPT = "prompt"
    INPUT = "input"
    SPEECH = "speech"
    CONDITION = "condition"
    SWITCH = "switch"
    SET_VARIABLE = "set_variable"
    TRANSFER = "transfer"
    CALLBACK = "callback"
    API_CALL = "api_call"
    LOOP = "loop"
    UNKNOWN = "unknown"

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class IVRNode(BaseModel):
    id: str
    name: str
    type: NodeType
    next_nodes: list[str] = Field(default_factory=list)
    prompt_text: Optional[str] = None
    timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None
    transfer_target: Optional[str] = None
    variable_name: Optional[str] = None
    api_endpoint: Optional[str] = None
    raw_config: Optional[dict] = None

class FlowError(BaseModel):
    error_type: str
    severity: Severity
    affected_node_id: str
    description: str
    recommendation: str

class IVRFlow(BaseModel):
    flow_id: str
    flow_name: str
    provider: str = "genesys"
    nodes: dict[str, IVRNode] = Field(default_factory=dict)
    entry_node_id: Optional[str] = None
    errors: list[FlowError] = Field(default_factory=list)
    total_nodes: int = 0
    created_at: datetime = Field(default_factory=datetime.now)

    def add_node(self, node: IVRNode) -> None:
        self.nodes[node.id] = node
        self.total_nodes = len(self.nodes)
        if node.type == NodeType.ENTRY:
            self.entry_node_id = node.id

    def add_error(self, error: FlowError) -> None:
        self.errors.append(error)

    def get_critical_errors(self) -> list[FlowError]:
        return [e for e in self.errors if e.severity == Severity.CRITICAL]

    def summary(self) -> dict:
        return {
            "flow_name": self.flow_name,
            "total_nodes": self.total_nodes,
            "total_errors": len(self.errors),
            "critical_errors": len(self.get_critical_errors()),
            "node_types": {
                nt.value: sum(1 for n in self.nodes.values() if n.type == nt)
                for nt in NodeType
                if any(n.type == nt for n in self.nodes.values())
            }
        }
