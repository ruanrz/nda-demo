---
id: "2"
title: Post-signing transaction-related information
type: replace
enabled: true
document_type: NDA
---

# Post-signing transaction-related information

## Rule Summary

Restrict the definition of "Confidential Information" to information disclosed **in connection with the Transaction on or after the date hereof**.

## Rules

### Rule: rule_2 — Restrict definition scope of 'Confidential Information'

- **Type:** replace
- **Trigger:** When a Confidential Information definition clause exists in the document
- **Action:** Ensure the definition is restricted to information provided
  "in connection with the Transaction on or after the date hereof"

#### Execution Strategy

1. **Preferred: Replace conflicting phrase**
   - If the original text contains "whether furnished before or after the date hereof",
     replace that phrase with "on or after the date hereof"
   - find: "whether furnished before or after the date hereof"
   - replace: "on or after the date hereof"

2. **Fallback: Targeted insertion** (only when the phrase above does NOT exist)
   - Insert "in connection with the Transaction on or after the date hereof"
     after "to the Recipient" or "to the Receiving Party"

#### Constraints

- `[CRITICAL]` Do NOT insert "on or after" while retaining "before or after" — this creates a direct semantic contradiction
- `[CRITICAL]` If the original text has ANY time-restriction phrase, REPLACE it rather than adding alongside it
- `[PROHIBITED]` Do NOT insert after "information" — this causes a semantic error
- Clearly define the specific content and parties involved in this transaction
- Strictly enforce time range requirement: only covering information on or after agreement date

#### Example — Replace Path

**Before:**
> "Confidential Information" means any information furnished by the Company to the Recipient, whether furnished before or after the date hereof, including...

**After:**
> "Confidential Information" means any information furnished by the Company to the Recipient, on or after the date hereof, including...

#### Example — Insertion Path

**Before:**
> "Confidential Information" means any information provided by the Company to the Recipient, including...

**After:**
> "Confidential Information" means any information provided by the Company to the Recipient in connection with the Transaction on or after the date hereof, including...

#### Rationale

Restrict confidential information to transaction-related info disclosed on or after the agreement date, preventing coverage of unrelated or earlier information.
