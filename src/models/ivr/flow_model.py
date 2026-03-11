"""
Universal IVR Flow Model
========================
Schema interno que representa cualquier flujo IVR independientemente
del proveedor (Genesys, Avaya, Cisco...).

El Parser convierte configuraciones nativas a este modelo.
El Analyzer trabaja exclusivamente sobre este modelo.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ── TIPOS DE NODO ────────────────────────────────────────────────────────────

class NodeType(str, Enum):
    """14 tipos de nodo universales en cualquier flujo IVR."""
    
    # Entrada y salida
    ENTRY          = "entry"           # Punto de entrada al flujo
    EXIT           = "exit"            # Punto de salida (cuelga, transfiere)
    
    # Interacción con el cliente
    MENU           = "menu"            # Menú DTMF (pulse 1 put"           # Captura de dígitos del cliente
    SPEECH         = "speech"          # Reconocimiento de voz
    
    # Lógica y decisiones
    CONDITION      = "condition"       # Bifurcación condicional (if/else)
    SWITCH         = "switch"          # Múltiples ramas según variable
    
    # Operaciones
    SET_VARIABLE   = "set_variable"    # Asigna valor a una variable
    TRANSFER       = "transfer"        # Transfiere a agente, cola o número
    CALLBACK       = "callback"        # Programa una llamada de vuelta
    
    # Integraciones
    API_CALL       = "api_call"        # Llamada a sistema externo (CRM, BD)
    
    # Control de flujo
    LOOP           = "loop"            # Bucle con contador
    UNKNOWN        = "unknown"         # Nodo no reconocido (señal de error)


# ── SEVERIDAD DE ERRORES ─────────────────────────────────────────────────────

class Severity(str, Enum):cia significativamente  
    MEDIUM   = "medium"     # Problema menor, flujo funciona
    LOW      = "low"        # Mejora recomendada


# ── NODO ─────────────────────────────────────────────────────────────────────

class IVRNode(BaseModel):
    """Representa un nodo individual dentro del flujo IVR."""
    
    id: str = Field(..., description="Identificador único del nodo")
    name: str = Field(..., description="Nombre descriptivo del nodo")
    type: NodeType = Field(..., description="Tipo de nodo")
    
    # Conexiones
    next_nodes: list[str] = Field(
        default_factory=list,
        description="IDs de los nodos a los que puede ir este nodo"
    )
    
    # Propiedades opcionales según el tipo
    prompt_text: Optional[str] = Field(
        None, description="Texto del audio que escucha el cliente"
    )
    timeout_seconds: Optional[int] = Field(
  ximo de reintentos"
    )
    transfer_target: Optional[str] = Field(
        None, description="Destino de transferencia (cola, número, agente)"
    )
    variable_name: Optional[str] = Field(
        None, description="Variable que lee o escribe este nodo"
    )
    api_endpoint: Optional[str] = Field(
        None, description="Endpoint al que llama este nodo"
    )
    
    # Metadata
    raw_config: Optional[dict] = Field(
        None, description="Configuración original del proveedor (para trazabilidad)"
    )


# ── ERROR DETECTADO ──────────────────────────────────────────────────────────

class FlowError(BaseModel):
    """Error o problema detectado en el flujo."""
    
    error_type: str = Field(..., description="Tipo de error (dead_end, infinite_loop...)")
    severity: Severity = Field(..., description="Severidad del error")
    affected_node_id: str = Field(..., descriptioendation: str = Field(..., description="Qué hacer para corregirlo")


# ── FLUJO COMPLETO ───────────────────────────────────────────────────────────

class IVRFlow(BaseModel):
    """
    Representación completa de un flujo IVR.
    Esta es la unidad de trabajo de OrchestrIA.
    """
    
    # Identificación
    flow_id: str = Field(..., description="ID único del flujo")
    flow_name: str = Field(..., description="Nombre del flujo")
    provider: str = Field(
        default="genesys",
        description="Proveedor origen (genesys, avaya, cisco...)"
    )
    
    # Estructura
    nodes: dict[str, IVRNode] = Field(
        default_factory=dict,
        description="Diccionario de nodos indexados por ID"
    )
    entry_node_id: Optional[str] = Field(
        None, description="ID del nodo de entrada al flujo"
    )
    
    # Análisis
    errors: list[FlowError] = Field(
       eld(default=0, description="Total de nodos en el flujo")
    created_at: datetime = Field(default_factory=datetime.now)
    
    def add_node(self, node: IVRNode) -> None:
        """Añade un nodo al flujo y actualiza el contador."""
        self.nodes[node.id] = node
        self.total_nodes = len(self.nodes)
        if node.type == NodeType.ENTRY:
            self.entry_node_id = node.id
    
    def add_error(self, error: FlowError) -> None:
        """Registra un error detectado en el flujo."""
        self.errors.append(error)
    
    def get_critical_errors(self) -> list[FlowError]:
        """Devuelve solo los errores críticos."""
        return [e for e in self.errors if e.severity == Severity.CRITICAL]
    
    def summary(self) -> dict:
        """Resumen ejecutivo del flujo para el Documentor."""
        return {
            "flow_name": self.flow_name,
            "total_nodes": self.total_nodes,
            "total_errors": len(self.errors),
            "critical_errors": len(self.get_criticaerrors()),
            "node_types": {
                nt.value: sum(1 for n in self.nodes.values() if n.type == nt)
                for nt in NodeType
                if any(n.type == nt for n in self.nodes.values())
            }
        }
