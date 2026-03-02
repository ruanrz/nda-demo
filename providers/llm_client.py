# -*- coding: utf-8 -*-
"""
OpenAI LLM Client with intelligent model routing.

Two presets available (selected via MODEL_PRESET env var):
- "quality"  : o3 for analysis, gpt-4o for summary/validation (best accuracy)
- "cost"     : gpt-4o for analysis/execution, gpt-4o-mini for summary (default)
"""

import os
import json
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from openai import OpenAI

logger = logging.getLogger("llm_client")

QUALITY_ROUTING = {
    "analysis":    "o3",
    "execution":   "o3",
    "parsing":     "gpt-4o-mini",
    "summary":     "gpt-4o",
    "validation":  "gpt-4o",
}

COST_ROUTING = {
    "analysis":    "gpt-4o",
    "execution":   "gpt-4o",
    "parsing":     "gpt-4o-mini",
    "summary":     "gpt-4o-mini",
    "validation":  "gpt-4o-mini",
}

PRESETS = {"quality": QUALITY_ROUTING, "cost": COST_ROUTING}


def _default_routing() -> Dict[str, str]:
    preset = os.environ.get("MODEL_PRESET", "cost").lower()
    return PRESETS.get(preset, COST_ROUTING)


def _extract_error_param(error_text: str) -> Optional[str]:
    """Best-effort extraction of the unsupported request parameter name."""
    patterns = [
        r"param['\"]?\s*:\s*['\"]([^'\"]+)['\"]",
        r"Unsupported parameter:\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, error_text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_error_code(error_text: str) -> Optional[str]:
    """Best-effort extraction of provider error code."""
    patterns = [
        r"['\"]code['\"]\s*:\s*['\"]([^'\"]+)['\"]",
        r"Error code:\s*([A-Za-z0-9_\-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, error_text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _apply_env_model_overrides(routing: Dict[str, str]) -> Dict[str, str]:
    """Allow endpoint-specific model routing without code changes."""
    resolved = dict(routing)

    global_model = os.environ.get("OPENAI_MODEL")
    if global_model:
        for task in list(resolved.keys()):
            resolved[task] = global_model

    env_map = {
        "analysis": "MODEL_ANALYSIS",
        "execution": "MODEL_EXECUTION",
        "parsing": "MODEL_PARSING",
        "summary": "MODEL_SUMMARY",
        "validation": "MODEL_VALIDATION",
    }
    for task, env_key in env_map.items():
        model_name = os.environ.get(env_key)
        if model_name:
            resolved[task] = model_name
    return resolved


class LLMCallError(RuntimeError):
    """Raised when an LLM provider request fails with user-facing guidance."""

    def __init__(self, message: str, *, code: Optional[str] = None, details: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.details = details or ""


class LLMClient:
    """OpenAI-compatible LLM client with task-based model routing."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_routing: Optional[Dict[str, str]] = None,
        preset: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = (
            base_url
            or os.environ.get("OPENAI_API_BASE")
            or os.environ.get("OPENAI_BASE_URL")
        )
        if model_routing:
            self.routing = model_routing
        elif preset:
            self.routing = PRESETS.get(preset, _default_routing())
        else:
            self.routing = _default_routing()
        self.routing = _apply_env_model_overrides(self.routing)
        self.preset_name = preset or os.environ.get("MODEL_PRESET", "cost").lower()

        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. "
                "Set OPENAI_API_KEY environment variable or pass api_key."
            )

        kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self.client = OpenAI(**kwargs)
        self.call_log: List[Dict[str, Any]] = []

    def _resolve_model(self, task_type: str, model_override: Optional[str] = None) -> str:
        if model_override:
            return model_override
        return self.routing.get(task_type, "gpt-4o")

    def call(
        self,
        task_type: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        json_mode: bool = True,
        model_override: Optional[str] = None,
        seed: Optional[int] = 42,
    ) -> str:
        model = self._resolve_model(task_type, model_override)
        logger.info(f"LLM call: task={task_type} model={model} temp={temperature} seed={seed}")

        start = datetime.now()
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        if seed is not None:
            kwargs["seed"] = seed
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self._create_with_compat(kwargs, max_tokens=max_tokens)
        content = response.choices[0].message.content or ""
        duration = (datetime.now() - start).total_seconds()

        usage = response.usage
        tokens = usage.total_tokens if usage else 0
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        logger.info(
            f"LLM response: {duration:.1f}s  tokens={tokens} "
            f"(prompt={prompt_tokens} completion={completion_tokens})  "
            f"chars={len(content)}"
        )

        self.call_log.append({
            "task": task_type,
            "model": model,
            "duration": round(duration, 2),
            "tokens": tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "timestamp": start.isoformat(),
        })
        return content

    def call_json(
        self, task_type: str, system_prompt: str, user_prompt: str, **kwargs
    ) -> Dict[str, Any]:
        kwargs.setdefault("json_mode", True)
        raw = self.call(task_type, system_prompt, user_prompt, **kwargs)
        return _safe_json_parse(raw)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_calls": len(self.call_log),
            "total_duration": round(sum(c["duration"] for c in self.call_log), 1),
            "total_tokens": sum(c["tokens"] for c in self.call_log),
            "calls": list(self.call_log),
        }

    def reset_stats(self):
        self.call_log.clear()

    def _create_with_compat(self, kwargs: Dict[str, Any], max_tokens: int):
        """
        Send chat completion request with compatibility retries across model families.
        Handles common migration issues such as:
        - max_tokens vs max_completion_tokens
        - temperature unsupported by reasoning models
        """
        current_kwargs = dict(kwargs)

        for attempt in range(4):
            try:
                return self.client.chat.completions.create(**current_kwargs)
            except Exception as exc:
                if attempt == 3:
                    raise self._to_user_error(exc, current_kwargs)

                error_text = str(exc)
                error_text_lower = error_text.lower()
                bad_param = _extract_error_param(error_text)
                changed = False

                if bad_param == "temperature" or (
                    "temperature" in error_text_lower and "unsupported" in error_text_lower
                ):
                    if "temperature" in current_kwargs:
                        current_kwargs.pop("temperature", None)
                        changed = True
                        logger.warning(
                            "Model %s does not support 'temperature' — removed from request. "
                            "The model will use its internal default, which may reduce output determinism.",
                            current_kwargs.get("model", "unknown"),
                        )

                elif bad_param == "seed" or (
                    "seed" in error_text_lower and "unsupported" in error_text_lower
                ):
                    if "seed" in current_kwargs:
                        current_kwargs.pop("seed", None)
                        changed = True
                        logger.warning(
                            "Model %s does not support 'seed' — removed from request. "
                            "Output determinism cannot be guaranteed.",
                            current_kwargs.get("model", "unknown"),
                        )

                elif bad_param == "max_tokens" or (
                    "max_tokens" in error_text_lower and "unsupported" in error_text_lower
                ):
                    if "max_tokens" in current_kwargs:
                        current_kwargs.pop("max_tokens", None)
                        current_kwargs["max_completion_tokens"] = max_tokens
                        changed = True

                elif bad_param == "max_completion_tokens" or (
                    "max_completion_tokens" in error_text_lower and "unsupported" in error_text_lower
                ):
                    if "max_completion_tokens" in current_kwargs:
                        current_kwargs.pop("max_completion_tokens", None)
                        current_kwargs["max_tokens"] = max_tokens
                        changed = True

                elif bad_param == "response_format" and "response_format" in current_kwargs:
                    current_kwargs.pop("response_format", None)
                    changed = True

                if not changed:
                    raise self._to_user_error(exc, current_kwargs)

                logger.warning(
                    "Retrying LLM call after removing/switching unsupported param: %s",
                    bad_param or "unknown",
                )

        # Defensive fallback, loop should always return/raise.
        raise RuntimeError("Unexpected retry loop exit in _create_with_compat")

    def _to_user_error(self, exc: Exception, request_kwargs: Dict[str, Any]) -> LLMCallError:
        error_text = str(exc)
        error_lower = error_text.lower()
        error_code = _extract_error_code(error_text)
        model = request_kwargs.get("model", "unknown")
        endpoint = self.base_url or "https://api.openai.com/v1"

        if "unsupported_country_region_territory" in error_lower:
            return LLMCallError(
                (
                    "OpenAI 请求被地区策略拒绝（unsupported_country_region_territory）。"
                    f" 当前 endpoint: {endpoint}，模型: {model}。"
                    " 请改用可访问的 OpenAI 兼容网关，并设置 OPENAI_API_BASE（或 OPENAI_BASE_URL）"
                    " 和可用模型；或在支持地区使用官方 OpenAI API。"
                ),
                code="unsupported_country_region_territory",
                details=error_text,
            )

        if "invalid_api_key" in error_lower or "authentication" in error_lower:
            return LLMCallError(
                (
                    f"OpenAI 鉴权失败（endpoint: {endpoint}, model: {model}）。"
                    " 请检查 OPENAI_API_KEY 是否正确、是否已生效。"
                ),
                code=error_code,
                details=error_text,
            )

        if "insufficient_quota" in error_lower or "quota" in error_lower:
            return LLMCallError(
                (
                    f"OpenAI 配额不足或账单受限（endpoint: {endpoint}, model: {model}）。"
                    " 请检查账号额度/账单状态。"
                ),
                code=error_code,
                details=error_text,
            )

        if "model_not_found" in error_lower or "does not exist" in error_lower:
            return LLMCallError(
                (
                    f"模型不可用（endpoint: {endpoint}, model: {model}）。"
                    " 请切换 MODEL_PRESET（cost/quality），或通过 OPENAI_MODEL / MODEL_ANALYSIS 等环境变量指定该 endpoint 支持的模型。"
                ),
                code=error_code,
                details=error_text,
            )

        return LLMCallError(
            f"LLM 调用失败（endpoint: {endpoint}, model: {model}）: {error_text}",
            code=error_code,
            details=error_text,
        )


def _safe_json_parse(content: str) -> Dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        logger.error(f"JSON parse failed: {content[:300]}...")
        return {}


_client: Optional[LLMClient] = None


def get_llm_client(**kwargs) -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient(**kwargs)
    return _client


def reset_llm_client():
    global _client
    _client = None
