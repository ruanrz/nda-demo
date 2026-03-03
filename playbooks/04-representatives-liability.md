---
id: "representatives_liability"
title: Conduct of Representatives (Liability)
enabled: true
document_type: NDA
priority: P1
---

# Conduct of Representatives (Liability Isolation)

## 1. Rule Summary

**Trigger:** Any clause where the Recipient and their Representatives are grouped together as a single subject for an obligation (e.g., "Recipient and its Representatives shall [Action]").

## 2. Rationale: Agency and Control Logic

**The "Non-Contracting Party" Problem:** Representatives (especially external ones like banks or law firms) are typically not signatories to the NDA. A Recipient cannot legally "force" a non-signatory to act; they can only control their own internal actions and the instructions they provide to their agents.

**Avoidance of "Guaranty" Liability:** Grouping the Recipient and Representatives together implies the Recipient is guaranteeing the behavior of third parties. By using "direct to," the Recipient is only promising to perform their specific duty: providing clear instructions.

**Liability Isolation:** This framing helps protect the Recipient from a "Technical Breach" if a Representative acts out of alignment, provided the Recipient can prove they gave the proper "Direction" (the paper trail).

## 3. AI-Friendly Logic Schema

| Scenario | Original Phrase | AI Polished Action |
|----------|----------------|-------------------|
| Affirmative Covenants | "You and your Representatives shall..." | Change to: "You shall and shall direct your Representatives to..." |
| Negative Covenants | "You and your Representatives shall not..." | Change to: "You shall not and shall direct your Representatives not to..." |

| Logic Component | Structural Change | AI Rule |
|----------------|-------------------|---------|
| Subject Separation | Splits a joint subject (Recipient + Reps) into a Primary and Secondary subject. | SPLIT_SUBJECT(Recipient, Representatives) |
| Obligation Shift | Changes "Performance" to "Direction of Performance." | REPLACE(Joint_Performance, Recipient_Direction) |
| Standard of Care | Moves from Strict Liability to Conduct-Based. | SET_STANDARD(Covenant_to_Direct) |
