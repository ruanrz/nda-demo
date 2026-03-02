# AI Legal Assistant — Technical Architecture

## 1. Design Goal

Playbook-driven NDA contract review with **surgical-precision redlining**: minimal edits, preserved original language, zero hallucinated clauses.

---

## 2. Review Pipeline

A single review invocation makes **1–3 sequential LLM calls** (plus local deterministic steps), each with a distinct role:

```
Contract Text + Playbook Rules
        │
        ▼
┌───────────────────────────────────────────┐
│  Step 0  CONTRACT PARSER         (local)  │
│  Regex-based clause segmentation.         │
│  Identifies Section / Clause / Sub-clause │
│  hierarchy (level 0/1/2). Zero latency.   │
└───────────────────┬───────────────────────┘
                    │  structured clauses
                    ▼
┌───────────────────────────────────────────┐
│  Step 1  ANALYSIS                 (LLM)   │
│  Model: preset-dependent                  │
│                                            │
│  Input:  full contract + all Playbook MD   │
│  Method: per-rule structured reasoning     │
│          LOCATE → ASSESS → CLASSIFY        │
│          → PLAN → VERIFY                   │
│  Output: for each rule —                   │
│    • matched clause (exact quote)          │
│    • compliance: GREEN / YELLOW / RED      │
│    • brief rationale (1–3 bullets)         │
│    • modification plan:                    │
│        find_text  (exact substring)        │
│        replace_with (using exact_wording)  │
└───────────────────┬───────────────────────┘
                    │  modification plan[]
                    ▼
┌───────────────────────────────────────────┐
│  Step 2  EXECUTION              (local*)  │
│                                            │
│  Input:  original text + plan from Step 1  │
│  Method: deterministic find → replace      │
│  Output:                                   │
│    • final_text (complete contract)        │
│    • per-modification diff                 │
│    • verification (planned vs applied)     │
└───────────────────┬───────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────┐
│  Step 3  ISSUES LIST              (LLM)   │
│  (optional, model: preset-dependent)       │
│                                            │
│  Input:  analysis[] + modifications[]      │
│  Output:                                   │
│    • issues[] with P0/P1/P2 severity       │
│    • executive summary                     │
│    • compliance score (%)                  │
└───────────────────┬───────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   HTML Redline   Word .docx   Issues Report
```

**Why 2 calls instead of 1:**  Separating analysis from execution lets Step 1 focus on *reasoning* (which clause, what's wrong, how to fix) while Step 2 focuses on *precision* (exact text substitution without creative drift). This mirrors the "plan then act" pattern that consistently outperforms single-shot generation in LLM benchmarks.

**\*Note on Step 2:** If the plan is truly a list of exact `find_text → replace_with` operations, execution is best done locally for determinism, speed, and cost. A model-based execution step is only needed if you allow context-sensitive edits (e.g., insertions relative to headings, formatting-aware changes, or multi-span edits).

---

## 3. Model Routing

The `LLMClient` routes each call by task type. Two presets are provided:

### Quality-first (recommended when accuracy matters more than cost)

| Task | Model | Why |
|------|-------|-----|
| `analysis` | **o3** (or best-available reasoning model) | Strongest multi-step legal reasoning; fewest YELLOW/RED misclassifications |
| `execution` | **local find/replace** + o3 fallback | Deterministic first; model fallback only when exact match fails |
| `summary` | gpt-4o | Better synthesis and risk framing than mini |
| `validation` | gpt-4o | Catches subtle plan-vs-result mismatches |

### Cost-optimised (production default for high-volume)

| Task | Model | Why |
|------|-------|-----|
| `analysis` | gpt-4o | Good reasoning at ~1/5 the cost of o3 |
| `execution` | **local find/replace** + gpt-4o fallback | Same local-first strategy; lighter fallback model |
| `summary` | gpt-4o-mini | Classification task; mini suffices at 1/10 cost |
| `validation` | gpt-4o-mini | Binary correctness checks |

The routing table is a plain dict and can be overridden per-call or globally. The client also supports `OPENAI_API_BASE` for Azure OpenAI or any OpenAI-compatible endpoint.

> **How to switch:** set `MODEL_PRESET=quality` in env, or select the preset in the Streamlit UI sidebar. The quality preset is roughly 5–8x the per-review cost but measurably reduces misclassification and missed clauses.

---

## 4. Playbook System

### 4.1 Format

Each Playbook is a standalone Markdown file with YAML frontmatter:

```markdown
---
id: "4"
title: Compelled Disclosure
type: conditional
priority: P0
---

# Compelled Disclosure

## Rule Summary
Ensure that when the Receiving Party or its Representatives are
required by law to disclose Confidential Information...

## Rules
### Rule 6.2 — Notice Requirement Modifications
- **Type:** conditional
- **Trigger:** When counterparty requires Recipient to provide notice...
...
```

The **Markdown body is injected verbatim** into the LLM prompt. This means the rules the model sees are identical to what a human reads in the file — no lossy JSON serialisation, no schema translation.

### 4.2 Rule Types

Five rule types, each with different semantics the LLM must follow:

| Type | Trigger → Action | LLM behaviour |
|------|-------------------|---------------|
| **add_text** | keyword detected → insert exact wording at specified position | Find trigger, insert exact string, respect `insert_position` |
| **checklist** | clause exists → verify all required elements present | Enumerate existing vs required, add only missing items |
| **conditional** | evaluate N conditions → apply action if condition met | Check each condition against contract text, branch on result |
| **simplify** | verbose pattern detected → reduce to minimal form | Keep listed terms, remove listed terms |
| **replace** | problematic phrase → swap with preferred phrase | Direct find/replace, preserve surrounding grammar |

### 4.3 Severity Classification

Every rule match is classified using a three-tier system (adopted from [Anthropic's open-source legal plugin](https://github.com/anthropics/knowledge-work-plugins/tree/main/legal)):

| Level | Meaning | Action |
|-------|---------|--------|
| **GREEN** | Clause complies with Playbook | No modification |
| **YELLOW** | Deviation within fixable range (P1) | Generate targeted redline |
| **RED** | Critical gap or missing clause (P0) | Generate redline + flag for escalation |

---

## 5. Prompt Engineering

### 5.1 Analysis Prompt — Structured Reasoning

The Analysis system prompt enforces a five-step reasoning structure for every rule:

```
1. LOCATE   — Which clause does this rule target? (exact quote)
2. ASSESS   — Does the clause comply? What's the gap?
3. CLASSIFY — GREEN / YELLOW / RED
4. PLAN     — Minimal change: find_text → replace_with, exact position
5. VERIFY   — Will grammar and meaning survive the edit?
```

To keep decisions auditable without relying on hidden reasoning, the model should output **evidence-first fields** (exact quotes) plus a short, non-sensitive `rationale` (1–3 bullets) and the concrete modification plan.

### 5.2 Execution Prompt — Deterministic Substitution

The Execution prompt is deliberately restrictive:

- Apply EVERY planned modification exactly as specified
- find_text → replace_with: direct text substitution
- Do NOT make any changes beyond the planned modifications
- Keep all unchanged text EXACTLY as-is
- Output the COMPLETE contract

This separation prevents the "creative drift" problem where a model asked to both analyse and edit in one pass starts inventing improvements.

### 5.3 Mode-Specific Behaviour

Two prompt variants alter the model's stance:

| Mode | System instruction effect |
|------|--------------------------|
| **Own Paper** | Focus on Playbook compliance. Protective but not adversarial. |
| **Counterparty** | Flag one-sided provisions, missing protections, non-market terms. Issues List emphasises risks to our side. |

---

## 6. Output Generation

### 6.1 Word Redline Document

Uses `python-docx` + `diff_match_patch` to produce a `.docx` with native Word review revisions (`<w:ins>/<w:del>`):

| Diff operation | Rendering |
|----------------|-----------|
| `DIFF_EQUAL` | Black, normal font |
| `DIFF_DELETE` | Red, strikethrough |
| `DIFF_INSERT` | Red, bold, single underline |

The document appends:
- native Word review revisions (`<w:ins>/<w:del>`) for all edits;
- concise per-change rationale comments (when reason cannot be represented in revision metadata);
- the Issues List as a severity-coloured table.

### 6.2 Issues List

Structured JSON array, each item containing:

```
id, severity (P0/P1/P2), category, title, description,
clause_reference, current_language, recommended_action,
status (resolved/needs_review/informational), playbook_rule
```

Plus an `executive_summary` and `compliance_score` (percentage of rules satisfied).

---

## 7. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Markdown playbooks, not JSON** | LLMs comprehend Markdown natively; files are human-editable; git-diff-friendly. Aligned with Anthropic's plugin architecture. |
| **2-call pipeline, not 1** | Analysis-then-execution prevents creative drift. Each call's system prompt is tightly scoped. |
| **Two model presets: quality-first vs cost-optimised** | Quality preset uses o3 for analysis (strongest reasoning, fewest misclassifications) + local execution; cost preset uses gpt-4o/mini. Switch via `MODEL_PRESET` env var. |
| **Local contract parsing, not LLM** | Regex clause detection is instant and deterministic. Gives the LLM structural hints without spending tokens on formatting. |
| **GREEN/YELLOW/RED classification** | Industry-standard severity triage (used by Anthropic's `/review-contract`, Dioptra, and most in-house legal teams). Makes output immediately actionable. |
| **Exact-wording enforcement** | Playbook rules carry `exact_wording` fields. Prompts repeatedly instruct "CHARACTER-FOR-CHARACTER". This is the single most important constraint against over-editing. |
| **Counterparty mode as prompt variant** | Same pipeline, different system instruction. Avoids code duplication while fundamentally changing the analytical stance. |
