"""
Dashboard integration - Pushes objectives and events to the live dashboard.
"""

import requests
from typing import List, Dict, Any


def push_objectives(objectives: List[Dict[str, Any]], base_url: str = "http://localhost:8765", timeout: int = 10) -> bool:
    try:
        resp = requests.post(f"{base_url}/objectives", json={"objectives": objectives}, timeout=timeout)
        return resp.status_code == 200
    except Exception as e:
        print(f"[Dashboard] Objectives error: {e}")
        return False


def push_event(event_type: str, text: str, base_url: str = "http://localhost:8765", timeout: int = 10) -> bool:
    try:
        resp = requests.post(f"{base_url}/event", json={"type": event_type, "text": text}, timeout=timeout)
        return resp.status_code == 200
    except Exception as e:
        print(f"[Dashboard] Event error: {e}")
        return False


def push_token(token: str, agent_type: str = "", base_url: str = "http://localhost:8765") -> None:
    """Fire-and-forget a streaming token to the dashboard. Non-blocking, no retries."""
    try:
        requests.post(
            f"{base_url}/event",
            json={"type": "token", "text": token, "agent": agent_type},
            timeout=2,
        )
    except Exception:
        pass  # never let token streaming break the agent