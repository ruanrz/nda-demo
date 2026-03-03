---
id: "ci_carveout"
title: "Confidential Information Carveout (Exclusions)"
enabled: true
document_type: NDA
priority: P1
---

# Confidential Information Carveout (Exclusions)

This rule set is the "Gold Standard" for protecting a Recipient from overbroad confidentiality claims. It focuses on Knowledge Qualifiers, Residuals, and ensuring that Representatives are shielded alongside the Recipient.

## 1. Rule Summary

**Trigger:** Any section titled "Exclusions," "Carve-outs," or "Inoperative as to..."

## 2. Rationale: Defensive Logic & Risk Mitigation

- **The "Knowledge" Qualifier (Recipient's Knowledge):** Without this, the Recipient is strictly liable if a third-party source breaches a secret contract with the Company that the Recipient had no way of knowing about. This shifts the standard from Strict Liability to Good Faith.
- **Residuals (Unaided Memory):** This protects the "human capital" of the Recipient's team. It acknowledges that employees cannot "brain-wipe" themselves after a deal. It prevents the Company from suing the Recipient just because a former deal team member uses a general technique or idea learned during the process.
- **Representative Coverage:** Since Representatives (banks, lawyers) are the ones actually handling the data, they must benefit from the same exclusions as the Recipient to avoid "back-door" liability.
- **"Is not Evaluation Material":** By defining excluded info as not being Evaluation Material in the first place, you ensure that other clauses (like Return/Destruction or Non-Use) never apply to that data.

## 3. AI-Friendly Logic Schema

| Logic Component | Requirement | AI Polished Action |
|----------------|-------------|-------------------|
| Symmetry Requirement | Ensure "Recipient AND Representatives" are covered in (ii), (iii), and (iv). | Append "or its Representatives" if missing. |
| The "Knowledge" Buffer | If a source must be "entitled to disclose," add a subjective knowledge filter. | Insert "to the Recipient's or its Representatives' knowledge". |
| The 5th Pillar | Standard NDAs often miss "Residuals." | Append the full Residual Information definition. |
| Exclusion Logic | Excluded info must not just be "permitted for use," it must be "not Confidential Information." | Change phrasing to: "and the information is not Evaluation Material/Confidential Information if..." |

| Exception Type | Logic Gate | Required Phrase / Condition |
|---------------|-----------|---------------------------|
| Public Domain | Source == Public | disclosure ... in breach hereof (Only add Reps if already present). |
| Prior Possession | Date < Disclosure_Date | Must include Recipient OR Representatives. |
| Third Party | Source != Company | Add: to Recipient's knowledge, [Source] is not prohibited. |
| Ind. Development | Process == No_Use | Must include without use of or reference to. |
| Residuals | Type == Memory | Include unaided memory + ordinary person definition. |

## 4. Polished Example for AI Processing

**Original Boilerplate (Typical):**
> "...if such information (i) is public, (ii) was known to you, or (iii) was received from a third party."

**Polished Version (AI-Optimized):**
> "...and the information is not Evaluation Material if such information: (i) is generally available to the public other than as a result of a disclosure by you [or your Representatives]*; (ii) was available to you or your Representatives on a non-confidential basis prior to disclosure by the Company; (iii) becomes available to you or your Representatives from a source other than the Company when such source, to your or your Representatives' knowledge, is not prohibited from disclosing such information; (iv) is independently developed by you or your Representatives without use of or reference to the Evaluation Material; or (v) is Residual Information [Insert full Residuals Definition]."

*Note: Only include Reps in (i) if the original text had them.

## 5. Strategic "Why" for AI Reasoning

"The goal is to ensure the 'Definition of Confidential Information' is not a trap. By adding the Knowledge Qualifier, we protect the Recipient from third-party bad actors. By adding Residuals, we protect the Recipient's internal talent from 'thought-policing' after the transaction ends. AI should verify that all five categories are present and that the 'Recipient and Representatives' symmetry is maintained throughout."
