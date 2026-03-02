"""
OpenAI rule learning module.

Canonical import path for rule learning APIs used by the demo app.
"""

from .openai_rule_learning_impl import (  # noqa: F401
    learn_from_contract_diff,
    load_learned_rules,
    save_learned_rules,
    get_learned_rules_stats,
    LearnedRule,
    LearnedRulesStore,
    get_openai_client,
    call_openai_api,
)

