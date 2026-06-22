#!/usr/bin/env python3
"""Start the Pokemon Agent server.

Usage:
    python scripts/serve.py --rom path/to/pokemon.gb [--port 8765] [--data-dir ~/.pokemon-agent]
    python scripts/serve.py --config config.yaml
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Pokemon Agent Server")
    parser.add_argument("--rom", help="Path to Pokemon ROM (.gb or .gba)")
    parser.add_argument("--port", type=int, default=8765, help="Server port (default 8765)")
    parser.add_argument("--data-dir", default="~/.pokemon-agent", help="Data directory")
    parser.add_argument("--game-type", default="auto", choices=["auto", "red", "firered"])
    parser.add_argument("--config", help="Path to config.yaml (overrides other flags)")
    parser.add_argument("--load-state", help="Save state to auto-load on startup")
    args = parser.parse_args()

    # Ensure project root is on path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    from pokemon_agent.server.app import configure, app, GameConfig

    data_dir = Path(args.data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "saves").mkdir(exist_ok=True)

    if args.rom:
        rom = Path(args.rom).expanduser().resolve()
        if not rom.exists():
            print(f"ERROR: ROM file not found: {rom}", file=sys.stderr)
            sys.exit(1)
        game_type = args.game_type
        if game_type == "auto":
            ext = rom.suffix.lower()
            game_type = "red" if ext in (".gb", ".gbc") else "firered" if ext == ".gba" else "unknown"
        configure(GameConfig(
            rom_path=str(rom),
            game_type=game_type,
            port=args.port,
            data_dir=str(data_dir),
            load_state=args.load_state,
        ))

    import uvicorn
    print(f"[serve] Starting server on port {args.port}")
    print(f"[serve] Dashboard: http://localhost:{args.port}/dashboard")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
