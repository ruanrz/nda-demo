---
id: "ci_restraint"
title: "Scope of Evaluation Material (CI Restraint)"
enabled: true
document_type: NDA
priority: P1
---

# Scope of Evaluation Material (Confidential Information Restraint)

## 1. Rule Summary

**Trigger:** Any definition of "Evaluation Material," "Confidential Information," or "Proprietary Information."

## 2. Rationale: Scope Containment & Liability Risk

- **Prevention of Retroactive Liability:** Using "before the date hereof" creates a trap where the Recipient might unknowingly be in breach of an NDA for information shared months or years ago under different (or no) confidentiality expectations.
- **Transaction Segregation:** Large firms often have multiple touchpoints with a Company. This logic ensures that data shared for Project A is not accidentally governed by the stricter terms of Project B (The Transaction).
- **Auditability:** It is operationally simpler for an AI or a Compliance Officer to flag protected data if there is a fixed "T-Zero" date and a specific "Deal Identifier."

## 3. AI-Friendly Logic Schema

| Constraint Type | Logic Requirement | Action |
|----------------|------------------|--------|
| Purpose-Based | Link data strictly to the current deal. | Insert: "in connection with the Transaction" |
| Time-Based | Establish a clear "Starting Line" for liability. | Replace "whether before or after" with: "on or after the date hereof" |

| Component | Logic Filter | AI Processing Instruction |
|-----------|-------------|--------------------------|
| Nexus Filter | Subject.Purpose == "The Transaction" | Reject any info not explicitly deal-related. |
| Temporal Filter | Info.Date >= Agreement.Date | Reject info shared prior to the effective date. |
| Boilerplate Scrub | STRIP("before or after") | Always replace with the "Temporal Floor." |

## 4. Polished Example for AI Processing

**Original Boilerplate:**
> "Evaluation Material" means all information furnished by the Company... whether furnished before or after the date hereof, whether oral or written, and regardless of the manner in which it is furnished.

**Polished Version (AI-Optimized):**
> "Evaluation Material" means all information furnished by the Company... furnished in connection with the Transaction on or after the date hereof, whether oral or written, and regardless of the manner in which it is furnished.

## 5. Strategic "Why" for AI Reasoning

"Universal scope in an NDA is a high-risk vulnerability. By applying a Transactional Nexus and a Temporal Floor, the AI ensures the Recipient's liability is strictly gated. This protects against 'historical taint' and ensures that only data specifically intended for this deal falls under the contract's restrictive covenants."
