---
id: "representatives_definition"
title: Definition of Representatives
enabled: true
document_type: NDA
priority: P0
---

# Definition of "Representatives"

## 1. Rule Objective

Ensures the definition of "Representatives" is sufficiently broad to cover all necessary parties while maintaining a restrictive qualifier for liability management.

## 2. Scope Architecture (The "Entity" List)

This defines the Universal Set of who can be a Representative.

- **Internal Tier:** Recipient's affiliates and affiliated funds
- **Personnel Tier:** Officers, directors, employees, partners, and members
- **Advisory Tier:** Legal counsel, consultants, accountants, and financial advisors
- **Strategic Tier:** Insurers and potential financing sources
- **Recursive Tier:** The respective representatives of any of the above parties

## 3. The Qualifier (The "Activation Gate")

This is the Boolean Filter that determines if a party from the list above is legally a Representative under the NDA.

**Final Logic Rule:** Representative = True IF Step 1 AND Step 2 AND Step 3 are all TRUE.

| Logic Step | Variable | Condition |
|-----------|----------|-----------|
| Step 1 | Is_In_Scope | Is the party part of the "Scope Architecture" list above? |
| Step 2 | Information_Flow | Has the party actually received Confidential Information? |
| Step 3 | Directionality | Was the information sent by the Recipient or at its direction? |

The definition is strictly limited to individuals or entities listed above who **actually receive Confidential Information from the Recipient or at the Recipient's direction**.

## 4. Strategic Rationale (The "Why")

### A. Operational Autonomy Logic
- **Constraint:** Recipient cannot predict all necessary parties at the NDA stage.
- **Solution:** Broadly pre-authorize categories (e.g., insurers/financing) to eliminate the "Consent Request" bottleneck.
- Disclosing information to Representatives should not require prior consent from the Disclosing Party.
- **AI Tag:** `[Administrative_Efficiency] = High`

### B. Deal Uncertainty
- At the NDA stage, the Recipient lacks sufficient deal visibility to pre-identify every necessary stakeholder. A broad definition prevents future bottlenecks.

### C. Administrative Efficiency
- Including all potential parties upfront removes the administrative burden of seeking constant amendments or waivers as the deal team expands.

### D. Liability Mitigation Logic (The "Big Firm" Rule)
- **Constraint:** Large firms (e.g., EY, Goldman) have thousands of unrelated employees.
- **Solution:** Use the "Actual Receipt" filter to prevent the NDA from binding a global corporation's unrelated departments.
- **Goal:** Isolates liability to the specific Deal Team.
- **AI Tag:** `[Entity_Wide_Liability] = Mitigated`

### E. Qualifier Rationale
- **Liability Containment:** Prevents the Receiving Party from being held contractually liable for the actions of every employee or affiliate in their global organization.
- **Audit Trail Alignment:** Ensures that "Representatives" are defined by the actual flow of information, creating a verifiable nexus between the disclosure and the recipient.
- **Standard of Care:** Establishes that the Receiving Party is only responsible for the conduct of those it has affirmatively directed to receive the Confidential Information.
- **Burden of Proof:** Shifts the focus from a theoretical list of parties to a factual determination of who was actually "in the loop."

## 5. Drafting Pattern [CRITICAL]

The "Actual Receipt" qualifier **MUST** be embedded **INLINE** within the parenthetical that defines "Representatives". It must NOT be drafted as a separate standalone sentence.

**Correct pattern — qualifier INSIDE the parenthetical:**
> "...your affiliates and affiliated funds, and your and their respective officers, directors, employees, partners, members, legal counsel, consultants, accountants, financial advisors, insurers, potential financing sources, and other agents and representatives **(such parties who actually receive [Confidential Info Term] from [Recipient Term] or at [Recipient Term]'s direction, collectively, "Representatives")**"

**WRONG — qualifier as a separate sentence or relative clause:**
> ~~"...(collectively, "Representatives") who actually receive..."~~
> ~~"...(collectively, "Representatives"). Representatives means only those parties who actually receive..."~~

**AI Drafting Rule:**
1. Find the existing parenthetical `(collectively, "Representatives")` or equivalent.
2. Replace it with `(such parties who actually receive [Confidential Info Term] from [Recipient Term] or at [Recipient Term]'s direction, collectively, "Representatives")`.
3. Adapt `[Confidential Info Term]` and `[Recipient Term]` to the contract's own defined terms (e.g., "Evaluation Material", "you").
4. Do NOT add a separate sentence or relative clause for the qualifier.

## 6. Data Mapping for Document Generation

| Field | Value |
|-------|-------|
| Primary Term | Confidential Information (Standardize across doc) |
| Defined Class | Representatives |
| Recipient Symmetry | Asymmetric (Only Receiving Party has the "Actual Receipt" Qualifier) |
| Recursive Depth | Infinite ("...and their respective representatives") |
