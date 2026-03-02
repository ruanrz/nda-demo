# -*- coding: utf-8 -*-
"""
Unified contract review pipeline.

Replaces the old 6-call approach (search+apply × 3 rule types) with a
streamlined pipeline:

  Step 1  analysis   → analyse contract against ALL rules  (LLM)
  Step 2  execution  → apply planned modifications         (local first, LLM fallback)
  Step 3  summary    → generate Issues List                (LLM, optional)

Model selection depends on the active preset (quality / cost).
See llm_client.py for routing details.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .llm_client import LLMClient, get_llm_client
from .contract_parser import parse_contract_structure, format_structured_contract
from .playbook_loader import (
    load_playbooks_from_markdown,
    format_markdown_playbooks_for_prompt,
)
from .unified_prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    ANALYSIS_USER_PROMPT,
    EXECUTION_SYSTEM_PROMPT,
    EXECUTION_USER_PROMPT,
    ISSUES_LIST_SYSTEM_PROMPT,
    ISSUES_LIST_USER_PROMPT,
    OWN_PAPER_MODE,
    COUNTERPARTY_MODE,
    ISSUES_OWN_PAPER_CONTEXT,
    ISSUES_COUNTERPARTY_CONTEXT,
    format_rules_for_prompt,
)

logger = logging.getLogger("unified_review")


# ─── Public API ──────────────────────────────────────────────────

def unified_review_contract(
    contract_text: str,
    playbook_entries: Optional[List[Dict[str, Any]]] = None,
    mode: str = "own_paper",
    client: Optional[LLMClient] = None,
    generate_issues: bool = True,
    progress_callback=None,
    playbook_source: str = "markdown",
) -> Dict[str, Any]:
    """
    Run the full review pipeline.

    Args:
        contract_text:    Raw contract text (plain text or parsed .docx content).
        playbook_entries: Playbook entries (JSON dicts). If None, loads from Markdown files.
        mode:             "own_paper" or "counterparty".
        client:           LLMClient instance (auto-created if None).
        generate_issues:  Whether to make the 3rd call for Issues List.
        progress_callback: Optional callable(stage: str, detail: str) for UI updates.
        playbook_source:  "markdown" (default) or "json". Controls how rules are
                          formatted for the prompt.

    Returns:
        {
            "analysis":       [...],       # per-rule analysis
            "modifications":  [...],       # per-modification detail
            "final_text":     "...",       # complete modified contract
            "issues_list":    [...],       # structured issues (if generate_issues)
            "executive_summary": "...",
            "compliance_score": {...},
            "summary":        {...},       # stats
            "llm_stats":      {...},       # call timing / token usage
            "contract_structure": [...],   # parsed clause structure
        }
    """
    if client is None:
        client = get_llm_client()
    client.reset_stats()

    result: Dict[str, Any] = {
        "analysis": [],
        "modifications": [],
        "final_text": contract_text,
        "issues_list": [],
        "executive_summary": "",
        "compliance_score": {},
        "summary": {},
        "llm_stats": {},
        "contract_structure": [],
        "step_trace": [],
    }

    def _progress(stage, detail=""):
        if progress_callback:
            progress_callback(stage, detail)

    # ── Step 0: local structure parsing ──────────────────────────
    _progress("parsing", "Parsing contract structure…")
    clauses = parse_contract_structure(contract_text)
    result["contract_structure"] = [c.to_dict() for c in clauses]
    result["step_trace"].append({
        "step": "Step 0",
        "name": "Parsing",
        "engine": "Local parser",
        "thinking": [
            f"Detected {len(clauses)} structural clauses/sections from contract text.",
            "Prepared structured clause map as context for downstream analysis.",
        ],
        "output": {"clauses_detected": len(clauses)},
    })
    logger.info(f"Parsed {len(clauses)} clauses from contract")

    # ── Load playbooks if not provided ───────────────────────────
    if playbook_entries is None:
        playbook_entries = load_playbooks_from_markdown()
        playbook_source = "markdown"

    # ── Prepare rule text for prompt ─────────────────────────────
    if playbook_source == "markdown" and playbook_entries and "markdown_body" in playbook_entries[0]:
        rules_text = format_markdown_playbooks_for_prompt(playbook_entries)
    else:
        rules_text = format_rules_for_prompt(playbook_entries)
    mode_instruction = COUNTERPARTY_MODE if mode == "counterparty" else OWN_PAPER_MODE

    # ── Step 1: Analysis (model depends on preset) ─────────────
    _progress("analysis", "Analysing contract against all Playbook rules…")
    logger.info(f"Step 1: Analysis call (preset={client.preset_name})")

    analysis_result = client.call_json(
        task_type="analysis",
        system_prompt=ANALYSIS_SYSTEM_PROMPT,
        user_prompt=ANALYSIS_USER_PROMPT.format(
            playbook_rules_json=rules_text,
            contract_text=contract_text,
            mode_instruction=mode_instruction,
        ),
        temperature=0.0,
        max_tokens=16384,
    )

    analysis_items = analysis_result.get("analysis", [])
    analysis_summary = analysis_result.get("summary", {})
    result["analysis"] = analysis_items
    result["summary"] = analysis_summary

    modifications_planned = [
        item for item in analysis_items if item.get("modification_needed")
    ]
    logger.info(
        f"Analysis complete: {len(analysis_items)} rules checked, "
        f"{len(modifications_planned)} modifications planned"
    )
    representative_findings = []
    for item in analysis_items:
        if item.get("modification_needed"):
            rule_title = item.get("rule_title", item.get("rule_id", "Rule"))
            sev = item.get("severity", "YELLOW")
            rationale = item.get("rationale", "")
            if rationale:
                representative_findings.append(f"[{sev}] {rule_title}: {rationale}")
            else:
                representative_findings.append(f"[{sev}] {rule_title}: modification planned.")
        if len(representative_findings) >= 6:
            break
    if not representative_findings:
        representative_findings = ["All checked rules are compliant; no redline needed."]
    result["step_trace"].append({
        "step": "Step 1",
        "name": "Analysis",
        "engine": f"LLM ({client.routing.get('analysis', 'default')})",
        "thinking": representative_findings,
        "output": {
            "rules_checked": analysis_summary.get("total_rules_checked", len(analysis_items)),
            "modifications_planned": len(modifications_planned),
            "overall_risk": analysis_summary.get("overall_risk", "unknown"),
        },
    })
    _progress(
        "analysis_done",
        f"Found {len(modifications_planned)} issues in "
        f"{analysis_summary.get('total_rules_checked', len(analysis_items))} rules"
    )

    # ── Step 2: Execution (local find/replace first, LLM fallback) ──
    if modifications_planned:
        _progress("execution", f"Applying {len(modifications_planned)} modifications…")
        logger.info(f"Step 2: Executing {len(modifications_planned)} modifications")

        mods_for_prompt = []
        for item in modifications_planned:
            plan = item.get("modification_plan", {})
            mods_for_prompt.append({
                "rule_id": item.get("rule_id", ""),
                "rule_title": item.get("rule_title", ""),
                "source_playbook": item.get("source_playbook", ""),
                "find_text": plan.get("find_text", ""),
                "replace_with": plan.get("replace_with", ""),
                "type": plan.get("type", "replace"),
                "description": plan.get("insertion_point_description", ""),
            })

        local_text, applied, failed = _local_find_replace(contract_text, mods_for_prompt)
        logger.info(f"Local find/replace: {len(applied)} applied, {len(failed)} failed")

        if not failed:
            result["modifications"] = applied
            result["final_text"] = local_text
            result["step_trace"].append({
                "step": "Step 2",
                "name": "Execution",
                "engine": "Local deterministic find/replace",
                "thinking": [
                    f"Applied {len(applied)} planned edits via exact string matching.",
                    "All planned edits matched locally; no LLM execution fallback needed.",
                ],
                "output": {
                    "applied": len(applied),
                    "failed": 0,
                    "fallback_used": False,
                },
            })
            _progress("execution_done", f"Applied {len(applied)} modifications (local)")
        else:
            logger.info(f"Falling back to LLM for {len(failed)} unresolved modifications")
            _progress("execution", f"LLM fallback for {len(failed)} modifications…")
            exec_result = client.call_json(
                task_type="execution",
                system_prompt=EXECUTION_SYSTEM_PROMPT,
                user_prompt=EXECUTION_USER_PROMPT.format(
                    modifications_json=json.dumps(failed, ensure_ascii=False, indent=2),
                    original_text=local_text,
                ),
                temperature=0.0,
                max_tokens=16384,
            )

            llm_mods = exec_result.get("modifications_applied", [])
            result["modifications"] = applied + llm_mods
            result["final_text"] = exec_result.get("final_text", local_text)

            verification = exec_result.get("verification", {})
            exec_thinking = [
                f"Local find/replace succeeded for {len(applied)} modifications.",
                f"LLM fallback handled remaining {len(failed)} modifications.",
            ]
            for mod in result["modifications"][:6]:
                why = mod.get("explanation", "")
                title = mod.get("rule_title", mod.get("rule_id", "Rule"))
                if why:
                    exec_thinking.append(f"{title}: {why}")
                else:
                    exec_thinking.append(f"{title}: change applied.")
            result["step_trace"].append({
                "step": "Step 2",
                "name": "Execution",
                "engine": f"Local + LLM fallback ({client.routing.get('execution', 'default')})",
                "thinking": exec_thinking,
                "output": {
                    "planned": len(mods_for_prompt),
                    "applied_local": len(applied),
                    "applied_llm": len(llm_mods),
                    "applied_total": len(result["modifications"]),
                    "fallback_used": True,
                },
            })
            logger.info(
                f"LLM execution complete: "
                f"{verification.get('total_applied', 0)}/{verification.get('total_planned', 0)} applied"
            )
            _progress("execution_done", f"Applied {len(result['modifications'])} modifications (LLM fallback)")
    else:
        _progress("execution_done", "No modifications needed — contract is compliant")
        result["modifications"] = []
        result["step_trace"].append({
            "step": "Step 2",
            "name": "Execution",
            "engine": "Skipped",
            "thinking": ["No non-compliant findings from analysis; no edits executed."],
            "output": {"applied": 0, "fallback_used": False},
        })

    # ── Step 3: Issues List (optional) ──────────────────────────
    if generate_issues:
        _progress("issues", "Generating Issues List & risk summary…")
        logger.info("Step 3: Issues list generation")

        mode_ctx = (
            ISSUES_COUNTERPARTY_CONTEXT if mode == "counterparty"
            else ISSUES_OWN_PAPER_CONTEXT
        )

        issues_result = client.call_json(
            task_type="summary",
            system_prompt=ISSUES_LIST_SYSTEM_PROMPT,
            user_prompt=ISSUES_LIST_USER_PROMPT.format(
                analysis_json=json.dumps(result["analysis"], ensure_ascii=False, indent=2),
                modifications_json=json.dumps(result["modifications"], ensure_ascii=False, indent=2),
                final_text=result["final_text"],
                mode_context=mode_ctx,
            ),
            temperature=0.0,
            max_tokens=8192,
        )

        result["issues_list"] = issues_result.get("issues", [])
        result["executive_summary"] = issues_result.get("executive_summary", "")
        result["compliance_score"] = issues_result.get("compliance_score", {})
        issue_thinking = []
        for iss in result["issues_list"][:6]:
            sev = iss.get("severity", "P2")
            title = iss.get("title", iss.get("description", "Issue"))
            action = iss.get("recommended_action", "")
            if action:
                issue_thinking.append(f"[{sev}] {title}: {action}")
            else:
                issue_thinking.append(f"[{sev}] {title}")
        if result["executive_summary"]:
            issue_thinking.insert(0, f"Executive summary: {result['executive_summary']}")
        if not issue_thinking:
            issue_thinking = ["No material issues identified by summary stage."]
        result["step_trace"].append({
            "step": "Step 3",
            "name": "Issues & Risk Summary",
            "engine": f"LLM ({client.routing.get('summary', 'default')})",
            "thinking": issue_thinking,
            "output": {
                "issues_count": len(result["issues_list"]),
                "compliance_percentage": result["compliance_score"].get("percentage", 0),
            },
        })
        _progress("issues_done", f"Generated {len(result['issues_list'])} issues")

    # ── Finalise ─────────────────────────────────────────────────
    result["llm_stats"] = client.get_stats()
    _progress("done", "Review complete")
    return result


# ─── Helpers ─────────────────────────────────────────────────────

_PUNCT_MAP = str.maketrans({
    '\u201c': '"', '\u201d': '"',   # curly double quotes → straight
    '\u2018': "'", '\u2019': "'",   # curly single quotes → straight
    '\u2014': '-', '\u2013': '-',   # em-dash / en-dash → hyphen
    '\u00a0': ' ',                  # non-breaking space → space
})


def _normalize_text(text: str) -> str:
    """Normalize whitespace and common punctuation variants for matching."""
    return re.sub(r'\s+', ' ', text.translate(_PUNCT_MAP)).strip()


def _local_find_replace(
    text: str,
    modifications: List[Dict[str, Any]],
) -> tuple:
    """
    Attempt deterministic find/replace on the contract text.

    Returns (modified_text, applied_list, failed_list).
    - applied_list: modifications that succeeded locally.
    - failed_list:  modifications where find_text was not found (need LLM fallback).

    Matching strategy:
      1. Exact substring match (preferred).
      2. Normalized flexible match — normalizes whitespace and punctuation variants
         (curly quotes, em-dashes, non-breaking spaces, etc.) then builds a regex
         that tolerates variable whitespace between words.
    """
    applied: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    current = text

    for mod in modifications:
        find = mod.get("find_text", "")
        replace = mod.get("replace_with", "")
        if not find:
            failed.append(mod)
            continue

        success_record = {
            "rule_id": mod.get("rule_id", ""),
            "rule_title": mod.get("rule_title", ""),
            "original_fragment": find,
            "modified_fragment": replace,
            "modification_type": mod.get("type", "replace"),
            "explanation": mod.get("description", "Applied via local find/replace"),
            "severity": "P1",
        }

        if find in current:
            current = current.replace(find, replace, 1)
            applied.append(success_record)
            continue

        norm_find = _normalize_text(find)
        if not norm_find:
            failed.append(mod)
            continue

        escaped_words = [re.escape(w) for w in norm_find.split()]
        flex_pattern = r'\s+'.join(escaped_words)
        match = re.search(flex_pattern, current)
        if match:
            current = current[:match.start()] + replace + current[match.end():]
            success_record["original_fragment"] = match.group(0)
            success_record["explanation"] += " (normalized match)"
            applied.append(success_record)
            continue

        punct_current = current.translate(_PUNCT_MAP)
        match = re.search(flex_pattern, punct_current)
        if match:
            success_record["original_fragment"] = current[match.start():match.end()]
            current = current[:match.start()] + replace + current[match.end():]
            success_record["explanation"] += " (punctuation-normalized match)"
            applied.append(success_record)
            continue

        failed.append(mod)

    return current, applied, failed


def load_playbook_entries(
    path: str,
    filter_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Load playbook entries from JSON file, optionally filtering by id."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    if filter_ids:
        data = [e for e in data if str(e.get("id", "")) in filter_ids]
    return [e for e in data if e.get("enabled", True)]
