---
id: "5"
title: Exception to Confidential Information
type: checklist_with_conditions
enabled: true
document_type: NDA
---

# Exception to Confidential Information

## Rule Summary

Ensure that some information, although fitting the definition of "Confidential Information", is **nonetheless not confidential information**. Must ensure both 'Recipient' and 'its Representatives' are covered in each exception.

## Rules

### Rule: General Requirements

- **Type:** checklist
- **Trigger:** When an exception to confidential information clause exists
- **Priority:** P0

#### General Constraints

- Can have more than five exceptions, but the following **must** be included
- Must ensure both 'Recipient' and 'its Representatives' are covered

#### Required Exceptions

- [ ] generally available to the public
- [ ] from a source other than the Company/Disclosing Party
- [ ] independently developed
- [ ] already in possession before disclosure
- [ ] approved for release by written authorization

---

### Rule: Exception One — Publicly Available Information

- **Type:** conditional
- **Trigger:** Check if 'generally available to the public' exception exists
- **Priority:** P1

#### Conditions

| Condition | Check |
|-----------|-------|
| `cond_public_1` | Whether clause contains 'generally available to the public' or equivalent (**required**) |
| `cond_public_2` | Whether clause contains restriction like 'other than as a result of disclosure by Receiving Party' |

#### Actions

- **IF** `cond_public_1 = false` **THEN** add "is or becomes generally available to the public"
- **IF** `cond_public_2 = true` **THEN** ensure wording matches: "a result of a disclosure by Receiving Party's or its Representatives in breach of this Agreement"
- **IF** `cond_public_2 = false` **THEN** do NOT proactively add the restriction (preserve original intent)

#### Example

**Before:** information that is publicly available

**After:** information that is or becomes generally available to the public [other than as a result of a disclosure by you or your Representatives in violation of this Agreement]

---

### Rule: Exception Two — Third Party Source

- **Type:** conditional
- **Trigger:** Check if third party source information exception exists
- **Priority:** P1

#### Conditions

| Condition | Check |
|-----------|-------|
| `cond_third_1` | Whether clause contains 'from a source other than the Company/Disclosing Party' (**required**) |
| `cond_third_2` | Whether clause contains restriction that third party did not breach confidentiality to Company |

#### Actions (if `cond_third_2 = true`)

Ensure the restriction satisfies **three conditions**:

1. **Recipient awareness:** "was not known by you or your Representatives" — must confirm Recipient or Representatives are aware
2. **Obligation to Company:** "obligations owed to the Company" — third party's obligation must be to Company
3. **Relates to disclosed information:** "with respect to such information" — obligation must relate to the specific information

#### Example

**Before:** information received from a third party

**After:** information that becomes available to you or your Representatives from a source other than the Company; provided that the source of such information was not known by you or your Representatives to have made the disclosure in violation of any confidentiality obligations owed to the Company with respect to such information

---

### Rule: Exception Three — Independently Developed

- **Type:** simplify
- **Trigger:** Check if independently developed information exception exists
- **Priority:** P1

#### Simplification Rule

If existing language has multiple restrictions like "without use of, reference to, based upon", simplify:

| Keep | Remove |
|------|--------|
| "without use of" | "based upon" |
| "without reference to" | "reliance on" |
| | "derived from" |

> Principle: **Fewer restrictions are better** for the Receiving Party.

#### Preferred Wording

> was or is independently developed by or for you or your Representatives without use of Confidential Information

---

### Rule: Remove unnecessary 'lawfully' modifier

- **Type:** replace
- **Trigger:** When exception clause contains 'lawfully in the possession', 'was lawfully', or 'lawfully received'
- **Priority:** P1

#### Find → Replace

| Find | Replace with |
|------|-------------|
| `lawfully in the possession` | `in the possession` |
| `was lawfully` | `was` |
| `lawfully received` | `received` |

#### Constraints

- Remove 'lawfully' modifier in exception clauses (a) and (d)
- Keep other parts of the sentence unchanged

#### Rationale

'lawful' is a legal judgment with vague standards. Keeping this word may make it difficult for the Recipient to invoke the exception clause.

---

### Rule: Replace 'no fault' with 'no disclosure'

- **Type:** replace
- **Trigger:** When public information exception contains 'through no fault of you' or 'no fault of'
- **Priority:** P1

#### Find → Replace

| Find | Replace with |
|------|-------------|
| `no fault of` | `no disclosure by` |

#### Constraints

- Replace in the public availability exception clause (c)
- Keep qualifiers like "in breach of this agreement" unchanged
- Ensure sentence grammar is correct after replacement

#### Rationale

'fault' is a subjective judgment standard that is difficult to prove. 'disclosure' is an objective fact standard that is easier to determine.

#### Example

**Before:** (c) becomes generally available to the public through no fault of you or any of your Representatives in breach of this agreement

**After:** (c) is or becomes generally available to the public through no disclosure by you or any of your Representatives in breach of this agreement
