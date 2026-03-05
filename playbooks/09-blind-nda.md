---
id: "blind_nda"
title: "Conflict Check (Blind NDA)"
enabled: true
document_type: NDA
priority: P1
---

# Conflict Check (Blind NDA)

## 1. Rule Summary

**Trigger:** Any NDA where the Disclosing Party (Company) identity is initially withheld or replaced with a code name **in the body of the agreement** (e.g., "a company" or "[Company Name]" as the disclosing party). Do NOT trigger merely because the signature block has a placeholder like "[CLIENT NAME]" — that is standard for unsigned drafts.

| Logic Condition | AI Polished Action |
|-----------------|-------------------|
| If Identity is Hidden | Insert the "3-Business Day Conflict Check" clause immediately following the identification of the Company. |
| Exclusion Rule | Advisors are NOT Target Companies. The conflict check applies to the ultimate Target entity, not the intermediary bankers or law firms. |

## 2. Rationale: Ethical and Regulatory Compliance

- **Conflict of Interest (COI) Management:** Professional services firms and investment funds cannot sign a "blind" agreement that might accidentally bind them to a competitor or a party they are currently litigating against.
- **The "Right of Refusal":** The Recipient must have a clear "off-ramp." If a conflict is found, the Recipient must be able to terminate the agreement immediately without being burdened by "Non-Use" or "Non-Solicitation" clauses that could paralyze their existing business.
- **Liability Minimization:** By limiting the obligation to "only the name and the nature of the transaction" during the 3-day window, the Recipient ensures they don't accidentally "taint" their team with deeper Confidential Information before they are sure they can legally proceed.

## 3. AI-Friendly Logic Schema

| Logic Component | Structural Change | AI Rule |
|----------------|-------------------|---------|
| Trigger Verification | Checks if Company_Identity == [REDACTED/CODE_NAME]. | IF (Blind_Identity) THEN (INSERT_CONFLICT_CLAUSE) |
| Temporal Window | Sets a strict T+3 Business Days deadline for the "Exit" option. | SET_DEADLINE(3_Business_Days) |
| Post-Conflict Status | Defines the "Zero-Obligation" state if a conflict exists. | IF (Conflict_Found) THEN (Obligations = 0) EXCEPT (Identity_Secrecy) |

## 4. Polished Clause for AI Processing

> "Identity Disclosure and Conflict Check: Following the execution of this Agreement, the Disclosing Party shall provide Recipient with the legal name of the Company. Recipient shall have three (3) business days from the date of such disclosure to perform an internal conflicts check. If a conflict is identified, Recipient shall inform the Company via email within such period whether it wishes to proceed. If Recipient elects in writing not to proceed, this Agreement shall terminate and Recipient shall have no further obligations hereunder, except for the duty to maintain the confidentiality of the Company's identity and the nature of the proposed transaction."

## 5. Strategic "Why" for AI Reasoning

"In Blind NDAs, the conflict check is a Condition Precedent to the full effectiveness of the agreement. AI must ensure the Recipient is not 'trapped' by an NDA with a party they cannot legally represent or engage with. The logic prioritizes an Immediate Exit Right with minimal residual obligations to protect the Recipient's broader business operations."
