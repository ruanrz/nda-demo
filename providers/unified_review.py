# -*- coding: utf-8 -*-
"""
Unified contract review pipeline (v2).

New architecture — replaces the old find/replace approach:

  Step 1  analysis   → diagnose contract against ALL rules     (1 LLM call)
  Step 2  revision   → per-clause AI rewrite                   (N LLM calls, parallel)
  Step 3  assembly   → stitch revised clauses into full text   (local)
  Step 4  summary    → generate Issues List                    (1 LLM call, optional)
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

from .llm_client import LLMClient, get_llm_client
from .contract_parser import parse_contract_structure
from .playbook_loader import (
    load_playbooks_from_markdown,
    format_markdown_playbooks_for_prompt,
)
from .unified_prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    ANALYSIS_USER_PROMPT,
    REVISION_SYSTEM_PROMPT,
    REVISION_USER_PROMPT,
    ISSUES_LIST_SYSTEM_PROMPT,
    ISSUES_LIST_USER_PROMPT,
    OWN_PAPER_MODE,
    COUNTERPARTY_MODE,
    ISSUES_OWN_PAPER_CONTEXT,
    ISSUES_COUNTERPARTY_CONTEXT,
    format_rules_for_prompt,
    get_rules_text_by_ids,
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
    Run the full review pipeline (v2).

    Architecture:
      Step 1: Analysis  — diagnose which clauses need revision (1 LLM call)
      Step 2: Revision  — per-clause AI rewrite (N parallel LLM calls)
      Step 3: Assembly  — replace original clauses with revised versions
      Step 4: Issues    — generate structured issues list (optional)

    Returns dict with: analysis, defined_terms, revisions, final_text,
    issues_list, executive_summary, compliance_score, summary, llm_stats,
    step_trace.
    """
    if client is None:
        client = get_llm_client()
    client.reset_stats()

    result: Dict[str, Any] = {
        "analysis": [],
        "defined_terms": {},
        "revisions": [],
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
        "step": "Step 0", "name": "Parsing",
        "engine": "Local parser",
        "thinking": [f"Detected {len(clauses)} structural clauses/sections."],
        "output": {"clauses_detected": len(clauses)},
    })

    # ── Load playbooks if not provided ───────────────────────────
    if playbook_entries is None:
        playbook_entries = load_playbooks_from_markdown()
        playbook_source = "markdown"

    rules_text = format_rules_for_prompt(playbook_entries)
    mode_instruction = COUNTERPARTY_MODE if mode == "counterparty" else OWN_PAPER_MODE

    # ── Step 1: Analysis — diagnose gaps (1 LLM call) ───────────
    _progress("analysis", "Analysing contract against all Playbook rules…")
    logger.info("Step 1: Analysis call (preset=%s)", client.preset_name)

    analysis_result = client.call_json(
        task_type="analysis",
        system_prompt=ANALYSIS_SYSTEM_PROMPT,
        user_prompt=ANALYSIS_USER_PROMPT.format(
            playbook_rules=rules_text,
            contract_text=contract_text,
            mode_instruction=mode_instruction,
        ),
        temperature=0.0,
        max_tokens=16384,
    )

    defined_terms = analysis_result.get("defined_terms", {})
    clause_analysis = analysis_result.get("clause_analysis", [])
    analysis_summary = analysis_result.get("summary", {})

    result["analysis"] = clause_analysis
    result["defined_terms"] = defined_terms
    result["summary"] = analysis_summary

    clauses_needing_revision = [
        c for c in clause_analysis
        if c.get("compliance_status") != "compliant"
        and c.get("severity") != "GREEN"
    ]

    # Group by clause_text to avoid revising the same clause multiple times
    clause_groups = _group_analyses_by_clause(clauses_needing_revision)

    logger.info(
        "Analysis: %d rules checked, %d unique clauses need revision",
        len(clause_analysis), len(clause_groups),
    )

    analysis_thinking = []
    for item in clause_analysis:
        if item.get("compliance_status") != "compliant":
            sev = item.get("severity", "YELLOW")
            cid = item.get("clause_id", "?")
            gaps = item.get("gaps", "")
            analysis_thinking.append(f"[{sev}] {cid}: {gaps[:120]}")
    if not analysis_thinking:
        analysis_thinking = ["All checked rules are compliant; no revision needed."]

    result["step_trace"].append({
        "step": "Step 1", "name": "Analysis",
        "engine": f"LLM ({client.routing.get('analysis', 'default')})",
        "thinking": analysis_thinking[:8],
        "output": {
            "rules_checked": analysis_summary.get("total_rules_checked", len(clause_analysis)),
            "clauses_to_revise": len(clause_groups),
            "overall_risk": analysis_summary.get("overall_risk", "unknown"),
        },
    })
    _progress(
        "analysis_done",
        f"Found {len(clause_groups)} clauses to revise across "
        f"{analysis_summary.get('total_rules_checked', len(clause_analysis))} rules"
    )

    # ── Step 2: Per-clause revision (N parallel LLM calls) ───────
    if clause_groups:
        _progress("execution", f"Revising {len(clause_groups)} clauses…")
        logger.info("Step 2: Revising %d clauses (parallel)", len(clause_groups))

        defined_terms_str = json.dumps(defined_terms, ensure_ascii=False, indent=2)
        revisions = _revise_clauses_parallel(
            clause_groups=clause_groups,
            playbook_entries=playbook_entries,
            defined_terms_str=defined_terms_str,
            client=client,
            progress_callback=_progress,
        )

        result["revisions"] = revisions

        # Build modifications list for backward compatibility
        for rev in revisions:
            for ch in rev.get("changes_made", []):
                result["modifications"].append({
                    "rule_id": ch.get("rule_id", ""),
                    "rule_title": ch.get("what", ""),
                    "original_fragment": rev.get("original_clause", "")[:200],
                    "modified_fragment": rev.get("revised_clause", "")[:200],
                    "modification_type": "revision",
                    "explanation": ch.get("why", ""),
                    "severity": "P1",
                })

        rev_thinking = []
        for rev in revisions:
            reasoning = rev.get("reasoning", "")
            cid = rev.get("clause_id", "?")
            rev_thinking.append(f"{cid}: {reasoning[:150]}")

        result["step_trace"].append({
            "step": "Step 2", "name": "Revision",
            "engine": f"LLM ({client.routing.get('revision', 'default')}) × {len(clause_groups)}",
            "thinking": rev_thinking[:8],
            "output": {
                "clauses_revised": len(revisions),
                "total_changes": sum(len(r.get("changes_made", [])) for r in revisions),
            },
        })
        _progress("execution_done", f"Revised {len(revisions)} clauses")
    else:
        _progress("execution_done", "No revisions needed — contract is compliant")
        result["step_trace"].append({
            "step": "Step 2", "name": "Revision",
            "engine": "Skipped",
            "thinking": ["No non-compliant findings; no revisions needed."],
            "output": {"clauses_revised": 0},
        })

    # ── Step 3: Assembly — stitch revised clauses back ───────────
    final_text = _assemble_final_text(contract_text, result["revisions"])
    result["final_text"] = final_text

    # ── Step 4: Issues List (optional) ───────────────────────────
    if generate_issues:
        _progress("issues", "Generating Issues List & risk summary…")
        logger.info("Step 4: Issues list generation")

        mode_ctx = (
            ISSUES_COUNTERPARTY_CONTEXT if mode == "counterparty"
            else ISSUES_OWN_PAPER_CONTEXT
        )

        issues_result = client.call_json(
            task_type="summary",
            system_prompt=ISSUES_LIST_SYSTEM_PROMPT,
            user_prompt=ISSUES_LIST_USER_PROMPT.format(
                analysis_json=json.dumps(result["analysis"], ensure_ascii=False, indent=2),
                revisions_json=json.dumps(result["revisions"], ensure_ascii=False, indent=2),
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
        if result["executive_summary"]:
            issue_thinking.append(f"Executive summary: {result['executive_summary']}")
        for iss in result["issues_list"][:6]:
            sev = iss.get("severity", "P2")
            title = iss.get("title", "Issue")
            issue_thinking.append(f"[{sev}] {title}")
        if not issue_thinking:
            issue_thinking = ["No material issues identified."]

        result["step_trace"].append({
            "step": "Step 4", "name": "Issues & Risk Summary",
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
    '\u201c': '"', '\u201d': '"',
    '\u2018': "'", '\u2019': "'",
    '\u2014': '-', '\u2013': '-',
    '\u00a0': ' ',
})


def _normalize_text(text: str) -> str:
    """Normalize whitespace and common punctuation variants for matching."""
    return re.sub(r'\s+', ' ', text.translate(_PUNCT_MAP)).strip()


def _group_analyses_by_clause(
    analyses: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Group analysis entries by clause_text so each unique clause is revised
    only once, even if multiple rules apply to it.

    Returns a list of dicts:
      { clause_id, clause_text, clause_location, applicable_rule_ids, combined_gaps, severity }
    """
    groups: Dict[str, Dict[str, Any]] = {}

    for item in analyses:
        clause_text = item.get("clause_text", "").strip()
        if not clause_text:
            continue

        norm_key = _normalize_text(clause_text)[:200]

        if norm_key not in groups:
            groups[norm_key] = {
                "clause_id": item.get("clause_id", "unknown"),
                "clause_text": clause_text,
                "clause_location": item.get("clause_location", ""),
                "applicable_rule_ids": [],
                "combined_gaps": [],
                "severity": item.get("severity", "YELLOW"),
            }

        rule_ids = item.get("applicable_rule_ids", [])
        if isinstance(rule_ids, str):
            rule_ids = [rule_ids]
        for rid in rule_ids:
            if rid not in groups[norm_key]["applicable_rule_ids"]:
                groups[norm_key]["applicable_rule_ids"].append(rid)

        gaps = item.get("gaps", "")
        if gaps and gaps not in groups[norm_key]["combined_gaps"]:
            groups[norm_key]["combined_gaps"].append(gaps)

        if item.get("severity") == "RED":
            groups[norm_key]["severity"] = "RED"

    result = []
    for g in groups.values():
        g["combined_gaps"] = "\n".join(g["combined_gaps"])
        result.append(g)
    return result


def _revise_clauses_parallel(
    clause_groups: List[Dict[str, Any]],
    playbook_entries: List[Dict[str, Any]],
    defined_terms_str: str,
    client: LLMClient,
    progress_callback=None,
) -> List[Dict[str, Any]]:
    """
    Revise each clause in parallel using ThreadPoolExecutor.
    """
    revisions: List[Dict[str, Any]] = []

    def _revise_one(group: Dict[str, Any]) -> Dict[str, Any]:
        applicable_rules_text = get_rules_text_by_ids(
            group["applicable_rule_ids"], playbook_entries
        )

        rev_result = client.call_json(
            task_type="revision",
            system_prompt=REVISION_SYSTEM_PROMPT,
            user_prompt=REVISION_USER_PROMPT.format(
                original_clause=group["clause_text"],
                applicable_rules=applicable_rules_text,
                gap_assessment=group["combined_gaps"],
                defined_terms=defined_terms_str,
            ),
            temperature=0.1,
            max_tokens=8192,
        )

        return {
            "clause_id": group["clause_id"],
            "clause_location": group.get("clause_location", ""),
            "original_clause": group["clause_text"],
            "revised_clause": rev_result.get("revised_clause", ""),
            "reasoning": rev_result.get("reasoning", ""),
            "changes_made": rev_result.get("changes_made", []),
            "severity": group["severity"],
            "applicable_rule_ids": group["applicable_rule_ids"],
        }

    max_workers = min(4, len(clause_groups))
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_revise_one, g): g
            for g in clause_groups
        }
        for future in as_completed(futures):
            group = futures[future]
            try:
                rev = future.result()
                revisions.append(rev)
                completed += 1
                logger.info(
                    "Revised clause '%s' (%d/%d)",
                    group["clause_id"], completed, len(clause_groups),
                )
                if progress_callback:
                    progress_callback(
                        "execution",
                        f"Revised {completed}/{len(clause_groups)} clauses…"
                    )
            except Exception as exc:
                logger.error("Failed to revise clause '%s': %s", group["clause_id"], exc)
                revisions.append({
                    "clause_id": group["clause_id"],
                    "original_clause": group["clause_text"],
                    "revised_clause": group["clause_text"],
                    "reasoning": f"Revision failed: {exc}",
                    "changes_made": [],
                    "severity": group["severity"],
                    "applicable_rule_ids": group["applicable_rule_ids"],
                    "error": str(exc),
                })

    return revisions


def _assemble_final_text(
    original_text: str,
    revisions: List[Dict[str, Any]],
) -> str:
    """
    Replace each original clause with its revised version in the full text.

    Matching strategy:
      1. Exact substring match.
      2. Normalized match (whitespace/punctuation tolerance).
    """
    current = original_text

    for rev in revisions:
        original_clause = rev.get("original_clause", "")
        revised_clause = rev.get("revised_clause", "")

        if not original_clause or not revised_clause:
            continue
        if original_clause == revised_clause:
            continue

        if original_clause in current:
            current = current.replace(original_clause, revised_clause, 1)
            continue

        # Normalized fallback
        norm_original = _normalize_text(original_clause)
        if not norm_original:
            continue

        escaped_words = [re.escape(w) for w in norm_original.split()]
        flex_pattern = r'\s+'.join(escaped_words)
        match = re.search(flex_pattern, current)
        if match:
            current = current[:match.start()] + revised_clause + current[match.end():]
            logger.info("Assembled clause '%s' via normalized match", rev.get("clause_id"))
            continue

        # Punctuation-normalized fallback
        punct_current = current.translate(_PUNCT_MAP)
        match = re.search(flex_pattern, punct_current)
        if match:
            current = current[:match.start()] + revised_clause + current[match.end():]
            logger.info("Assembled clause '%s' via punctuation-normalized match", rev.get("clause_id"))
            continue

        logger.warning(
            "Could not locate clause '%s' in contract for assembly",
            rev.get("clause_id"),
        )

    return current


# ── Legacy compatibility ─────────────────────────────────────────

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
