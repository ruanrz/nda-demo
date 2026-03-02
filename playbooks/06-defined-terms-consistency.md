---
id: "6"
title: Defined Terms Consistency
type: checklist
enabled: true
document_type: NDA
---

# Defined Terms Consistency

## Rule Summary

Ensure defined words are used consistently throughout the entire agreement. Do not add new definitions. Do not change existing definitions.

## Rules

### Rule: rule_defined_terms — Defined Terms Consistency Check

- **Type:** checklist
- **Trigger:** Applies to the entire agreement whenever any modification is made
- **Action:** Verify that all defined terms are used consistently and that no definitions are added or changed during modifications
- **Priority:** P0

#### Requirements

The following three constraints **must** be satisfied:

- [ ] **Consistency of defined terms:** All defined terms (e.g., "Confidential Information", "Recipient", "Receiving Party", "Representatives", "Company", "Disclosing Party", "Transaction") must be used in the same form throughout the entire agreement. If the agreement defines and uses "Recipient", do not introduce "Receiving Party" (and vice versa).
- [ ] **No new definitions:** When making modifications, do NOT introduce any new defined terms that do not already exist in the agreement.
- [ ] **No changed definitions:** When making modifications, do NOT alter the meaning or wording of any existing definition clause.

#### Constraints

- This rule applies **globally** across all clauses and sections
- When inserting language from other playbook rules, **adapt** the inserted wording to match the defined terms already used in the agreement
  - Example: If the agreement uses "Receiving Party" instead of "Recipient", all insertions must also use "Receiving Party"
  - Example: If the agreement uses "Company" instead of "Disclosing Party", all insertions must also use "Company"
- Capitalized terms in inserted text must match their defined forms in the agreement
- If a playbook rule's sample wording uses a different party label than the agreement, substitute with the agreement's label
- `preserve_existing: true` — never modify or remove existing definition clauses

#### Example

**Issue — Inconsistent term usage after modification:**

> Agreement uses "Receiving Party" throughout, but a playbook insertion added "Recipient" in Section 4.

**Action:** Replace "Recipient" with "Receiving Party" in the inserted text to maintain consistency.

---

**Issue — New definition introduced:**

> A modification added the phrase '"Permitted Disclosure" means…' which creates a new defined term not present in the original agreement.

**Action:** Remove the new definition. Rephrase the modification without introducing new defined terms.

#### Rationale

Inconsistent use of defined terms can create ambiguity about whether different labels refer to the same or different parties/concepts. Introducing new definitions or changing existing ones may alter the contractual scope beyond the intended playbook modifications.
