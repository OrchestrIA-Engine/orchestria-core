from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import os, sys
sys.path.insert(0, ".")
from src.parsers.genesys_yaml_parser import GenesysYAMLParser
from src.agents.analyzer import IVRAnalyzer

app = FastAPI(title="OrchestrIA API", description="AI-powered IVR analysis engine", version="0.2.0")
parser = GenesysYAMLParser()

class AnalyzeRequest(BaseModel):
    flow_yaml: str
    flow_name: str = "Unnamed Flow"
    provider: str = "genesys"

class AnalyzeResponse(BaseModel):
    flow_id: str
    flow_name: str
    total_nodes: int
    total_errors: int
    critical_errors: int
    score: int
    summary: str
    critical_issues: list[str]
    improvements: list[str]
    recommendation: str
    status: str
    processed_at: str

@app.get("/")
def root():
    return {"product": "OrchestrIA", "version": "0.2.0", "status": "operational"}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


def detect_and_parse(content: str):
    content = content.strip()
    if content.startswith('{'):
        from src.parsers.genesys_cloud_parser import GenesysCloudParser
        return GenesysCloudParser().parse(content)
    else:
        from src.parsers.genesys_yaml_parser import GenesysYAMLParser
        return detect_and_parse(content)

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_flow(request: AnalyzeRequest):
    if not request.flow_yaml.strip():
        raise HTTPException(status_code=400, detail="flow_yaml no puede estar vacio")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API key no configurada")
    flow = parser.parse(request.flow_yaml, flow_name=request.flow_name)
    analyzer = IVRAnalyzer(api_key=api_key)
    result = analyzer.analyze(flow)
    return AnalyzeResponse(flow_id=flow.flow_id, flow_name=flow.flow_name, total_nodes=flow.total_nodes, total_errors=len(flow.errors), critical_errors=len(flow.get_critical_errors()), score=result.get("score", 0), summary=result.get("summary", ""), critical_issues=result.get("critical_issues", []), improvements=result.get("improvements", []), recommendation=result.get("recommendation", ""), status="analyzed", processed_at=datetime.now().isoformat())
