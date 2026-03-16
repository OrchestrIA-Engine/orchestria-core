"""
OrchestrIA — Refactoring Agent v0
===================================
Genera propuestas de corrección deterministas para los 3 issues más frecuentes:
  1. DEAD_ENDS                 — añadir transfer_to_agent al nodo sin salida
  2. MENUS_NO_INPUT_HANDLER    — añadir noInput/noMatch/timeout a menús
  3. MISSING_FALLBACKS         — añadir timeout/fallback a transfers

Principio: el agente SOLO actúa sobre issues explícitos del DeterministicScorer.
Nunca inventa mejoras. El LLM solo genera el YAML corregido con sintaxis válida.
"""

import os
import re
import yaml
import copy
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from src.llm.anthropic_adapter import AnthropicAdapter
from src.llm.base import Message, LLMConfig


# ── PROPUESTA DE CAMBIO ───────────────────────────────────────────────────────

@dataclass
class RefactoringProposal:
    issue_code: str
    severity: str
    node_id: str
    description: str
    original_yaml: str          # fragmento YAML del nodo original
    proposed_yaml: str          # fragmento YAML corregido
    explanation: str            # por qué este cambio resuelve el issue
    accepted: Optional[bool] = None  # None = pendiente, True = aceptado, False = rechazado

    def to_dict(self) -> dict:
        return {
            "issue_code":    self.issue_code,
            "severity":      self.severity,
            "node_id":       self.node_id,
            "description":   self.description,
            "original_yaml": self.original_yaml,
            "proposed_yaml": self.proposed_yaml,
            "explanation":   self.explanation,
            "accepted":      self.accepted,
        }


@dataclass
class RefactoringResult:
    proposals: List[RefactoringProposal]
    issues_addressed: List[str]
    issues_skipped: List[str]
    score_delta_estimate: int  # puntos que se recuperarían si se aceptan todos

    def to_dict(self) -> dict:
        return {
            "proposals":           [p.to_dict() for p in self.proposals],
            "issues_addressed":    self.issues_addressed,
            "issues_skipped":      self.issues_skipped,
            "score_delta_estimate": self.score_delta_estimate,
            "proposals_count":     len(self.proposals),
        }


# ── REFACTORING AGENT ─────────────────────────────────────────────────────────

class RefactoringAgent:
    """
    Genera propuestas de corrección basadas en issues del DeterministicScorer.
    
    Flujo:
    1. Recibe el YAML original + lista de issues del scorer
    2. Para cada issue en SCOPE, genera una propuesta de corrección
    3. Propuestas deterministas para handlers simples
    4. LLM para casos que requieren sintaxis específica de Genesys
    5. Devuelve RefactoringResult listo para human validation
    """

    # Issues que este agente v0 puede corregir
    SCOPE = {"DEAD_ENDS", "MENUS_NO_INPUT_HANDLER", "MISSING_FALLBACKS"}

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.llm = AnthropicAdapter(api_key=api_key)
        self.config = LLMConfig(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            temperature=0.0
        )

    def refactor(self, yaml_content: str, issues: List[Dict], flow_name: str = "") -> RefactoringResult:
        """
        Punto de entrada principal.
        
        Args:
            yaml_content: YAML original del flujo
            issues: lista de issues del DeterministicScorer
            flow_name: nombre del flujo para contexto
        
        Returns:
            RefactoringResult con propuestas por issue
        """
        try:
            data = yaml.safe_load(yaml_content)
        except Exception as e:
            return RefactoringResult(
                proposals=[],
                issues_addressed=[],
                issues_skipped=[f"YAML parse error: {e}"],
                score_delta_estimate=0,
            )

        proposals = []
        addressed = []
        skipped = []
        score_delta = 0

        for issue in issues:
            code = issue.get("issue_code") or issue.get("code", "")
            if code not in self.SCOPE:
                skipped.append(code)
                continue

            if code == "DEAD_ENDS":
                props = self._fix_dead_ends(data, issue, yaml_content)
                proposals.extend(props)
                if props:
                    addressed.append(code)
                    score_delta += issue.get("penalty", 0)

            elif code == "MENUS_NO_INPUT_HANDLER":
                props = self._fix_menu_handlers(data, issue, yaml_content)
                proposals.extend(props)
                if props:
                    addressed.append(code)
                    score_delta += issue.get("penalty", 0)

            elif code == "MISSING_FALLBACKS":
                props = self._fix_missing_fallbacks(data, issue, yaml_content)
                proposals.extend(props)
                if props:
                    addressed.append(code)
                    score_delta += issue.get("penalty", 0)

        return RefactoringResult(
            proposals=proposals,
            issues_addressed=list(set(addressed)),
            issues_skipped=skipped,
            score_delta_estimate=min(score_delta, 100),
        )

    # ── FIX: DEAD ENDS ────────────────────────────────────────────────────────
    def _fix_dead_ends(self, data: dict, issue: dict, original_yaml: str) -> List[RefactoringProposal]:
        proposals = []
        node_ids = issue.get("nodes", [])

        for section in ["menus", "tasks", "transfers"]:
            section_data = data.get(section, {})
            for node_id in node_ids:
                if node_id not in section_data:
                    continue
                node = section_data[node_id]
                if not isinstance(node, dict):
                    continue

                original = yaml.dump({node_id: node}, default_flow_style=False, allow_unicode=True)

                # Corrección determinista: añadir next con transfer_to_agent
                fixed_node = copy.deepcopy(node)
                if not fixed_node.get("next") and not fixed_node.get("choices"):
                    fixed_node["next"] = "./transfer_to_agent"
                    fixed_node["_orchestria_fix"] = "dead_end_resolved"

                proposed = yaml.dump({node_id: fixed_node}, default_flow_style=False, allow_unicode=True)

                proposals.append(RefactoringProposal(
                    issue_code="DEAD_ENDS",
                    severity=issue.get("severity", "HIGH"),
                    node_id=node_id,
                    description=f"Node '{node_id}' has no exit path — callers get stuck",
                    original_yaml=original,
                    proposed_yaml=proposed,
                    explanation=(
                        f"Added 'next: ./transfer_to_agent' to node '{node_id}'. "
                        f"This ensures callers are never stranded — they're transferred to an agent "
                        f"if the flow reaches a dead end. Replace 'transfer_to_agent' with the "
                        f"appropriate queue name for this flow."
                    ),
                ))

        return proposals

    # ── FIX: MENUS SIN HANDLERS ───────────────────────────────────────────────
    def _fix_menu_handlers(self, data: dict, issue: dict, original_yaml: str) -> List[RefactoringProposal]:
        proposals = []
        node_ids = issue.get("nodes", [])

        for section in ["menus", "tasks"]:
            section_data = data.get(section, {})
            for node_id in node_ids:
                if node_id not in section_data:
                    continue
                node = section_data[node_id]
                if not isinstance(node, dict):
                    continue

                original = yaml.dump({node_id: node}, default_flow_style=False, allow_unicode=True)
                fixed_node = copy.deepcopy(node)
                changes = []

                # Añadir noInput si no existe
                if not fixed_node.get("noInput") and not fixed_node.get("noInputAction"):
                    fixed_node["noInput"] = {
                        "next": "./transfer_to_agent",
                        "prompt": "Lo siento, no he recibido ninguna entrada."
                    }
                    changes.append("noInput handler")

                # Añadir noMatch si no existe
                if not fixed_node.get("noMatch") and not fixed_node.get("noMatchAction"):
                    fixed_node["noMatch"] = {
                        "next": "./transfer_to_agent",
                        "prompt": "Lo siento, no he reconocido su selección."
                    }
                    changes.append("noMatch handler")

                # Añadir timeout si no existe
                if not fixed_node.get("timeout") and not fixed_node.get("timeoutAction"):
                    fixed_node["timeout"] = {
                        "duration": 5,
                        "next": "./transfer_to_agent"
                    }
                    changes.append("timeout handler (5s)")

                if not changes:
                    continue

                proposed = yaml.dump({node_id: fixed_node}, default_flow_style=False, allow_unicode=True)

                proposals.append(RefactoringProposal(
                    issue_code="MENUS_NO_INPUT_HANDLER",
                    severity=issue.get("severity", "HIGH"),
                    node_id=node_id,
                    description=f"Menu '{node_id}' missing: {', '.join(changes)}",
                    original_yaml=original,
                    proposed_yaml=proposed,
                    explanation=(
                        f"Added {', '.join(changes)} to menu '{node_id}'. "
                        f"Without these handlers, callers who don't respond or press an invalid key "
                        f"get no feedback and the flow hangs. These handlers transfer to agent as a "
                        f"safe fallback — review the target queue and prompts for your use case."
                    ),
                ))

        return proposals

    # ── FIX: MISSING FALLBACKS EN TRANSFERS ───────────────────────────────────
    def _fix_missing_fallbacks(self, data: dict, issue: dict, original_yaml: str) -> List[RefactoringProposal]:
        proposals = []
        node_ids = issue.get("nodes", [])

        section_data = data.get("transfers", {})
        # También buscar en tasks
        section_data.update({
            k: v for k, v in data.get("tasks", {}).items()
            if isinstance(v, dict) and v.get("type") == "transfer"
        })

        for node_id in node_ids:
            if node_id not in section_data:
                continue
            node = section_data[node_id]
            if not isinstance(node, dict):
                continue

            original = yaml.dump({node_id: node}, default_flow_style=False, allow_unicode=True)
            fixed_node = copy.deepcopy(node)
            changes = []

            if not fixed_node.get("timeout"):
                fixed_node["timeout"] = {
                    "duration": 30,
                    "next": "./exit_no_answer"
                }
                changes.append("timeout (30s → exit_no_answer)")

            if not fixed_node.get("fallback") and not fixed_node.get("onFailure"):
                fixed_node["fallback"] = {
                    "next": "./transfer_to_agent",
                    "prompt": "No ha sido posible completar la transferencia. Le conectamos con un agente."
                }
                changes.append("fallback path")

            if not changes:
                continue

            proposed = yaml.dump({node_id: fixed_node}, default_flow_style=False, allow_unicode=True)

            proposals.append(RefactoringProposal(
                issue_code="MISSING_FALLBACKS",
                severity=issue.get("severity", "MEDIUM"),
                node_id=node_id,
                description=f"Transfer '{node_id}' missing: {', '.join(changes)}",
                original_yaml=original,
                proposed_yaml=proposed,
                explanation=(
                    f"Added {', '.join(changes)} to transfer '{node_id}'. "
                    f"Without a timeout, transfers that never connect leave callers waiting indefinitely. "
                    f"Without a fallback, transfer failures have no recovery path. "
                    f"Review timeout duration and target nodes for your SLA requirements."
                ),
            ))

        return proposals
