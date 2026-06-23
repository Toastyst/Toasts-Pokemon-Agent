"""
LLM Client — Thin wrapper around OpenAI-compatible API.

Supports any provider with an OpenAI-compatible /v1/chat/completions endpoint.
Logs every call to /tmp/pokemon-llm-calls.jsonl for observability.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import requests

_LLM_LOG_PATH = Path("/tmp/pokemon-llm-calls.jsonl")


def _log_llm_call(
    agent_type: str,
    model: str,
    system_prompt: str,
    user_message: str,
    response: Optional[str],
    duration_ms: float,
    status_code: int = 0,
    error: str = "",
    token_usage: Optional[Dict[str, int]] = None,
) -> None:
    """Append one LLM call to the structured log file."""
    try:
        entry = {
            "ts": time.time(),
            "agent": agent_type,
            "model": model,
            "system_len": len(system_prompt),
            "user_len": len(user_message),
            "system_prompt": system_prompt,
            "user_message": user_message,
            "response": response,
            "duration_ms": round(duration_ms, 1),
            "status": status_code,
            "error": error,
            "tokens": token_usage,
        }
        with open(_LLM_LOG_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # never let logging break the agent


class LLMClient:
    def __init__(
        self,
        base_url: str = "http://192.168.1.179:1234/v1",
        api_key: str = "not-needed",
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: int = 120,
        vision_fallback_models: Optional[list[str]] = None,
        providers: Optional[Dict[str, Dict[str, str]]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.error_count = 0
        self.last_error = ""
        self.vision_fallback_models = vision_fallback_models or []
        # Provider registry: provider_name → {base_url, api_key}
        # Used by chat_vision to route local: prefixed models to the right server
        self._providers: Dict[str, Dict[str, str]] = providers or {}
        # Resolve which model to use for vision at init time
        self._vision_model = self._resolve_vision_model()
        # Optional streaming token callback — when set, chat() streams tokens
        self._token_callback = None
        self._streaming = False

    def set_token_callback(self, callback, streaming: bool = True):
        """Set a callback for streaming tokens. chat() will use streaming when set."""
        self._token_callback = callback
        self._streaming = streaming

    def clear_token_callback(self):
        """Clear the token callback, reverting chat() to non-streaming."""
        self._token_callback = None
        self._streaming = False

    def _resolve_vision_model(self) -> str:
        """
        Determine the best model for vision calls.

        If the primary model is on OpenRouter, query the models API to check
        input_modalities. If it doesn't support images, pick the first fallback
        that does. This avoids wasting an API call on every dialog step.

        For non-OpenRouter providers (e.g. local LM Studio), just use the
        primary model and rely on runtime fallback if it fails.
        """
        models_to_check = [self.model] + self.vision_fallback_models
        # Skip local: prefixed models during OpenRouter API lookup — they're
        # resolved at runtime via _get_vision_endpoint instead.
        def _is_local(m: str) -> bool:
            return ":" in m and not m.startswith("http") and m.split(":")[0] in self._providers

        or_models_to_check = [m for m in models_to_check if not _is_local(m)]
        # Only query OpenRouter API if we're using OpenRouter
        if "openrouter.ai" in self.base_url and self.api_key and self.api_key != "not-needed":
            try:
                resp = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=15,
                )
                if resp.status_code == 200:
                    model_data = {m["id"]: m for m in resp.json().get("data", [])}
                    for m in or_models_to_check:
                        # Look up model, trying with and without :free suffix
                        info = model_data.get(m) or model_data.get(m.replace(":free", ""))
                        if info:
                            arch = info.get("architecture", {})
                            input_mods = [str(x).lower() for x in arch.get("input_modalities", [])]
                            if "image" in input_mods:
                                if m != self.model:
                                    print(f"  [Vision] Primary model '{self.model}' doesn't support images. Using fallback: {m}")
                                return m
                    print(f"  [Vision] WARNING: No vision-capable model found among configured models")
            except Exception as e:
                print(f"  [Vision] Model capability check failed: {e}, will use runtime fallback")
        # Check if any local provider models are available — trust config
        for m in models_to_check:
            if _is_local(m):
                print(f"  [Vision] Using local model from config: {m}")
                return m
        # Default: use primary model (runtime fallback will handle failures)
        return self.model

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        agent_type: str = "nav",
    ) -> Optional[str]:
        """
        Send a chat completion request. Returns the response text.
        agent_type: label for the log ("nav", "guide", "critique", "battle").

        If set_token_callback() was called with streaming=True, this uses
        SSE streaming and calls the callback for each token chunk. The full
        response is still returned so callers need no changes.
        """
        if self._token_callback and self._streaming:
            return self._chat_streaming(
                system_prompt, user_message,
                token_callback=self._token_callback,
                temperature=temperature, max_tokens=max_tokens,
                agent_type=agent_type,
            )

        # --- non-streaming path (original) ---
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        t0 = time.time()
        response = None
        status_code = 0
        error = ""
        token_usage = None

        try:
            with requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            ) as resp:
                status_code = resp.status_code

                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if not choices:
                        error = "API returned empty choices list"
                        self.error_count += 1
                        self.last_error = error
                        print(f"[LLM] Error: {error}")
                        _log_llm_call(agent_type=agent_type, model=self.model,
                                       system_prompt=system_prompt, user_message=user_message,
                                       response=None, duration_ms=(time.time()-t0)*1000,
                                       status_code=status_code, error=error)
                        return None
                    msg = choices[0].get("message", {})
                    content = msg.get("content") or ""
                    content = content.strip()
                    # Some models (reasoning models) put output in reasoning_content
                    if not content:
                        content = (msg.get("reasoning_content") or "").strip()
                    response = content
                    usage = data.get("usage")
                    if usage:
                        token_usage = {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                        }
                else:
                    error = resp.text[:300]
                    print(f"[LLM] HTTP {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            error = str(e)
            print(f"[LLM] Error: {e}")

        duration_ms = (time.time() - t0) * 1000
        tok_str = ""
        if token_usage:
            tok_str = f" tokens={token_usage.get('total_tokens', '?')}"
        status_str = f"HTTP {status_code}" if status_code else "OK"
        print(f"  [LLM] {agent_type} | {self.model} | {status_str} | {duration_ms:.0f}ms{tok_str}")
        _log_llm_call(
            agent_type=agent_type,
            model=self.model,
            system_prompt=system_prompt,
            user_message=user_message,
            response=response,
            duration_ms=duration_ms,
            status_code=status_code,
            error=error,
            token_usage=token_usage,
        )
        return response

    def _chat_streaming(
        self,
        system_prompt: str,
        user_message: str,
        token_callback,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        agent_type: str = "nav",
    ) -> Optional[str]:
        """
        Streaming variant of chat(). Sends the request with stream: true and
        calls token_callback(chunk_text) for each content delta received.
        Returns the full reconstructed response text (same as chat()).

        token_callback receives individual content fragments (may be single
        chars or multi-char chunks depending on the provider). It should be
        fast / non-blocking — it is called from the read loop.

        Falls back silently to non-streaming chat() on any streaming setup error.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "stream": True,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "text/event-stream",
        }

        t0 = time.time()
        full_text = []
        status_code = 0
        error = ""
        token_usage = None

        try:
            with requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
                stream=True,
            ) as resp:
                status_code = resp.status_code

                if resp.status_code != 200:
                    error = resp.text[:300]
                    print(f"  [LLM] stream HTTP {resp.status_code}: {resp.text[:200]}, falling back to non-streaming")
                    return self.chat(system_prompt, user_message,
                                     temperature=temperature, max_tokens=max_tokens,
                                     agent_type=agent_type)

                for raw_line in resp.iter_lines():
                    if not raw_line:
                        continue
                    # SSE format: "data: {json}" or "data: [DONE]"
                    line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # Check for mid-stream errors
                        if "error" in chunk:
                            err_msg = chunk.get("error", {}).get("message", "unknown stream error")
                            print(f"  [LLM] stream error: {err_msg}")
                            error = err_msg
                            break

                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content_piece = delta.get("content")
                            if content_piece:
                                full_text.append(content_piece)
                                token_callback(content_piece)

                        # Final chunk may include usage
                        usage = chunk.get("usage")
                        if usage:
                            token_usage = {
                                "prompt_tokens": usage.get("prompt_tokens", 0),
                                "completion_tokens": usage.get("completion_tokens", 0),
                                "total_tokens": usage.get("total_tokens", 0),
                            }

        except Exception as e:
            error = str(e)
            print(f"  [LLM] stream exception: {e}, falling back")
            # Clear token callback to prevent infinite recursion
            saved_cb = self._token_callback
            self._token_callback = None
            self._streaming = False
            result = self.chat(system_prompt, user_message,
                             temperature=temperature, max_tokens=max_tokens,
                             agent_type=agent_type)
            self._token_callback = saved_cb
            self._streaming = True
            return result

        response = "".join(full_text).strip()
        duration_ms = (time.time() - t0) * 1000
        tok_str = ""
        if token_usage:
            tok_str = f" tokens={token_usage.get('total_tokens', '?')}"
        status_str = f"HTTP {status_code}" if status_code else "OK"
        print(f"  [LLM] {agent_type} | {self.model} | {status_str} | {duration_ms:.0f}ms{tok_str} (streamed)")
        _log_llm_call(
            agent_type=agent_type,
            model=self.model,
            system_prompt=system_prompt,
            user_message=user_message,
            response=response,
            duration_ms=duration_ms,
            status_code=status_code,
            error=error,
            token_usage=token_usage,
        )
        return response

    def _get_vision_endpoint(self, model_name: str) -> Tuple[str, str, str]:
        """
        Resolve the base_url, api_key, and actual model name for a vision model.

        If model_name has a "provider:" prefix (e.g. "local:smolvlm-500m-instruct"),
        look up that provider in self._providers and strip the prefix.
        Otherwise use the default (OpenRouter) base_url/api_key and keep the
        full model name as-is.

        Returns: (base_url, api_key, actual_model_name)
        """
        if ":" in model_name and not model_name.startswith("http"):
            prefix = model_name.split(":")[0]
            if prefix in self._providers:
                prov = self._providers[prefix]
                # Strip provider prefix for the API call
                actual_model = model_name.split(":", 1)[1]
                return prov["base_url"].rstrip("/"), prov.get("api_key", "not-needed"), actual_model
        return self.base_url, self.api_key, model_name

    def chat_vision(
        self,
        image_b64: str,
        text_prompt: str = "",
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """
        Send a screenshot to the model. Returns whatever the model says.
        No system prompt, no special instructions — just the image.

        Uses the vision model resolved at startup. If that model fails with
        an image-unsupported error, tries remaining fallback models.
        """
        content = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}]
        if text_prompt:
            content.append({"type": "text", "text": text_prompt})

        # Build ordered list: resolved vision model first, then remaining fallbacks
        models_to_try = [self._vision_model] + [m for m in self.vision_fallback_models if m != self._vision_model]
        last_error = ""

        for i, model_name in enumerate(models_to_try):
            # Resolve the correct endpoint and actual model name for this model
            endpoint_base, endpoint_key, actual_model = self._get_vision_endpoint(model_name)
            payload = {
                "model": actual_model,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": max_tokens,
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {endpoint_key}",
            }
            try:
                with requests.post(
                    f"{endpoint_base}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=300,
                ) as resp:
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            msg = choices[0].get("message", {})
                            # Some models (e.g. nemotron omni) put output in
                            # "reasoning" instead of "content". Try all known
                            # output fields in order of preference.
                            raw = msg.get("content")
                            if raw is None:
                                raw = msg.get("reasoning_content") or msg.get("reasoning")
                            result = (raw or "").strip()
                            if result:
                                return result
                            last_error = "empty content/reasoning"
                        last_error = "empty choices"
                    else:
                        err_text = resp.text[:500]
                        last_error = f"HTTP {resp.status_code}: {err_text[:200]}"
                        err_lower = err_text.lower()
                        image_unsupported = any(
                            phrase in err_lower
                            for phrase in [
                                "image", "vision", "multimodal", "unsupported",
                                "not supported", "does not support",
                                "invalid message content", "media type",
                                "no endpoints found",
                            ]
                        )
                        if image_unsupported and resp.status_code in (400, 404, 415, 422):
                            is_last = (i == len(models_to_try) - 1)
                            if not is_last:
                                print(f"  [Vision] {model_name} doesn't support images, trying next...")
                                continue
                        # Rate limit — try next model
                        if resp.status_code == 429:
                            is_last = (i == len(models_to_try) - 1)
                            if not is_last:
                                print(f"  [Vision] {model_name} rate-limited, trying next...")
                                continue
                        # Other HTTP error or last model — stop
                        print(f"  [Vision] {model_name} error: HTTP {resp.status_code}")
                        break
            except requests.Timeout:
                last_error = "timeout"
                if i < len(models_to_try) - 1:
                    print(f"  [Vision] {model_name} timeout, trying next...")
                    continue
                break
            except Exception as e:
                last_error = str(e)
                print(f"  [Vision] {model_name} exception: {e}")
                break

        print(f"  [Vision] All models failed. Last error: {last_error[:200]}")
        return None

    def chat_json(
        self,
        system_prompt: str,
        user_message: str,
        max_retries: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """
        Send a chat request and parse the response as JSON.
        Retries if parsing fails.
        """
        for attempt in range(max_retries):
            response = self.chat(
                system_prompt,
                user_message,
                temperature=0.1,
                max_tokens=self.max_tokens,
                agent_type="json",
            )
            if response is None:
                continue

            # Try to extract JSON from the response
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass

            # Try to find JSON in the response (may have markdown code blocks)
            text = response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            try:
                return json.loads(text.strip())
            except json.JSONDecodeError:
                print(f"[LLM] JSON parse failed (attempt {attempt + 1}): {response[:100]}")
                continue

        return None
