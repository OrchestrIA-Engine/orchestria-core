import json, sys
sys.path.insert(0, ".")
from src.parsers.genesys_cloud_parser import GenesysCloudParser

def test_cloud_parser_basic():
    sample = {"name": "TestFlow", "flow": {"states": [
        {"refId": "start", "type": "menu", "name": "Main Menu", "transitions": [{"targetStateRefId": "transfer"}]},
        {"refId": "transfer", "type": "transfer", "name": "Transfer Agent", "transitions": []}
    ]}}
    flow = GenesysCloudParser().parse(json.dumps(sample))
    assert flow.flow_name == "TestFlow"
    assert len(flow.nodes) == 2
    assert len(flow.errors) == 0
    print(f"✅ Cloud parser OK: {flow.flow_name}, {len(flow.nodes)} nodos, {len(flow.errors)} errores")

test_cloud_parser_basic()
