import time
from ..models.ivr.flow_model import IVRFlow
from .analyzer import IVRAnalyzer

class BatchAnalyzer:
    def __init__(self):
        self.analyzer = IVRAnalyzer()

    def analyze_batch(self, flows: list, delay_seconds: float = 1.0) -> dict:
        results = []
        for i, (name, flow) in enumerate(flows):
            print(f"Analizando {i+1}/{len(flows)}: {name}")
            result = self.analyzer.analyze(flow)
            results.append({
                "flow_name": name,
                "score": result.get("score", 0),
                "dimension_scores": result.get("dimension_scores", {}),
                "critical_issues": result.get("critical_issues", []),
                "improvements": result.get("improvements", []),
                "api_analysis": result.get("api_analysis", {}),
                "summary": result.get("summary", ""),
                "recommendation": result.get("recommendation", ""),
                "tokens_used": result.get("tokens_used", {})
            })
            if i < len(flows) - 1:
                time.sleep(delay_seconds)

        results.sort(key=lambda x: x["score"], reverse=True)
        scores = [r["score"] for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0

        distribution = {"excelente": 0, "sano": 0, "atencion": 0, "critico": 0}
        for s in scores:
            if s >= 85: distribution["excelente"] += 1
            elif s >= 70: distribution["sano"] += 1
            elif s >= 50: distribution["atencion"] += 1
            else: distribution["critico"] += 1

        return {
            "results": results,
            "summary": {
                "total_flows": len(results),
                "avg_score": round(avg_score, 1),
                "best_flow": results[0]["flow_name"] if results else None,
                "worst_flow": results[-1]["flow_name"] if results else None,
                "distribution": distribution
            }
        }
