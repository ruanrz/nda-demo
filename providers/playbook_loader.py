# -*- coding: utf-8 -*-
"""
Playbook loader — reads playbooks from Markdown files.

Each .md file in the playbooks/ directory represents one playbook entry.
YAML frontmatter (between --- delimiters) contains metadata.
The Markdown body contains the full rule content (rationale, logic schema,
examples, strategic reasoning) that is passed directly into the LLM prompt.
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("playbook_loader")

PLAYBOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "playbooks")


def _parse_frontmatter(content: str) -> tuple:
    """Extract YAML frontmatter and body from Markdown content."""
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not fm_match:
        return {}, content

    fm_text = fm_match.group(1)
    body = fm_match.group(2)

    meta: Dict[str, Any] = {}
    for line in fm_text.strip().split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip().strip('"').strip("'")
        if val.lower() == "true":
            val = True
        elif val.lower() == "false":
            val = False
        meta[key.strip()] = val

    return meta, body


def load_playbooks_from_markdown(
    directory: Optional[str] = None,
    filter_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Load all playbook .md files from the given directory.

    Returns a list of dicts with:
      - id, title, type, enabled, document_type, priority  (from frontmatter)
      - markdown_body  (full markdown content for LLM prompt injection)
      - source_file    (filename)
    """
    directory = directory or PLAYBOOKS_DIR
    path = Path(directory)

    if not path.exists():
        logger.warning(f"Playbooks directory not found: {directory}")
        return []

    entries: List[Dict[str, Any]] = []

    for md_file in sorted(path.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(content)

            entry_id = str(meta.get("id", md_file.stem))

            if filter_ids and entry_id not in filter_ids:
                continue

            if meta.get("enabled") is False:
                continue

            entries.append({
                "id": entry_id,
                "title": meta.get("title", md_file.stem),
                "type": meta.get("type", "rule"),
                "enabled": meta.get("enabled", True),
                "document_type": meta.get("document_type", "NDA"),
                "priority": meta.get("priority", "P1"),
                "markdown_body": body.strip(),
                "source_file": md_file.name,
            })
            logger.debug(f"Loaded playbook: {md_file.name} (id={entry_id})")
        except Exception as e:
            logger.error(f"Failed to load {md_file}: {e}")

    logger.info(f"Loaded {len(entries)} playbooks from {directory}")
    return entries


def format_markdown_playbooks_for_prompt(entries: List[Dict[str, Any]]) -> str:
    """
    Format playbook entries for LLM prompt injection with intent-driven ordering.

    Restructures each playbook's content so the LLM sees:
      1. INTENT/RATIONALE — why this rule exists (legal/business reasoning)
      2. REQUIREMENTS — what specifically needs to change
      3. REFERENCE — polished examples and AI processing guidance
    """
    sections = []
    for entry in entries:
        header = f"═══ RULE: {entry['title']} (id={entry['id']}) ═══"
        body = reorder_playbook_sections(entry.get("markdown_body", ""))
        sections.append(f"{header}\n\n{body}")
    return "\n\n" + "\n\n".join(sections) + "\n"


# ── Section classification patterns ─────────────────────────────

_INTENT_RE = re.compile(
    r"(rationale|why|objective|strategic|purpose|reasoning)",
    re.IGNORECASE,
)
_REFERENCE_RE = re.compile(
    r"(example|polished|ai[- ]friendly|ai[- ]optimized|schema)",
    re.IGNORECASE,
)


def reorder_playbook_sections(markdown_body: str) -> str:
    """
    Reorder a playbook's markdown sections: intent/rationale first, then
    rules/requirements, then examples/reference.  Preserves all content.
    """
    if not markdown_body or not markdown_body.strip():
        return markdown_body

    parts = re.split(r"(?=^## )", markdown_body.strip(), flags=re.MULTILINE)

    preamble = ""
    sections: List[tuple] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("## "):
            heading = part.split("\n", 1)[0]
            if _INTENT_RE.search(heading):
                category = "intent"
            elif _REFERENCE_RE.search(heading):
                category = "reference"
            else:
                category = "requirement"
            sections.append((part, category))
        else:
            preamble = part

    if not sections:
        return markdown_body

    ordered = (
        [s for s in sections if s[1] == "intent"]
        + [s for s in sections if s[1] == "requirement"]
        + [s for s in sections if s[1] == "reference"]
    )

    result_parts = []
    if preamble:
        result_parts.append(preamble)
    for text, _ in ordered:
        result_parts.append(text)
    return "\n\n".join(result_parts)


def load_playbooks_for_display(
    directory: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load playbooks with display-friendly metadata for the Streamlit sidebar."""
    entries = load_playbooks_from_markdown(directory)
    for e in entries:
        lines = e["markdown_body"].split("\n")
        summary = ""
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                summary = stripped
                break
        e["summary"] = summary[:300] if summary else e["title"]
    return entries


# ── Legacy fallback: load from JSON ──────────────────────────────

def load_playbook_entries_json(
    path: str,
    filter_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Load playbook entries from JSON file (legacy format)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    if filter_ids:
        data = [e for e in data if str(e.get("id", "")) in filter_ids]
    return [e for e in data if e.get("enabled", True)]
