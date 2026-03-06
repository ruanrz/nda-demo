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
    INSERTION_SYSTEM_PROMPT,
    INSERTION_USER_PROMPT,
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
    source_docx_bytes: Optional[bytes] = None,
    source_docx_name: str = "contract.docx",
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
        "insertions": [],
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

    # ── Step 0: local structure parsing (disabled) ─────────────
    # parse_contract_structure output is not consumed downstream;
    # Step 1 sends the full contract_text to the LLM directly.
    # clauses = parse_contract_structure(contract_text)
    # result["contract_structure"] = [c.to_dict() for c in clauses]

    # ── Load playbooks if not provided ───────────────────────────
    if playbook_entries is None:
        playbook_entries = load_playbooks_from_markdown()
        playbook_source = "markdown"

    rules_text = format_rules_for_prompt(playbook_entries)
    mode_instruction = COUNTERPARTY_MODE if mode == "counterparty" else OWN_PAPER_MODE

    # ── Step 1: Analysis — diagnose gaps (1 LLM call) ───────────
    _progress("analysis", "Analysing contract against all Playbook rules…")
    logger.info("Step 1: Analysis call (preset=%s)", client.preset_name)

    analysis_kwargs: Dict[str, Any] = {
        "task_type": "analysis",
        "system_prompt": ANALYSIS_SYSTEM_PROMPT,
        "user_prompt": ANALYSIS_USER_PROMPT.format(
            playbook_rules=rules_text,
            contract_text=contract_text,
            mode_instruction=mode_instruction,
        ),
        "temperature": 0.0,
        "max_tokens": 16384,
    }
    if getattr(client, "is_gemini_provider", lambda: False)():
        analysis_kwargs["file_attachments"] = _build_playbook_file_attachments(playbook_entries)
    # Gemini best-effort document grounding: attach source DOCX when available.
    if (
        source_docx_bytes
        and getattr(client, "is_gemini_provider", lambda: False)()
    ):
        analysis_kwargs.update({
            "document_bytes": source_docx_bytes,
            "document_name": source_docx_name or "contract.docx",
            "document_mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        })

    analysis_result = client.call_json(
        **analysis_kwargs,
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
        and c.get("clause_text", "").strip()
    ]

    missing_rule_analyses = [
        c for c in clause_analysis
        if c.get("compliance_status") != "compliant"
        and c.get("severity") != "GREEN"
        and not c.get("clause_text", "").strip()
    ]
    missing_rule_ids: set = set()
    for item in missing_rule_analyses:
        for rid in (item.get("applicable_rule_ids") or []):
            missing_rule_ids.add(rid)

    if "blind_nda" in missing_rule_ids and _has_template_placeholders(contract_text):
        logger.info(
            "blind_nda suppressed: contract contains template placeholders "
            "(e.g. [CLIENT NAME]), not a true Blind NDA."
        )
        missing_rule_ids.discard("blind_nda")

    # Group by clause_text to avoid revising the same clause multiple times
    clause_groups = _group_analyses_by_clause(clauses_needing_revision, playbook_entries)

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
    print(f"\n{'#'*80}")
    print(f"  STEP 1: ANALYSIS RESULT")
    print(f"{'#'*80}")
    print(f"  Rules checked: {analysis_summary.get('total_rules_checked', len(clause_analysis))}")
    print(f"  Compliant: {analysis_summary.get('compliant', 0)}")
    print(f"  Non-compliant: {analysis_summary.get('non_compliant', 0)}")
    print(f"  Overall risk: {analysis_summary.get('overall_risk', '?')}")
    print(f"  Clauses needing revision: {len(clause_groups)}")
    for item in clause_analysis:
        status = item.get("compliance_status", "?")
        cid = item.get("clause_id", "?")
        sev = item.get("severity", "?")
        mark = "✅" if status == "compliant" else "❌"
        print(f"    {mark} {cid} [{sev}] {status}")
    print()

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

        print(f"\n{'#'*80}")
        print(f"  STEP 2: REVISION RESULTS  ({len(revisions)} clauses revised)")
        print(f"{'#'*80}")
        for i, rev in enumerate(revisions, 1):
            cid = rev.get("clause_id", "?")
            sev = rev.get("severity", "?")
            reasoning = rev.get("reasoning", "")
            changes = rev.get("changes_made", [])
            print(f"\n  --- Clause {i}: {cid} [{sev}] ---")
            print(f"  Reasoning: {reasoning}")
            for ch in changes:
                print(f"    • {ch.get('what','')} — {ch.get('why','')}")
            orig = rev.get("original_clause", "")
            revised = rev.get("revised_clause", "")
            if orig != revised and revised:
                print(f"  [Original]\n{orig}")
                print(f"  [Revised]\n{revised}")
            if rev.get("error"):
                print(f"  ⚠ ERROR: {rev['error']}")
        print()

        _progress("execution_done", f"Revised {len(revisions)} clauses")
    else:
        _progress("execution_done", "No revisions needed — contract is compliant")
        result["step_trace"].append({
            "step": "Step 2", "name": "Revision",
            "engine": "Skipped",
            "thinking": ["No non-compliant findings; no revisions needed."],
            "output": {"clauses_revised": 0},
        })

    # ── Step 2b: Insert missing clauses (1 LLM call) ─────────────
    insertions: List[Dict[str, Any]] = []
    if missing_rule_ids:
        _progress("insertion", f"Drafting {len(missing_rule_ids)} missing clauses…")
        logger.info("Step 2b: Inserting clauses for %d missing rules", len(missing_rule_ids))

        missing_rules_text = get_rules_text_by_ids(
            list(missing_rule_ids), playbook_entries
        )
        defined_terms_str_ins = json.dumps(defined_terms, ensure_ascii=False, indent=2)

        insertion_kwargs: Dict[str, Any] = {
            "task_type": "insertion",
            "system_prompt": INSERTION_SYSTEM_PROMPT,
            "user_prompt": INSERTION_USER_PROMPT.format(
                contract_text=contract_text,
                missing_rules=missing_rules_text,
                defined_terms=defined_terms_str_ins,
            ),
            "temperature": 0.1,
            "max_tokens": 8192,
        }

        insertion_result = client.call_json(**insertion_kwargs)
        insertions = insertion_result.get("insertions", [])
        result["insertions"] = insertions

        for ins in insertions:
            for ch in ins.get("changes_made", []):
                result["modifications"].append({
                    "rule_id": ch.get("rule_id", ""),
                    "rule_title": ch.get("what", ""),
                    "original_fragment": "",
                    "modified_fragment": ins.get("clause_text", "")[:200],
                    "modification_type": "insertion",
                    "explanation": ch.get("why", ""),
                    "severity": "P0",
                })

        ins_thinking = []
        for ins in insertions:
            reasoning = ins.get("reasoning", "")
            heading = ins.get("clause_heading", "?")
            ins_thinking.append(f"{heading}: {reasoning[:150]}")

        result["step_trace"].append({
            "step": "Step 2b", "name": "Insertion",
            "engine": f"LLM ({client.routing.get('insertion', 'default')})",
            "thinking": ins_thinking[:8],
            "output": {
                "clauses_inserted": len(insertions),
                "total_changes": sum(len(i.get("changes_made", [])) for i in insertions),
            },
        })

        print(f"\n{'#'*80}")
        print(f"  STEP 2b: INSERTION RESULTS  ({len(insertions)} clauses drafted)")
        print(f"{'#'*80}")
        for i, ins in enumerate(insertions, 1):
            heading = ins.get("clause_heading", "?")
            rid = ins.get("rule_id", "?")
            reasoning = ins.get("reasoning", "")
            insert_after = ins.get("insert_after", "?")
            full_clause = ins.get("clause_text", "")
            print(f"\n  --- Insertion {i}: {heading} (rule={rid}) ---")
            print(f"  Insert after: {insert_after}")
            print(f"  Reasoning: {reasoning}")
            print(f"  [Full clause text] ({len(full_clause)} chars)")
            print(f"{full_clause}")
            if rid == "mandatory_language":
                has_a = "Dual Representative" in full_clause
                has_b = "investment business" in full_clause.lower() or "competitors" in full_clause.lower()
                has_c = "electronic data room" in full_clause.lower()
                print(f"  [mandatory_language check] Rule A (Dual Rep): {'YES' if has_a else 'MISSING'}")
                print(f"  [mandatory_language check] Rule B (Non-Restriction): {'YES' if has_b else 'MISSING'}")
                print(f"  [mandatory_language check] Rule C (Data Room): {'YES' if has_c else 'MISSING'}")
        print()

        _progress("insertion_done", f"Drafted {len(insertions)} new clauses")

    # ── Step 3: Assembly — stitch revised clauses back ───────────
    final_text = _assemble_final_text(contract_text, result["revisions"])

    # Keep revision-only text for clean paragraph-aligned redline diff.
    # Insertions are passed separately to the Word generator so they
    # appear as pure tracked-insert paragraphs without breaking alignment.
    result["final_text_revisions_only"] = final_text

    if insertions:
        final_text = _insert_new_clauses(final_text, insertions)

    result["final_text"] = final_text

    print(f"\n{'#'*80}")
    print(f"  STEP 3: ASSEMBLY (local text stitching)")
    print(f"{'#'*80}")
    if final_text != contract_text:
        print(f"  Final text length: {len(final_text)} chars (original: {len(contract_text)} chars)")
        print(f"  [Final text]")
        for line in final_text.split('\n'):
            print(f"    {line}")
    else:
        print(f"  No changes — final text is identical to original.")
    print()

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

        print(f"\n{'#'*80}")
        print(f"  STEP 4: ISSUES & RISK SUMMARY")
        print(f"{'#'*80}")
        print(f"  Executive Summary: {result['executive_summary']}")
        print(f"  Compliance Score: {result['compliance_score']}")
        print(f"  Issues ({len(result['issues_list'])}):")
        for iss in result["issues_list"]:
            sev = iss.get("severity", "?")
            title = iss.get("title", iss.get("description", "?"))
            cat = iss.get("category", "")
            print(f"    [{sev}] {title}" + (f"  ({cat})" if cat else ""))
        print()

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

    stats = result["llm_stats"]
    print(f"\n{'#'*80}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'#'*80}")
    print(f"  Total LLM calls: {stats.get('total_calls', 0)}")
    print(f"  Total duration:  {stats.get('total_duration', 0):.1f}s")
    print(f"  Total tokens:    {stats.get('total_tokens', 0):,}")
    for i, call in enumerate(stats.get("calls", []), 1):
        print(f"    Call {i}: task={call.get('task','')}  model={call.get('model','')}"
              f"  {call.get('duration',0):.1f}s  {call.get('tokens',0):,} tokens")
    print(f"{'#'*80}\n")

    _progress("done", "Review complete")
    return result


# ─── Helpers ─────────────────────────────────────────────────────

_PUNCT_MAP = str.maketrans({
    '\u201c': '"', '\u201d': '"',
    '\u2018': "'", '\u2019': "'",
    '\u2014': '-', '\u2013': '-',
    '\u00a0': ' ',
})


_TEMPLATE_PLACEHOLDER_RE = re.compile(
    r"\[(?:CLIENT|COMPANY|DISCLOSING\s+PARTY|PARTY|ENTITY|TARGET)\s*NAME\]",
    re.IGNORECASE,
)


def _has_template_placeholders(contract_text: str) -> bool:
    """Return True if the contract uses standard fill-in-the-blank placeholders
    for the company name (e.g. [CLIENT NAME]), indicating an unsigned template
    rather than a genuine Blind NDA with a concealed identity."""
    return bool(_TEMPLATE_PLACEHOLDER_RE.search(contract_text))


def _normalize_text(text: str) -> str:
    """Normalize whitespace and common punctuation variants for matching."""
    return re.sub(r'\s+', ' ', text.translate(_PUNCT_MAP)).strip()


def _safe_attachment_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._")
    return cleaned or "attachment"


def _build_playbook_file_attachments(
    playbook_entries: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Build in-memory file attachments so Gemini native SDK can receive each
    selected playbook as a separate uploaded file.
    """
    attachments: List[Dict[str, Any]] = []
    for idx, entry in enumerate(playbook_entries or [], 1):
        rid = str(entry.get("id", f"rule_{idx}"))
        title = str(entry.get("title", "Rule"))
        source_file = str(entry.get("source_file", f"{rid}.md"))
        priority = str(entry.get("priority", "P1"))
        rule_type = str(entry.get("type", "rule"))
        body = str(entry.get("markdown_body", "") or "")

        file_text = (
            f"# {title}\n\n"
            f"- id: {rid}\n"
            f"- type: {rule_type}\n"
            f"- priority: {priority}\n"
            f"- source_file: {source_file}\n\n"
            f"{body}\n"
        )
        file_name = _safe_attachment_name(f"playbook_{rid}.md")
        attachments.append({
            "display_name": f"Playbook_{idx}_{_safe_attachment_name(rid)}",
            "file_name": file_name,
            "mime_type": "text/markdown",
            "content_bytes": file_text.encode("utf-8"),
        })
    return attachments


def _group_analyses_by_clause(
    analyses: List[Dict[str, Any]],
    playbook_entries: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Group analysis entries by clause_text so each unique clause is revised
    only once, even if multiple rules apply to it.

    Returns a list of dicts:
      {
        clause_id, clause_text, clause_location, applicable_rule_ids, combined_gaps, severity,
        highest_priority, priority_rule_ids, has_conflict, conflict_notes
      }
    """
    priority_by_rule_id: Dict[str, str] = {}
    for entry in playbook_entries or []:
        rid = str(entry.get("id", "")).strip()
        if not rid:
            continue
        priority = str(entry.get("priority", "P1")).strip().upper()
        priority_by_rule_id[rid] = priority if priority.startswith("P") else "P1"

    def _priority_rank(priority: str) -> int:
        ranks = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        return ranks.get(str(priority).upper(), 9)

    def _detect_conflicts(gaps: List[str]) -> List[str]:
        notes: List[str] = []
        merged = "\n".join(gaps).lower()

        has_insert = bool(re.search(r"\b(add|insert|append|include)\b", merged))
        has_replace = bool(re.search(r"\b(replace|substitute|remove|delete)\b", merged))
        if has_insert and has_replace:
            notes.append(
                "Mixed edit intents detected (insert + replace/remove). "
                "Prioritize replacement when both cannot coexist cleanly."
            )

        if "before or after" in merged and "on or after" in merged:
            notes.append(
                "Potential time-scope conflict detected: both 'before or after' and "
                "'on or after' appear in gap assessments."
            )
        return notes

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
                "rule_priorities": {},
            }

        rule_ids = item.get("applicable_rule_ids", [])
        if isinstance(rule_ids, str):
            rule_ids = [rule_ids]
        for rid in rule_ids:
            if rid not in groups[norm_key]["applicable_rule_ids"]:
                groups[norm_key]["applicable_rule_ids"].append(rid)
            groups[norm_key]["rule_priorities"][rid] = priority_by_rule_id.get(rid, "P2")

        gaps = item.get("gaps", "")
        if gaps and gaps not in groups[norm_key]["combined_gaps"]:
            groups[norm_key]["combined_gaps"].append(gaps)

        if item.get("severity") == "RED":
            groups[norm_key]["severity"] = "RED"

    result = []
    for g in groups.values():
        priority_rule_ids = sorted(
            g["applicable_rule_ids"],
            key=lambda rid: (_priority_rank(g["rule_priorities"].get(rid, "P2")), str(rid)),
        )
        g["priority_rule_ids"] = priority_rule_ids
        g["highest_priority"] = (
            g["rule_priorities"].get(priority_rule_ids[0], "P2")
            if priority_rule_ids else "P2"
        )

        conflict_notes = _detect_conflicts(g["combined_gaps"])
        top_tier = [
            rid for rid in priority_rule_ids
            if g["rule_priorities"].get(rid, "P2") == g["highest_priority"]
        ]
        if len(top_tier) > 1:
            conflict_notes.append(
                f"Multiple top-priority rules ({g['highest_priority']}) apply to this clause: "
                + ", ".join(top_tier)
            )
        g["has_conflict"] = bool(conflict_notes)
        g["conflict_notes"] = conflict_notes

        combined = "\n".join(g["combined_gaps"]).strip()
        if priority_rule_ids:
            priority_lines = [
                f"- {rid}: {g['rule_priorities'].get(rid, 'P2')}" for rid in priority_rule_ids
            ]
            combined += (
                "\n\n[PRIORITY ANNOTATION]\n"
                "Apply lower-numbered priority first (P0 > P1 > P2 > P3).\n"
                + "\n".join(priority_lines)
            )
        if conflict_notes:
            combined += (
                "\n\n[CONFLICT CHECK]\n"
                + "\n".join(f"- {note}" for note in conflict_notes)
            )
        g["combined_gaps"] = combined
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
            "highest_priority": group.get("highest_priority", "P2"),
            "priority_rule_ids": group.get("priority_rule_ids", []),
            "has_conflict": group.get("has_conflict", False),
            "conflict_notes": group.get("conflict_notes", []),
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


def _find_insert_position(text: str, insert_after: str) -> int:
    """Find the end-of-paragraph position after the section matching *insert_after*."""
    if not insert_after:
        return -1

    idx = text.find(insert_after)
    if idx >= 0:
        para_end = text.find("\n\n", idx + len(insert_after))
        return para_end if para_end >= 0 else len(text)

    norm_after = _normalize_text(insert_after)
    if len(norm_after) < 10:
        return -1

    escaped_words = [re.escape(w) for w in norm_after.split()[:20]]
    flex_pattern = r'\s+'.join(escaped_words)
    match = re.search(flex_pattern, text, re.IGNORECASE)
    if match:
        para_end = text.find("\n\n", match.end())
        return para_end if para_end >= 0 else len(text)

    return -1


_SIGNATURE_MARKERS = [
    "Very truly yours",
    "Sincerely",
    "IN WITNESS WHEREOF",
    "(Remainder of page intentionally left blank)",
]


def _insert_new_clauses(
    text: str,
    insertions: List[Dict[str, Any]],
) -> str:
    """Insert new clauses at designated locations in the contract text."""
    current = text
    logger.info("_insert_new_clauses: processing %d insertions", len(insertions))

    for ins in insertions:
        insert_after = ins.get("insert_after", "").strip()
        clause_text = ins.get("clause_text", "").strip()
        clause_heading = ins.get("clause_heading", "")
        rule_id = ins.get("rule_id", "")

        if not clause_text:
            logger.warning("Skipping insertion '%s' (rule=%s): empty clause_text", clause_heading, rule_id)
            continue

        logger.info(
            "Inserting '%s' (rule=%s): %d chars, insert_after='%s'",
            clause_heading, rule_id, len(clause_text), insert_after[:80],
        )

        if insert_after.upper() == "END":
            current = current.rstrip() + "\n\n" + clause_text
            logger.info("  -> Inserted at END")
            continue

        pos = _find_insert_position(current, insert_after)
        if pos >= 0:
            current = current[:pos] + "\n\n" + clause_text + current[pos:]
            logger.info("  -> Inserted at position %d (after '%s')", pos, insert_after[:50])
            continue

        logger.warning(
            "  -> insert_after='%s' not found in text (%d chars), trying signature fallback",
            insert_after[:80], len(current),
        )
        inserted = False
        for marker in _SIGNATURE_MARKERS:
            idx = current.find(marker)
            if idx > 0:
                current = current[:idx] + clause_text + "\n\n" + current[idx:]
                logger.info("  -> Inserted before signature marker '%s' at pos %d", marker, idx)
                inserted = True
                break
        if not inserted:
            current = current.rstrip() + "\n\n" + clause_text
            logger.info("  -> Inserted at document end (final fallback)")

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
