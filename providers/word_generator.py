# -*- coding: utf-8 -*-
"""
Word document generator with native Word Track Changes.

Produces a .docx using Word revision elements:
  - Deleted text → <w:del> (real deletion revision)
  - Added text   → <w:ins> (real insertion revision)
  - Unchanged    → normal runs

Uses diff_match_patch for character-level diffing.
When rationale cannot be encoded in revision metadata, attach one concise
comment per changed paragraph/revision anchor.
"""

import io
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional

import diff_match_patch as dmp_module
from docx import Document
from docx.text.paragraph import Paragraph
from docx.text.run import Run
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


# ── Colours ──────────────────────────────────────────────────────
_RED = RGBColor(0xCF, 0x22, 0x2E)
_GREEN = RGBColor(0x1A, 0x7F, 0x37)
_BLACK = RGBColor(0x00, 0x00, 0x00)
_GREY = RGBColor(0x66, 0x66, 0x66)

_PARA_PUNCT_MAP = str.maketrans({
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2014": "-",
    "\u2013": "-",
    "\u00a0": " ",
})


def generate_redline_docx(
    original_text: str,
    modified_text: str,
    issues_list: Optional[List[Dict[str, Any]]] = None,
    modifications: Optional[List[Dict[str, Any]]] = None,
    title: Optional[str] = None,
    redline_heading: Optional[str] = None,
    include_issues_list: bool = False,
    source_docx_bytes: Optional[bytes] = None,
) -> io.BytesIO:
    """
    Generate a Word document with native Track Changes markup.

    Args:
        original_text:  The original contract text.
        modified_text:  The modified contract text.
        issues_list:    Optional issues list to append as a table.
        modifications:  Optional modification list used for short rationale comments.
        title:          Optional document title heading (H1). If None, no title heading.
        redline_heading: Optional section heading before redlined body (H2). If None, no section heading.
        include_issues_list: Whether to append Issues List table at the end.
        source_docx_bytes: Optional original .docx bytes used as template to preserve
                          paragraph-level styles (including native numbering).

    Returns:
        BytesIO buffer containing the .docx file.
    """
    use_source_template = False
    if source_docx_bytes:
        try:
            doc = Document(io.BytesIO(source_docx_bytes))
            use_source_template = True
        except Exception:
            doc = Document()
    else:
        doc = Document()

    if not use_source_template:
        # ── Styles ───────────────────────────────────────────────
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Calibri"
        font.size = Pt(11)

        # ── Optional headings ───────────────────────────────────
        # Keep disabled by default so exported redline mirrors contract structure.
        if title:
            doc.add_heading(title, level=1)
        if redline_heading:
            doc.add_heading(redline_heading, level=2)

        # ── Redline body (plain mode) ───────────────────────────
        _add_redline_paragraphs(doc, original_text, modified_text, modifications or [])
    else:
        # ── Redline body (template mode; keeps paragraph properties) ──
        _add_redline_paragraphs_from_template(
            doc, original_text, modified_text, modifications or []
        )

    # ── Issues List table ────────────────────────────────────────
    if include_issues_list and issues_list:
        doc.add_page_break()
        doc.add_heading("Issues List", level=2)
        _add_issues_table(doc, issues_list)

    # ── Write to buffer ──────────────────────────────────────────
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def _compute_diffs(text1: str, text2: str):
    """Character-level diff using diff_match_patch."""
    dmp = dmp_module.diff_match_patch()
    dmp.Diff_Timeout = 2.0
    diffs = dmp.diff_main(text1, text2)
    dmp.diff_cleanupSemantic(diffs)
    return diffs


def _iso_now_utc() -> str:
    """Return current UTC time in Word-friendly ISO8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _needs_space_preserve(text: str) -> bool:
    return bool(text) and (text[0].isspace() or text[-1].isspace())


def _append_tracked_insert(
    para: Paragraph,
    text: str,
    revision_id: int,
    author: str,
    date_iso: str,
) -> Optional[Run]:
    """Append a native Word insertion revision and return run anchor."""
    if not text:
        return None
    ins = OxmlElement("w:ins")
    ins.set(qn("w:id"), str(revision_id))
    ins.set(qn("w:author"), author)
    ins.set(qn("w:date"), date_iso)

    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    if _needs_space_preserve(text):
        t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    ins.append(r)
    para._p.append(ins)
    return Run(r, para)


def _append_tracked_delete(
    para: Paragraph,
    text: str,
    revision_id: int,
    author: str,
    date_iso: str,
) -> Optional[Run]:
    """Append a native Word deletion revision and return run anchor."""
    if not text:
        return None
    deleted = OxmlElement("w:del")
    deleted.set(qn("w:id"), str(revision_id))
    deleted.set(qn("w:author"), author)
    deleted.set(qn("w:date"), date_iso)

    r = OxmlElement("w:r")
    del_text = OxmlElement("w:delText")
    if _needs_space_preserve(text):
        del_text.set(qn("xml:space"), "preserve")
    del_text.text = text
    r.append(del_text)
    deleted.append(r)
    para._p.append(deleted)
    return Run(r, para)


def _find_mod_reason(
    original_para: str,
    modified_para: str,
    changed_text: str,
    modifications: List[Dict[str, Any]],
) -> str:
    """Pick the most relevant playbook rationale for a changed paragraph."""
    changed_norm = changed_text.strip()
    best_reason = ""

    for mod in modifications:
        orig_fragment = str(mod.get("original_fragment", "") or "")
        mod_fragment = str(mod.get("modified_fragment", "") or "")
        explanation = str(mod.get("explanation", "") or "").strip()
        rule_title = str(mod.get("rule_title", "") or "").strip()
        rule_id = str(mod.get("rule_id", "") or "").strip()

        if not explanation:
            continue

        reason_prefix = rule_title or rule_id or "Playbook rule"
        reason = _short_reason(f"{reason_prefix}: {explanation}")

        # Strong match: changed token appears in known before/after fragments.
        if changed_norm and (
            (orig_fragment and changed_norm in orig_fragment)
            or (mod_fragment and changed_norm in mod_fragment)
        ):
            return reason

        # Paragraph-level fallback.
        if (
            (orig_fragment and orig_fragment in original_para)
            or (mod_fragment and mod_fragment in modified_para)
        ):
            if not best_reason:
                best_reason = reason

    return best_reason


def _try_add_comment(doc: Document, anchor_run: Run, reason: str) -> None:
    """Best-effort add_comment, without breaking document generation."""
    if not reason:
        return
    try:
        doc.add_comment(
            anchor_run,
            text=reason,
            author="AI Legal Assistant",
            initials="AI",
        )
    except Exception:
        pass


def _add_redline_paragraphs(
    doc: Document,
    original: str,
    modified: str,
    modifications: List[Dict[str, Any]],
):
    """
    Split both texts into paragraphs, diff each pair, and write
    redline-formatted runs into the Word document.
    """
    orig_paras = original.split("\n")
    mod_paras = modified.split("\n")

    # Use the longer list length
    max_len = max(len(orig_paras), len(mod_paras))

    # Pad shorter list
    while len(orig_paras) < max_len:
        orig_paras.append("")
    while len(mod_paras) < max_len:
        mod_paras.append("")

    author = "AI Legal Assistant"
    revision_id = 1
    date_iso = _iso_now_utc()

    for orig_p, mod_p in zip(orig_paras, mod_paras):
        para = doc.add_paragraph()
        revision_id = _render_paragraph_diff(
            doc=doc,
            para=para,
            orig_p=orig_p,
            mod_p=mod_p,
            modifications=modifications,
            author=author,
            revision_id=revision_id,
            date_iso=date_iso,
        )


def _clear_paragraph_content(para: Paragraph) -> None:
    """Remove runs/revisions while preserving paragraph properties (w:pPr)."""
    p_elm = para._p
    for child in list(p_elm):
        if child.tag != qn("w:pPr"):
            p_elm.remove(child)


def _normalize_paragraph_for_alignment(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.translate(_PARA_PUNCT_MAP)).strip()


def _render_paragraph_diff(
    doc: Document,
    para: Paragraph,
    orig_p: str,
    mod_p: str,
    modifications: List[Dict[str, Any]],
    author: str,
    revision_id: int,
    date_iso: str,
) -> int:
    """
    Render a paragraph diff into an existing paragraph and return next revision id.

    Important behavior:
    - If normalized text is effectively equal, keep paragraph clean (no synthetic redline).
    - Only changed paragraphs get rewritten with ins/del revisions.
    """
    _clear_paragraph_content(para)

    if orig_p == mod_p or (
        _normalize_paragraph_for_alignment(orig_p)
        == _normalize_paragraph_for_alignment(mod_p)
    ):
        if mod_p:
            run = para.add_run(mod_p)
            run.font.color.rgb = _BLACK
        return revision_id

    diffs = _compute_diffs(orig_p, mod_p)
    comment_anchor: Optional[Run] = None
    comment_reason = ""
    for op, text in diffs:
        if not text:
            continue
        if op == dmp_module.diff_match_patch.DIFF_EQUAL:
            run = para.add_run(text)
            run.font.color.rgb = _BLACK
            if comment_anchor is None:
                comment_anchor = run
        elif op == dmp_module.diff_match_patch.DIFF_DELETE:
            deleted_run = _append_tracked_delete(
                para=para,
                text=text,
                revision_id=revision_id,
                author=author,
                date_iso=date_iso,
            )
            revision_id += 1
            if comment_anchor is None and deleted_run is not None:
                comment_anchor = deleted_run
            if not comment_reason:
                comment_reason = _find_mod_reason(orig_p, mod_p, text, modifications)
        elif op == dmp_module.diff_match_patch.DIFF_INSERT:
            inserted_run = _append_tracked_insert(
                para=para,
                text=text,
                revision_id=revision_id,
                author=author,
                date_iso=date_iso,
            )
            revision_id += 1
            if comment_anchor is None and inserted_run is not None:
                comment_anchor = inserted_run
            if not comment_reason:
                comment_reason = _find_mod_reason(orig_p, mod_p, text, modifications)

    if not comment_reason:
        comment_reason = "Aligned this edit with the selected playbook requirement."
    if comment_anchor is not None:
        _try_add_comment(doc, comment_anchor, _short_reason(comment_reason))
    return revision_id


def _split_contract_paragraphs(text: str) -> List[str]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return []
    if "\n\n" in normalized:
        chunks = re.split(r"\n{2,}", normalized)
    else:
        chunks = normalized.split("\n")
    return [p.strip() for p in chunks if p.strip()]


def _add_redline_paragraphs_from_template(
    doc: Document,
    original: str,
    modified: str,
    modifications: List[Dict[str, Any]],
):
    """
    Rewrite the source document's existing paragraphs so paragraph-level formatting
    (including native numbering) is preserved in output.
    """
    orig_paras = _split_contract_paragraphs(original)
    mod_paras = _split_contract_paragraphs(modified)
    if not orig_paras and not mod_paras:
        return

    existing_paras = [p for p in doc.paragraphs if (p.text or "").strip()]
    while len(existing_paras) < len(orig_paras):
        existing_paras.append(doc.add_paragraph())

    author = "AI Legal Assistant"
    revision_id = 1
    date_iso = _iso_now_utc()
    matcher = SequenceMatcher(
        a=[_normalize_paragraph_for_alignment(p) for p in orig_paras],
        b=[_normalize_paragraph_for_alignment(p) for p in mod_paras],
        autojunk=False,
    )

    def _insert_before(anchor: Optional[Paragraph], style_source: Optional[Paragraph]) -> Paragraph:
        if anchor is not None:
            p = anchor.insert_paragraph_before("")
        else:
            p = doc.add_paragraph()
        if style_source is not None:
            try:
                p.style = style_source.style
            except Exception:
                pass
        return p

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            # Keep untouched paragraphs as-is to preserve run-level formatting.
            continue

        if tag == "replace":
            pair_count = min(i2 - i1, j2 - j1)
            for offset in range(pair_count):
                orig_idx = i1 + offset
                mod_idx = j1 + offset
                para = existing_paras[orig_idx]
                revision_id = _render_paragraph_diff(
                    doc=doc,
                    para=para,
                    orig_p=orig_paras[orig_idx],
                    mod_p=mod_paras[mod_idx],
                    modifications=modifications,
                    author=author,
                    revision_id=revision_id,
                    date_iso=date_iso,
                )

            for orig_idx in range(i1 + pair_count, i2):
                para = existing_paras[orig_idx]
                revision_id = _render_paragraph_diff(
                    doc=doc,
                    para=para,
                    orig_p=orig_paras[orig_idx],
                    mod_p="",
                    modifications=modifications,
                    author=author,
                    revision_id=revision_id,
                    date_iso=date_iso,
                )

            if j1 + pair_count < j2:
                anchor_idx = i1 + pair_count
                anchor = existing_paras[anchor_idx] if anchor_idx < len(existing_paras) else None
                style_source = (
                    anchor
                    if anchor is not None
                    else (existing_paras[anchor_idx - 1] if anchor_idx > 0 else None)
                )
                for mod_idx in range(j1 + pair_count, j2):
                    para = _insert_before(anchor=anchor, style_source=style_source)
                    revision_id = _render_paragraph_diff(
                        doc=doc,
                        para=para,
                        orig_p="",
                        mod_p=mod_paras[mod_idx],
                        modifications=modifications,
                        author=author,
                        revision_id=revision_id,
                        date_iso=date_iso,
                    )
            continue

        if tag == "delete":
            for orig_idx in range(i1, i2):
                para = existing_paras[orig_idx]
                revision_id = _render_paragraph_diff(
                    doc=doc,
                    para=para,
                    orig_p=orig_paras[orig_idx],
                    mod_p="",
                    modifications=modifications,
                    author=author,
                    revision_id=revision_id,
                    date_iso=date_iso,
                )
            continue

        if tag == "insert":
            anchor = existing_paras[i1] if i1 < len(existing_paras) else None
            style_source = anchor if anchor is not None else (existing_paras[i1 - 1] if i1 > 0 else None)
            for mod_idx in range(j1, j2):
                para = _insert_before(anchor=anchor, style_source=style_source)
                revision_id = _render_paragraph_diff(
                    doc=doc,
                    para=para,
                    orig_p="",
                    mod_p=mod_paras[mod_idx],
                    modifications=modifications,
                    author=author,
                    revision_id=revision_id,
                    date_iso=date_iso,
                )


def _short_reason(reason: str, max_len: int = 160) -> str:
    """Keep rationale short and readable for Word comments."""
    if not reason:
        return ""
    compact = " ".join(reason.split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3].rstrip() + "..."


def _add_issues_table(doc: Document, issues: List[Dict[str, Any]]):
    """Render the issues list as a formatted table."""
    headers = ["#", "Severity", "Category", "Issue", "Clause", "Status"]
    table = doc.add_table(rows=1, cols=len(headers), style="Light Grid Accent 1")

    # Header row
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for run in cell.paragraphs[0].runs:
            run.bold = True

    # Data rows
    for issue in issues:
        row = table.add_row()
        row.cells[0].text = str(issue.get("id", ""))
        row.cells[1].text = str(issue.get("severity", ""))
        row.cells[2].text = str(issue.get("category", ""))
        row.cells[3].text = str(issue.get("title", issue.get("description", "")))
        row.cells[4].text = str(issue.get("clause_reference", ""))
        row.cells[5].text = str(issue.get("status", ""))

    # Severity colouring
    severity_colors = {"P0": _RED, "P1": RGBColor(0xE6, 0x7E, 0x22), "P2": _GREY}
    for row_idx in range(1, len(table.rows)):
        sev_cell = table.rows[row_idx].cells[1]
        sev_text = sev_cell.text.strip()
        if sev_text in severity_colors:
            for para in sev_cell.paragraphs:
                for run in para.runs:
                    run.font.color.rgb = severity_colors[sev_text]
                    run.bold = True


def generate_clean_docx(
    text: str,
    title: str = "Contract — Clean Copy",
) -> io.BytesIO:
    """Generate a clean Word document (no redlines) with the modified text."""
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    doc.add_heading(title, level=1)
    for para_text in text.split("\n\n"):
        stripped = para_text.strip()
        if stripped:
            doc.add_paragraph(stripped)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
