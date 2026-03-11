"""
Test del Universal IVR Flow Model.
Construye un flujo de ejemplo y verifica que el schema funciona.
"""
import sys
sys.path.insert(0, 'src')

from models.ivr.flow_model import (
    IVRFlow, IVRNode, FlowError, NodeType, Severity
)

def test_basic_flow():
    """Construye un flujo IVR simple y verifica el schema."""
    
    # Crear flujo
    flow = IVRFlow(
        flow_id="test-001",
        flow_name="Flujo de Bienvenida",
        provider="genesys"
    )
    
    # Añadir nodos
    flow.add_node(IVRNode(
        id="node_entry",
        name="Entrada principal",
        type=NodeType.ENTRY,
        next_nodes=["node_menu"]
    ))
    
    flow.add_node(IVRNode(
        id="node_menu",
        name="Menú principal",
        type=NodeType.MENU,
        prompt_text="Pulse 1 para ventas, pulse 2 para soporte",
        next_nodes=["node_ventas", "node_soporte"],
        timeout_seconds=10,
        max_retries=3
    ))
    
    flow.add_node(IVRNode(
       d="node_ventas",
        name="Transferencia a ventas",
        type=NodeType.TRANSFER,
        transfer_target="cola_ventas",
        next_nodes=["node_exit"]
    ))
    
    flow.add_node(IVRNode(
        id="node_soporte",
        name="Transferencia a soporte",
        type=NodeType.TRANSFER,
        transfer_target="cola_soporte",
        next_nodes=["node_exit"]
    ))
    
    flow.add_node(IVRNode(
        id="node_exit",
        name="Salida del flujo",
        type=NodeType.EXIT,
        next_nodes=[]
    ))
    
    # Añadir un error de ejemplo
    flow.add_error(FlowError(
        error_type="missing_timeout",
        severity=Severity.MEDIUM,
        affected_node_id="node_menu",
        description="El nodo de menú no tiene configurado un timeout de fallback",
        recommendation="Añadir rama de timeout que dirija al cliente a un agente"
    ))
    
    # Verificaciones
    assert flow.total_nodes == 5, f"Esperaba 5 nodos, tengo {flow.total_nodes}"
    assert flow.entry_node_id == "node_ry", "Entry node no detectado"
    assert len(flow.errors) == 1, "Debería haber 1 error"
    assert flow.get_critical_errors() == [], "No debería haber errores críticos"
    
    summary = flow.summary()
    assert summary["total_nodes"] == 5
    assert summary["total_errors"] == 1
    assert summary["critical_errors"] == 0
    
    print("✅ IVRFlow schema funciona correctamente")
    print(f"   Nodos: {summary['total_nodes']}")
    print(f"   Errores: {summary['total_errors']}")
    print(f"   Tipos de nodo: {summary['node_types']}")
    print(f"   Entry node: {flow.entry_node_id}")

if __name__ == "__main__":
    test_basic_flow()
