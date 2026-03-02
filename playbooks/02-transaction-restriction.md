---
id: "2"
title: Post-signing transaction-related information
type: add_text
enabled: true
document_type: NDA
---

# Post-signing transaction-related information

## Rule Summary

Restrict the definition of "Confidential Information" to information disclosed **in connection with the Transaction on or after the date hereof**.

## Rules

### Rule: rule_2 — Restrict definition scope of 'Confidential Information'

- **Type:** add_text
- **Trigger:** When a Confidential Information definition clause exists in the document
- **Action:** Add 'in connection with the Transaction on or after the date hereof' after 'to the Recipient' or 'to the Receiving Party'
- **Exact Wording:** `in connection with the Transaction on or after the date hereof`
#### Insert Position

| Position | After these phrases |
|----------|-------------------|
| **Required** | `to the Recipient`, `to the Receiving Party`, `by the Company to the Recipient`, `by the Disclosing Party to the Receiving Party` |

> **CRITICAL:** Must insert **after** the recipient description (e.g. "to the Recipient"). **NEVER** insert after "information" — this causes a semantic error.

#### Constraints

- `[CRITICAL]` Must insert after "to the Recipient" or "to the Receiving Party"
- `[PROHIBITED]` Cannot insert after "information" — this will cause semantic error
- Clearly define the specific content and parties involved in this transaction
- Strictly enforce time range requirement: only covering information on or after agreement date

#### Example

**Before:**
> "Confidential Information" means any information provided by the Company to the Recipient, including...

**After:**
> "Confidential Information" means any information provided by the Company to the Recipient in connection with the Transaction on or after the date hereof, including...

#### Rationale

Restrict confidential information to transaction-related info disclosed on or after the agreement date, preventing coverage of unrelated or earlier information.
