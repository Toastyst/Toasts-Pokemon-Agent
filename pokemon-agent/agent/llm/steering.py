"""
Steering input reader — reads viewer commands from the Twitch bridge's JSONL file.

The bridge writes steering inputs to ~/services/twitch-bridge/steering_inputs.jsonl.
This module reads new lines since the last consumed offset, sanitizes them,
and returns them as pending viewer commands for the agent to act on.

Prompt injection defense: all input is sanitized (blocked phrases + truncation)
and injected into the nav prompt as clearly delimited untrusted data.
"""

import os
import json
import time
from typing import List, Dict, Optional

STEERING_FILE = os.path.expanduser("~/services/twitch-bridge/steering_inputs.jsonl")
OFFSET_FILE = os.path.expanduser("~/.hermes/pokemon-agent/steering_offset.txt")

# Prompt injection patterns (mirrors bridge's sanitize_input)
BLOCKED_PATTERNS = [
    "ignore previous", "ignore all", "system prompt", "you are now",
    "forget your instructions", "jailbreak", "dan", "developer mode",
    "reveal your prompt", "show your instructions", "api key",
    "secret", "password", "token", "credential", "new instructions",
    "override", "disregard", "stop being", "pretend you",
    "you must now", "from now on", "forget that", "instead,",
    "do not follow", "break character", "ignore safety",
]

MAX_INPUT_LENGTH = 200


def sanitize(text: str) -> str:
    """Sanitize untrusted viewer input. Returns empty string if blocked."""
    if not text:
        return ""
    lower = text.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in lower:
            return ""
    # Truncate
    text = text[:MAX_INPUT_LENGTH].strip()
    return text


def _read_offset() -> int:
    """Read the last consumed line offset."""
    try:
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip() or "0")
    except (FileNotFoundError, ValueError):
        return 0


def _write_offset(offset: int) -> None:
    """Persist the consumed offset."""
    os.makedirs(os.path.dirname(OFFSET_FILE), exist_ok=True)
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))


def get_steering_inputs() -> List[Dict]:
    """
    Read new steering inputs since last call.
    Returns list of dicts: {username, message (sanitized), timestamp}
    Updates offset so these won't be returned again.
    """
    if not os.path.exists(STEERING_FILE):
        return []

    offset = _read_offset()

    # Read all lines
    try:
        with open(STEERING_FILE, "r") as f:
            lines = f.readlines()
    except Exception:
        return []

    total_lines = len(lines)
    new_lines = lines[offset:]

    if not new_lines:
        return []

    results = []
    for line in new_lines:
        line = line.strip()
        if not line:
            offset += 1
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            offset += 1
            continue

        message = sanitize(entry.get("message", ""))
        if not message:
            # Sanitization blocked it — skip but count as consumed
            offset += 1
            continue

        results.append({
            "username": entry.get("username", "viewer")[:30],
            "message": message,
            "timestamp": entry.get("timestamp", 0),
        })
        offset += 1

    _write_offset(offset)
    return results


def peek_steering_inputs() -> List[Dict]:
    """
    Same as get_steering_inputs() but does NOT advance the offset.
    Useful for previewing what's queued without consuming.
    """
    if not os.path.exists(STEERING_FILE):
        return []

    offset = _read_offset()

    try:
        with open(STEERING_FILE, "r") as f:
            lines = f.readlines()
    except Exception:
        return []

    new_lines = lines[offset:]
    results = []
    for line in new_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = sanitize(entry.get("message", ""))
        if not message:
            continue
        results.append({
            "username": entry.get("username", "viewer")[:30],
            "message": message,
            "timestamp": entry.get("timestamp", 0),
        })
    return results
