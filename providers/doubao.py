# -*- coding: utf-8 -*-
"""
Legacy compatibility shim.

This module is kept to avoid breaking old imports. The canonical
implementation now lives in `providers/openai_rule_learning.py`.
"""

from .openai_rule_learning import *  # noqa: F401,F403

