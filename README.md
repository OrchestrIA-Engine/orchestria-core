# OrchestrIA Core — IVR·IA

> Analisis inteligente de flujos IVR Genesys con IA

## Que hace

OrchestrIA analiza configuraciones de flujos IVR de Genesys Engage y detecta automaticamente errores estructurales, problemas de experiencia de cliente y oportunidades de mejora.

Genera un informe ejecutivo PDF listo para presentar al cliente en menos de 60 segundos.

## Stack

- Python 3.12 + FastAPI
- Claude API (claude-sonnet-4-6)
- Pydantic v2
- Streamlit (UI)
- ReportLab (PDF)

## Arrancar en local
```bash
git clone https://github.com/OrchestrIA-Engine/orchestria-core
cd orchestria-core
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```

## API
```bash
uvicorn src.api.main:app --reload --port 8000
```

Swagger en http://localhost:8000/docs

## Tests
```bash
python tests/test_parser.py
python tests/test_analyzer.py
python tests/test_documentor.py
python tests/evaluation/run_suite
```

## Arquitectura

YAML Genesys -> Parser -> IVRFlow -> Analyzer (Claude) -> Documentor -> PDF

## Estado

- Parser YAML Genesys v0.1
- Analyzer v0.1 — Claude detecta errores en flujos IVR
- Documentor v0.1 — genera informes PDF ejecutivos
- API FastAPI v0.2
- UI Streamlit v0.1
- Evaluation suite 5/5 passing
