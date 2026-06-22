"""
Config loader for providers and server settings.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    # Load .env file from the same directory as config
    env_path = path.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ[key] = value

    # Resolve env vars in config
    for provider in config.get("providers", {}).values():
        key = provider.get("api_key", "")
        if isinstance(key, str) and key.startswith("${") and key.endswith("}"):
            env_var = key[2:-1]
            resolved = os.getenv(env_var, "")
            provider["api_key"] = resolved
            if not resolved:
                print(f"[Config] WARNING: env var {env_var} is empty, provider may fail auth")

    return config


def get_provider_config(config: Dict[str, Any], name: str = None) -> Dict[str, Any]:
    providers = config.get("providers", {})
    if name is None:
        name = config.get("default_provider", "local")
    return providers[name]


def get_pokemon_agent_config(config: Dict[str, Any]) -> Dict[str, Any]:
    return config.get("pokemon_agent", {"base_url": "http://localhost:8765", "timeout": 30})