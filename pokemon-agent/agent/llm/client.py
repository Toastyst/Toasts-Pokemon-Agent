"""
LLM Client — Thin wrapper around OpenAI-compatible API.

Simple failover chain:
  1. Try primary model with primary key
  2. On 429 → rotate to next key (same model)
  3. On 400/invalid → try next model in fallback chain
  4. On daily limit → mark key exhausted, try next key
  5. If all fail → return None, caller decides retry delay

Vision uses the same chain but only with models that support images.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

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
        base_url: str = "https://openrouter.ai/api/v1",
        api_key: str = "",
        model: str = "google/gemma-4-31b-it:free",
        temperature: float = 0.7,
        max_tokens: int = 8192,
        timeout: int = 120,
        # --- Simple failover chain ---
        fallback_models: Optional[List[str]] = None,
        api_keys: Optional[List[str]] = None,
        # --- Vision ---
        vision_model: Optional[str] = None,
        vision_fallbacks: Optional[List[str]] = None,
        # --- Provider registry for local models ---
        providers: Optional[Dict[str, Dict[str, str]]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        # --- Keys: try in order, skip exhausted ones ---
        self._api_keys = api_keys or ([api_key] if api_key else [""])
        self._key_idx = 0  # which key to try first
        self._exhausted_keys: set = set()  # indices of keys that hit daily limit

        # --- Models: primary + fallbacks ---
        self._model_chain = [model] + (fallback_models or [])

        # --- Vision ---
        self._providers: Dict[str, Dict[str, str]] = providers or {}
        self._vision_model = vision_model or model
        self._vision_chain = [self._vision_model] + [
            m for m in (vision_fallbacks or []) if m != self._vision_model
        ]

        # --- Streaming ---
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

    # ------------------------------------------------------------------
    # Core: try model+key chain, return response or None
    # ------------------------------------------------------------------

    def _get_current_key(self) -> str:
        """Get the current non-exhausted key, or the last exhausted one if all are done."""
        for offset in range(len(self._api_keys)):
            idx = (self._key_idx + offset) % len(self._api_keys)
            if idx not in self._exhausted_keys:
                return self._api_keys[idx]
        # All exhausted — fall back to primary key (will get 429 but at least returns error)
        return self._api_keys[0]

    def _mark_key_exhausted(self, key: str) -> None:
        """Mark a key as daily-exhausted so we skip it."""
        try:
            idx = self._api_keys.index(key)
            self._exhausted_keys.add(idx)
            print(f"  [Key] Key #{idx+1} marked exhausted — skipping for rest of session")
        except ValueError:
            pass

    @staticmethod
    def _should_rotate_model(status_code: int, error_text: str) -> bool:
        """Check if we should try the next model."""
        if status_code == 400:
            return True  # Invalid model / bad request
        if status_code == 429:
            return True  # Rate limit — try next model
        if status_code in (502, 503, 504):
            return True  # Server error
        return False

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        agent_type: str = "nav",
    ) -> Optional[str]:
        """
        Send a chat completion request with model+key failover chain.
        Returns response text, or None if all models/keys failed.
        """
        temp = temperature if temperature is not None else self.temperature
        toks = max_tokens if max_tokens is not None else self.max_tokens

        # If streaming is enabled, use streaming path
        if self._token_callback and self._streaming:
            return self._chat_streaming(
                system_prompt, user_message,
                token_callback=self._token_callback,
                temperature=temp, max_tokens=toks,
                agent_type=agent_type,
            )

        # --- Non-streaming: try model chain ---
        last_error = ""
        t_start = time.time()

        for model_idx, model in enumerate(self._model_chain):
            # --- Try key chain for this model ---
            for key_offset in range(len(self._api_keys)):
                key_idx = (self._key_idx + key_offset) % len(self._api_keys)
                if key_idx in self._exhausted_keys:
                    continue
                key = self._api_keys[key_idx]

                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": temp,
                    "max_tokens": toks,
                    "stream": False,
                }
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                }

                t0 = time.time()
                status_code = 0
                error = ""
                token_usage = None
                content = ""
                try:
                    with requests.post(
                        f"{self.base_url}/chat/completions",
                        json=payload, headers=headers, timeout=self.timeout,
                    ) as resp:
                        status_code = resp.status_code

                        if status_code == 200:
                            data = resp.json()
                            choices = data.get("choices", [])
                            if choices:
                                msg = choices[0].get("message", {})
                                raw = msg.get("content") or ""
                                if not raw:
                                    raw = (msg.get("reasoning_content") or "").strip()
                                content = raw.strip()
                                if content:
                                    self._key_idx = key_idx  # stick with this key
                                    duration_ms = (time.time() - t0) * 1000
                                    usage = data.get("usage")
                                    if usage:
                                        token_usage = {
                                            "prompt_tokens": usage.get("prompt_tokens", 0),
                                            "completion_tokens": usage.get("completion_tokens", 0),
                                            "total_tokens": usage.get("total_tokens", 0),
                                        }
                                    tok_str = f" tokens={token_usage.get('total_tokens', '?')}" if token_usage else ""
                                    print(f"  [LLM] {agent_type} | {model} | HTTP 200 | {duration_ms:.0f}ms{tok_str}")
                                    _log_llm_call(agent_type=agent_type, model=model,
                                                   system_prompt=system_prompt, user_message=user_message,
                                                   response=content, duration_ms=duration_ms,
                                                   status_code=200, token_usage=token_usage)
                                    return content
                            else:
                                error = "API returned empty choices list"
                        else:
                            error = resp.text[:300]
                except requests.Timeout:
                    error = "request timeout"
                except Exception as e:
                    error = str(e)

                if content:
                    return content

                # --- Failure: decide what to do ---
                err_lower = error.lower()

                if status_code == 429:
                    if "daily" in err_lower or "per-day" in err_lower:
                        self._mark_key_exhausted(key)
                        continue
                    # Per-min limit — try next key for fresh window
                    print(f"  [LLM] {model} key #{key_idx+1} rate-limited (per-min), trying next key...")
                    continue

                if self._should_rotate_model(status_code, error):
                    print(f"  [LLM] {model} failed (HTTP {status_code}): {error[:80]} — trying next model...")
                    break  # break key loop, try next model

                # Other error — try next key
                print(f"  [LLM] {model} key #{key_idx+1} error: {error[:80]}")
                last_error = error

            # Check if all keys are exhausted for ALL keys
            if len(self._exhausted_keys) >= len(self._api_keys):
                # All keys exhausted — reset exhausted set for model rotation
                # (different models may have different limits)
                if model_idx < len(self._model_chain) - 1:
                    print(f"  [LLM] All keys exhausted for {model}, trying next model...")
                    self._exhausted_keys.clear()

        # All models and keys failed
        total_ms = (time.time() - t_start) * 1000
        print(f"  [LLM] All models/keys failed ({total_ms:.0f}ms). Last error: {last_error[:100]}")
        return None

    def _chat_streaming(
        self,
        system_prompt: str,
        user_message: str,
        token_callback,
        temperature: float,
        max_tokens: int,
        agent_type: str = "nav",
    ) -> Optional[str]:
        """
        Streaming variant. Tries model+key chain with streaming.
        Falls back to non-streaming if all attempts fail.
        """
        t_start = time.time()

        for model_idx, model in enumerate(self._model_chain):
            for key_offset in range(len(self._api_keys)):
                key_idx = (self._key_idx + key_offset) % len(self._api_keys)
                if key_idx in self._exhausted_keys:
                    continue
                key = self._api_keys[key_idx]

                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                }
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                    "Accept": "text/event-stream",
                }

                full_text = []
                t0 = time.time()
                try:
                    with requests.post(
                        f"{self.base_url}/chat/completions",
                        json=payload, headers=headers,
                        timeout=self.timeout, stream=True,
                    ) as resp:
                        status_code = resp.status_code

                        if status_code == 429:
                            error = resp.text[:300]
                            if "daily" in error.lower():
                                self._mark_key_exhausted(key)
                                continue
                            print(f"  [LLM] {model} key #{key_idx+1} stream rate-limited, trying next...")
                            continue

                        if status_code != 200:
                            error = resp.text[:300]
                            if self._should_rotate_model(status_code, error):
                                print(f"  [LLM] {model} stream failed (HTTP {status_code}): {error[:80]} — next model")
                                break
                            print(f"  [LLM] {model} key #{key_idx+1} stream error: {error[:80]}")
                            continue

                        # Success — stream tokens
                        for raw_line in resp.iter_lines():
                            if not raw_line:
                                continue
                            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str.strip() == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue
                                if "error" in chunk:
                                    err_msg = chunk.get("error", {}).get("message", "stream error")
                                    print(f"  [LLM] stream error: {err_msg}")
                                    break
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    piece = delta.get("content")
                                    if piece:
                                        full_text.append(piece)
                                        token_callback(piece)

                        response = "".join(full_text).strip()
                        duration_ms = (time.time() - t0) * 1000
                        self._key_idx = key_idx
                        tok_str = ""
                        print(f"  [LLM] {agent_type} | {model} | HTTP 200 | {duration_ms:.0f}ms{tok_str} (streamed)")
                        _log_llm_call(agent_type=agent_type, model=model,
                                       system_prompt=system_prompt, user_message=user_message,
                                       response=response, duration_ms=duration_ms,
                                       status_code=200)
                        return response

                except Exception as e:
                    print(f"  [LLM] {model} key #{key_idx+1} stream exception: {e}")

        # All failed — fall back to non-streaming as last resort
        print(f"  [LLM] Streaming failed on all models, falling back to non-streaming...")
        self._token_callback = None
        self._streaming = False
        return self.chat(system_prompt, user_message,
                         temperature=temperature, max_tokens=max_tokens,
                         agent_type=agent_type)

    # ------------------------------------------------------------------
    # Vision
    # ------------------------------------------------------------------

    def _resolve_vision_endpoint(self, model_name: str) -> Tuple[str, str, str]:
        """Resolve base_url, api_key, and actual model name for a vision model."""
        if ":" in model_name and not model_name.startswith("http"):
            prefix = model_name.split(":")[0]
            if prefix in self._providers:
                prov = self._providers[prefix]
                actual_model = model_name.split(":", 1)[1]
                return prov["base_url"].rstrip("/"), prov.get("api_key", "not-needed"), actual_model
        # Use primary endpoint with current non-exhausted key
        return self.base_url, self._get_current_key(), model_name

    def chat_vision(
        self,
        image_b64: str,
        text_prompt: str = "",
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """
        Send a screenshot to the vision model. Returns whatever the model says.
        Tries the vision chain in order, falls back on image-unsupported errors.
        Aborts immediately on 429 to avoid burning quota.
        """
        content = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}]
        if text_prompt:
            content.append({"type": "text", "text": text_prompt})

        last_error = ""

        for model_name in self._vision_chain:
            endpoint_base, endpoint_key, actual_model = self._resolve_vision_endpoint(model_name)
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
                    json=payload, headers=headers, timeout=300,
                ) as resp:
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            msg = choices[0].get("message", {})
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
                            ]
                        )
                        if image_unsupported and resp.status_code in (400, 404, 415, 422):
                            print(f"  [Vision] {model_name} doesn't support images, trying next...")
                            continue
                        if resp.status_code == 429:
                            print(f"  [Vision] {model_name} rate-limited, aborting vision")
                            return None
                        print(f"  [Vision] {model_name} error: HTTP {resp.status_code}")
            except requests.Timeout:
                last_error = "timeout"
                print(f"  [Vision] {model_name} timeout, trying next...")
                continue
            except Exception as e:
                last_error = str(e)
                print(f"  [Vision] {model_name} exception: {e}")
                break

        print(f"  [Vision] All models failed. Last error: {last_error[:200]}")
        return None

    # ------------------------------------------------------------------
    # JSON mode
    # ------------------------------------------------------------------

    def chat_json(
        self,
        system_prompt: str,
        user_message: str,
        max_retries: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """Send a chat request and parse the response as JSON."""
        for attempt in range(max_retries):
            response = self.chat(
                system_prompt, user_message,
                temperature=0.1, max_tokens=self.max_tokens,
                agent_type="json",
            )
            if response is None:
                continue
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass
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
