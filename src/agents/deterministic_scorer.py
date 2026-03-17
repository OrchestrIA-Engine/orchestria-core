"""
OrchestrIA — Deterministic Scoring Engine
==========================================
Scoring 100% determinista basado en análisis de grafo.
Sin LLM. Irrefutable ante clientes enterprise.

Dimensiones:
  D1  Structural Integrity      25 pts
  D2  Dependency Exposure       20 pts
  D3  UX Architecture           20 pts
  D4  Failure Resilience        20 pts
  D5  Maintainability           10 pts
  D6  Migration Readiness        5 pts
  ─────────────────────────────────────
  TOTAL                        100 pts
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


# ── SECTOR BENCHMARKS ─────────────────────────────────────────────────────────
# Self-service ratio benchmarks por sector (fuente: Genesys State of CX 2024)
SECTOR_BENCHMARKS = {
    "banking":     {"self_service_avg": 52, "self_service_top": 72},
    "telco":       {"self_service_avg": 48, "self_service_top": 68},
    "insurance":   {"self_service_avg": 44, "self_service_top": 62},
    "public":      {"self_service_avg": 38, "self_service_top": 55},
    "ecommerce":   {"self_service_avg": 55, "self_service_top": 75},
    "healthcare":  {"self_service_avg": 35, "self_service_top": 50},
    "default":     {"self_service_avg": 45, "self_service_top": 65},
}

# Penalizaciones por tipo de problema (puntos perdidos)
PENALTIES = {
    # D1 — Structural Integrity
    "dead_end":              4,   # por cada dead end
    "deep_flow":             3,   # flujo con depth > 8
    "very_deep_flow":        5,   # flujo con depth > 12 (acumulativo)
    "unreachable_node":      2,   # por cada nodo no alcanzable

    # D2 — Dependency Exposure
    "api_without_fallback":  5,   # por cada API sin fallback estático
    "single_point_failure":  8,   # auth sin alternativa = SPOF
    "unresolved_tts_var":    2,   # variable TTS sin valor por defecto

    # D3 — UX Architecture
    "below_avg_ss_ratio":    8,   # self-service < average sectorial
    "menu_gt_5_options":     3,   # menú con >5 opciones
    "no_zero_out":           5,   # sin opción de hablar con agente
    "deep_menu_nesting":     4,   # menú anidado > 3 niveles

    # D4 — Failure Resilience
    "menu_no_handler":       4,   # por cada menú sin noInput/noMatch
    "transfer_no_timeout":   3,   # por cada transfer sin timeout handler
    "missing_fallback":      3,   # fallback path ausente

    # D5 — Maintainability
    "no_inter_flow":         3,   # monolito sin sub-flows
    "excessive_nodes":       4,   # >60 nodos en un solo flujo

    # D6 — Migration Readiness
    "voicemail_node":        2,   # Voicemail no soportado en Cloud nativo
    "schedule_node":         1,   # Schedule requiere config adicional Cloud
    "dual_input_complexity": 2,   # DTMF + Speech = doble effort de testing
}


@dataclass
class DimensionResult:
    name: str
    max_pts: int
    earned_pts: int
    issues: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def pct(self) -> float:
        return round(self.earned_pts / self.max_pts * 100, 1) if self.max_pts else 0

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "max":        self.max_pts,
            "score":      self.earned_pts,
            "pct":        self.pct,
            "issues":     self.issues,
        }


@dataclass
class ScoringResult:
    total: int
    dimensions: Dict[str, DimensionResult]
    all_issues: List[Dict[str, Any]]
    explanation: str

    def to_dict(self) -> dict:
        return {
            "deterministic_score":      self.total,
            "deterministic_breakdown":  {k: v.to_dict() for k, v in self.dimensions.items()},
            "deterministic_issues":     self.all_issues,
            "score_explanation":        self.explanation,
        }


class DeterministicScorer:
    """
    Calcula el score de calidad de un flujo IVR de forma 100% determinista.
    Input: dict producido por FlowInventoryExtractor.extract()
    Output: ScoringResult con desglose granular por dimensión.
    """

    def __init__(self, sector: str = "default"):
        self.sector = sector
        self.benchmark = SECTOR_BENCHMARKS.get(sector, SECTOR_BENCHMARKS["default"])

    def score(self, inv: dict) -> ScoringResult:
        d1 = self._d1_structural_integrity(inv)
        d2 = self._d2_dependency_exposure(inv)
        d3 = self._d3_ux_architecture(inv)
        d4 = self._d4_failure_resilience(inv)
        d5 = self._d5_maintainability(inv)
        d6 = self._d6_migration_readiness(inv)

        dims = {"D1": d1, "D2": d2, "D3": d3, "D4": d4, "D5": d5, "D6": d6}
        total = sum(d.earned_pts for d in dims.values())
        total = max(0, min(100, total))

        all_issues = []
        for d in dims.values():
            all_issues.extend(d.issues)

        explanation = self._build_explanation(total, dims, all_issues)

        return ScoringResult(
            total=total,
            dimensions=dims,
            all_issues=all_issues,
            explanation=explanation,
        )

    # ── D1 — STRUCTURAL INTEGRITY (25 pts) ────────────────────────────────────
    def _d1_structural_integrity(self, inv: dict) -> DimensionResult:
        max_pts = 25
        penalty = 0
        issues = []

        dead_ends = inv.get("dead_ends", [])
        if dead_ends:
            p = min(len(dead_ends) * PENALTIES["dead_end"], 16)
            penalty += p
            issues.append({
                "dim": "D1", "severity": "HIGH",
                "code": "DEAD_ENDS",
                "message": f"{len(dead_ends)} dead end(s) detected — nodes with no valid exit path",
                "nodes": dead_ends[:10],
                "penalty": p,
                "fix": "Add a fallback transfer_to_agent or exit node to each dead end",
            })

        depth = inv.get("flow_depth", 0)
        if depth > 12:
            p = PENALTIES["deep_flow"] + PENALTIES["very_deep_flow"]
            penalty += p
            issues.append({
                "dim": "D1", "severity": "MEDIUM",
                "code": "VERY_DEEP_FLOW",
                "message": f"Flow depth {depth} exceeds recommended maximum of 12 hops",
                "penalty": p,
                "fix": "Refactor deep branches into reusable sub-flows",
            })
        elif depth > 8:
            p = PENALTIES["deep_flow"]
            penalty += p
            issues.append({
                "dim": "D1", "severity": "LOW",
                "code": "DEEP_FLOW",
                "message": f"Flow depth {depth} exceeds recommended maximum of 8 hops",
                "penalty": p,
                "fix": "Consider splitting deep flows into sub-flows for maintainability",
            })

        earned = max(0, max_pts - penalty)
        return DimensionResult("Structural Integrity", max_pts, earned, issues)

    # ── D2 — DEPENDENCY EXPOSURE (20 pts) ─────────────────────────────────────
    def _d2_dependency_exposure(self, inv: dict) -> DimensionResult:
        max_pts = 20
        penalty = 0
        issues = []

        auth_services = inv.get("auth_services", [])
        if auth_services and inv.get("total_external_deps", 0) > 0:
            # Auth sin fallback = SPOF
            p = PENALTIES["single_point_failure"]
            penalty += p
            issues.append({
                "dim": "D2", "severity": "CRITICAL",
                "code": "AUTH_SPOF",
                "message": f"Auth service(s) {auth_services} — single point of failure if unavailable",
                "penalty": p,
                "fix": "Add static fallback path if auth service is unreachable",
            })

        data_services = inv.get("data_services", [])
        api_calls = inv.get("api_calls", 0)
        if data_services or api_calls > 0:
            # Penalizar APIs sin fallback (aproximación: si hay APIs y no hay inter_flow_calls de fallback)
            n_apis = len(data_services) + (1 if api_calls > 3 else 0)
            p = min(n_apis * PENALTIES["api_without_fallback"], 12)
            if p > 0:
                penalty += p
                issues.append({
                    "dim": "D2", "severity": "HIGH",
                    "code": "API_NO_FALLBACK",
                    "message": f"{n_apis} external API(s) detected without confirmed static fallback",
                    "services": data_services,
                    "penalty": p,
                    "fix": "Implement static fallback responses for each external API call",
                })

        dynamic_vars = inv.get("dynamic_variables", [])
        if len(dynamic_vars) > 3:
            p = min((len(dynamic_vars) - 3) * PENALTIES["unresolved_tts_var"], 6)
            penalty += p
            issues.append({
                "dim": "D2", "severity": "LOW",
                "code": "EXCESS_DYNAMIC_VARS",
                "message": f"{len(dynamic_vars)} dynamic TTS variables — verify default values exist",
                "penalty": p,
                "fix": "Ensure all dynamic TTS variables have static fallback values",
            })

        earned = max(0, max_pts - penalty)
        return DimensionResult("Dependency Exposure", max_pts, earned, issues)

    # ── D3 — UX ARCHITECTURE (20 pts) ─────────────────────────────────────────
    def _d3_ux_architecture(self, inv: dict) -> DimensionResult:
        max_pts = 20
        penalty = 0
        issues = []

        ss_ratio = inv.get("self_service_ratio", 0)
        avg_benchmark = self.benchmark["self_service_avg"]
        top_benchmark = self.benchmark["self_service_top"]

        if ss_ratio < avg_benchmark:
            p = PENALTIES["below_avg_ss_ratio"]
            penalty += p
            issues.append({
                "dim": "D3", "severity": "HIGH",
                "code": "LOW_SELF_SERVICE",
                "message": (
                    f"Self-service ratio {ss_ratio}% is below sector average "
                    f"({avg_benchmark}% for {self.sector}). "
                    f"Top performers reach {top_benchmark}%."
                ),
                "penalty": p,
                "fix": "Review routing logic — too many paths escalate to agent unnecessarily",
            })

        menu_nodes = inv.get("menu_nodes", 0)
        total_nodes = inv.get("total_nodes", 1)
        if menu_nodes > 0 and total_nodes > 0:
            menu_ratio = menu_nodes / total_nodes
            if menu_ratio > 0.4:
                p = PENALTIES["deep_menu_nesting"]
                penalty += p
                issues.append({
                    "dim": "D3", "severity": "MEDIUM",
                    "code": "HIGH_MENU_DENSITY",
                    "message": f"Menu density {round(menu_ratio*100)}% — complex nested menu structure detected",
                    "penalty": p,
                    "fix": "Flatten menu hierarchy — more than 3 levels degrades caller experience",
                })

        unique_queues = inv.get("unique_queues", [])
        if not unique_queues:
            p = PENALTIES["no_zero_out"]
            penalty += p
            issues.append({
                "dim": "D3", "severity": "HIGH",
                "code": "NO_AGENT_ESCALATION",
                "message": "No agent transfer queues detected — callers cannot reach a human agent",
                "penalty": p,
                "fix": "Add zero-out (0 key) option in main menus to transfer to agent",
            })

        earned = max(0, max_pts - penalty)
        return DimensionResult("UX Architecture", max_pts, earned, issues)

    # ── D4 — FAILURE RESILIENCE (20 pts) ──────────────────────────────────────
    def _d4_failure_resilience(self, inv: dict) -> DimensionResult:
        max_pts = 20
        penalty = 0
        issues = []

        menus_no_handler = inv.get("menus_without_handlers", [])
        if menus_no_handler:
            p = min(len(menus_no_handler) * PENALTIES["menu_no_handler"], 12)
            penalty += p
            issues.append({
                "dim": "D4", "severity": "HIGH",
                "code": "MENUS_NO_INPUT_HANDLER",
                "message": (
                    f"{len(menus_no_handler)} menu(s) missing noInput/noMatch/timeout handlers"
                ),
                "nodes": menus_no_handler[:10],
                "penalty": p,
                "fix": "Add noInput, noMatch and timeout handlers to all menu nodes",
            })

        missing_fb = inv.get("missing_fallbacks", [])
        if missing_fb:
            p = min(len(missing_fb) * PENALTIES["missing_fallback"], 9)
            penalty += p
            issues.append({
                "dim": "D4", "severity": "MEDIUM",
                "code": "MISSING_FALLBACKS",
                "message": f"{len(missing_fb)} transfer node(s) missing timeout/fallback configuration",
                "nodes": missing_fb[:10],
                "penalty": p,
                "fix": "Add timeout and fallback handlers to all transfer nodes",
            })

        earned = max(0, max_pts - penalty)
        return DimensionResult("Failure Resilience", max_pts, earned, issues)

    # ── D5 — MAINTAINABILITY (10 pts) ─────────────────────────────────────────
    def _d5_maintainability(self, inv: dict) -> DimensionResult:
        max_pts = 10
        penalty = 0
        issues = []

        inter_flow = inv.get("inter_flow_calls", [])
        total_nodes = inv.get("total_nodes", 0)

        if total_nodes > 30 and not inter_flow:
            p = PENALTIES["no_inter_flow"]
            penalty += p
            issues.append({
                "dim": "D5", "severity": "MEDIUM",
                "code": "MONOLITHIC_FLOW",
                "message": f"Flow has {total_nodes} nodes with no sub-flow references — monolithic structure",
                "penalty": p,
                "fix": "Extract reusable logic (auth, error handling) into dedicated sub-flows",
            })

        if total_nodes > 60:
            p = PENALTIES["excessive_nodes"]
            penalty += p
            issues.append({
                "dim": "D5", "severity": "HIGH",
                "code": "EXCESSIVE_NODES",
                "message": f"Flow has {total_nodes} nodes — exceeds recommended maximum of 60",
                "penalty": p,
                "fix": "Decompose into multiple focused flows connected via inter-flow calls",
            })

        earned = max(0, max_pts - penalty)
        return DimensionResult("Maintainability", max_pts, earned, issues)

    # ── D6 — MIGRATION READINESS (5 pts) ──────────────────────────────────────
    def _d6_migration_readiness(self, inv: dict) -> DimensionResult:
        max_pts = 5
        penalty = 0
        issues = []

        if inv.get("voicemail_nodes", 0) > 0:
            p = PENALTIES["voicemail_node"]
            penalty += p
            issues.append({
                "dim": "D6", "severity": "MEDIUM",
                "code": "VOICEMAIL_NODES",
                "message": "Voicemail nodes detected — not natively supported in Genesys Cloud",
                "penalty": p,
                "fix": "Replace with Cloud-native callback or message options",
            })

        if inv.get("schedule_nodes", 0) > 0:
            p = PENALTIES["schedule_node"]
            penalty += p
            issues.append({
                "dim": "D6", "severity": "LOW",
                "code": "SCHEDULE_NODES",
                "message": "Schedule nodes require additional configuration in Genesys Cloud",
                "penalty": p,
                "fix": "Map schedule logic to Genesys Cloud Architect schedule actions",
            })

        if inv.get("speech_input") and inv.get("dtmf_input_nodes"):
            p = PENALTIES["dual_input_complexity"]
            penalty += p
            issues.append({
                "dim": "D6", "severity": "LOW",
                "code": "DUAL_INPUT",
                "message": "Both DTMF and Speech input detected — doubles testing effort in Cloud",
                "penalty": p,
                "fix": "Verify NLU model compatibility with Genesys Cloud Voice Bot",
            })

        earned = max(0, max_pts - penalty)
        return DimensionResult("Migration Readiness", max_pts, earned, issues)

    # ── EXPLANATION BUILDER ────────────────────────────────────────────────────
    def _build_explanation(
        self,
        total: int,
        dims: Dict[str, DimensionResult],
        issues: list,
    ) -> str:
        high   = [i for i in issues if i.get("severity") in ("CRITICAL", "HIGH")]
        medium = [i for i in issues if i.get("severity") == "MEDIUM"]
        lost   = 100 - total

        if lost == 0:
            return "Perfect score. No structural issues detected."

        lines = [f"Score: {total}/100 — {lost} point(s) lost across {len(issues)} issue(s)."]

        if high:
            lines.append(f"\nCritical/High issues ({len(high)}):")
            for i in high[:5]:
                lines.append(f"  • [{i['dim']}] {i['message']} (−{i['penalty']} pts)")

        if medium:
            lines.append(f"\nMedium issues ({len(medium)}):")
            for i in medium[:3]:
                lines.append(f"  • [{i['dim']}] {i['message']} (−{i['penalty']} pts)")

        lines.append(f"\nDimension breakdown:")
        for key, d in dims.items():
            bar = "█" * int(d.pct / 10) + "░" * (10 - int(d.pct / 10))
            lines.append(f"  {key} {d.name:<22} {bar} {d.earned_pts}/{d.max_pts}")

        return "\n".join(lines)
