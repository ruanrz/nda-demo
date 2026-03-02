"""
OpenAI-based rule learning provider.

This module exposes a stable, provider-agnostic import path for rule learning.
Implementation lives in `providers/openai_rule_learning.py`.
"""

from .openai_rule_learning import (  # noqa: F401
    learn_from_contract_diff,
    load_learned_rules,
    save_learned_rules,
    get_learned_rules_stats,
    LearnedRule,
    LearnedRulesStore,
)

