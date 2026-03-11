from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime

app = FastAPI(
    title="OrchestrIA API",
    description="AI-powered IVR analysis engine",
    version="0.1.0"
)

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
    status: str
    processed_at: str

@app.get("/")
def root():
    return {"product": "OrchestrIA", "version": "0.1.0", "status": "operational"}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_flow(request: AnalyzeRequest):
    if not request.flow_yaml.strip():
        raise HTTPException(status_code=400, detail="flow_yaml no puede estar vacío")
    return AnalyzeResponse(
        flow_id="flow-001",
        flow_name=request.flow_name,
        total_nodes=0,
        total_errors=0,
        critical_errors=0,
        status="parsed",
        processed_at=datetime.now().isoformat()
    )
    