import os
import yaml
import copy
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from src.llm.anthropic_adapter import AnthropicAdapter
from src.llm.base import Message, LLMConfig

SCOPE = {"DEAD_ENDS", "MENUS_NO_INPUT_HANDLER", "MISSING_FALLBACKS"}

@dataclass
class RefactoringProposal:
    issue_code: str
    severity: str
    node_id: str
    description: str
    original_yaml: str
    proposed_yaml: str
    explanation: str
    accepted: Optional[bool] = None
    def to_dict(self):
        return {"issue_code":self.issue_code,"severity":self.severity,"node_id":self.node_id,
                "description":self.description,"original_yaml":self.original_yaml,
                "proposed_yaml":self.proposed_yaml,"explanation":self.explanation,"accepted":self.accepted}

@dataclass
class RefactoringResult:
    proposals: List[RefactoringProposal]
    issues_addressed: List[str]
    issues_skipped: List[str]
    score_delta_estimate: int
    def to_dict(self):
        return {"proposals":[p.to_dict() for p in self.proposals],
                "issues_addressed":self.issues_addressed,"issues_skipped":self.issues_skipped,
                "score_delta_estimate":self.score_delta_estimate,"proposals_count":len(self.proposals)}

def _get_section(data, section):
    raw = data.get(section, {})
    return raw if isinstance(raw, dict) else {}

def _all_nodes(data):
    result = {}
    for section in ["menus","tasks","transfers","nodes","steps","actions"]:
        raw = data.get(section, {})
        if isinstance(raw, dict):
            result.update(raw)
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get('id'):
                    result[item['id']] = item
    return result

class RefactoringAgent:
    def __init__(self):
        self.llm = AnthropicAdapter(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.config = LLMConfig(model="claude-sonnet-4-6", max_tokens=2000, temperature=0.0)

    def refactor(self, yaml_content, issues, flow_name=""):
        try:
            import json
            try:
                data = yaml.safe_load(yaml_content)
            except Exception:
                data = json.loads(yaml_content)
            if not isinstance(data, dict):
                raise ValueError("Could not parse flow content")
            # Si el YAML está envuelto (fixture con key 'yaml')
            if set(data.keys()) <= {"id","name","yaml","expected"} and "yaml" in data:
                data = yaml.safe_load(data["yaml"]) or data
        except Exception as e:
            return RefactoringResult([], [], [f"Parse error: {e}"], 0)

        proposals, addressed, skipped, delta = [], [], [], 0
        for issue in issues:
            code = issue.get("code") or issue.get("issue_code","")
            if code not in SCOPE:
                skipped.append(code)
                continue
            if code == "DEAD_ENDS":
                props = self._fix_dead_ends(data, issue)
            elif code == "MENUS_NO_INPUT_HANDLER":
                props = self._fix_menu_handlers(data, issue)
            elif code == "MISSING_FALLBACKS":
                props = self._fix_missing_fallbacks(data, issue)
            else:
                props = []
            proposals.extend(props)
            if props:
                addressed.append(code)
                delta += issue.get("penalty", 0)

        return RefactoringResult(proposals, list(set(addressed)), skipped, min(delta, 100))

    def _fix_dead_ends(self, data, issue):
        proposals = []
        all_nodes = _all_nodes(data)
        for node_id in issue.get("nodes", []):
            if node_id not in all_nodes:
                continue
            node = all_nodes[node_id]
            if not isinstance(node, dict):
                continue
            original = yaml.dump({node_id: node}, default_flow_style=False, allow_unicode=True)
            fixed = copy.deepcopy(node)
            if not fixed.get("next") and not fixed.get("choices"):
                fixed["next"] = "./transfer_to_agent"
            proposed = yaml.dump({node_id: fixed}, default_flow_style=False, allow_unicode=True)
            if original == proposed:
                continue
            proposals.append(RefactoringProposal(
                issue_code="DEAD_ENDS", severity=issue.get("severity","HIGH"),
                node_id=node_id,
                description=f"Node '{node_id}' has no exit path — callers get stuck",
                original_yaml=original, proposed_yaml=proposed,
                explanation=(f"Added 'next: ./transfer_to_agent' to '{node_id}'. "
                             f"Callers are never stranded — transferred to agent at dead end. "
                             f"Replace with the appropriate queue name for this flow.")
            ))
        return proposals

    def _fix_menu_handlers(self, data, issue):
        proposals = []
        all_nodes = _all_nodes(data)
        for node_id in issue.get("nodes", []):
            if node_id not in all_nodes:
                continue
            node = all_nodes[node_id]
            if not isinstance(node, dict):
                continue
            original = yaml.dump({node_id: node}, default_flow_style=False, allow_unicode=True)
            fixed = copy.deepcopy(node)
            changes = []
            if not fixed.get("noInput") and not fixed.get("noInputAction"):
                fixed["noInput"] = {"next":"./transfer_to_agent","prompt":"No input received."}
                changes.append("noInput")
            if not fixed.get("noMatch") and not fixed.get("noMatchAction"):
                fixed["noMatch"] = {"next":"./transfer_to_agent","prompt":"Selection not recognised."}
                changes.append("noMatch")
            if not fixed.get("timeout") and not fixed.get("timeoutAction"):
                fixed["timeout"] = {"duration":5,"next":"./transfer_to_agent"}
                changes.append("timeout(5s)")
            if not changes:
                continue
            proposed = yaml.dump({node_id: fixed}, default_flow_style=False, allow_unicode=True)
            proposals.append(RefactoringProposal(
                issue_code="MENUS_NO_INPUT_HANDLER", severity=issue.get("severity","HIGH"),
                node_id=node_id,
                description=f"Menu '{node_id}' missing: {', '.join(changes)}",
                original_yaml=original, proposed_yaml=proposed,
                explanation=(f"Added {', '.join(changes)} to '{node_id}'. "
                             f"Without these, callers who don't respond get no feedback and the flow hangs. "
                             f"Review transfer targets and prompts for your use case.")
            ))
        return proposals

    def _fix_missing_fallbacks(self, data, issue):
        proposals = []
        all_nodes = _all_nodes(data)
        for node_id in issue.get("nodes", []):
            if node_id not in all_nodes:
                continue
            node = all_nodes[node_id]
            if not isinstance(node, dict):
                continue
            original = yaml.dump({node_id: node}, default_flow_style=False, allow_unicode=True)
            fixed = copy.deepcopy(node)
            changes = []
            if not fixed.get("timeout"):
                fixed["timeout"] = {"duration":30,"next":"./exit_no_answer"}
                changes.append("timeout(30s)")
            if not fixed.get("fallback") and not fixed.get("onFailure"):
                fixed["fallback"] = {"next":"./transfer_to_agent",
                                     "prompt":"Transfer failed. Connecting to agent."}
                changes.append("fallback")
            if not changes:
                continue
            proposed = yaml.dump({node_id: fixed}, default_flow_style=False, allow_unicode=True)
            proposals.append(RefactoringProposal(
                issue_code="MISSING_FALLBACKS", severity=issue.get("severity","MEDIUM"),
                node_id=node_id,
                description=f"Transfer '{node_id}' missing: {', '.join(changes)}",
                original_yaml=original, proposed_yaml=proposed,
                explanation=(f"Added {', '.join(changes)} to '{node_id}'. "
                             f"Without timeout, failed transfers leave callers waiting indefinitely. "
                             f"Review duration and target nodes for your SLA.")
            ))
        return proposals
