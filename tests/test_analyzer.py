import sys, os
sys.path.insert(0, '.')

from src.parsers.genesys_yaml_parser import GenesysYAMLParser
from src.agents.analyzer import IVRAnalyzer

YAML_CON_PROBLEMAS = """
nodes:
  - id: entrada
    name: Entrada principal
    type: entry
    next: [menu_principal]

  - id: menu_principal
    name: Menu de bienvenida
    type: menu
    prompt: "Pulse 1 para ventas, pulse 2 para soporte, pulse 3 para facturacion, pulse 4 para reclamaciones, pulse 5 para otros"
    next: [ventas, soporte, facturacion, reclamaciones]

  - id: ventas
    name: Cola de ventas
    type: transfer
    queue: cola_ventas
    next: []

  - id: soporte
    name: Cola de soporte
    type: transfer
    queue: cola_soporte
    next: []

  - id: facturacion
    name: Nodo huerfano sin salida
    type: condition
    next: []

  - id: reclamaciones
    name: Cola reclamaciones
    type: transfer
    queue: cola_reclamaciones
    next: [salida]

  - id: salida
    name: Fin del flujo
    type: exit
"""

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY no encontrada")
    sys.exit(1)

print("Parseando flujo IVR...")
parser = GenesysYAMLParser()
flow = parser.parse(YAML_CON_PROBLEMAS, flow_name="Flujo con Problemas")
print(f"Nodos: {flow.total_nodes} | Errores parser: {len(flow.errors)}")

print("\nAnalizando con Claude...")
analyzer = IVRAnalyzer(api_key=api_key)
result = analyzer.analyze(flow)

print("\n" + "="*50)
print("RESULTADO DEL ANALYZER")
print("="*50)
print(f"Score: {result.get('score')}/100")
print(f"Resumen: {result.get('summary')}")
print(f"\nProblemas criticos:")
for issue in result.get('critical_issues', []):
    print(f"  - {issue}")
print(f"\nMejoras sugeridas:")
for imp in result.get('improvements', []):
    print(f"  + {imp}")
print(f"\nRecomendacion: {result.get('recommendation')}")
print(f"\nTokens usados: {result.get('tokens_used')}")
