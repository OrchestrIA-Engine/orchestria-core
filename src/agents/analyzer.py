import os
import json
import re
from src.models.ivr.flow_model import IVRFlow
from src.agents.inventory import FlowInventoryExtractor
from src.agents.deterministic_scorer import DeterministicScorer
from src.llm.anthropic_adapter import AnthropicAdapter
from src.llm.base import Message, LLMConfig

ANALYSIS_PROMPT = """Eres un experto en contact center y soluciones IVR de Genesys.
El score de calidad ya ha sido calculado de forma determinista: {deterministic_score}/100.

Desglose del score:
{score_breakdown}

Issues detectados:
{issues_list}

Basandote UNICAMENTE en estos datos, proporciona un analisis cualitativo.
Responde UNICAMENTE con JSON valido sin markdown ni texto adicional:
{{
  "summary": "<resumen ejecutivo de 2-3 frases>",
  "critical_issues": ["<issue critico 1>", "<issue critico 2>"],
  "improvements": ["<mejora recomendada 1>", "<mejora recomendada 2>"],
  "recommendation": "<recomendacion principal>"
}}
No inventes issues que no esten en los datos."""


class IVRAnalyzer:
    def __init__(self, sector: str = "default"):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.llm = AnthropicAdapter(api_key=api_key)
        self.config = LLMConfig(model="claude-sonnet-4-6", max_tokens=1500, temperature=0.0)
        self.sector = sector

    def analyze(self, flow: IVRFlow) -> dict:
        inv = FlowInventoryExtractor().extract(flow)
        scorer = DeterministicScorer(sector=self.sector)
        scoring = scorer.score(inv)
        sd = scoring.to_dict()

        breakdown_text = "\n".join([
            f"  {k}: {v['score']}/{v['max']} pts"
            for k, v in sd["deterministic_breakdown"].items()
        ])
        issues_text = "\n".join([
            f"  [{i['dim']}] {i['severity']}: {i['message']} (-{i['penalty']} pts)"
            for i in sd["deterministic_issues"]
        ]) or "  No issues detected."

        prompt = ANALYSIS_PROMPT.format(
            deterministic_score=sd["deterministic_score"],
            score_breakdown=breakdown_text,
            issues_list=issues_text,
        )

        result = {
            "score":                   sd["deterministic_score"],
            "deterministic_breakdown": sd["deterministic_breakdown"],
            "deterministic_issues":    sd["deterministic_issues"],
            "score_explanation":       sd["score_explanation"],
            "summary":        "",
            "critical_issues": [],
            "improvements":   [],
            "recommendation": "",
            "inventory":      inv,
            "tokens_used":    {"input": 0, "output": 0},
        }

        try:
            response = self.llm.complete([Message(role="user", content=prompt)], self.config)
            result["tokens_used"] = {"input": response.input_tokens, "output": response.output_tokens}
            raw = response.content.strip()
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                raw = match.group(0)
            parsed = json.loads(raw)
            for key in ("summary", "critical_issues", "improvements", "recommendation"):
                if key in parsed:
                    result[key] = parsed[key]
        except Exception as e:
            result["critical_issues"] = [f"Error en analisis: {str(e)}"]

        return result
