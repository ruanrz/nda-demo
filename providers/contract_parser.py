# -*- coding: utf-8 -*-
"""
Contract structure parser.

Regex-based clause / section identification — no LLM call needed.
Produces a structured representation that improves LLM accuracy
by giving it explicit clause boundaries and numbering.
"""

import re
from typing import List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ContractClause:
    index: int
    level: int        # 0 = section header, 1 = clause, 2 = sub-clause
    number: str       # e.g. "1.", "(a)", "(iii)"
    title: str        # section title if detected
    text: str         # full text of this clause
    char_offset: int  # character offset in original document

    def to_dict(self):
        return asdict(self)


# ── Detection helpers ────────────────────────────────────────────

_SECTION_HEADER = re.compile(
    r"^(?:"
    r"(?:ARTICLE|SECTION|PART)\s+[IVXLC\d]+[.:)]?\s*"  # ARTICLE I, SECTION 3
    r"|(\d+)\.\s+([A-Z][A-Z\s&,]{2,})"                 # 1. DEFINITIONS
    r")",
    re.MULTILINE,
)

_ALLCAPS_LINE = re.compile(r"^[A-Z][A-Z\s&,\-]{4,}$")

_NUMBERED_CLAUSE = re.compile(r"^(\d+(?:\.\d+)*\.?)\s+")

_SUB_CLAUSE = re.compile(r"^(\([a-z]+\)|\([ivxlc]+\))\s*", re.IGNORECASE)


def _detect_level(first_line: str):
    """Return (level, number, title) for the first line of a paragraph."""
    stripped = first_line.strip()

    if _SECTION_HEADER.match(stripped):
        m = re.match(r"^(\d+)\.\s+(.*)", stripped)
        if m:
            return 0, m.group(1) + ".", m.group(2).strip()
        return 0, "", stripped

    if _ALLCAPS_LINE.match(stripped) and len(stripped) < 80:
        return 0, "", stripped

    m = _NUMBERED_CLAUSE.match(stripped)
    if m:
        num = m.group(1)
        rest = stripped[m.end():].strip()
        title = rest.split(".")[0] if rest and rest[0].isupper() else ""
        return 1, num, title

    m = _SUB_CLAUSE.match(stripped)
    if m:
        return 2, m.group(1), ""

    return 1, "", ""


# ── Public API ───────────────────────────────────────────────────

def parse_contract_structure(text: str) -> List[ContractClause]:
    """Split contract text into structured clauses."""
    paragraphs = re.split(r"\n\s*\n", text)
    clauses: List[ContractClause] = []
    offset = 0

    for i, para in enumerate(paragraphs):
        stripped = para.strip()
        if not stripped:
            offset += len(para) + 1
            continue

        first_line = stripped.split("\n")[0]
        level, number, title = _detect_level(first_line)

        clauses.append(ContractClause(
            index=i,
            level=level,
            number=number,
            title=title,
            text=stripped,
            char_offset=offset,
        ))
        offset += len(para) + 1

    return clauses


def format_structured_contract(clauses: List[ContractClause]) -> str:
    """Render clauses into a numbered text block suitable for an LLM prompt."""
    parts: List[str] = []
    for c in clauses:
        tag = f"[§{c.index + 1}"
        if c.title:
            tag += f" – {c.title}"
        tag += "]"
        parts.append(f"{tag}\n{c.text}")
    return "\n\n".join(parts)


def find_clause_by_keywords(
    clauses: List[ContractClause],
    keywords: List[str],
) -> Optional[ContractClause]:
    """Return the first clause whose text contains all *keywords* (case-insensitive)."""
    for c in clauses:
        low = c.text.lower()
        if all(k.lower() in low for k in keywords):
            return c
    return None
