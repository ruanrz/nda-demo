---
id: "3"
title: Definition of Representatives — Checklist
type: checklist
enabled: true
document_type: NDA
---

# Definition of Representatives — Checklist

## Rule Summary

Ensure the "Representatives" definition includes **all required parties** and the **qualifier** about actually receiving Confidential Information.

> Definition of Representatives: affiliates and its and their respective directors, officers, employees, professional advisors, actual or potential debt or financing sources, consultants, agents (such parties actually receiving Confidential Information from Recipient or at its direction, collectively, "Representatives")

## Rules

### Rule: rule_representatives — Representatives Definition Check

- **Type:** checklist
- **Trigger:** When a Representatives definition clause exists in the document
- **Action:** Ensure definition includes all required representative types and qualifier
#### Required Elements

The definition **must** include all of the following:

- [ ] affiliates
- [ ] directors
- [ ] officers
- [ ] employees
- [ ] professional advisors
- [ ] actual or potential debt or financing sources
- [ ] consultants
- [ ] agents

#### Required Qualifier

> such parties actually receiving Confidential Information from Recipient or at its direction

#### Constraints

- If existing clause contains more party types, **do not delete** them
- Ensure each party type is listed
- Must include the qualifier about actually receiving Confidential Information
- The order of listed parties can be different
- `preserve_existing: true` — only add missing elements, never remove existing ones

#### Example

**Before:**
> "Representatives" means the Recipient's directors, officers and employees.

**After:**
> "Representatives" means the Recipient's affiliates and its and their respective directors, officers, employees, professional advisors, actual or potential debt or financing sources, consultants, agents (such parties actually receiving Confidential Information from Recipient or at its direction, collectively, "Representatives").
