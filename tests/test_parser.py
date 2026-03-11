import sys
sys.path.insert(0, '.')

from src.parsers.genesys_yaml_parser import GenesysYAMLParser

YAML_EJEMPLO = """
nodes:
  - id: entrada
    name: Entrada principal
    type: entry
    next: [menu_principal]

  - id: menu_principal
    name: Menu de bienvenida
    type: menu
    prompt: "Pulse 1 para ventas, pulse 2 para soporte"
    timeout: 10
    next: [ventas, soporte]

  - id: ventas
    name: Cola de ventas
    type: transfer
    queue: cola_ventas
    next: [salida]

  - id: soporte
    name: Cola de soporte
    type: transfer
    queue: cola_soporte
    next: [salida]

  - id: salida
    name: Fin del flujo
    type: exit
"""

parser = GenesysYAMLParser()
flow = parser.parse(YAML_EJEMPLO, flow_name="Flujo Demo Genesys")

print(f"✅ Parser funcionando")
print(f"   Flow: {flow.flow_name}")
print(f"   Nodos parseados: {flow.total_nodes}")
print(f"   Entry node: {flow.entry_node_id}")
print(f"   Errores: {len(flow.errors)}")
print(f"   Resumen: {flow.summary}")
