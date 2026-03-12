import sys, os
sys.path.insert(0, '.')
from src.parsers.genesys_yaml_parser import GenesysYAMLParser
from src.agents.analyzer import IVRAnalyzer
from src.agents.documentor import IVRDocumentor

YAML = """
nodes:
  - id: entrada
    name: Entrada
    type: entry
    next: [menu]
  - id: menu
    name: Menu principal
    type: menu
    prompt: Pulse 1 ventas pulse 2 soporte
    timeout: 10
    next: [ventas, soporte]
  - id: ventas
    name: Ventas
    type: transfer
    queue: cola_ventas
    next: [salida]
  - id: soporte
    name: Soporte
    type: transfer
    queue: cola_soporte
    next: [salida]
  - id: salida
    name: Fin
    type: exit
"""

api_key = os.environ.get("ANTHROPIC_API_KEY")
parser = GenesysYAMLParser()
flow = parser.parse(YAML, flow_name="Flujo Prueba PDF")
analyzer = IVRAnalyzer(api_key=api_key)
analysis = analyzer.analyze(flow)
print(f"Score: {analysis.get('score')}/100")
documentor = IVRDocumentor(api_key=api_key)
pdf = documentor.generate_pdf(flow, analysis, "informe_test.pdf")
print(f"PDF generado: {pdf}")
