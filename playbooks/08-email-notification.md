---
id: "email_notification"
title: "Email Notification Sufficiency"
enabled: true
document_type: NDA
priority: P2
---

# Email Notification Sufficiency

## 1. Rule Summary

Whenever the Agreement requires a party to "notify," provide "notice," obtain "consent," or "approval," append the parenthetical **(email being sufficient)** to the requirement. This applies to both the Recipient and the Disclosing Party.

## 2. The Exceptions (The "Negative" Rule)

Do **not** apply this rule to:
- **Assignment Clauses:** (e.g., "The Agreement may not be assigned without prior written consent").
- **Definitive Agreement References:** (e.g., "The parties will not be bound until a definitive agreement is executed").
- **Formal Notice Addresses:** The specific paragraph detailing where legal notices must be physically mailed.

## 3. Rationale: Operational Efficiency

Modern deal-making happens over email. This rule avoids a technical breach where a party provides "notice" (e.g., regarding a conflict check or a request for a data room extension) via email, but the contract technically requires a physical letter or "written notice" without clarifying that digital communication is valid. It ensures speed without legal ambiguity.

## 4. AI Logic Schema

| Logic Component | Requirement | AI Action |
|----------------|-------------|-----------|
| Primary Trigger | Keyword: notice, notify, consent, approval. | Append (email being sufficient). |
| Exclusion 1 | String contains Assign or Assignment. | SKIP ACTION. |
| Exclusion 2 | String contains Definitive Agreement. | SKIP ACTION. |
| Subjectivity | Apply to both parties? | YES (Mutual). |

## 5. Polished Examples for AI Processing

**Example A: Notice of Compelled Disclosure**
- Original: "...you will provide the Company with prompt written notice of such request(s)."
- Polished: "...you will provide the Company with prompt written notice (email being sufficient) of such request(s)."

**Example B: Request for Consent**
- Original: "...unless the Company provides its prior written consent."
- Polished: "...unless the Company provides its prior written consent (email being sufficient)."

**Example C: The Exception (Assignment)**
- Original: "Neither party may assign this agreement without the prior written consent of the other."
- Polished: (No change). AI Logic identifies "Assign" and skips.

## 6. Strategic "Why" for AI Reasoning

"The goal is to modernize the notice requirements to reflect current deal workflows. However, for fundamental structural changes (Assignment) or finality of the deal (Definitive Agreements), the AI must preserve the formality of traditional written notice to prevent accidental or unauthorized changes to the contract's core existence."
