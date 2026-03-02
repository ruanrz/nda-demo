---
id: "4"
title: Compelled Disclosure
type: conditional
enabled: true
document_type: NDA
---

# Compelled Disclosure

## Rule Summary

Ensure that when the Receiving Party or its Representatives are **required by law** to disclose Confidential Information, they will **not be deemed to breach** confidential obligations. Must ensure both 'Recipient' and 'its Representatives' are covered.

## Rules

### Rule 6.1 — Minimum Required Terms for Compelled Disclosure

- **Type:** checklist
- **Trigger:** When a Compelled Disclosure or related clause exists in the document
- **Action:** Ensure minimum required terms are included for the compelled disclosure exception
- **Priority:** P0

#### Minimum Required Terms

| Element | Required wording |
|---------|-----------------|
| **Coverage** | Must cover both "Recipient" and "its Representatives" |
| **Legal basis** | "requested or required by law, regulation, order and legal process" |

#### Constraints

- These are the minimum terms that must be present
- If there are more terms, do not delete them

---

### Rule 6.2 — Notice Requirement Modifications

- **Type:** conditional
- **Trigger:** When counterparty requires Recipient to provide notice before compelled disclosure
- **Action:** Modify notice requirement clauses according to sub-rules below
- **Priority:** P0

#### Conditions to Check

| Condition | Description | Check |
|-----------|-------------|-------|
| `cond_6_2_1` | Coverage of Representatives | Whether clause covers both 'Recipient' AND 'its Representatives' or 'any of its Representatives' |
| `cond_6_2_2` | Notification requirement exists | Whether clause requires Recipient to notify Disclosing Party before disclosure |
| `cond_6_2_3` | Reasonable qualifier on notification | Whether notification has 'to the extent reasonably practicable and legally permissible' qualifier |
| `cond_6_2_4` | Notification timing language | Whether notification uses 'first' or 'prior' (problematic) vs 'promptly notify' (preferred) |
| `cond_6_2_5` | Assurance language | Whether clause uses 'ensure' or 'obtain assurance' (problematic) vs 'request' (preferred) |

#### Conditional Actions

1. **IF** `cond_6_2_1 = false` **THEN** add "or any of its Representatives" after "Recipient" to ensure both are covered

2. **IF** `cond_6_2_2 = true AND cond_6_2_3 = false` **THEN** add qualifier "to the extent reasonably practicable and legally permissible" before the notification requirement
   - **Rationale:** Ensures Recipient is not bound by absolute obligation to notify before disclosure

3. **IF** `cond_6_2_4 = 'first' OR 'prior'` **THEN** change to "promptly notify"
   - **Find:** "first notify", "prior written notice", "prior notice"
   - **Replace with:** "promptly notify"
   - **Rationale:** Avoid binding Recipient to provide notification *before* disclosing to authorities

4. **IF** `cond_6_2_5 = 'ensure' OR 'obtain assurance'` **THEN** change to "request"
   - **Find:** "ensure that", "obtain assurance that", "ensure the court"
   - **Replace with:** "request that", "request assurance that", "request the court"
   - **Rationale:** Recipient should only commit to *request* assurance of confidential treatment, not *guarantee* it

#### Example

**Before:**
> where the Recipient is ordered by a court of competent jurisdiction to do so; provided that the Recipient shall (i) first notify the Disclosing Party in writing before any disclosure under such order is made; and (ii) ensure that the court is made aware, prior to the disclosure, of the confidential nature of the Confidential Information

**After:**
> where the Recipient or any of its Representatives is requested or required by law, regulation, rule, legal process or ordered by a court of competent jurisdiction to do so; provided that the Recipient or such Representative shall, to the extent reasonably practicable and legally permissible (i) promptly notify the Disclosing Party in writing (email being sufficient) of any disclosure request or requirement; and (ii) request that the court is made aware, prior to the disclosure, of the confidential nature of the Confidential Information

---

### Rule 6.3 — Regulatory Examination Exception to Notification

- **Type:** conditional
- **Trigger:** When clause requires Recipient to provide notice to Company of compelled disclosure
- **Action:** Add exception for routine supervisory examinations by regulatory authorities
- **Priority:** P1

#### Conditions

| Condition | Check |
|-----------|-------|
| `cond_6_3_1` | Whether clause requires Recipient to notify Company/Disclosing Party before compelled disclosure |

#### Conditional Actions

- **IF** `cond_6_3_1 = true` **THEN** add the following exception clause:

> Notwithstanding the foregoing, Confidential Information may be disclosed, and no notice as referenced above is required to be provided, pursuant to requests for information in connection with routine supervisory examinations by regulatory authorities with the jurisdiction over you or your Representatives and not directed at the disclosing party or the Potential Transaction; provided that you or your Representatives, as applicable, inform any such authority of the confidential nature of the information disclosed to them and to keep such information confidential in accordance with such authority's policies and procedures.

- **IF** `cond_6_3_1 = false` **THEN** do NOT add this exception (it only applies when a notification requirement exists)

#### Constraints

- This exception should **only** be inserted when there is a notification requirement
- Exception must cover both 'you' (Recipient) and 'your Representatives'
- Exception applies only to 'routine supervisory examinations' not directed at the disclosing party or the Potential Transaction
