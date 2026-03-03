---
id: "mandatory_language"
title: Investment Safe Harbors (Mandatory Language)
enabled: true
document_type: NDA
priority: P0
---

# Investment Safe Harbors (Mandatory Language)

These three rules are vital "Safe Harbor" provisions for investment firms and private equity funds. They prevent the NDA from accidentally paralyzing your firm's broader business activities or trapping you in "click-through" data room agreements.

## 1. Rule Summary

**Trigger:** These three specific acknowledgment clauses must exist in every NDA.

**Logic Condition:** Before adding, the AI must check if "similar language" already exists. If the concept is already covered, do not duplicate.

## 2. The Rules (Standardized Text)

### Rule A: Dual Representative Safe Harbor

"The Company acknowledges that certain directors, officers, and employees who serve on the board of directors (or similar governing body) of one or more of your affiliates or portfolio companies may also serve as a representative of you in another position or role (a "Dual Representative") and no such affiliates or portfolio companies will be deemed to have received such Evaluation Materials solely as a result of such dual role of any such Dual Representative, provided that such Dual Representative shall not have directly or indirectly disclosed any Evaluation Material to such affiliate or portfolio company."

### Rule B: Non-Restriction (Competition)

"The Company acknowledges that you are in the investment business and that you and your affiliates may now or in the future evaluate, invest in (directly or indirectly, including providing financing to) or do business with competitors or potential competitors of the Company, or entities engaged in business similar to or the same as the Company, and that neither the execution of this Agreement nor receipt of the Evaluation Material is intended to or shall restrict or preclude such activities."

### Rule C: Data Room Override

"This Agreement will not be modified or amended by the terms of use or confidentiality or non-disclosure provisions of any electronic data room acknowledged in order to access such electronic data room, and no such terms of use or confidentiality or non-disclosure provisions will be considered binding on you or your Representatives."

## 3. AI Logic Schema

| Acknowledgment | Key Concept | Purpose |
|---|---|---|
| I. Dual Representatives | Board members/Employees with roles at portfolio companies. | Prevents a portfolio company from being "tainted" or bound by the NDA just because a person has two jobs. |
| II. Non-Restriction | Right to invest in competitors. | Ensures the NDA is not a "Non-Compete." Protects the firm's right to evaluate other deals in the same industry. |
| III. Data Room Supremacy | "Click-wrap" vs. Signed NDA. | Ensures the signed NDA (which you've negotiated) overrides the generic, often aggressive terms of an online data room. |

| Logic Component | Action |
|---|---|
| Comparison Check | IF NOT (Text contains "Dual Representative" OR "board of directors of... affiliates") → ADD Rule A |
| Investment Freedom | IF NOT (Text contains "invest in... competitors" OR "restrict or preclude such activities") → ADD Rule B |
| Data Room Priority | IF NOT (Text contains "electronic data room" AND "modified or amended") → ADD Rule C |

## 4. Strategic "Why" for AI Reasoning

"These acknowledgments protect the Firm's Ecosystem. Without Rule A, a dual-hatted employee could accidentally bind an entire portfolio company to the NDA. Without Rule B, the NDA could be used as an injunction to stop the firm from buying a competitor. Without Rule C, the firm's carefully negotiated NDA could be wiped out by a junior associate clicking 'I Agree' to get into a virtual data room."
