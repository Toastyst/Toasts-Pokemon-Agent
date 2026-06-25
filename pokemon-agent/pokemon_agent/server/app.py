"""
Pokemon Agent — FastAPI Game Server

Provides HTTP + WebSocket API for controlling a Game Boy / GBA emulator
running a Pokemon ROM, reading game state, and broadcasting events.
"""

import asyncio
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
from functools import partial
from pathlib import Path
from typing import Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GameConfig(BaseModel):
    """Server configuration — set before startup."""
    rom_path: str
    game_type: str = "auto"       # "red", "firered", or "auto"
    port: int = 8765
    data_dir: str = "~/.pokemon-agent"
    load_state: Optional[str] = None  # Save-state name to auto-load on startup
    cgb: bool = False                # Force Game Boy Color mode
    cgb_palette: Optional[list] = None  # CGB color palette (12 hex colors → 3×4)


class ActionRequest(BaseModel):
    """Body for POST /action."""
    actions: list[str]


class EventRequest(BaseModel):
    """Body for POST /event — the agent pushes narration to the dashboard."""
    type: str                       # "reasoning" | "decision" | "key_moment" | "alert" | "token"
    text: Optional[str] = None      # for reasoning / decision / alert / token
    description: Optional[str] = None  # for key_moment
    category: Optional[str] = None     # key_moment category: milestone/badge/catch/alert
    agent: Optional[str] = None        # for token: which agent (guide/nav/critique/battle/dialog)


class SaveRequest(BaseModel):
    """Body for POST /save and POST /load."""
    name: str


class Objective(BaseModel):
    """A single objective shown on the dashboard."""
    tier: str            # "primary" | "secondary" | "tertiary"
    text: str
    done: bool = False


class ObjectivesRequest(BaseModel):
    """Body for POST /objectives — replace the full objective list."""
    objectives: list[Objective]


class ControlRequest(BaseModel):
    """Body for POST /control — set the agent run state."""
    state: str           # "running" | "paused" | "stopped"


class NewGameRequest(BaseModel):
    """Body for POST /games/new."""
    name: Optional[str] = None


class AgentConfigRequest(BaseModel):
    """Body for POST /agent/config — switch the agent's LLM provider/model."""
    provider: str           # "local" | "local_4b" | "openrouter"
    model: Optional[str] = None  # optional override model name


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_config: Optional[GameConfig] = None
_emulator = None          # Emulator instance
_reader = None            # GameMemoryReader subclass instance
_start_time: float = 0.0
_loop: Optional[asyncio.AbstractEventLoop] = None

# Dynamic objectives shown on the dashboard (default = Kanto opening goals).
_objectives: list = [
    {"tier": "primary", "text": "Deliver Oak's Parcel · get Pokédex", "done": False},
    {"tier": "secondary", "text": "Reach Pewter City · Boulder Badge", "done": False},
    {"tier": "tertiary", "text": "Catch a Grass/Electric type", "done": False},
]

# Agent run state. "stopped" (default) | "running" | "paused".
# A standalone `pokemon-agent play` loop reads this and only acts when running.
_control_state: str = "stopped"

# Game-session layer (binds emulator saves + objectives/stats).
_session_mgr = None       # GameSessionManager
_active_session = None     # GameSession currently being played

# WebSocket clients
_ws_clients: Set[WebSocket] = set()

# Replay buffer — recent narration/milestone events so a client that connects
# mid-run sees the Field Log already populated instead of an empty panel.
# Only display-worthy events are kept (reasoning/decision/key_moment/alert/
# action), not the high-frequency screenshot/state_update frames.
from collections import deque
_event_history: deque = deque(maxlen=200)
_REPLAYABLE = {"reasoning", "decision", "thought", "key_moment", "moment", "alert", "battle", "action"}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Pokemon Agent Server",
    version=__version__,
    description="HTTP + WebSocket API for Pokemon emulator control",
)

# CORS — allow everything for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_game_type(rom_path: str) -> str:
    """Pick reader type based on file extension."""
    ext = Path(rom_path).suffix.lower()
    if ext in (".gb", ".gbc"):
        return "red"
    elif ext == ".gba":
        return "firered"
    raise ValueError(f"Unrecognised ROM extension: {ext}")


def _ensure_emulator():
    """Raise 503 if the emulator isn't ready."""
    if _emulator is None:
        raise HTTPException(status_code=503, detail="Emulator not initialised")


async def _run_sync(func, *args):
    """Run a blocking emulator call in the default executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args))


async def broadcast(event: dict):
    """Send a JSON event to every connected WebSocket client.

    Display-worthy events (narration, milestones, actions) are also recorded
    in a replay buffer so a client connecting mid-run can backfill the log.
    """
    etype = event.get("type")
    if etype in _REPLAYABLE:
        rec = dict(event)
        rec.setdefault("ts", time.time())
        if etype == "action":
            # Don't store the full state snapshot in the buffer — just the moves.
            rec.pop("state_after", None)
        _event_history.append(rec)

    dead: list[WebSocket] = []
    payload = json.dumps(event)
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


def _get_state_dict() -> dict:
    """Build full game state from the memory reader."""
    from pokemon_agent.server.state import build_game_state
    state = build_game_state(_reader)
    # Attach the on-screen walkability grid for Red/Blue (overworld tilesets).
    # This is ground-truth collision read from RAM — far more reliable than
    # inferring walkability from pixels.
    try:
        if _config and _config.game_type == "red" and not (
            state.get("battle") or {}
        ).get("in_battle"):
            from pokemon_agent.server.collision import (
                build_collision_grid,
                build_special_tiles,
                render_ascii_map,
            )
            col = build_collision_grid(_reader.emu)
            # Read warp entries and sprite data for special tile detection
            warps = _reader.read_warps() if _reader else None
            sprites = _reader.read_sprites() if _reader else []
            special = build_special_tiles(_reader.emu, col, warps=warps)
            # Read player position for absolute coord labels
            px = _reader.emu.read_u8(0xD362)  # wXCoord
            py = _reader.emu.read_u8(0xD361)  # wYCoord
            col["ascii"] = render_ascii_map(
                col, special=special, legend=True,
                player_pos={"x": px, "y": py},
                sprites=sprites,
            )
            col["special"] = special
            state["collision"] = col
            state["warps"] = warps or []
    except Exception as exc:  # noqa: BLE001
        state["collision_error"] = f"{type(exc).__name__}: {exc}"
    return state


def _get_screenshot_bytes() -> bytes:
    """Grab the current frame as PNG bytes."""
    screen = _emulator.get_screen()          # PIL Image or numpy array
    buf = io.BytesIO()
    # If it's a numpy array, convert to PIL first
    try:
        from PIL import Image
        if not isinstance(screen, Image.Image):
            import numpy as np
            screen = Image.fromarray(screen)
        screen.save(buf, format="PNG")
    except ImportError:
        # Fallback: assume screen already has save()
        screen.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Action parser
# ---------------------------------------------------------------------------

_ACTION_RE = re.compile(
    r"^(?P<kind>press|walk|hold|wait|a_until_dialog_end)(?:_(?P<rest>.+))?$"
)


async def _execute_action(action_str: str) -> None:
    """Parse and execute a single action string on the emulator.

    Supported formats:
        press_X       — press button X for 8 frames, wait 240 frames (dialog-safe)
        walk_X        — press direction for 16 frames, wait 8 frames
        hold_X_N      — hold button X for N frames
        wait_N        — tick N frames with no input
        a_until_dialog_end — press A every 30 frames until dialog clears (max 300)
    """
    action_str = action_str.strip().lower()

    if action_str == "a_until_dialog_end":
        for _ in range(10):  # max 300 frames = 10 * 30
            await _run_sync(_emulator.press, "a")
            await _run_sync(_emulator.tick, 30)
            # Check dialog flag via reader if available
            try:
                state = _get_state_dict()
                if not state.get("dialog_active", False):
                    break
            except Exception:
                pass
        return

    # Split into tokens
    parts = action_str.split("_")

    if parts[0] == "press" and len(parts) >= 2:
        button = "_".join(parts[1:])
        # Hold button for 8 frames so the game registers the press,
        # then wait 240 frames for dialog/text to fully process.
        # Gen 1 dialog is slow — 240 frames (~4 seconds) ensures the
        # game has finished printing text and is ready for next input.
        await _run_sync(_emulator.press, button, 8)
        await _run_sync(_emulator.tick, 240)
        return

    if parts[0] == "walk" and len(parts) >= 2:
        direction = parts[1]
        # Gen 1 movement timing:
        #   - Button held 8 frames for reliable joypad registration.
        #   - Walk animation = ~16 frames (8 counter * 2px/frame = 16px = 1 tile).
        #   - tick 60 after release allows ~100 total frames which is enough for:
        #     * single tile walk to complete
        #     * stair/door warp to fire and screen transition to begin
        #     * state_after to reflect the post-warp position
        #   - This matches the behavior of manual controller press_ which uses
        #     hold=8 + tick=240 but is more aggressive (60 vs 240).
        await _run_sync(_emulator.press, direction, 8)
        await _run_sync(_emulator.tick, 60)
        return

    if parts[0] == "hold" and len(parts) >= 3:
        button = "_".join(parts[1:-1])
        frames = int(parts[-1])
        await _run_sync(_emulator.press, button, frames)
        return

    if parts[0] == "wait" and len(parts) == 2:
        frames = int(parts[1])
        await _run_sync(_emulator.tick, frames)
        return

    raise ValueError(f"Unknown action format: {action_str}")


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

def configure(config: GameConfig):
    """Set server configuration (call before app startup)."""
    global _config
    _config = config


@app.on_event("startup")
async def _startup():
    global _emulator, _reader, _start_time, _config, _loop
    _loop = asyncio.get_running_loop()
    _start_time = time.time()

    # Try mounting dashboard (do this regardless of config so UI is always available)
    try:
        import pokemon_agent.dashboard as dashboard_mod  # noqa: F401
        from fastapi.staticfiles import StaticFiles
        dash_dir = Path(dashboard_mod.__file__).parent / "static"
        if dash_dir.is_dir():
            app.mount("/dashboard", StaticFiles(directory=str(dash_dir), html=True), name="dashboard")
            print(f"[server] Dashboard mounted at /dashboard")

            @app.get("/dashboard", include_in_schema=False)
            async def dashboard_redirect():
                from fastapi.responses import RedirectResponse
                return RedirectResponse(url="/dashboard/")
        else:
            print("[server] Dashboard module found but no static/ directory")
    except ImportError:
        print("[server] Dashboard not installed — /dashboard unavailable")
        print("[server]   Install with: pip install pokemon-agent[dashboard]")

    if _config is None:
        # Config can be injected via environment or set beforehand
        print("[server] WARNING: No GameConfig set — emulator will NOT start.")
        print("[server] Call server.configure(GameConfig(...)) before startup.")
        # Mount manual controller even without config so it's accessible
        try:
            # Path: pokemon_agent/server/app.py → pokemon_agent/ → project root
            ctrl_html = Path(__file__).parent.parent.parent / "manual-controller.html"
            if ctrl_html.exists():
                from fastapi.responses import HTMLResponse
                @app.get("/controller/", response_class=HTMLResponse)
                async def serve_controller():
                    return HTMLResponse(content=ctrl_html.read_text(), status_code=200)
                print("[server] Manual controller at /controller/")
        except Exception as e:
            print(f"[server] Manual controller not mounted: {e}")
        return

    rom = Path(_config.rom_path).expanduser().resolve()
    if not rom.exists():
        print(f"[server] ERROR: ROM not found: {rom}")
        return

    # Auto-detect game type
    game_type = _config.game_type
    if game_type == "auto":
        game_type = _detect_game_type(str(rom))

    print(f"[server] Loading ROM: {rom}")
    print(f"[server] Detected game type: {game_type}")

    # Create emulator
    from pokemon_agent.server.emulator import create_emulator
    _emulator = create_emulator(str(rom), cgb=_config.cgb, cgb_palette=_config.cgb_palette)

    # Create memory reader
    if game_type == "red":
        from pokemon_agent.server.memory.red import PokemonRedReader
        _reader = PokemonRedReader(_emulator)
    elif game_type == "firered":
        from pokemon_agent.server.memory.firered import FireRedMemoryReader
        _reader = FireRedMemoryReader(_emulator)
    else:
        raise ValueError(f"Unknown game type: {game_type}")

    # Create data directories
    data_dir = Path(_config.data_dir).expanduser().resolve()
    (data_dir / "saves").mkdir(parents=True, exist_ok=True)

    # Initialise the game-session manager.
    global _session_mgr
    from pokemon_agent.server.sessions import GameSessionManager
    _session_mgr = GameSessionManager(str(data_dir))

    # Mount manual controller at /controller/ (config is set, normal operation)
    try:
        # Path: pokemon_agent/server/app.py → pokemon_agent/ → project root
        ctrl_html = Path(__file__).parent.parent.parent / "manual-controller.html"
        if ctrl_html.exists():
            from fastapi.responses import HTMLResponse
            @app.get("/controller/", response_class=HTMLResponse)
            async def serve_controller():
                return HTMLResponse(content=ctrl_html.read_text(), status_code=200)
            print(f"[server] Manual controller at /controller/")
    except Exception as e:
        print(f"[server] Manual controller not mounted: {e}")

    # Auto-load a save state if specified
    if _config.load_state:
        saves_dir = data_dir / "saves"
        state_path = saves_dir / f"{_config.load_state}.state"
        if state_path.exists():
            try:
                _emulator.load_state(str(state_path))
                print(f"[server] Loaded save state: {_config.load_state}")
            except Exception as e:
                print(f"[server] WARNING: Failed to load state '{_config.load_state}': {e}")
        else:
            print(f"[server] WARNING: Save state not found: {state_path}")

    # Load persisted agent model config (if any).
    _load_agent_model_cfg()

    print(f"[server] Ready — listening on port {_config.port}")
    print(f"[server] Agent model: {_agent_model_cfg['provider']} / {_agent_model_cfg['model']}")
    print(f"[server] Endpoints:")
    print(f"[server]   GET  /          — server info")
    print(f"[server]   GET  /state     — game state")
    print(f"[server]   GET  /screenshot — current frame (PNG)")
    print(f"[server]   POST /action    — execute actions")
    print(f"[server]   POST /save      — save state")
    print(f"[server]   POST /load      — load state")
    print(f"[server]   GET  /saves     — list saves")
    print(f"[server]   GET  /minimap   — ASCII minimap")
    print(f"[server]   GET  /health    — health check")
    print(f"[server]   WS   /ws        — live events")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def index():
    """Server info."""
    return {
        "name": "pokemon-agent",
        "version": __version__,
        "game": _config.game_type if _config else None,
        "rom": _config.rom_path if _config else None,
        "uptime_seconds": round(time.time() - _start_time, 1) if _start_time else 0,
        "emulator_ready": _emulator is not None,
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "emulator_ready": _emulator is not None}


@app.get("/state")
async def get_state():
    """Full game state JSON."""
    _ensure_emulator()
    try:
        state = await _run_sync(_get_state_dict)
        return JSONResponse(content=state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading state: {e}")


@app.get("/screenshot/grid")
async def screenshot_grid(scale: int = 4):
    """Current frame with a labelled A1..J9 movement grid drawn on top.

    The grid divides the 160x144 screen into the game's 10x9 walkable
    block layout. The player is always in cell E5 (marked). This gives a
    vision model discrete, nameable coordinates to plan movement with.
    """
    _ensure_emulator()
    try:
        from pokemon_agent.overlay import render_grid_overlay_bytes

        def _grid_png() -> bytes:
            screen = _emulator.get_screen()
            from PIL import Image
            if not isinstance(screen, Image.Image):
                import numpy as np  # noqa: F401
                screen = Image.fromarray(screen)
            return render_grid_overlay_bytes(screen, scale=scale)

        png_bytes = await _run_sync(_grid_png)
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grid screenshot error: {e}")


@app.get("/screenshot")
async def screenshot():
    """Current emulator frame as PNG image."""
    _ensure_emulator()
    try:
        png_bytes = await _run_sync(_get_screenshot_bytes)
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screenshot error: {e}")


@app.get("/screenshot/base64")
async def screenshot_base64():
    """Current emulator frame as base64-encoded PNG in JSON."""
    _ensure_emulator()
    try:
        png_bytes = await _run_sync(_get_screenshot_bytes)
        b64 = base64.b64encode(png_bytes).decode("ascii")
        return {"image": b64, "format": "png"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screenshot error: {e}")


@app.post("/event")
async def push_event(req: EventRequest):
    """Push an agent-narration event to the dashboard (broadcast over WS).

    The agent calls this to make its reasoning visible on the stream:
      - type "reasoning" / "decision" / "alert": send `text`
      - type "key_moment": send `description` (+ optional `category`:
        milestone | badge | catch | alert)
    These are display-only; they are NOT stored in conversation history.
    """
    event: dict = {"type": req.type}
    if req.text is not None:
        event["text"] = req.text
    if req.description is not None:
        event["description"] = req.description
    if req.category is not None:
        event["category"] = req.category
    if req.agent is not None:
        event["agent"] = req.agent
    # Persist real milestones into the active session's timeline.
    if req.type in ("key_moment", "moment") and req.description \
            and _active_session is not None and _session_mgr is not None:
        _session_mgr.add_milestone(_active_session, req.description,
                                   req.category or "milestone")
    await broadcast(event)
    return {"success": True, "broadcast_to": len(_ws_clients)}


@app.get("/objectives")
async def get_objectives():
    """Current objective list (primary/secondary/tertiary + done flags)."""
    return {"objectives": _objectives}


@app.post("/objectives")
async def set_objectives(req: ObjectivesRequest):
    """Replace the full objective list and broadcast it to the dashboard.

    The player (agent) sets real goals here so the dashboard
    reflects the actual plan instead of static placeholder text.
    """
    global _objectives
    _objectives = [o.model_dump() for o in req.objectives]
    if _active_session is not None and _session_mgr is not None:
        _active_session.objectives = _objectives
        _session_mgr.save(_active_session)
    await broadcast({"type": "objectives", "objectives": _objectives})
    return {"success": True, "objectives": _objectives}


# ---------------------------------------------------------------------------
# Guide + Prompt Editor endpoints
# ---------------------------------------------------------------------------

# Paths to editable data files (standalone agent lives in a sibling project)
import json as _json_module

def _get_project_root():
    """Resolve the pokemon-agent project root (three levels up from app.py)."""
    return Path(__file__).parent.parent.parent


def _get_guide_path():
    return _get_project_root() / "pokemon_agent" / "guide" / "guide.json"


def _get_prompts_path():
    return _get_project_root() / "pokemon_agent" / "agent" / "llm" / "prompts.py"

@app.get("/editor/guide")
async def editor_get_guide():
    """Return the current guide.json content."""
    gp = _get_guide_path()
    if not gp or not gp.exists():
        raise HTTPException(404, "guide.json not found in pokemon_agent/guide/")
    return _json_module.loads(gp.read_text())


@app.post("/editor/guide")
async def editor_save_guide(req: dict):
    """Save a new guide.json. Expects {"steps": [...]}."""
    gp = _get_guide_path()
    if not gp:
        raise HTTPException(404, "guide.json path not found")
    steps = req.get("steps")
    if steps is None:
        raise HTTPException(400, "Request body must include 'steps' array")
    # Write atomically: dump to temp then rename
    data = _json_module.dumps({"game": "Pokemon Red", "format_version": "1.0",
                                "description": "State-driven walkthrough guide",
                                "steps": steps}, indent=2)
    gp.write_text(data + "\n")
    return {"success": True, "path": str(gp), "step_count": len(steps)}


@app.get("/editor/guide/step/{step_id}")
async def editor_get_step(step_id: str):
    """Return a single step by ID."""
    gp = _get_guide_path()
    if not gp or not gp.exists():
        raise HTTPException(404, "guide.json not found")
    guide = _json_module.loads(gp.read_text())
    for s in guide.get("steps", []):
        if s.get("id") == step_id:
            return s
    raise HTTPException(404, f"Step '{step_id}' not found")


@app.get("/editor/prompts")
async def editor_get_prompts():
    """Return the raw prompts.py source and the nav prompt template."""
    pp = _get_prompts_path()
    if not pp or not pp.exists():
        raise HTTPException(404, "prompts.py not found")
    return {
        "prompts_py": pp.read_text(),
        "prompts_path": str(pp),
    }




@app.get("/control")
async def get_control():
    """Current agent run state: running | paused | stopped."""
    return {"state": _control_state}


@app.post("/control")
async def set_control(req: ControlRequest):
    """Set the agent run state (drives the Start/Pause/Stop buttons).

    A standalone agent loop polls this and only takes actions
    while the state is "running". This endpoint is the wiring behind the
    dashboard's control buttons; it does not itself drive the emulator.
    """
    global _control_state
    valid = {"running", "paused", "stopped"}
    if req.state not in valid:
        raise HTTPException(status_code=400, detail=f"state must be one of {sorted(valid)}")
    _control_state = req.state
    await broadcast({"type": "control", "state": _control_state})
    return {"success": True, "state": _control_state}


# ---------------------------------------------------------------------------
# Game sessions — new game / load game / list / delete
# ---------------------------------------------------------------------------

def _game_summary() -> dict:
    if _active_session is None:
        return {"active": None}
    gs = _active_session
    return {"active": {"id": gs.id, "name": gs.name, "game": gs.game,
                       
                       "objectives": gs.objectives, "stats": gs.stats}}


async def _activate(gs) -> None:
    """Make `gs` the active session: sync objectives, broadcast, persist."""
    global _active_session, _objectives
    _active_session = gs
    _objectives = gs.objectives or _objectives
    _session_mgr.save(gs)
    await broadcast({"type": "objectives", "objectives": _objectives})
    await broadcast({"type": "game", **_game_summary()})


@app.get("/games")
async def list_games():
    """List all game sessions (newest first) + which one is active."""
    if _session_mgr is None:
        raise HTTPException(status_code=503, detail="Session manager not ready")
    return {"games": _session_mgr.list(),
            "active": _active_session.id if _active_session else None}


@app.get("/games/current")
async def current_game():
    """The active game session summary (or {active: null})."""
    return _game_summary()


@app.post("/reset")
async def reset_emulator():
    """Soft-reset the emulator (reload ROM, no wake sequence, no session).

    Use this to return to the title screen without running the wake sequence.
    The dashboard will show the boot/title screen after reset.
    """
    _ensure_emulator()
    if _emulator is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    try:
        await _run_sync(_emulator.reset)
        await _run_sync(_emulator.tick, 60)
        # Push screenshot so dashboard shows the title screen
        try:
            _png = await _run_sync(_get_screenshot_bytes)
            _b64 = base64.b64encode(_png).decode("ascii")
            await broadcast({
                "type": "screenshot",
                "data": {"image": _b64, "format": "png"},
            })
        except Exception:
            pass
        return {"success": True, "message": "Emulator reset to title screen"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset failed: {e}")


# ---------------------------------------------------------------------------
# Agent process management
# ---------------------------------------------------------------------------

_agent_proc: Optional[subprocess.Popen] = None

# Agent model/provider selection — persisted so the dashboard can switch
# between local LM Studio and OpenRouter without restarting the server.
_agent_model_cfg: dict = {
    "provider": "local",
    "model": "google/gemma-4-e2b",
}
_AGENT_MODEL_FILE = Path.home() / ".pokemon-agent" / "agent_model.json"


def _load_agent_model_cfg() -> dict:
    """Load persisted agent model config from disk (if any)."""
    global _agent_model_cfg
    if _AGENT_MODEL_FILE.exists():
        try:
            data = json.loads(_AGENT_MODEL_FILE.read_text())
            if data.get("provider"):
                _agent_model_cfg = data
        except Exception:
            pass
    return _agent_model_cfg


def _save_agent_model_cfg(cfg: dict) -> None:
    """Persist agent model config to disk so agent picks it up on next start."""
    _AGENT_MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    _AGENT_MODEL_FILE.write_text(json.dumps(cfg, indent=2))


def _write_agent_model_to_config(provider: str, model: str) -> None:
    """Write the selected provider/model into config.yaml so the agent reads it.

    This keeps config.yaml as the single source of truth — the dashboard, server,
    and agent all agree on what model to use.
    """
    import yaml as _yaml
    config_path = Path.home() / "projects" / "pokemon-agent" / "config.yaml"
    if not config_path.exists():
        return
    with open(config_path) as f:
        cfg = _yaml.safe_load(f) or {}
    providers = cfg.setdefault("providers", {})
    if provider == "local":
        providers.setdefault("local", {})["model"] = model
    elif provider == "openrouter":
        providers.setdefault("openrouter", {})["model"] = model
    # Update default_provider so the agent picks the right provider block
    cfg["default_provider"] = provider
    with open(config_path, "w") as f:
        _yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)


def _read_agent_model_from_config() -> dict:
    """Read the current provider/model from config.yaml."""
    import yaml as _yaml
    config_path = Path.home() / "projects" / "pokemon-agent" / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        cfg = _yaml.safe_load(f) or {}
    providers = cfg.get("providers", {})
    # Return whichever provider has a model set
    for name, pcfg in providers.items():
        if pcfg.get("model"):
            return {"provider": name, "model": pcfg["model"]}
    return {}


@app.get("/agent/status")
async def agent_status():
    """Check whether the standalone agent loop is running."""
    global _agent_proc
    if _agent_proc is None:
        return {"running": False, "pid": None}
    ret = _agent_proc.poll()
    if ret is not None:
        # Process exited — clear the reference so we can start again.
        _agent_proc = None
        return {"running": False, "pid": None, "exit_code": ret}
    return {"running": True, "pid": _agent_proc.pid}


@app.post("/agent/start")
async def agent_start(new_game: bool = False):
    """Start the standalone pokemon-agent loop as a background process.

    Idempotent: if the agent is already running this returns immediately.
    The agent respects /control (pause/stop) so you can manage it from the
    dashboard or manual controller after launch.

    If new_game=True, performs a full /games/new reset + wake first, then
    spawns the agent only after the emulator is past title screen. This
    prevents the race condition where the agent starts acting on stale state.
    """
    global _agent_proc

    if new_game:
        # Synchronous reset + wake BEFORE spawning agent so it sees valid
        # game state from the first turn. No race condition.
        await _reset_and_wake()
        print(f"[server] new_game reset + wake complete, now spawning agent")

    # Re-check in case a previous reference went stale.
    if _agent_proc is not None and _agent_proc.poll() is None:
        return {"success": True, "pid": _agent_proc.pid, "note": "already running"}
    # Kill any leftover agent processes.
    try:
        subprocess.run(
            ["pkill", "-f", "pokemon_agent.agent.main_loop"],
            timeout=5, capture_output=True,
        )
    except Exception:
        pass
    await asyncio.sleep(0.5)
    # Spawn the standalone agent (pokemon-agent) in its own session.
    agent_dir = Path.home() / "projects" / "pokemon-agent"
    log_path = Path("/tmp/pokemon-agent-stdout.log")
    log_fd = open(log_path, "a")
    _agent_env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    _agent_env["POKEMON_AGENT_DELAY"] = os.environ.get("POKEMON_AGENT_DELAY", "1.5")
    # Load additional API keys from .env for rate-limit rotation
    _env_file = Path.home() / "projects" / "pokemon-agent" / ".env"
    if _env_file.exists():
        for _line in _env_file.read_text().splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())
                _agent_env.setdefault(_k.strip(), _v.strip())
    # Read provider/model from config.yaml (single source of truth)
    try:
        import yaml as _yaml
        _cfg_path = Path.home() / "projects" / "pokemon-agent" / "config.yaml"
        with open(_cfg_path) as _f:
            _cfg = _yaml.safe_load(_f) or {}
        _default_prov = _cfg.get("default_provider", "local")
        _prov_cfg = _cfg.get("providers", {}).get(_default_prov, {})
        _agent_env["POKEMON_AGENT_PROVIDER"] = _default_prov
        _agent_env["POKEMON_AGENT_MODEL"] = _prov_cfg.get("model", "openrouter/owl-alpha")
    except Exception:
        _agent_env["POKEMON_AGENT_PROVIDER"] = "openrouter"
        _agent_env["POKEMON_AGENT_MODEL"] = "openrouter/owl-alpha"
    # Use the venv python from the consolidated repo
    venv_python = agent_dir / ".venv" / "bin" / "python3"
    _agent_proc = subprocess.Popen(
        [str(venv_python), "-m", "pokemon_agent.agent.main_loop"],
        cwd=str(agent_dir),
        stdout=log_fd,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=_agent_env,
        preexec_fn=lambda: __import__("resource").setrlimit(
            __import__("resource").RLIMIT_NOFILE, (65536, 65536)
        ),
    )
    print(f"[server] Agent started — pid={_agent_proc.pid}  log={log_path}")
    return {"success": True, "pid": _agent_proc.pid}


@app.get("/agent/log")
async def agent_log(lines: int = 60, offset: int = 0):
    """Return recent lines from the agent stdout log (for the dashboard console)."""
    log_path = Path("/tmp/pokemon-agent-stdout.log")
    if not log_path.exists():
        return {"lines": [], "total": 0}
    try:
        # Read last N lines efficiently
        all_lines = log_path.read_text().splitlines()
        total = len(all_lines)
        if offset > 0:
            chunk = all_lines[offset:offset + lines]
        else:
            chunk = all_lines[-lines:]
        return {"lines": chunk, "total": total}
    except Exception as e:
        return {"lines": [f"Error reading log: {e}"], "total": 0}


@app.post("/agent/stop")
async def agent_stop():
    """Stop the standalone agent loop (SIGTERM, graceful)."""
    global _agent_proc
    if _agent_proc is None or _agent_proc.poll() is not None:
        _agent_proc = None
        # Also kill any stray agent processes.
        try:
            subprocess.run(["pkill", "-f", "src.main_loop"], timeout=5, capture_output=True)
        except Exception:
            pass
        return {"success": True, "note": "no agent was running"}
    pid = _agent_proc.pid
    _agent_proc.terminate()
    try:
        _agent_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _agent_proc.kill()
        _agent_proc.wait(timeout=3)
    _agent_proc = None
    print(f"[server] Agent stopped — pid={pid}")
    return {"success": True, "pid": pid}


@app.get("/agent/config")
async def agent_get_config():
    """Get the current agent model/provider config."""
    cfg = _load_agent_model_cfg()
    return {"success": True, "config": cfg}


@app.get("/agent/models")
async def agent_get_models():
    """Return the available providers and their models from config.yaml.

    Response format:
    {
        "success": true,
        "default_provider": "local",
        "providers": {
            "local": {
                "models": ["google/gemma-4-e2b", "google/gemma-4-e4b"],
                "model": "google/gemma-4-e4b"
            },
            "openrouter": {
                "models": ["openrouter/owl-alpha", "nex-agi/nex-n2-pro:free", ...],
                "model": "openrouter/owl-alpha"
            }
        }
    }
    """
    import yaml as _yaml
    config_path = Path.home() / "projects" / "pokemon-agent" / "config.yaml"
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")
    with open(config_path) as f:
        cfg = _yaml.safe_load(f) or {}
    providers = cfg.get("providers", {})
    result = {}
    for name, pcfg in providers.items():
        # Skip non-LLM providers (like pokemon_agent)
        if "base_url" not in pcfg:
            continue
        result[name] = {
            "models": pcfg.get("models", []),
            "model": pcfg.get("model", ""),
        }
    return {"success": True, "default_provider": cfg.get("default_provider", "local"), "providers": result}


@app.post("/agent/config")
async def agent_set_config(req: AgentConfigRequest):
    """Switch the agent's LLM provider/model.

    Persists the choice to disk so the next agent start picks it up.
    For local: provider="local" uses LM Studio at 192.168.1.25:1234.
    For OpenRouter: pass the full model string as provider (e.g. "openrouter/owl-alpha")
                    or as model with provider="openrouter".
    """
    global _agent_model_cfg
    # Determine provider and model from the request
    if req.provider == "local":
        provider = "local"
        # Keep existing model from config.yaml if present, don't overwrite with hardcoded default
        existing = _read_agent_model_from_config()
        model = req.model or (existing.get("model") if existing else None) or "google/gemma-4-e4b"
    elif req.provider.startswith("openrouter/") or req.provider.startswith("nvidia/") or req.provider.startswith("poolside/") or req.provider.startswith("openai/"):
        # Full OpenRouter model string passed as provider
        provider = "openrouter"
        model = req.provider
    elif req.provider == "openrouter":
        provider = "openrouter"
        model = req.model or "openrouter/owl-alpha"
    else:
        raise HTTPException(
            status_code=400,
            detail="provider must be 'local' or an OpenRouter model string (e.g. 'openrouter/owl-alpha', 'nvidia/nemotron-3-ultra-550b-a55b:free')",
        )
    _agent_model_cfg = {"provider": provider, "model": model}
    _save_agent_model_cfg(_agent_model_cfg)

    # Also write to config.yaml so the agent picks it up on next start
    _write_agent_model_to_config(provider, model)

    print(f"[server] Agent model switched: provider={provider} model={model}")
    return {"success": True, "config": _agent_model_cfg}


@app.get("/debug/ram")
async def debug_ram(start: str = "0xC4F0", end: str = "0xD740"):
    """Dump a range of RAM addresses for debugging. Only available in dev."""
    _ensure_emulator()
    if _emulator is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    try:
        start_int = int(start, 16) if start.startswith("0x") else int(start)
        end_int = int(end, 16) if end.startswith("0x") else int(end)
        data = {}
        for addr in range(start_int, end_int + 1):
            val = await _run_sync(_emulator.read_u8, addr)
            if val != 0:
                data[f"0x{addr:04X}"] = val
        return {"non_zero": data, "range": f"0x{start_int:04X}-0x{end_int:04X}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAM read failed: {e}")


@app.get("/debug/sprites")
async def debug_sprites():
    """Dump raw sprite state data (C100-C2FF) for debugging NPC positions."""
    _ensure_emulator()
    if _emulator is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    try:
        c1 = []
        for addr in range(0xC100, 0xC200):
            c1.append(await _run_sync(_emulator.read_u8, addr))
        c2 = []
        for addr in range(0xC200, 0xC300):
            c2.append(await _run_sync(_emulator.read_u8, addr))
        return {"c1_sprite_state": c1, "c2_sprite_state": c2}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sprite debug failed: {e}")


async def _reset_and_wake() -> None:
    """Shared helper: reset emulator, run wake sequence, create fresh session.

    Used by both /games/new and /agent/start?new_game=true so the logic
    lives in one place.
    """
    global _emulator, _reader
    _ensure_emulator()
    if _session_mgr is None or _config is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    # Fresh boot: rebuild the emulator from the ROM (clears all game state).
    try:
        from pokemon_agent.server.emulator import create_emulator
        _emulator = await _run_sync(create_emulator, _config.rom_path, _config.cgb, _config.cgb_palette)
        if _config.game_type == "red":
            from pokemon_agent.server.memory.red import PokemonRedReader
            _reader = PokemonRedReader(_emulator)
        else:
            from pokemon_agent.server.memory.firered import FireRedMemoryReader
            _reader = FireRedMemoryReader(_emulator)
        await _run_sync(_emulator.tick, 60)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"New-game reset failed: {e}")

    # Wake sequence: boots to title, starts new game, names player RED,
    # names rival BLUE, advances through Oak's intro dialog, and lands
    # in Red's House 2F ready to play.
    _WAKE_SEQUENCE: list[str] = [
        "hold_b_1500",
        "press_start",
        "press_start",
        "press_b", "press_b", "press_b", "press_b", "press_b",
        "press_b", "press_b", "press_b", "press_b", "press_b",
        "press_b", "press_b", "press_b",
        "press_down", "press_a",
        "press_b", "press_b", "press_b", "press_b", "press_b",
        "press_b", "press_b", "press_b",
        "press_down", "press_a",
        "press_b", "press_b", "press_b", "press_b",
        "press_b", "press_b", "press_b", "press_b",
    ]

    try:
        for action_str in _WAKE_SEQUENCE:
            await _execute_action(action_str)
            if action_str.startswith("press_") or action_str.startswith("hold_"):
                try:
                    _png = await _run_sync(_get_screenshot_bytes)
                    _b64 = base64.b64encode(_png).decode("ascii")
                    await broadcast({
                        "type": "screenshot",
                        "data": {"image": _b64, "format": "png"},
                    })
                except Exception:
                    pass
        print(f"[server] Wake sequence complete ({len(_WAKE_SEQUENCE)} actions)")
    except Exception as e:
        print(f"[server] WARNING: Wake sequence failed: {e}")

    # Push post-wake screenshot
    try:
        _png = await _run_sync(_get_screenshot_bytes)
        _b64 = base64.b64encode(_png).decode("ascii")
        await broadcast({
            "type": "screenshot",
            "data": {"image": _b64, "format": "png"},
        })
    except Exception:
        pass


@app.post("/games/new")
async def new_game(req: NewGameRequest):
    """Start a NEW game: fresh emulator boot + a fresh session manifest.

    Resets the emulator to the ROM's title/boot (no save loaded) and creates a
    new GameSession. After boot, runs the known-good wake sequence to advance
    past the title screen and naming dialog so the game is ready to play.
    """
    await _reset_and_wake()
    gs = _session_mgr.create(name=req.name, game=_config.game_type)
    await _activate(gs)
    await broadcast({"type": "control", "state": _control_state})

    # Push a second screenshot after session activation
    try:
        _png2 = await _run_sync(_get_screenshot_bytes)
        _b64_2 = base64.b64encode(_png2).decode("ascii")
        await broadcast({
            "type": "screenshot",
            "data": {"image": _b64_2, "format": "png"},
        })
    except Exception:
        pass

    return {"success": True, "game": gs.to_dict()}


@app.post("/games/{sid}/load")
async def load_game(sid: str):
    """Load an existing game session: restore its latest save-state and make
    it active (its session is restored too, so the agent resumes
    the SAME brain). If the session has no save yet, just activate it."""
    _ensure_emulator()
    if _session_mgr is None:
        raise HTTPException(status_code=503, detail="Session manager not ready")
    gs = _session_mgr.load(sid)
    if gs is None:
        raise HTTPException(status_code=404, detail=f"Game session not found: {sid}")
    latest = _session_mgr.latest_save_path(sid)
    if latest is not None:
        try:
            await _run_sync(_emulator.load_state, str(latest))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load save: {e}")
    await _activate(gs)
    state_after = await _run_sync(_get_state_dict)
    await broadcast({"type": "state_update", "reason": "load_game", "state": state_after})
    return {"success": True, "game": gs.to_dict(),
            "restored_save": latest.stem if latest else None}




@app.delete("/games/{sid}")
async def delete_game(sid: str):
    """Delete a game session and its saves (cannot delete the active one)."""
    if _session_mgr is None:
        raise HTTPException(status_code=503, detail="Session manager not ready")
    if _active_session and _active_session.id == sid:
        raise HTTPException(status_code=400, detail="Cannot delete the active game; load another first.")
    ok = _session_mgr.delete(sid)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Game session not found: {sid}")
    return {"success": True, "deleted": sid}


@app.post("/action")
async def execute_actions(req: ActionRequest):
    """Execute a sequence of game actions."""
    _ensure_emulator()
    try:
        executed = 0
        for action_str in req.actions:
            await _execute_action(action_str)
            executed += 1

        state_after = await _run_sync(_get_state_dict)

        # Bump per-session stats.
        if _active_session is not None and _session_mgr is not None:
            s = _active_session.stats
            s["actions"] = s.get("actions", 0) + executed
            s["turns"] = s.get("turns", 0) + 1
            _session_mgr.save(_active_session)

        try:
            png_bytes = await _run_sync(_get_screenshot_bytes)
            screenshot_b64 = base64.b64encode(png_bytes).decode("ascii")
        except Exception:
            screenshot_b64 = None

        # Broadcast to WebSocket clients
        await broadcast({
            "type": "action",
            "actions": req.actions,
            "actions_executed": executed,
            "state_after": state_after,
        })
        # Also push the latest frame so the dashboard updates immediately
        if screenshot_b64:
            await broadcast({
                "type": "screenshot",
                "data": {"image": screenshot_b64, "format": "png"},
            })

        return {
            "success": True,
            "actions_executed": executed,
            "state_after": state_after,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Action error: {e}")


@app.post("/save")
async def save_state(req: SaveRequest):
    """Save emulator state. Routed into the active game session's folder when
    one is active; otherwise the legacy flat saves/ dir."""
    _ensure_emulator()
    if not _config:
        raise HTTPException(status_code=503, detail="Server not configured")
    try:
        if _active_session is not None and _session_mgr is not None:
            saves_dir = _session_mgr.saves_dir(_active_session.id)
        else:
            saves_dir = Path(_config.data_dir).expanduser().resolve() / "saves"
            saves_dir.mkdir(parents=True, exist_ok=True)
        save_path = saves_dir / f"{req.name}.state"
        await _run_sync(_emulator.save_state, str(save_path))
        if _active_session is not None and _session_mgr is not None:
            _active_session.stats["saves"] = _active_session.stats.get("saves", 0) + 1
            _session_mgr.save(_active_session)
        return {"success": True, "path": str(save_path),
                "session": _active_session.id if _active_session else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Save error: {e}")


@app.post("/load")
async def load_state(req: SaveRequest):
    """Load emulator state from disk."""
    _ensure_emulator()
    if not _config:
        raise HTTPException(status_code=503, detail="Server not configured")
    try:
        saves_dir = Path(_config.data_dir).expanduser().resolve() / "saves"
        save_path = saves_dir / f"{req.name}.state"
        if not save_path.exists():
            raise HTTPException(status_code=404, detail=f"Save not found: {req.name}")
        await _run_sync(_emulator.load_state, str(save_path))
        state_after = await _run_sync(_get_state_dict)

        await broadcast({"type": "state_update", "reason": "load", "state": state_after})

        return {"success": True, "name": req.name, "state_after": state_after}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Load error: {e}")


@app.get("/saves")
async def list_saves():
    """List available save-state files."""
    if not _config:
        raise HTTPException(status_code=503, detail="Server not configured")
    try:
        saves_dir = Path(_config.data_dir).expanduser().resolve() / "saves"
        if not saves_dir.exists():
            return {"saves": []}
        files = sorted(saves_dir.glob("*.state"))
        saves = [
            {
                "name": f.stem,
                "file": f.name,
                "size_bytes": f.stat().st_size,
                "modified": f.stat().st_mtime,
            }
            for f in files
        ]
        return {"saves": saves}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing saves: {e}")


@app.get("/map/ascii")
async def map_ascii():
    """The current on-screen walkability grid as an ASCII map (text/plain).

    @ = player (E5), . = walkable, # = blocked, S = stairs/warp, D = door.
    Read from RAM collision data + warp entries — ground truth.
    """
    _ensure_emulator()
    try:
        def _ascii() -> str:
            from pokemon_agent.server.collision import (
                build_collision_grid,
                build_special_tiles,
                render_ascii_map,
            )
            col = build_collision_grid(_reader.emu)
            warps = _reader.read_warps() if _reader else None
            sprites = _reader.read_sprites() if _reader else []
            special = build_special_tiles(_reader.emu, col, warps=warps)
            px = _reader.emu.read_u8(0xD362)
            py = _reader.emu.read_u8(0xD361)
            return render_ascii_map(
                col, special=special, legend=True,
                player_pos={"x": px, "y": py},
                sprites=sprites,
            )
        text = await _run_sync(_ascii)
        return Response(content=text, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ASCII map error: {e}")


@app.get("/minimap")
async def minimap():
    """Simple ASCII minimap — current map name + player position."""
    _ensure_emulator()
    try:
        state = await _run_sync(_get_state_dict)
        map_info = state.get("map", {})
        player = state.get("player", {})
        map_name = map_info.get("map_name", "Unknown")
        pos = player.get("position", {})
        x = pos.get("x", "?")
        y = pos.get("y", "?")

        lines = [
            f"=== {map_name} ===",
            f"Player position: ({x}, {y})",
            "",
            "  N",
            "W + E",
            "  S",
        ]
        text = "\n".join(lines)
        return Response(content=text, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Minimap error: {e}")


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Live event stream via WebSocket."""
    await ws.accept()
    _ws_clients.add(ws)
    try:
        # Send a welcome message
        await ws.send_json({
            "type": "connected",
            "version": __version__,
            "emulator_ready": _emulator is not None,
        })
        # Backfill: replay recent narration/milestone/action events so the
        # Field Log is populated immediately instead of starting empty.
        if _event_history:
            await ws.send_json({
                "type": "replay",
                "events": list(_event_history),
            })
        # Send current objectives + control state so the panel + buttons sync.
        await ws.send_json({"type": "objectives", "objectives": _objectives})
        await ws.send_json({"type": "control", "state": _control_state})
        await ws.send_json({"type": "game", **_game_summary()})

        # Send a screenshot frame so the dashboard shows the game immediately
        # instead of a blank screen waiting for the next action broadcast.
        try:
            png_bytes = await _run_sync(_get_screenshot_bytes)
            b64 = base64.b64encode(png_bytes).decode("ascii")
            await ws.send_json({
                "type": "screenshot",
                "data": {"image": b64, "format": "png"},
            })
        except Exception:
            pass  # Screenshot on connect is best-effort

        # Keep alive — wait for client messages (or disconnect)
        while True:
            data = await ws.receive_text()
            # Clients can send a "ping" to keep alive
            if data.strip().lower() == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _ws_clients.discard(ws)


# ---------------------------------------------------------------------------
# Dashboard fallback — only registered if dashboard static files are missing
# ---------------------------------------------------------------------------

def _register_dashboard_fallback():
    """Register a fallback route for /dashboard if static files aren't available."""
    try:
        import pokemon_agent.dashboard as _dm
        static_dir = Path(_dm.__file__).parent / "static"
        if static_dir.is_dir() and (static_dir / "index.html").exists():
            return  # Dashboard exists — don't register fallback
    except ImportError:
        pass

    @app.get("/dashboard")
    @app.get("/dashboard/{path:path}")
    async def dashboard_fallback(path: str = ""):
        raise HTTPException(
            status_code=404,
            detail="Dashboard not installed. Install with: pip install pokemon-agent[dashboard]",
        )

_register_dashboard_fallback()
