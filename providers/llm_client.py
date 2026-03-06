# -*- coding: utf-8 -*-
"""
LLM Client with intelligent model routing — supports OpenAI and Google Gemini.

Presets available (selected via MODEL_PRESET env var or UI):
- "quality"       : o3 for analysis, gpt-4o for summary/validation (best accuracy)
- "cost"          : gpt-4o for analysis/execution, gpt-4o-mini for summary
- "gemini"        : Gemini 3.1 Pro via Google's OpenAI-compatible endpoint
- "gpt54"         : GPT-5.4 (2026-03-05) for all tasks via OpenAI API
"""

import os
import json
import logging
import re
import time
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any, List

from openai import OpenAI, RateLimitError, APIConnectionError, APITimeoutError, InternalServerError

logger = logging.getLogger("llm_client")

QUALITY_ROUTING = {
    "analysis":    "o3",
    "revision":    "gpt-4o",
    "insertion":   "gpt-4o",
    "execution":   "o3",
    "parsing":     "gpt-4o-mini",
    "summary":     "gpt-4o",
    "validation":  "gpt-4o",
}

COST_ROUTING = {
    "analysis":    "gpt-4o",
    "revision":    "gpt-4o",
    "insertion":   "gpt-4o",
    "execution":   "gpt-4o",
    "parsing":     "gpt-4o-mini",
    "summary":     "gpt-4o-mini",
    "validation":  "gpt-4o-mini",
}

GEMINI_ROUTING = {
    "analysis":    "gemini-3.1-pro-preview",
    "revision":    "gemini-3.1-pro-preview",
    "insertion":   "gemini-3.1-pro-preview",
    "execution":   "gemini-3.1-pro-preview",
    "parsing":     "gemini-3.1-pro-preview",
    "summary":     "gemini-3.1-pro-preview",
    "validation":  "gemini-3.1-pro-preview",
}

GPT54_ROUTING = {
    "analysis":    "gpt-5.4-2026-03-05",
    "revision":    "gpt-5.4-2026-03-05",
    "insertion":   "gpt-5.4-2026-03-05",
    "execution":   "gpt-5.4-2026-03-05",
    "parsing":     "gpt-5.4-2026-03-05",
    "summary":     "gpt-5.4-2026-03-05",
    "validation":  "gpt-5.4-2026-03-05",
}

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

PRESETS = {
    "quality": QUALITY_ROUTING,
    "cost": COST_ROUTING,
    "gemini": GEMINI_ROUTING,
    "gpt54": GPT54_ROUTING,
}

PROVIDER_LABELS = {
    "gemini": "Google Gemini 3.1 Pro Preview",
    "gpt54": "OpenAI GPT-5.4 (2026-03-05)",
}


def _default_routing() -> Dict[str, str]:
    preset = os.environ.get("MODEL_PRESET", "gemini").lower()
    return PRESETS.get(preset, GEMINI_ROUTING)


def _is_gemini_preset(preset: str) -> bool:
    return preset.lower().startswith("gemini")


def _extract_error_param(error_text: str) -> Optional[str]:
    """Best-effort extraction of the unsupported request parameter name."""
    patterns = [
        r"param['\"]?\s*:\s*['\"]([^'\"]+)['\"]",
        r"Unsupported parameter:\s*['\"]([^'\"]+)['\"]",
        r'Unknown name\s*["\']([^"\']+)["\']',
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
        "revision": "MODEL_REVISION",
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


def _print_llm_content(content: str, task_type: str):
    """Pretty-print LLM response content to the terminal."""
    try:
        parsed = json.loads(content)
        if task_type == "analysis":
            summary = parsed.get("summary", {})
            clause_analysis = parsed.get("clause_analysis", [])
            print(f"  [Analysis Summary] risk={summary.get('overall_risk','?')}  "
                  f"rules_checked={summary.get('total_rules_checked','?')}  "
                  f"compliant={summary.get('compliant',0)}  "
                  f"non_compliant={summary.get('non_compliant',0)}")
            for item in clause_analysis:
                status = item.get("compliance_status", "?")
                cid = item.get("clause_id", "?")
                sev = item.get("severity", "?")
                gaps = item.get("gaps", "")
                mark = "✅" if status == "compliant" else "❌"
                print(f"    {mark} {cid} [{sev}] {status}"
                      + (f" — {gaps}" if gaps else ""))
        elif task_type == "revision":
            revised = parsed.get("revised_clause", "")
            reasoning = parsed.get("reasoning", "")
            changes = parsed.get("changes_made", [])
            print(f"  [Revision] reasoning: {reasoning}")
            for ch in changes:
                print(f"    • {ch.get('what','')} — {ch.get('why','')}")
            if revised:
                preview = revised.replace('\n', '\n    ')
                print(f"  [Revised text]\n    {preview}")
        elif task_type == "summary":
            exec_sum = parsed.get("executive_summary", "")
            issues = parsed.get("issues", [])
            score = parsed.get("compliance_score", {})
            print(f"  [Executive Summary] {exec_sum}")
            print(f"  [Compliance Score] {score}")
            for iss in issues:
                sev = iss.get("severity", "?")
                title = iss.get("title", iss.get("description", "?"))
                print(f"    [{sev}] {title}")
        else:
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        print(content)


class LLMCallError(RuntimeError):
    """Raised when an LLM provider request fails with user-facing guidance."""

    def __init__(self, message: str, *, code: Optional[str] = None, details: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.details = details or ""


class LLMClient:
    """OpenAI-compatible LLM client with task-based model routing.

    Supports OpenAI and Google Gemini (via OpenAI-compatible endpoint).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_routing: Optional[Dict[str, str]] = None,
        preset: Optional[str] = None,
    ):
        self.preset_name = preset or os.environ.get("MODEL_PRESET", "gemini").lower()
        self._is_gemini = _is_gemini_preset(self.preset_name)

        if self._is_gemini:
            self.api_key = (
                api_key
                or os.environ.get("GOOGLE_API_KEY")
                or os.environ.get("GEMINI_API_KEY", "")
            )
            self.base_url = base_url or GEMINI_BASE_URL
        else:
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

        if not self.api_key:
            key_env = "GOOGLE_API_KEY" if self._is_gemini else "OPENAI_API_KEY"
            raise ValueError(
                f"API key not found for provider '{self.preset_name}'. "
                f"Set {key_env} environment variable or pass api_key."
            )

        kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self.client = OpenAI(**kwargs)
        self.call_log: List[Dict[str, Any]] = []
        self._doc_attach_warned = False
        self._native_sdk_warned = False

    def _resolve_model(self, task_type: str, model_override: Optional[str] = None) -> str:
        if model_override:
            return model_override
        fallback = self.routing.get("revision", "gpt-4o")
        model = self.routing.get(task_type, fallback)
        if task_type not in self.routing:
            logger.warning(
                "Unknown task_type '%s' — falling back to '%s'", task_type, model,
            )
        return model

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
        document_bytes: Optional[bytes] = None,
        document_name: str = "contract.docx",
        document_mime_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        model = self._resolve_model(task_type, model_override)
        logger.info(f"LLM call: task={task_type} model={model} temp={temperature} seed={seed}")

        start = datetime.now()
        native_files_requested = bool(document_bytes) or bool(file_attachments)
        if self._is_gemini and native_files_requested:
            native_result = self._call_gemini_native_with_files(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
                document_bytes=document_bytes,
                document_name=document_name,
                document_mime_type=document_mime_type,
                file_attachments=file_attachments or [],
            )
            if native_result is not None:
                content = native_result.get("content", "")
                duration = (datetime.now() - start).total_seconds()
                tokens = int(native_result.get("tokens", 0) or 0)
                prompt_tokens = int(native_result.get("prompt_tokens", 0) or 0)
                completion_tokens = int(native_result.get("completion_tokens", 0) or 0)
                used_model = native_result.get("model", model)

                logger.info(
                    f"LLM response (native Gemini): {duration:.1f}s  tokens={tokens} "
                    f"(prompt={prompt_tokens} completion={completion_tokens})  "
                    f"chars={len(content)}"
                )
                print(f"\n{'='*80}")
                print(
                    f"  LLM RESPONSE  |  task={task_type}  model={used_model}  "
                    f"duration={duration:.1f}s  tokens={tokens}"
                )
                print(f"{'='*80}")
                _print_llm_content(content, task_type)
                print(f"\n  [RAW FULL RESPONSE]")
                print(content)
                print(f"{'='*80}\n")

                self.call_log.append({
                    "task": task_type,
                    "model": used_model,
                    "duration": round(duration, 2),
                    "tokens": tokens,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "timestamp": start.isoformat(),
                })
                return content

            if not self._doc_attach_warned:
                logger.warning(
                    "Gemini native file flow unavailable; falling back to OpenAI-compatible "
                    "text-only prompt for this request."
                )
                self._doc_attach_warned = True

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        if seed is not None and not self._is_gemini:
            kwargs["seed"] = seed
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        if self._is_gemini and native_files_requested and not self._doc_attach_warned:
            logger.info(
                "Gemini OpenAI-compatible chat endpoint does not support input_file parts; "
                "using text-only prompt for this request."
            )
            self._doc_attach_warned = True

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

        # ── Print LLM output to terminal ─────────────────────────
        print(f"\n{'='*80}")
        print(f"  LLM RESPONSE  |  task={task_type}  model={model}  "
              f"duration={duration:.1f}s  tokens={tokens}")
        print(f"{'='*80}")
        _print_llm_content(content, task_type)
        print(f"\n  [RAW FULL RESPONSE]")
        print(content)
        print(f"{'='*80}\n")

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

    def is_gemini_provider(self) -> bool:
        return self._is_gemini

    def supports_document_input(self) -> bool:
        """
        Whether current provider/endpoint supports chat.completions document parts.

        Gemini's OpenAI-compatible endpoint currently rejects `input_file` parts
        with 400 INVALID_ARGUMENT, so we disable doc attachment for this route.
        """
        if self._is_gemini:
            return False
        return True

    def supports_native_file_upload(self) -> bool:
        return self._is_gemini

    def _map_native_gemini_model(self, model: str) -> str:
        """Map routing model name to native Gemini SDK model name.
        Pass through as-is; gemini-1.5-pro is deprecated (404 in v1beta).
        """
        override = os.environ.get("GEMINI_NATIVE_MODEL")
        if override:
            return override
        return model

    def _write_temp_attachment(self, content_bytes: bytes, file_name: str) -> str:
        _, ext = os.path.splitext(file_name or "")
        suffix = ext or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content_bytes)
            return tmp.name

    def _upload_and_wait_genai(
        self,
        genai_module,
        file_path: str,
        display_name: str,
        mime_type: Optional[str] = None,
    ):
        upload_kwargs: Dict[str, Any] = {
            "path": file_path,
            "display_name": display_name,
        }
        if mime_type:
            upload_kwargs["mime_type"] = mime_type
        file_obj = genai_module.upload_file(**upload_kwargs)
        state = getattr(file_obj, "state", None)
        while state is not None and getattr(state, "name", "") == "PROCESSING":
            time.sleep(2)
            file_obj = genai_module.get_file(file_obj.name)
            state = getattr(file_obj, "state", None)
        if state is not None and getattr(state, "name", "") == "FAILED":
            raise RuntimeError(f"Gemini file upload failed: {display_name}")
        return file_obj

    def _call_gemini_native_with_files(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        document_bytes: Optional[bytes],
        document_name: str,
        document_mime_type: str,
        file_attachments: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not self._is_gemini:
            return None

        upload_specs: List[Dict[str, Any]] = []
        if document_bytes:
            upload_specs.append({
                "display_name": "Target_Contract",
                "file_name": document_name or "contract.docx",
                "mime_type": document_mime_type,
                "content_bytes": document_bytes,
            })

        for idx, att in enumerate(file_attachments or [], 1):
            content_bytes = att.get("content_bytes")
            if content_bytes is None and att.get("text") is not None:
                content_bytes = str(att["text"]).encode("utf-8")
            if not content_bytes:
                continue
            upload_specs.append({
                "display_name": str(att.get("display_name", f"Attachment_{idx}")),
                "file_name": str(att.get("file_name", f"attachment_{idx}.txt")),
                "mime_type": str(att.get("mime_type", "text/plain")),
                "content_bytes": content_bytes,
            })

        if not upload_specs:
            return None

        # ── Strategy 1: google-generativeai SDK (File API) ────────
        genai = None
        try:
            import google.generativeai as genai  # type: ignore
        except Exception as exc:
            if not self._native_sdk_warned:
                logger.info(
                    "google-generativeai SDK not installed (%s); "
                    "using REST inline-data fallback for Gemini file upload",
                    exc,
                )
                self._native_sdk_warned = True

        if genai is not None:
            tmp_paths: List[str] = []
            uploaded_files: List[Any] = []
            try:
                genai.configure(api_key=self.api_key)
                for spec in upload_specs:
                    tmp_path = self._write_temp_attachment(spec["content_bytes"], spec["file_name"])
                    tmp_paths.append(tmp_path)
                    uploaded = self._upload_and_wait_genai(
                        genai_module=genai,
                        file_path=tmp_path,
                        display_name=spec["display_name"],
                        mime_type=spec.get("mime_type"),
                    )
                    uploaded_files.append(uploaded)

                native_model = self._map_native_gemini_model(model)
                model_client = genai.GenerativeModel(model_name=native_model)
                combined_prompt = (
                    "Follow the instructions strictly.\n\n"
                    "[SYSTEM INSTRUCTION]\n"
                    f"{system_prompt}\n\n"
                    "[USER INSTRUCTION]\n"
                    f"{user_prompt}\n"
                )
                generation_config: Dict[str, Any] = {
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }

                response = model_client.generate_content(
                    [combined_prompt] + uploaded_files,
                    generation_config=generation_config,
                )
                content = getattr(response, "text", "") or ""
                if not content:
                    parts: List[str] = []
                    for cand in getattr(response, "candidates", []) or []:
                        cand_content = getattr(cand, "content", None)
                        for part in getattr(cand_content, "parts", []) or []:
                            text = getattr(part, "text", "")
                            if text:
                                parts.append(text)
                    content = "\n".join(parts).strip()

                if json_mode and content:
                    content = content.strip()

                usage = getattr(response, "usage_metadata", None)
                prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
                completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
                total_tokens = int(
                    getattr(usage, "total_token_count", prompt_tokens + completion_tokens)
                    or (prompt_tokens + completion_tokens)
                )
                return {
                    "content": content,
                    "tokens": total_tokens,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "model": native_model,
                }
            except Exception as exc:
                logger.warning(
                    "Gemini SDK file call failed (%s); trying REST inline-data fallback",
                    exc,
                )
            finally:
                for file_obj in uploaded_files:
                    try:
                        genai.delete_file(file_obj.name)
                    except Exception:
                        pass
                for path in tmp_paths:
                    try:
                        os.unlink(path)
                    except Exception:
                        pass

        # ── Strategy 2: REST API with inline base64 data ──────────
        try:
            return self._call_gemini_rest_inline(
                model, system_prompt, user_prompt,
                temperature, max_tokens, json_mode, upload_specs,
            )
        except Exception as exc:
            logger.warning(
                "Gemini REST inline-data call also failed, falling back to text-only: %s", exc
            )
            return None

    def _call_gemini_rest_inline(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        upload_specs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Call Gemini generateContent REST API with inline base64 file data."""
        import base64
        import urllib.request
        import urllib.error

        native_model = self._map_native_gemini_model(model)
        logger.info("Gemini REST inline call: model=%s, %d file(s)", native_model, len(upload_specs))

        user_parts: List[Dict[str, Any]] = [{"text": user_prompt}]
        for spec in upload_specs:
            b64 = base64.b64encode(spec["content_bytes"]).decode("ascii")
            user_parts.append({
                "inlineData": {
                    "mimeType": spec.get("mime_type", "application/octet-stream"),
                    "data": b64,
                }
            })

        body: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": user_parts}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{native_model}"
            f":generateContent?key={self.api_key}"
        )
        req_data = json.dumps(body).encode("utf-8")
        http_req = urllib.request.Request(
            url, data=req_data,
            headers={"Content-Type": "application/json"},
        )
        try:
            http_resp = urllib.request.urlopen(http_req, timeout=300)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Gemini REST API returned {e.code}: {error_body[:500]}"
            ) from e

        result = json.loads(http_resp.read().decode("utf-8"))

        text_parts: List[str] = []
        for cand in result.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                t = part.get("text", "")
                if t:
                    text_parts.append(t)
        content = "\n".join(text_parts).strip()

        usage_meta = result.get("usageMetadata", {})
        prompt_tokens = int(usage_meta.get("promptTokenCount", 0))
        completion_tokens = int(usage_meta.get("candidatesTokenCount", 0))
        total = int(usage_meta.get("totalTokenCount", prompt_tokens + completion_tokens))

        return {
            "content": content,
            "tokens": total,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "model": native_model,
        }

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
        Handles:
        - Rate-limit (429) errors with exponential backoff
        - Parameter compatibility (max_tokens, temperature, seed, etc.)
        """
        current_kwargs = dict(kwargs)
        rate_limit_retries = 0
        max_rate_limit_retries = 5
        base_delay = 2.0

        for attempt in range(4):
            try:
                return self.client.chat.completions.create(**current_kwargs)
            except (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError) as exc:
                rate_limit_retries += 1
                if rate_limit_retries > max_rate_limit_retries:
                    raise self._to_user_error(exc, current_kwargs)
                delay = base_delay * (2 ** (rate_limit_retries - 1))
                logger.warning(
                    "Request failed (%s) on attempt %d — retrying in %.1fs (retry %d/%d)",
                    type(exc).__name__, attempt + 1, delay, rate_limit_retries, max_rate_limit_retries,
                )
                time.sleep(delay)
                attempt = max(attempt - 1, 0)  # don't consume a compat-retry slot
                continue
            except Exception as exc:
                if attempt == 3:
                    raise self._to_user_error(exc, current_kwargs)

                error_text = str(exc)
                error_text_lower = error_text.lower()
                bad_param = _extract_error_param(error_text)
                changed = False

                _unsupported = "unsupported" in error_text_lower or "unknown name" in error_text_lower

                if bad_param == "temperature" or (
                    "temperature" in error_text_lower and _unsupported
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
                    "seed" in error_text_lower and _unsupported
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
                    "max_tokens" in error_text_lower and _unsupported
                ):
                    if "max_tokens" in current_kwargs:
                        current_kwargs.pop("max_tokens", None)
                        current_kwargs["max_completion_tokens"] = max_tokens
                        changed = True

                elif bad_param == "max_completion_tokens" or (
                    "max_completion_tokens" in error_text_lower and _unsupported
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

        raise RuntimeError("Unexpected retry loop exit in _create_with_compat")

    def _to_user_error(self, exc: Exception, request_kwargs: Dict[str, Any]) -> LLMCallError:
        error_text = str(exc)
        error_lower = error_text.lower()
        error_code = _extract_error_code(error_text)
        model = request_kwargs.get("model", "unknown")
        endpoint = self.base_url or "https://api.openai.com/v1"
        provider = "Google Gemini" if self._is_gemini else "OpenAI"
        key_env = "GOOGLE_API_KEY" if self._is_gemini else "OPENAI_API_KEY"

        if "unsupported_country_region_territory" in error_lower:
            return LLMCallError(
                (
                    f"{provider} 请求被地区策略拒绝（unsupported_country_region_territory）。"
                    f" 当前 endpoint: {endpoint}，模型: {model}。"
                    " 请改用可访问的兼容网关，或在支持地区使用官方 API。"
                ),
                code="unsupported_country_region_territory",
                details=error_text,
            )

        if "invalid_api_key" in error_lower or "authentication" in error_lower:
            return LLMCallError(
                (
                    f"{provider} 鉴权失败（endpoint: {endpoint}, model: {model}）。"
                    f" 请检查 {key_env} 是否正确、是否已生效。"
                ),
                code=error_code,
                details=error_text,
            )

        if "insufficient_quota" in error_lower or "quota" in error_lower or "rate_limit" in error_lower or "429" in error_lower:
            return LLMCallError(
                (
                    f"{provider} 配额不足或请求频率超限（endpoint: {endpoint}, model: {model}）。"
                    " 请检查账号额度/账单状态，或稍后重试。"
                ),
                code=error_code,
                details=error_text,
            )

        if "connection error" in error_lower or "timeout" in error_lower or "connect" in error_lower:
            return LLMCallError(
                (
                    f"{provider} 连接失败（endpoint: {endpoint}, model: {model}）。"
                    " 请检查网络连接或代理设置（HTTPS_PROXY）。"
                ),
                code=error_code,
                details=error_text,
            )

        if "model_not_found" in error_lower or "does not exist" in error_lower:
            return LLMCallError(
                (
                    f"模型不可用（endpoint: {endpoint}, model: {model}）。"
                    f" 请检查模型名称是否正确，或通过 OPENAI_MODEL 等环境变量指定该 endpoint 支持的模型。"
                ),
                code=error_code,
                details=error_text,
            )

        return LLMCallError(
            f"LLM 调用失败（{provider}, endpoint: {endpoint}, model: {model}）: {error_text}",
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
_client_preset: Optional[str] = None


def get_llm_client(**kwargs) -> LLMClient:
    global _client, _client_preset
    requested_preset = kwargs.get("preset") or os.environ.get("MODEL_PRESET", "gemini")
    if _client is None or _client_preset != requested_preset:
        _client = LLMClient(**kwargs)
        _client_preset = requested_preset
    return _client


def reset_llm_client():
    global _client, _client_preset
    _client = None
    _client_preset = None
