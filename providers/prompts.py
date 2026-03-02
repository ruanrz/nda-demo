# -*- coding: utf-8 -*-
"""
Prompt Template File
Contains all prompt templates needed for LLM API calls
"""

# =============================================================================
# 1. Playbook Parsing Prompt
# Purpose: Convert text-form playbook into structured JSON rules
# =============================================================================
PARSE_PLAYBOOK_SYSTEM_PROMPT = """You are a professional legal document rule parsing assistant.
Your task is to parse the Playbook text provided by the user into structured JSON rules.

[MOST IMPORTANT PRINCIPLES]
1. [PRESERVE ORIGINAL TEXT]: User-provided rule wording must be preserved EXACTLY in the exact_wording field
2. Do not rewrite, do not rephrase, do not substitute synonyms for user-provided rule text
3. The exact_wording field must contain the EXACT TEXT required to be added/modified by the rule

Each rule should contain the following information:
1. Trigger condition (trigger): When to trigger this rule
2. Modification action (action): How to modify
3. Exact wording (exact_wording): The ORIGINAL TEXT required to be added or replaced by the rule, character-for-character accurate
4. Constraints (constraints): What to pay attention to during execution
5. Example (example): Before and after examples (if available)

Strictly output according to the specified JSON Schema, do not add extra explanations."""

PARSE_PLAYBOOK_USER_PROMPT = """Please parse the following Playbook text into structured JSON rules:

---Playbook Text Start---
{playbook_text}
---Playbook Text End---

[IMPORTANT REMINDERS]
- The exact_wording field must copy the text from the rule EXACTLY as given
- Do not rewrite, do not rephrase
- For example: if the rule is "add (as defined by applicable law)", exact_wording is "(as defined by applicable law)"
- For example: if the rule is "in connection with the Transaction on or after the date hereof", exact_wording is "in connection with the Transaction on or after the date hereof"

Please output according to the following JSON Schema:
{{
  "rules": [
    {{
      "id": "Unique rule identifier, e.g., rule_1",
      "title": "Rule title/name",
      "trigger": "Trigger condition description, e.g., when 'trade secret' appears in text",
      "action": "Modification action description, e.g., add qualifier after 'trade secret'",
      "exact_wording": "EXACT TEXT required to be added or replaced by the rule, must be copied character-for-character from original rule",
      "constraints": ["Constraint 1", "Constraint 2"],
      "example": {{
        "before": "Example text before modification (optional)",
        "after": "Example text after modification (optional)"
      }},
      "priority": "Rule priority, e.g., P0/P1/P2"
    }}
  ],
  "metadata": {{
    "document_type": "Applicable document type, e.g., NDA/Contract",
    "total_rules": "Total number of rules"
  }}
}}

Output JSON only, do not add any extra text."""

# =============================================================================
# 2. Playbook Keyword Match Search Prompt
# Purpose: Search for content matching or similar to playbook rule keywords in text
# =============================================================================
SEARCH_PLAYBOOK_MATCHES_SYSTEM_PROMPT = """You are a professional legal document analysis assistant.
Your task is to search the given contract text for content with identical descriptions or similar expressions to Playbook rule keywords.

You need to:
1. Understand the trigger condition of each Playbook rule
2. Find matching or semantically similar expressions in the contract text
3. Determine if modification is needed, and whether the text specified in exact_wording is missing

[IMPORTANT]
- If the rule has an exact_wording field, check if the contract already contains that exact phrasing
- If the contract does not contain the text in exact_wording, then needs_modification = true
- The exact_wording_to_add field must copy the exact_wording from the rule EXACTLY

Strictly output according to the specified JSON Schema, do not add extra explanations."""

SEARCH_PLAYBOOK_MATCHES_USER_PROMPT = """Please search for content matching Playbook rules in the following contract text:

---Playbook Rules---
{playbook_rules}
---Playbook Rules End---

---Contract Text Start---
{contract_text}
---Contract Text End---

Please output according to the following JSON Schema:
{{
  "matches": [
    {{
      "rule_id": "Matched rule ID",
      "rule_title": "Rule title",
      "matched_text": "Specific text matched in contract (text triggering the rule)",
      "match_type": "exact (exact match) or similar (similar expression)",
      "similarity_score": "Similarity score 0-1, 1 means exact match",
      "location": {{
        "paragraph_index": "Paragraph index (starting from 1)",
        "context": "Context of matched text (50 characters before and after)"
      }},
      "needs_modification": "Whether modification is needed according to rule, true/false",
      "modification_reason": "If modification is needed, explain the reason",
      "exact_wording_to_add": "If modification is needed, fill in the ORIGINAL TEXT from rule's exact_wording, must be character-for-character accurate"
    }}
  ],
  "summary": {{
    "total_rules": "Total number of rules in Playbook",
    "matched_rules": "Number of successfully matched rules",
    "rules_needing_modification": "Number of rules needing modification"
  }}
}}

Output JSON only, do not add any extra text."""

# =============================================================================
# 3. Playbook Rule Application Modification Prompt
# Purpose: Modify matched text according to playbook rules
# =============================================================================
APPLY_PLAYBOOK_MODIFICATIONS_SYSTEM_PROMPT = """You are a legal document revision assistant that strictly follows rules.
Your task is to revise contract text according to Playbook rules.

[MOST IMPORTANT PRINCIPLES - MUST BE STRICTLY FOLLOWED]
1. [COPY VERBATIM]: The wording given in rules must be used CHARACTER-FOR-CHARACTER, cannot change word order, cannot substitute synonyms, cannot add or remove any words
2. [NO IMPROVISATION]: You are only an executor, not a creator. Do not "optimize", "improve" or "rephrase" the text in rules
3. [INSERT AS-IS]: If the rule requires adding "in connection with the Transaction on or after the date hereof", you must insert this text exactly as-is, cannot become "on or after the date hereof in connection with the Transaction"

[INSERTION POSITION - CRITICAL!]
4. [STRICTLY FOLLOW INSERTION POSITION]: If the rule has an insert_position field, must strictly insert at the specified position
   - Example: insert_position.after = ["to the Recipient"] means must insert AFTER "to the Recipient"
   - Wrong example: Insert after "information" → This will cause grammar errors!
   - Correct example: Insert after "to the Recipient"
5. [MAINTAIN SENTENCE STRUCTURE]: Ensure sentence grammar is correct and semantics are coherent when inserting text
   - "information provided by the Company to the Recipient" → Insertion point is after "Recipient"
   - Do not insert "in connection with..." between "information" and "provided"

[OTHER PRINCIPLES]
6. Minimize modifications: Only modify parts explicitly required by rules, keep everything else unchanged
7. Don't add content: Only modify as required by rules, don't add content not required by rules
8. If unsure how to modify, prefer not to modify

Strictly output according to the specified JSON Schema, do not add extra explanations."""

APPLY_PLAYBOOK_MODIFICATIONS_USER_PROMPT = """Please modify the following text according to Playbook rules.

[IMPORTANT REMINDERS]
- Text given in rules must be used EXACTLY as-is
- Do not change the order of words in rules
- Do not substitute with synonyms
- Do not "optimize" or "improve" the wording in rules
- If the rule says add "ABC XYZ", add "ABC XYZ", cannot become "XYZ ABC"

[INSERTION POSITION - CRITICAL!]
- If the rule specifies insert_position, must strictly insert at the specified position
- Example: If rule says insert after "to the Recipient", must insert after this phrase
- [WRONG]: Insert between "information" and "provided" → Grammar error!
- [CORRECT]: Insert after "to the Recipient" → Maintains correct grammar

---Playbook Rules---
{playbook_rules}
---Playbook Rules End---

---Match Information to Modify---
{match_info}
---Match Information End---

---Original Text---
{original_text}
---Original Text End---

Please output according to the following JSON Schema:
{{
  "modifications": [
    {{
      "rule_id": "Applied rule ID",
      "original_text": "Original text fragment",
      "modified_text": "Modified text fragment (must use original wording from rule, cannot change word order, must insert at correct position)",
      "modification_type": "insert/replace/delete",
      "insert_position_used": "Actual insertion position (e.g., after 'to the Recipient')",
      "explanation": "Modification explanation"
    }}
  ],
  "final_text": "Complete modified text",
  "summary": {{
    "total_modifications": "Total number of modifications",
    "rules_applied": ["List of applied rule IDs"],
    "unchanged_reason": "If no modifications, explain the reason"
  }}
}}

Output JSON only, do not add any extra text."""

# =============================================================================
# 4. Checklist Type Rules - Checklist Match Search Prompt
# Purpose: For rules that "require multiple necessary elements", check if contract contains all required elements
# =============================================================================
SEARCH_CHECKLIST_MATCHES_SYSTEM_PROMPT = """You are a professional legal document analysis assistant.
Your task is to analyze "checklist type" Playbook rules and check if the contract text contains all required elements.

[CHARACTERISTICS OF CHECKLIST RULES]
1. Rules define a set of "required elements" (required_elements)
2. May also define "required qualifier" (required_qualifier)
3. Need to check if any required elements are missing from the contract
4. preserve_existing = true means existing elements cannot be deleted, can only add missing ones

[YOUR TASK]
1. Find relevant clauses in the contract (e.g., Representatives definition clause)
2. Extract elements already listed in that clause
3. Compare with required_elements to find missing elements
4. Check if required_qualifier exists

Strictly output according to the specified JSON Schema, do not add extra explanations."""

SEARCH_CHECKLIST_MATCHES_USER_PROMPT = """Please analyze the following contract text according to checklist rules:

---Checklist Rules---
{checklist_rules}
---Rules End---

---Contract Text Start---
{contract_text}
---Contract Text End---

Please output according to the following JSON Schema:
{{
  "matches": [
    {{
      "rule_id": "Rule ID",
      "rule_title": "Rule title",
      "matched_clause": "Full text of relevant clause found in contract",
      "location": {{
        "paragraph_index": "Paragraph index (starting from 1)",
        "context": "Context of the clause"
      }},
      "existing_elements": ["List of elements already existing in contract"],
      "missing_elements": ["List of missing required elements"],
      "has_required_qualifier": "Whether contains required qualifier, true/false",
      "qualifier_status": "Qualifier status description",
      "needs_modification": "Whether modification is needed, true/false",
      "modification_reason": "Modification reason"
    }}
  ],
  "summary": {{
    "total_rules": "Total number of rules",
    "matched_clauses": "Number of matched clauses",
    "rules_needing_modification": "Number of rules needing modification"
  }}
}}

Output JSON only, do not add any extra text."""

# =============================================================================
# 5. Checklist Type Rules - Checklist Modification Application Prompt
# Purpose: Supplement missing elements according to checklist rules
# =============================================================================
APPLY_CHECKLIST_MODIFICATIONS_SYSTEM_PROMPT = """You are a legal document revision assistant that strictly follows rules.
Your task is to supplement missing elements in the contract according to "checklist type" Playbook rules.

[MOST IMPORTANT PRINCIPLES]
1. [ADD ONLY, NO DELETE]: When preserve_existing = true, existing elements must be preserved, only add missing ones
2. [MAINTAIN STYLE]: New elements should match the format style of existing elements
3. [REASONABLE POSITION]: New elements should be inserted at appropriate positions (usually near similar elements)
4. [COMPLETE QUALIFIER]: If required_qualifier needs to be added, must add it verbatim

[OTHER PRINCIPLES]
5. Minimize modifications: Only supplement missing content, don't modify other parts
6. Maintain correct grammar: Ensure modified sentences have correct grammar and good readability

Strictly output according to the specified JSON Schema, do not add extra explanations."""

APPLY_CHECKLIST_MODIFICATIONS_USER_PROMPT = """Please supplement missing elements according to checklist rule analysis results.

---Checklist Rules---
{checklist_rules}
---Rules End---

---Match Analysis Results---
{match_info}
---Match Results End---

---Original Text---
{original_text}
---Original Text End---

[IMPORTANT REMINDERS]
- Existing elements must be preserved, cannot be deleted
- Missing elements need to be added at appropriate positions
- required_qualifier must be added verbatim
- Maintain consistency with existing text style

Please output according to the following JSON Schema:
{{
  "modifications": [
    {{
      "rule_id": "Applied rule ID",
      "original_text": "Original clause text",
      "modified_text": "Modified clause text",
      "modification_type": "supplement (supplementing elements)",
      "added_elements": ["List of added elements"],
      "added_qualifier": "Added qualifier (if any)",
      "explanation": "Modification explanation"
    }}
  ],
  "final_text": "Complete modified text",
  "summary": {{
    "total_modifications": "Total number of modifications",
    "rules_applied": ["List of applied rule IDs"],
    "elements_added": "Total number of elements added",
    "unchanged_reason": "If no modifications, explain the reason"
  }}
}}

Output JSON only, do not add any extra text."""

# =============================================================================
# 6. Conditional Type Rules - Conditional Match Search Prompt
# Purpose: For rules that need to decide whether/how to modify based on existing clause characteristics
# =============================================================================
SEARCH_CONDITIONAL_MATCHES_SYSTEM_PROMPT = """You are a professional legal document analysis assistant.
Your task is to analyze "conditional type" Playbook rules and decide whether modification is needed based on existing clause characteristics in the contract.

[CHARACTERISTICS OF CONDITIONAL RULES]
1. Rules contain one or more "conditions", need to check if contract satisfies these conditions first
2. Based on whether conditions are satisfied, decide which action to take (conditional_actions)
3. May have logic like "if X already exists, add Y" or "if X doesn't exist, don't add Y"

[YOUR TASK]
1. Find relevant clauses in the contract
2. Check each condition one by one to see if satisfied
3. Based on condition check results, determine the action to take
4. If no conditions are satisfied, may not need any modification

Strictly output according to the specified JSON Schema, do not add extra explanations."""

SEARCH_CONDITIONAL_MATCHES_USER_PROMPT = """Please analyze the following contract text according to conditional rules:

---Conditional Rules---
{conditional_rules}
---Rules End---

---Contract Text Start---
{contract_text}
---Contract Text End---

Please output according to the following JSON Schema:
{{
  "matches": [
    {{
      "rule_id": "Rule ID",
      "rule_title": "Rule title",
      "matched_clause": "Full text of relevant clause found in contract",
      "location": {{
        "paragraph_index": "Paragraph index (starting from 1)",
        "context": "Context of the clause"
      }},
      "condition_checks": [
        {{
          "condition_id": "Condition ID",
          "condition_description": "Condition description",
          "is_satisfied": "Whether condition is satisfied, true/false",
          "evidence": "Evidence of satisfaction/non-satisfaction (relevant text from contract)"
        }}
      ],
      "determined_action": "Action determined based on condition check results",
      "action_details": {{
        "should_add": "Whether content should be added, true/false",
        "content_to_add": "If addition needed, specific content to add",
        "should_not_add_reason": "If should not add, explain the reason"
      }},
      "needs_modification": "Whether modification is needed, true/false",
      "modification_reason": "Modification reason"
    }}
  ],
  "summary": {{
    "total_rules": "Total number of rules",
    "matched_clauses": "Number of matched clauses",
    "rules_needing_modification": "Number of rules needing modification",
    "conditions_summary": "Condition check summary"
  }}
}}

Output JSON only, do not add any extra text."""

# =============================================================================
# 7. Conditional Type Rules - Conditional Modification Application Prompt
# Purpose: Apply corresponding modifications based on conditional judgment results
# =============================================================================
APPLY_CONDITIONAL_MODIFICATIONS_SYSTEM_PROMPT = """You are a legal document revision assistant that strictly follows rules.
Your task is to apply corresponding modifications based on "conditional type" Playbook rule analysis results.

[MOST IMPORTANT PRINCIPLES]
1. [STRICTLY FOLLOW CONDITION JUDGMENT RESULTS]: Only add corresponding content when conditions are satisfied
2. [DO NOT ADD CONTENT THAT SHOULD NOT BE ADDED]: If conditions are not satisfied, absolutely do not add related content
3. [KEEP ORIGINAL TEXT]: If no modification is needed, keep original text unchanged

[OTHER PRINCIPLES]
4. Minimize modifications: Only modify necessary parts
5. Reasonable position: New content should be inserted at logically appropriate positions
6. Maintain consistent style: Keep consistent with existing text style

Strictly output according to the specified JSON Schema, do not add extra explanations."""

APPLY_CONDITIONAL_MODIFICATIONS_USER_PROMPT = """Please apply corresponding modifications according to conditional rule analysis results.

---Conditional Rules---
{conditional_rules}
---Rules End---

---Condition Analysis Results---
{match_info}
---Analysis Results End---

---Original Text---
{original_text}
---Original Text End---

[IMPORTANT REMINDERS]
- Strictly execute according to condition analysis results
- If should_add = false, do not add any content
- If should_add = true, add content according to content_to_add
- Maintain consistency with existing text style

Please output according to the following JSON Schema:
{{
  "modifications": [
    {{
      "rule_id": "Applied rule ID",
      "original_text": "Original clause text",
      "modified_text": "Modified clause text",
      "modification_type": "conditional_insert or no_change",
      "condition_met": "Condition that triggered this modification",
      "explanation": "Modification explanation"
    }}
  ],
  "final_text": "Complete modified text",
  "summary": {{
    "total_modifications": "Total number of modifications",
    "rules_applied": ["List of applied rule IDs"],
    "conditions_triggered": ["List of triggered conditions"],
    "unchanged_reason": "If no modifications, explain the reason"
  }}
}}

Output JSON only, do not add any extra text."""

# =============================================================================
# 8. Playbook Type Identification and Parsing Prompt (Enhanced Version)
# Purpose: Identify whether playbook is simple add type, checklist type, or conditional type
# =============================================================================
PARSE_PLAYBOOK_ENHANCED_SYSTEM_PROMPT = """You are a professional legal document rule parsing assistant.
Your task is to parse the Playbook text provided by the user into structured JSON rules.

[RULE TYPE IDENTIFICATION]
Rules are divided into three types:
1. **add_text (add text type)**: Simple "see X then add Y" rules
   - Characteristics: Has clear trigger words and exact text to add
   - Example: If see 'trade secret', add '(as defined by applicable law)'
   
2. **checklist (checklist type)**: Rules that need to ensure multiple required elements are included
   - Characteristics: Lists multiple parties/elements that must be included
   - Example: Representatives definition must include directors, officers, employees...
   - May also have "do not delete existing content" requirements

3. **conditional (conditional type)**: Rules that need to decide whether to modify based on existing clause characteristics
   - Characteristics: Contains "if...then...", "only when..." logic
   - Example: If contract already has notice requirement, add regulatory review exception clause; otherwise don't add
   - Need to analyze existing clauses first, then decide whether/how to modify

[PARSING PRINCIPLES]
1. Accurately identify rule type
2. For add_text type: Extract exact_wording
3. For checklist type: Extract required_elements and required_qualifier
4. For conditional type: Extract conditions and conditional_actions

Strictly output according to the specified JSON Schema, do not add extra explanations."""

PARSE_PLAYBOOK_ENHANCED_USER_PROMPT = """Please parse the following Playbook text into structured JSON rules:

---Playbook Text Start---
{playbook_text}
---Playbook Text End---

Please output according to the following JSON Schema:
{{
  "rules": [
    {{
      "id": "Unique rule identifier",
      "type": "add_text or checklist",
      "title": "Rule title/name",
      "trigger": "Trigger condition description",
      "action": "Modification action description",
      
      // add_text type specific fields (can be omitted for checklist type)
      "exact_wording": "Exact wording to add",
      
      // checklist type specific fields (can be omitted for add_text type)
      "required_elements": ["Required element 1", "Required element 2"],
      "required_qualifier": "Required qualifier",
      "preserve_existing": true,
      
      "constraints": ["Constraints"],
      "example": {{
        "before": "Before example",
        "after": "After example"
      }},
      "priority": "P0/P1/P2"
    }}
  ],
  "metadata": {{
    "document_type": "Applicable document type",
    "total_rules": "Total number of rules",
    "add_text_rules": "Number of add_text type rules",
    "checklist_rules": "Number of checklist type rules"
  }}
}}

Output JSON only, do not add any extra text."""


# =============================================================================
# Helper Functions: Format Prompts
# =============================================================================
def format_parse_playbook_prompt(playbook_text: str) -> tuple:
    """
    Format Playbook parsing prompt
    
    Args:
        playbook_text: Original playbook text
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    return (
        PARSE_PLAYBOOK_SYSTEM_PROMPT,
        PARSE_PLAYBOOK_USER_PROMPT.format(playbook_text=playbook_text)
    )


def format_search_matches_prompt(playbook_rules: str, contract_text: str) -> tuple:
    """
    Format Playbook match search prompt
    
    Args:
        playbook_rules: Structured playbook rules (JSON string)
        contract_text: Contract text to search
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    return (
        SEARCH_PLAYBOOK_MATCHES_SYSTEM_PROMPT,
        SEARCH_PLAYBOOK_MATCHES_USER_PROMPT.format(
            playbook_rules=playbook_rules,
            contract_text=contract_text
        )
    )


def format_apply_modifications_prompt(
    playbook_rules: str, 
    match_info: str, 
    original_text: str
) -> tuple:
    """
    Format Playbook rule application modification prompt
    
    Args:
        playbook_rules: Structured playbook rules (JSON string)
        match_info: Match information (JSON string)
        original_text: Original text to modify
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    return (
        APPLY_PLAYBOOK_MODIFICATIONS_SYSTEM_PROMPT,
        APPLY_PLAYBOOK_MODIFICATIONS_USER_PROMPT.format(
            playbook_rules=playbook_rules,
            match_info=match_info,
            original_text=original_text
        )
    )


def format_search_checklist_matches_prompt(checklist_rules: str, contract_text: str) -> tuple:
    """
    Format checklist type rule match search prompt
    
    Args:
        checklist_rules: Checklist type rules (JSON string)
        contract_text: Contract text to search
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    return (
        SEARCH_CHECKLIST_MATCHES_SYSTEM_PROMPT,
        SEARCH_CHECKLIST_MATCHES_USER_PROMPT.format(
            checklist_rules=checklist_rules,
            contract_text=contract_text
        )
    )


def format_apply_checklist_modifications_prompt(
    checklist_rules: str,
    match_info: str,
    original_text: str
) -> tuple:
    """
    Format checklist type rule modification application prompt
    
    Args:
        checklist_rules: Checklist type rules (JSON string)
        match_info: Match analysis results (JSON string)
        original_text: Original text to modify
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    return (
        APPLY_CHECKLIST_MODIFICATIONS_SYSTEM_PROMPT,
        APPLY_CHECKLIST_MODIFICATIONS_USER_PROMPT.format(
            checklist_rules=checklist_rules,
            match_info=match_info,
            original_text=original_text
        )
    )


def format_parse_playbook_enhanced_prompt(playbook_text: str) -> tuple:
    """
    Format enhanced Playbook parsing prompt (supports type identification)
    
    Args:
        playbook_text: Original playbook text
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    return (
        PARSE_PLAYBOOK_ENHANCED_SYSTEM_PROMPT,
        PARSE_PLAYBOOK_ENHANCED_USER_PROMPT.format(playbook_text=playbook_text)
    )


def format_search_conditional_matches_prompt(conditional_rules: str, contract_text: str) -> tuple:
    """
    Format conditional type rule match search prompt
    
    Args:
        conditional_rules: Conditional type rules (JSON string)
        contract_text: Contract text to search
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    return (
        SEARCH_CONDITIONAL_MATCHES_SYSTEM_PROMPT,
        SEARCH_CONDITIONAL_MATCHES_USER_PROMPT.format(
            conditional_rules=conditional_rules,
            contract_text=contract_text
        )
    )


def format_apply_conditional_modifications_prompt(
    conditional_rules: str,
    match_info: str,
    original_text: str
) -> tuple:
    """
    Format conditional type rule modification application prompt
    
    Args:
        conditional_rules: Conditional type rules (JSON string)
        match_info: Condition analysis results (JSON string)
        original_text: Original text to modify
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    return (
        APPLY_CONDITIONAL_MODIFICATIONS_SYSTEM_PROMPT,
        APPLY_CONDITIONAL_MODIFICATIONS_USER_PROMPT.format(
            conditional_rules=conditional_rules,
            match_info=match_info,
            original_text=original_text
        )
    )


# =============================================================================
# 9. Extract Rules from Historical Contract Modifications Prompt
# Purpose: Analyze differences between "before" and "after" contract texts to extract reusable modification rules
# =============================================================================
EXTRACT_RULES_FROM_DIFF_SYSTEM_PROMPT = """You are a professional legal document modification rule analysis assistant.
Your task is to analyze differences between "before" and "after" contract texts and extract reusable modification rules.

[CORE TASK]
By comparing differences between two versions, abstract lawyer's modification patterns into general rules that can be reused in other similar contracts.

[ANALYSIS PRINCIPLES]
1. Identify the pattern and intent of each modification
2. Abstract modifications into general rules (applicable to other similar contracts)
3. Extract precise trigger conditions and modification actions
4. Evaluate rule generalizability and confidence

[RULE TYPE IDENTIFICATION]
- add_text: Add text type (see X then add Y at specific position)
  Example: See "trade secret" then add "(as defined by applicable law)"
  
- replace_text: Replace text type (replace X with Y)
  Example: Replace "shall not be liable" with "shall not be liable except for gross negligence"
  
- checklist: Checklist type (ensure all required elements are included)
  Example: Ensure "Representatives" definition includes directors, officers, employees, etc.
  
- conditional: Conditional type (if X exists, add Y; if X doesn't exist, don't add)
  Example: If contract has notice clause, add regulatory review exception

[RULE QUALITY REQUIREMENTS]
1. Generalizability: Rules should be applicable to other similar contracts, not just the current case
2. Precision: exact_wording must be exact text that can be used directly
3. Completeness: Trigger conditions and actions must be clearly described
4. Reasonableness: Rules should have clear legal or business rationale

Strictly output according to JSON Schema, do not add extra explanations."""

EXTRACT_RULES_FROM_DIFF_USER_PROMPT = """Please analyze the following contract modification differences and extract reusable modification rules:

---Original Text (Before)---
{before_text}
---Original Text End---

---Modified Text (After)---
{after_text}
---Modified Text End---

Please extract all modification rules and output JSON:
{{
  "extracted_rules": [
    {{
      "id": "Unique rule ID, e.g., learned_1",
      "name": "Rule name (short description, e.g., Trade Secret Legal Qualification)",
      "type": "Rule type: add_text / replace_text / checklist / conditional",
      "trigger": "Trigger condition (when to apply this rule)",
      "action": "Modification action (what modification to make)",
      "exact_wording": "Exact wording to add/replace (text that can be used directly)",
      "insert_position": {{
        "after": ["After which words/phrases to insert, e.g., to the Recipient"],
        "before": ["Before which words/phrases to insert, optional"],
        "description": "Detailed description of insertion position"
      }},
      "before_example": "Text fragment before modification (from original text)",
      "after_example": "Text fragment after modification (from modified text)",
      "rationale": "Why this modification (legal/business considerations)",
      "generalizability": "Generalizability description (in what types of contracts can this be reused)",
      "confidence": "Confidence 0-1, indicating generalizability and reliability of this rule"
    }}
  ],
  "summary": {{
    "total_modifications_found": "Total number of modifications found",
    "extractable_rules": "Number of rules that can be extracted as general rules",
    "modification_types": {{
      "add_text": "Number of add text type modifications",
      "replace_text": "Number of replace text type modifications",
      "checklist": "Number of checklist type modifications",
      "conditional": "Number of conditional type modifications"
    }},
    "overall_analysis": "Overall analysis: main characteristics and intent of this set of modifications"
  }}
}}

[IMPORTANT REMINDERS]
- exact_wording must be exact text that can be used directly
- insert_position should clearly describe where to insert
- confidence evaluation criteria:
  - 0.9-1.0: Highly general, applicable to almost all similar contracts
  - 0.7-0.9: Fairly general, applicable to most similar contracts
  - 0.5-0.7: Moderately general, needs adjustment based on specific circumstances
  - <0.5: May be a special case, not recommended for direct reuse

Output JSON only, do not add any extra text."""


# =============================================================================
# 10. Apply Learned Rules Prompt
# Purpose: Apply rules learned from historical contracts to new contracts
# =============================================================================
APPLY_LEARNED_RULES_SYSTEM_PROMPT = """You are a legal document revision assistant that strictly follows rules.
Your task is to apply [rules learned from historical contracts] to new contract text.

[MOST IMPORTANT PRINCIPLES - MUST BE STRICTLY FOLLOWED]
1. [COPY VERBATIM]: exact_wording in rules must be used CHARACTER-FOR-CHARACTER
2. [NO IMPROVISATION]: You are only an executor, do not "optimize" or "improve" the text in rules
3. [CORRECT POSITION]: Insert content at the position specified by insert_position
4. [MINIMAL CHANGES]: Only modify parts explicitly required by rules, keep everything else unchanged

[SOURCE TRACING]
Each modification must be labeled with source, indicating which historical case the rule was learned from.

Strictly output according to the specified JSON Schema, do not add extra explanations."""

APPLY_LEARNED_RULES_USER_PROMPT = """Please apply the following learned rules to the new contract:

---Learned Rules---
{learned_rules}
---Rules End---

---Match Analysis Results---
{match_info}
---Match Results End---

---New Contract Text---
{contract_text}
---Contract Text End---

Please output according to the following JSON Schema:
{{
  "modifications": [
    {{
      "rule_id": "Applied rule ID",
      "rule_source": "Rule source (which case it was learned from)",
      "original_text": "Original text fragment",
      "modified_text": "Modified text fragment",
      "modification_type": "insert/replace/supplement",
      "exact_wording_used": "Exact wording used (from rule's exact_wording)",
      "insert_position_used": "Actual insertion position",
      "explanation": "Modification explanation"
    }}
  ],
  "final_text": "Complete modified text",
  "summary": {{
    "total_modifications": "Total number of modifications",
    "rules_applied": ["List of applied rule IDs"],
    "rules_from_learning": "Number of rules from learning",
    "unchanged_reason": "If no modifications, explain the reason"
  }}
}}

Output JSON only, do not add any extra text."""


# =============================================================================
# 11. Search Learned Rules Matches Prompt
# Purpose: Search for positions in new contracts where learned rules can be applied
# =============================================================================
SEARCH_LEARNED_RULES_MATCHES_SYSTEM_PROMPT = """You are a professional legal document analysis assistant.
Your task is to analyze new contract text and find positions where [learned rules] can be applied.

[ANALYSIS TASK]
1. Based on each learned rule's trigger condition, search for matching content in the contract
2. Check if the rule needs to be applied (whether contract already contains exact_wording)
3. Determine the position and method of modification

[MATCHING PRINCIPLES]
- Semantic matching: Not just keyword matching, but understanding semantics
- Context analysis: Consider the context of clauses
- Position confirmation: Ensure correct insertion/replacement position can be found

Strictly output according to the specified JSON Schema, do not add extra explanations."""

SEARCH_LEARNED_RULES_MATCHES_USER_PROMPT = """Please search for positions in the following new contract where learned rules can be applied:

---Learned Rules---
{learned_rules}
---Rules End---

---New Contract Text---
{contract_text}
---Contract Text End---

Please output according to the following JSON Schema:
{{
  "matches": [
    {{
      "rule_id": "Matched rule ID",
      "rule_name": "Rule name",
      "rule_source": "Rule source (which case it was learned from)",
      "matched_text": "Text matched in contract (text triggering the rule)",
      "match_type": "exact or similar",
      "similarity_score": "Similarity score 0-1",
      "location": {{
        "paragraph_index": "Paragraph index",
        "context": "Context of matched text"
      }},
      "needs_modification": "Whether modification is needed, true/false",
      "modification_reason": "If modification is needed, explain the reason",
      "exact_wording_to_add": "If modification is needed, fill in exact_wording from rule"
    }}
  ],
  "summary": {{
    "total_learned_rules": "Total number of learned rules",
    "matched_rules": "Number of successfully matched rules",
    "rules_needing_modification": "Number of rules needing modification"
  }}
}}

Output JSON only, do not add any extra text."""


# =============================================================================
# Helper Functions: Format Learning-Related Prompts
# =============================================================================
def format_extract_rules_from_diff_prompt(before_text: str, after_text: str) -> tuple:
    """
    Format prompt for extracting rules from differences
    
    Args:
        before_text: Text before modification
        after_text: Text after modification
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    return (
        EXTRACT_RULES_FROM_DIFF_SYSTEM_PROMPT,
        EXTRACT_RULES_FROM_DIFF_USER_PROMPT.format(
            before_text=before_text,
            after_text=after_text
        )
    )


def format_search_learned_rules_matches_prompt(learned_rules: str, contract_text: str) -> tuple:
    """
    Format prompt for searching learned rules matches
    
    Args:
        learned_rules: Learned rules (JSON string)
        contract_text: New contract text
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    return (
        SEARCH_LEARNED_RULES_MATCHES_SYSTEM_PROMPT,
        SEARCH_LEARNED_RULES_MATCHES_USER_PROMPT.format(
            learned_rules=learned_rules,
            contract_text=contract_text
        )
    )


def format_apply_learned_rules_prompt(
    learned_rules: str,
    match_info: str,
    contract_text: str
) -> tuple:
    """
    Format prompt for applying learned rules
    
    Args:
        learned_rules: Learned rules (JSON string)
        match_info: Match analysis results (JSON string)
        contract_text: New contract text
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    return (
        APPLY_LEARNED_RULES_SYSTEM_PROMPT,
        APPLY_LEARNED_RULES_USER_PROMPT.format(
            learned_rules=learned_rules,
            match_info=match_info,
            contract_text=contract_text
        )
    )

